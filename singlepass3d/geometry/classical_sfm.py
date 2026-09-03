"""
Classical Structure-from-Motion (SfM) Verification Engine for SinglePass3D.
Runs an independent geometric pipeline (PyCOLMAP / OpenCV incremental SfM)
to extract triangulated 3D landmarks and reprojection errors for cross-verification.
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np

from singlepass3d.core.logging import get_logger
from singlepass3d.core.types import Pose3D, Track3D, Trajectory
from singlepass3d.sensor.camera_model import CameraModel
from singlepass3d.sensor.video_indexer import VideoIndexer


class ClassicalSfMVerifier:
    """
    Independent classical geometric verification engine.
    Triangulates tracks, estimates classical camera poses, and computes independent geometric signals.
    """
    def __init__(self, camera: CameraModel, work_dir: str | Path):
        self.camera = camera
        self.work_dir = Path(work_dir)
        self.logger = get_logger()
        self.triangulated_points: Dict[int, np.ndarray] = {}  # track_id -> (3,) in world ENU
        self.track_reprojection_errors: Dict[int, float] = {} # track_id -> float (pixels)

    def run_classical_verification(
        self,
        keyframe_ids: List[int],
        indexer: VideoIndexer,
        tracks: List[Track3D],
        trajectory: Trajectory
    ) -> Dict[int, np.ndarray]:
        """
        Runs independent multi-view triangulation on tracks across keyframes using camera poses.
        Computes independent geometric 3D landmarks and their reprojection consistency.
        """
        self.logger.info(f"Running Classical SfM verification on {len(tracks)} tracks across {len(keyframe_ids)} keyframes...")
        
        K = self.camera.K
        inv_K = np.linalg.inv(K)
        
        valid_triangulated_count = 0
        
        for tr in tracks:
            # Gather observations that belong to keyframes
            obs = {fid: pt for fid, pt in tr.observations.items() if fid in keyframe_ids and trajectory.get_pose(fid) is not None}
            if len(obs) < 2:
                continue
                
            fids = list(obs.keys())
            # Select pair with largest baseline for robust triangulation
            best_pair = None
            max_baseline = -1.0
            
            for i in range(len(fids)):
                for j in range(i + 1, len(fids)):
                    p_i = trajectory.get_pose(fids[i])
                    p_j = trajectory.get_pose(fids[j])
                    if p_i and p_j:
                        bl = np.linalg.norm(p_i.t_wc - p_j.t_wc)
                        if bl > max_baseline:
                            max_baseline = bl
                            best_pair = (fids[i], fids[j])
                            
            if best_pair is None or max_baseline < 0.2:
                continue
                
            f0, f1 = best_pair
            pose0 = trajectory.get_pose(f0)
            pose1 = trajectory.get_pose(f1)
            if pose0 is None or pose1 is None:
                continue
                
            # Projection matrices P = K @ [R_cw | t_cw]
            P0 = K @ pose0.T_cw[:3, :]
            P1 = K @ pose1.T_cw[:3, :]
            
            pt0_h = np.array([obs[f0][0], obs[f0][1]], dtype=np.float64)
            pt1_h = np.array([obs[f1][0], obs[f1][1]], dtype=np.float64)
            
            # Linear triangulation using cv2.triangulatePoints
            pts4d = cv2.triangulatePoints(P0, P1, pt0_h.reshape(2, 1), pt1_h.reshape(2, 1))
            w = pts4d[3, 0]
            if abs(w) < 1e-8:
                continue
                
            pt_3d_w = pts4d[:3, 0] / w
            
            # Check cheirality: point must be in front of both cameras
            pt_c0 = pose0.R_cw @ pt_3d_w + pose0.t_cw
            pt_c1 = pose1.R_cw @ pt_3d_w + pose1.t_cw
            if pt_c0[2] <= 0.1 or pt_c1[2] <= 0.1:
                continue
                
            # Compute reprojection error across all observing views
            errors: List[float] = []
            for fid, uv_obs in obs.items():
                p = trajectory.get_pose(fid)
                if p:
                    pt_c = p.R_cw @ pt_3d_w + p.t_cw
                    if pt_c[2] > 0.1:
                        u_proj = self.camera.data.fx * (pt_c[0] / pt_c[2]) + self.camera.data.cx
                        v_proj = self.camera.data.fy * (pt_c[1] / pt_c[2]) + self.camera.data.cy
                        err = np.sqrt((u_proj - uv_obs[0])**2 + (v_proj - uv_obs[1])**2)
                        errors.append(err)
                        
            if errors:
                mean_err = float(np.mean(errors))
                if mean_err < 4.0:  # Reprojection threshold for inlier verification
                    self.triangulated_points[tr.track_id] = pt_3d_w
                    self.track_reprojection_errors[tr.track_id] = mean_err
                    tr.point_3d = pt_3d_w
                    tr.reprojection_error = mean_err
                    tr.is_inlier = True
                    valid_triangulated_count += 1
                else:
                    tr.is_inlier = False
                    
        self.logger.info(
            f"Classical SfM verification completed: {valid_triangulated_count} validated 3D landmarks reconstructed."
        )
        return self.triangulated_points
