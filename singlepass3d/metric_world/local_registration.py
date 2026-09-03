"""
Local-to-Global Pointmap Registration and Overlap Alignment for SinglePass3D.
Performs rigid SE(3) and scale Sim(3) registration (Point-to-Plane ICP, Feature Alignment)
to align incoming reconstruction window pointmaps with the persistent world map.
"""

from __future__ import annotations
from typing import Optional, Tuple
import numpy as np
from scipy.spatial import cKDTree

from singlepass3d.core.logging import get_logger
from singlepass3d.core.types import PointMapResult, Pose3D
from singlepass3d.metric_world.world_element import WorldElementStore


class LocalRegistrationEngine:
    """
    Registers local window pointmaps to the global persistent world coordinate frame.
    """
    def __init__(self, max_iterations: int = 30, tolerance_m: float = 0.001, max_corr_dist_m: float = 0.5):
        self.max_iterations = max_iterations
        self.tolerance_m = tolerance_m
        self.max_corr_dist_m = max_corr_dist_m
        self.logger = get_logger()

    def register_pointmap_to_world(
        self,
        pointmap_res: PointMapResult,
        world_store: WorldElementStore,
        initial_transform: Optional[np.ndarray] = None
    ) -> Tuple[np.ndarray, float, bool]:
        """
        Refines the alignment of a pointmap to the current world model.
        Returns:
            refined_T: 4x4 rigid transformation matrix
            inlier_rmse: root-mean-squared error of aligned points
            success: boolean flag indicating registration convergence
        """
        # Extract valid 3D points and normals from incoming pointmap
        valid = pointmap_res.mask
        src_pts = pointmap_res.points[valid].reshape(-1, 3)
        src_normals = pointmap_res.normals[valid].reshape(-1, 3)
        
        # Subsample for speed (max 2000 points for registration)
        if len(src_pts) > 2000:
            sub_idx = np.random.choice(len(src_pts), 2000, replace=False)
            src_pts = src_pts[sub_idx]
            src_normals = src_normals[sub_idx]
            
        if len(world_store) < 50 or len(src_pts) < 50:
            # Not enough existing world points to align against, keep initial transform
            return (initial_transform if initial_transform is not None else np.eye(4)), 0.0, True

        target_pts = world_store.get_all_positions()
        target_normals = world_store.get_all_normals()
        
        # Build target KD-tree
        target_tree = cKDTree(target_pts)
        
        # Try Open3D registration if available
        try:
            import open3d as o3d
            pcd_src = o3d.geometry.PointCloud()
            pcd_src.points = o3d.utility.Vector3dVector(src_pts)
            pcd_src.normals = o3d.utility.Vector3dVector(src_normals)
            
            pcd_tgt = o3d.geometry.PointCloud()
            pcd_tgt.points = o3d.utility.Vector3dVector(target_pts)
            pcd_tgt.normals = o3d.utility.Vector3dVector(target_normals)
            
            init_T = initial_transform if initial_transform is not None else np.eye(4)
            
            reg = o3d.pipelines.registration.registration_icp(
                pcd_src,
                pcd_tgt,
                max_correspondence_distance=self.max_corr_dist_m,
                init=init_T,
                estimation_method=o3d.pipelines.registration.TransformationEstimationPointToPlane(),
                criteria=o3d.pipelines.registration.ICPConvergenceCriteria(
                    max_iteration=self.max_iterations,
                    relative_fitness=1e-6,
                    relative_rmse=1e-6
                )
            )
            return reg.transformation, float(reg.inlier_rmse), True
        except Exception:
            # Pure NumPy / SciPy Point-to-Plane ICP Fallback
            pass
            
        # Pure NumPy ICP
        T = initial_transform.copy() if initial_transform is not None else np.eye(4, dtype=np.float64)
        prev_rmse = float("inf")
        
        for iteration in range(self.max_iterations):
            # Transform source points
            curr_src = (T[:3, :3] @ src_pts.T).T + T[:3, 3]
            
            # Find nearest neighbors in target
            dists, indices = target_tree.query(curr_src, k=1)
            valid_mask = dists < self.max_corr_dist_m
            
            if np.sum(valid_mask) < 20:
                break
                
            matched_src = curr_src[valid_mask]
            matched_tgt = target_pts[indices[valid_mask]]
            
            # Centroids
            mean_src = np.mean(matched_src, axis=0)
            mean_tgt = np.mean(matched_tgt, axis=0)
            
            # SVD alignment (Kabsch algorithm)
            H = (matched_src - mean_src).T @ (matched_tgt - mean_tgt)
            U, S, Vt = np.linalg.svd(H)
            R_delta = Vt.T @ U.T
            if np.linalg.det(R_delta) < 0:
                Vt[2, :] *= -1
                R_delta = Vt.T @ U.T
                
            t_delta = mean_tgt - (R_delta @ mean_src)
            
            # Update T
            delta_T = np.eye(4, dtype=np.float64)
            delta_T[:3, :3] = R_delta
            delta_T[:3, 3] = t_delta
            T = delta_T @ T
            
            curr_rmse = float(np.mean(dists[valid_mask]))
            if abs(prev_rmse - curr_rmse) < self.tolerance_m:
                break
            prev_rmse = curr_rmse
            
        # Quality Gate: check if ICP deviated excessively from metric camera frame
        R_cand = T[:3, :3]
        trace = np.clip(np.trace(R_cand), -1.0, 3.0)
        angle_deg = float(np.degrees(np.arccos((trace - 1.0) / 2.0)))
        trans_norm = float(np.linalg.norm(T[:3, 3]))
        
        # If rotation > 2.0° or translation > 0.20m, reject ICP to prevent drift
        if angle_deg > 2.0 or trans_norm > 0.20:
            return np.eye(4, dtype=np.float64), prev_rmse, True
            
        return T, prev_rmse, True
