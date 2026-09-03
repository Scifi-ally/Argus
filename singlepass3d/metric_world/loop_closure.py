"""
Loop Closure Detection, Visual Revisit Identification, and Geometric Verification for SinglePass3D.
Uses GPS proximity, visual descriptor matching, and RANSAC 5-Point/Essential Matrix verification
to generate loop closure relative pose constraints.
"""

from __future__ import annotations
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np

from singlepass3d.core.logging import get_logger
from singlepass3d.core.types import LoopConstraint, Pose3D, Trajectory
from singlepass3d.sensor.camera_model import CameraModel
from singlepass3d.sensor.video_indexer import VideoIndexer


class LoopClosureDetector:
    """
    Detects loop closures and revisitations between non-adjacent video frames.
    """
    def __init__(
        self,
        camera: CameraModel,
        min_frame_gap: int = 25,
        gps_dist_threshold_m: float = 15.0,
        min_inliers: int = 30
    ):
        self.camera = camera
        self.min_frame_gap = min_frame_gap
        self.gps_dist_threshold_m = gps_dist_threshold_m
        self.min_inliers = min_inliers
        self.logger = get_logger()
        self.orb = cv2.ORB_create(nfeatures=1500)
        self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)

    def detect_loop_closures(
        self,
        keyframe_ids: List[int],
        indexer: VideoIndexer,
        trajectory: Trajectory
    ) -> List[LoopConstraint]:
        """
        Scans keyframe pairs for GPS proximity and feature matching loop closures.
        """
        self.logger.info(f"Scanning for loop closures across {len(keyframe_ids)} keyframes...")
        
        loop_constraints: List[LoopConstraint] = []
        N = len(keyframe_ids)
        
        # Precompute keypoints and descriptors for all keyframes
        kps_dict: Dict[int, List[cv2.KeyPoint]] = {}
        descs_dict: Dict[int, np.ndarray] = {}
        
        for fid in keyframe_ids:
            img = indexer.get_frame_image(fid, full_resolution=False)
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
            kps, descs = self.orb.detectAndCompute(gray, None)
            kps_dict[fid] = kps
            descs_dict[fid] = descs
            
        K = self.camera.K
        
        for i in range(N):
            fid_i = keyframe_ids[i]
            pose_i = trajectory.get_pose(fid_i)
            desc_i = descs_dict.get(fid_i)
            kps_i = kps_dict.get(fid_i)
            
            if pose_i is None or desc_i is None or len(kps_i) < 50:
                continue
                
            for j in range(i + self.min_frame_gap, N):
                fid_j = keyframe_ids[j]
                pose_j = trajectory.get_pose(fid_j)
                desc_j = descs_dict.get(fid_j)
                kps_j = kps_dict.get(fid_j)
                
                if pose_j is None or desc_j is None or len(kps_j) < 50:
                    continue
                    
                # 1. GPS / Spatial Proximity check
                dist = np.linalg.norm(pose_i.t_wc - pose_j.t_wc)
                if dist > self.gps_dist_threshold_m:
                    continue
                    
                # 2. Visual Descriptor Matching (Lowe's ratio test)
                knn_matches = self.matcher.knnMatch(desc_i, desc_j, k=2)
                good_matches = []
                for m_pair in knn_matches:
                    if len(m_pair) == 2:
                        m, n = m_pair
                        if m.distance < 0.75 * n.distance:
                            good_matches.append(m)
                            
                if len(good_matches) < self.min_inliers:
                    continue
                    
                pts_i = np.float32([kps_i[m.queryIdx].pt for m in good_matches])
                pts_j = np.float32([kps_j[m.trainIdx].pt for m in good_matches])
                
                # 3. Geometric Verification via Essential Matrix RANSAC
                E, inliers_mask = cv2.findEssentialMat(
                    pts_i, pts_j, K, method=cv2.RANSAC, prob=0.999, threshold=2.0
                )
                
                if inliers_mask is None:
                    continue
                    
                inlier_count = int(np.sum(inliers_mask))
                if inlier_count >= self.min_inliers:
                    _, R_rel, t_rel, _ = cv2.recoverPose(E, pts_i, pts_j, K, mask=inliers_mask)
                    
                    constraint = LoopConstraint(
                        frame_id_1=fid_i,
                        frame_id_2=fid_j,
                        relative_R=R_rel,
                        relative_t=t_rel.ravel(),
                        weight=float(inlier_count) / 10.0,
                        inlier_matches=inlier_count,
                        reprojection_error=1.5
                    )
                    loop_constraints.append(constraint)
                    self.logger.info(
                        f"Detected valid Loop Closure between frame {fid_i} and {fid_j} ({inlier_count} geometric inliers, dist={dist:.2f}m)"
                    )
                    
        self.logger.info(f"Loop closure detection complete: found {len(loop_constraints)} loop constraints.")
        return loop_constraints
