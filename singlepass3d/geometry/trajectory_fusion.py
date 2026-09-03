"""
GPS-Constrained Trajectory Optimization and Visual-Inertial-Telemetry Fusion for SinglePass3D.
Jointly solves for continuous camera poses using visual reprojection, GPS positions (ENU),
and kinematic temporal smoothness using robust nonlinear least squares (Huber loss).
"""

from __future__ import annotations
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np
from scipy.optimize import least_squares

from singlepass3d.core.logging import get_logger
from singlepass3d.core.types import Pose3D, Trajectory, Track3D, TelemetryPoint
from singlepass3d.sensor.camera_model import CameraModel
from singlepass3d.sensor.telemetry_parser import TelemetryParser
from singlepass3d.sensor.video_indexer import VideoIndexer


def rot_matrix_to_vec(R: np.ndarray) -> np.ndarray:
    """Convert 3x3 rotation matrix to Rodrigues rotation vector."""
    rvec, _ = cv2.Rodrigues(R)
    return rvec.reshape(3)


def rot_vec_to_matrix(rvec: np.ndarray) -> np.ndarray:
    """Convert Rodrigues rotation vector to 3x3 rotation matrix."""
    R, _ = cv2.Rodrigues(rvec.reshape(3, 1))
    return R


class TrajectoryOptimizer:
    """
    Formulates and solves the GPS-visual trajectory factor graph optimization problem.
    """
    def __init__(
        self,
        camera: CameraModel,
        gps_weight: float = 10.0,
        visual_weight: float = 1.0,
        smoothness_weight: float = 2.0,
        huber_delta: float = 2.0,
        max_iters: int = 50
    ):
        self.camera = camera
        self.gps_weight = gps_weight
        self.visual_weight = visual_weight
        self.smoothness_weight = smoothness_weight
        self.huber_delta = huber_delta
        self.max_iters = max_iters
        self.logger = get_logger()

    def optimize_trajectory(
        self,
        frame_ids: List[int],
        indexer: VideoIndexer,
        telemetry: Optional[TelemetryParser] = None,
        tracks: Optional[List[Track3D]] = None,
        initial_trajectory: Optional[Trajectory] = None
    ) -> Trajectory:
        """
        Executes trajectory optimization across the given frame sequence.
        """
        self.logger.info(f"Optimizing trajectory across {len(frame_ids)} frames...")
        
        N = len(frame_ids)
        if N == 0:
            return Trajectory()
            
        # 1. Initialize Poses from Telemetry or Visual Odometry
        init_rvecs = np.zeros((N, 3), dtype=np.float64)
        init_tvecs = np.zeros((N, 3), dtype=np.float64)
        gps_targets = np.zeros((N, 3), dtype=np.float64)
        gps_weights = np.zeros(N, dtype=np.float64)
        timestamps = np.zeros(N, dtype=np.float64)
        
        for i, fid in enumerate(frame_ids):
            meta = indexer.frame_index[fid]
            t = meta.timestamp
            timestamps[i] = t
            
            # Check telemetry
            tele = telemetry.get_telemetry_at(t) if telemetry else None
            if tele is not None:
                # GPS position in local ENU
                gps_targets[i] = np.array([tele.enu_x, tele.enu_y, tele.enu_z], dtype=np.float64)
                # Uncertainty weighting
                gps_weights[i] = 1.0 / max(0.1, tele.uncertainty)
                
                # Gimbal / drone orientation from yaw, pitch, roll
                # Yaw: heading around Z, Pitch: around X/Y, Roll: around Y/X
                yaw_rad = np.radians(tele.yaw)
                pitch_rad = np.radians(tele.pitch)
                roll_rad = np.radians(tele.roll)
                
                # Camera orientation in ENU: standard drone downward-forward camera:
                # Z_world is Up, X_world is East, Y_world is North.
                # Camera convention: Z_cam points forward along optical axis, X_cam right, Y_cam down
                # Base drone body to world rotation
                Rz = np.array([
                    [np.cos(yaw_rad), -np.sin(yaw_rad), 0],
                    [np.sin(yaw_rad), np.cos(yaw_rad), 0],
                    [0, 0, 1]
                ])
                Ry = np.array([
                    [np.cos(pitch_rad), 0, np.sin(pitch_rad)],
                    [0, 1, 0],
                    [-np.sin(pitch_rad), 0, np.cos(pitch_rad)]
                ])
                Rx = np.array([
                    [1, 0, 0],
                    [0, np.cos(roll_rad), -np.sin(roll_rad)],
                    [0, np.sin(roll_rad), np.cos(roll_rad)]
                ])
                R_body = Rz @ Ry @ Rx
                
                # Conversion from drone body (X: Forward, Y: Right, Z: Up) to camera (X: Right, Y: Down, Z: Forward)
                R_body_to_cam = np.array([
                    [0, 1, 0],
                    [0, 0, -1],
                    [1, 0, 0]
                ], dtype=np.float64)
                
                R_wc = R_body @ R_body_to_cam.T
                init_rvecs[i] = rot_matrix_to_vec(R_wc)
                init_tvecs[i] = gps_targets[i]
            else:
                # Fallback: simple forward motion trajectory if no telemetry
                init_tvecs[i] = np.array([i * 0.5, 0.0, 10.0], dtype=np.float64)
                # Look slightly downward
                R_default = np.array([
                    [1, 0, 0],
                    [0, 0, -1],
                    [0, 1, 0]
                ], dtype=np.float64)
                init_rvecs[i] = rot_matrix_to_vec(R_default)
                gps_weights[i] = 0.0

        # If an initial trajectory is provided, use it to seed
        if initial_trajectory:
            for i, fid in enumerate(frame_ids):
                pose = initial_trajectory.get_pose(fid)
                if pose:
                    init_rvecs[i] = rot_matrix_to_vec(pose.R_wc)
                    init_tvecs[i] = pose.t_wc

        # 2. Setup Landmarks from Tracks for Visual Reprojection Factors
        valid_tracks = tracks or []
        # Filter top tracks with >= 3 observations
        top_tracks = sorted(
            [t for t in valid_tracks if len(t.observations) >= 3],
            key=lambda tr: len(tr.observations),
            reverse=True
        )[:100]
        
        # Triangulate initial landmark 3D positions using calibrated linear triangulation
        landmark_3d = np.zeros((len(top_tracks), 3), dtype=np.float64)
        valid_landmark_mask = np.zeros(len(top_tracks), dtype=bool)
        
        for j, tr in enumerate(top_tracks):
            obs_fids = [fid for fid in frame_ids if fid in tr.observations]
            if len(obs_fids) >= 2:
                # Choose pair with largest baseline
                i0 = frame_ids.index(obs_fids[0])
                i1 = frame_ids.index(obs_fids[-1])
                R0 = rot_vec_to_matrix(init_rvecs[i0])
                t0 = init_tvecs[i0]
                R1 = rot_vec_to_matrix(init_rvecs[i1])
                t1 = init_tvecs[i1]
                
                # World to camera projection matrices: P = K @ [R_cw | t_cw]
                P0 = self.camera.K @ np.hstack([R0.T, -R0.T @ t0.reshape(3, 1)])
                P1 = self.camera.K @ np.hstack([R1.T, -R1.T @ t1.reshape(3, 1)])
                
                pt0 = np.array(tr.observations[obs_fids[0]], dtype=np.float64).reshape(2, 1)
                pt1 = np.array(tr.observations[obs_fids[-1]], dtype=np.float64).reshape(2, 1)
                
                pts4d = cv2.triangulatePoints(P0, P1, pt0, pt1)
                w = pts4d[3, 0]
                if abs(w) > 1e-6:
                    pt3d = (pts4d[:3, 0] / w)
                    # Cheirality check
                    z0 = (R0.T @ (pt3d - t0))[2]
                    z1 = (R1.T @ (pt3d - t1))[2]
                    if 0.5 < z0 < 150.0 and 0.5 < z1 < 150.0:
                        landmark_3d[j] = pt3d
                        valid_landmark_mask[j] = True
                        continue
            
            # Fallback: estimate from optical ray and median flight altitude (~14m)
            if obs_fids:
                i0 = frame_ids.index(obs_fids[0])
                R0 = rot_vec_to_matrix(init_rvecs[i0])
                t0 = init_tvecs[i0]
                ray_c = np.linalg.inv(self.camera.K) @ np.array([tr.observations[obs_fids[0]][0], tr.observations[obs_fids[0]][1], 1.0])
                ray_w = R0 @ (ray_c / np.linalg.norm(ray_c))
                landmark_3d[j] = t0 + ray_w * 14.0
                valid_landmark_mask[j] = True

        # 3. Vectorize Optimization Parameters: Poses only [rvecs (N*3), tvecs (N*3)]
        x0 = np.hstack([init_rvecs.ravel(), init_tvecs.ravel()])
        
        # Position lookup: a list scan here runs once per observation per Jacobian
        # column, which is thousands of linear searches per solver iteration.
        frame_pos = {int(f): i for i, f in enumerate(frame_ids)}

        # 4. Residual Function
        def residuals_func(x: np.ndarray) -> np.ndarray:
            rvecs = x[:N*3].reshape(N, 3)
            tvecs = x[N*3:N*6].reshape(N, 3)
            
            # Precompute rotation matrices for all N frames
            R_mats = [rot_vec_to_matrix(rvecs[i]) for i in range(N)]
            
            res_list: List[float] = []
            
            # (A) GPS Position Residuals
            for i in range(N):
                if gps_weights[i] > 0:
                    err_gps = (tvecs[i] - gps_targets[i]) * (self.gps_weight * gps_weights[i])
                    res_list.extend(err_gps.tolist())
                    
            # (B) Kinematic / Smoothness Residuals (velocity constancy)
            for i in range(1, N - 1):
                dt1 = max(1e-3, timestamps[i] - timestamps[i - 1])
                dt2 = max(1e-3, timestamps[i + 1] - timestamps[i])
                v1 = (tvecs[i] - tvecs[i - 1]) / dt1
                v2 = (tvecs[i + 1] - tvecs[i]) / dt2
                accel = (v2 - v1) * self.smoothness_weight
                res_list.extend(accel.tolist())
                
                # Angular smoothness
                rot_diff = (rvecs[i + 1] - 2 * rvecs[i] + rvecs[i - 1]) * (self.smoothness_weight * 0.5)
                res_list.extend(rot_diff.tolist())
                
            # (C) Visual Reprojection Residuals
            if len(top_tracks) > 0:
                for j, tr in enumerate(top_tracks):
                    pt_w = landmark_3d[j]
                    for fid, uv_obs in tr.observations.items():
                        i = frame_pos.get(fid)
                        if i is not None:
                            R_wc = R_mats[i]
                            t_wc = tvecs[i]
                            # World to Camera: X_c = R_wc.T @ (pt_w - t_wc)
                            pt_c = R_wc.T @ (pt_w - t_wc)
                            depth = max(0.1, pt_c[2])
                            u_proj = self.camera.data.fx * (pt_c[0] / depth) + self.camera.data.cx
                            v_proj = self.camera.data.fy * (pt_c[1] / depth) + self.camera.data.cy
                            err_u = (u_proj - uv_obs[0]) * (self.visual_weight * 0.1)
                            err_v = (v_proj - uv_obs[1]) * (self.visual_weight * 0.1)
                            res_list.append(float(err_u))
                            res_list.append(float(err_v))
                            
            return np.array(res_list, dtype=np.float64)

        # Run non-linear least squares optimization with Huber loss
        try:
            res = least_squares(
                residuals_func,
                x0,
                method='trf',
                loss='huber',
                f_scale=self.huber_delta,
                ftol=1e-3,
                xtol=1e-3,
                max_nfev=min(30, self.max_iters),
                verbose=0
            )
            opt_x = res.x
        except Exception as e:
            self.logger.warning(f"Nonlinear least squares failed ({e}), using initial estimates.")
            opt_x = x0

        opt_rvecs = opt_x[:N*3].reshape(N, 3)
        opt_tvecs = opt_x[N*3:N*6].reshape(N, 3)
        
        # Build Trajectory Object
        optimized_trajectory = Trajectory()
        for i, fid in enumerate(frame_ids):
            R_wc = rot_vec_to_matrix(opt_rvecs[i])
            t_wc = opt_tvecs[i]
            pose = Pose3D(
                frame_id=fid,
                timestamp=timestamps[i],
                R_wc=R_wc,
                t_wc=t_wc,
                covariance=np.eye(6, dtype=np.float64) * 0.05
            )
            optimized_trajectory.add_pose(pose)
            
        self.logger.info(f"Trajectory optimization complete for {len(optimized_trajectory.poses)} poses.")
        return optimized_trajectory
