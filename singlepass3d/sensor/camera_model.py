"""
Camera Calibration, Lens Distortion Models (Brown-Conrady, Fisheye),
Projection/Unprojection, and Camera-to-GPS Lever-Arm Transformations for SinglePass3D.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Optional, Tuple
import cv2
import numpy as np

from singlepass3d.core.logging import get_logger
from singlepass3d.core.types import CameraModelData, Pose3D


class CameraModel:
    """
    Handles camera intrinsics, distortion correction, projection/unprojection,
    and coordinate transformations between camera frame, gimbal frame, and GPS body frame.
    """
    def __init__(self, data: CameraModelData):
        self.data = data
        self.logger = get_logger()

    @property
    def K(self) -> np.ndarray:
        return self.data.K

    @property
    def fx(self) -> float:
        return self.data.fx

    @property
    def fy(self) -> float:
        return self.data.fy

    @property
    def cx(self) -> float:
        return self.data.cx

    @property
    def cy(self) -> float:
        return self.data.cy

    @property
    def width(self) -> int:
        return self.data.width

    @property
    def height(self) -> int:
        return self.data.height

    @classmethod
    def from_calibration_file(
        cls,
        calib_path: str | Path,
        width: int = 1920,
        height: int = 1080,
        model_type: str = "brown_conrady",
        lever_arm_xyz: Tuple[float, float, float] = (0.0, 0.0, -0.1)
    ) -> CameraModel:
        """
        Loads calibrated camera intrinsics and distortion coefficients from .npz or .json calibration file.
        """
        path = Path(calib_path)
        if not path.exists():
            raise FileNotFoundError(f"Calibration file not found: {path}")
            
        T_gps_cam = np.eye(4, dtype=np.float64)
        T_gps_cam[:3, 3] = np.array(lever_arm_xyz, dtype=np.float64)
        
        if path.suffix == ".npz":
            data = np.load(path)
            K = data["intrinsic_matrix"]
            dist = data["distCoeff"]
            if dist.ndim > 1:
                dist = dist.ravel()
            # Pad or trim distortion to 5 params
            dist_5 = np.zeros(5, dtype=np.float64)
            dist_5[:min(5, len(dist))] = dist[:min(5, len(dist))]
            
            cam_data = CameraModelData(
                fx=float(K[0, 0]),
                fy=float(K[1, 1]),
                cx=float(K[0, 2]),
                cy=float(K[1, 2]),
                width=int(width),
                height=int(height),
                distortion=dist_5,
                model_type=model_type,
                camera_to_gps_transform=T_gps_cam,
                calibration_uncertainty=0.005
            )
            return cls(cam_data)
        elif path.suffix == ".json":
            with open(path, "r") as f:
                d = json.load(f)
            cam_data = CameraModelData(
                fx=float(d.get("fx", width)),
                fy=float(d.get("fy", width)),
                cx=float(d.get("cx", width / 2.0)),
                cy=float(d.get("cy", height / 2.0)),
                width=int(d.get("width", width)),
                height=int(d.get("height", height)),
                distortion=np.array(d.get("distortion", [0, 0, 0, 0, 0]), dtype=np.float64),
                model_type=model_type,
                camera_to_gps_transform=T_gps_cam,
                calibration_uncertainty=0.005
            )
            return cls(cam_data)
        else:
            raise ValueError(f"Unsupported calibration format: {path.suffix}")

    @classmethod
    def create_default(
        cls,
        width: int,
        height: int,
        fov_deg: float = 80.0,
        known_focal_length_px: Optional[float] = None,
        model_type: str = "brown_conrady",
        lever_arm_xyz: Tuple[float, float, float] = (0.0, 0.0, -0.1)
    ) -> CameraModel:
        """
        Creates camera model from image dimensions and estimated FOV.
        """
        cx = width / 2.0
        cy = height / 2.0
        
        if known_focal_length_px is not None and known_focal_length_px > 0:
            fx = known_focal_length_px
            fy = known_focal_length_px
        else:
            # f = (width / 2) / tan(fov / 2)
            fov_rad = np.radians(fov_deg)
            fx = (width / 2.0) / np.tan(fov_rad / 2.0)
            fy = fx  # assume square pixels
            
        # Lever-arm transform from camera to GPS receiver
        T_gps_cam = np.eye(4, dtype=np.float64)
        T_gps_cam[:3, 3] = np.array(lever_arm_xyz, dtype=np.float64)
        
        data = CameraModelData(
            fx=float(fx),
            fy=float(fy),
            cx=float(cx),
            cy=float(cy),
            width=int(width),
            height=int(height),
            distortion=np.zeros(5, dtype=np.float64),
            model_type=model_type,
            camera_to_gps_transform=T_gps_cam,
            calibration_uncertainty=0.05
        )
        return cls(data)

    def undistort_image(self, img: np.ndarray) -> np.ndarray:
        """
        Removes lens distortion from image using calibrated camera matrix and distortion coefficients.
        """
        if np.allclose(self.data.distortion, 0):
            return img
        return cv2.undistort(img, self.K, self.data.distortion, None, self.K)

    def _distort_normalized(self, xn: np.ndarray, yn: np.ndarray):
        """Applies the calibrated forward (ideal -> observed) Brown-Conrady distortion."""
        k1, k2, p1, p2, k3 = [float(v) for v in self.data.distortion[:5]]
        r2 = xn * xn + yn * yn
        radial = 1.0 + k1 * r2 + k2 * r2 * r2 + k3 * r2 * r2 * r2
        xd = xn * radial + 2.0 * p1 * xn * yn + p2 * (r2 + 2.0 * xn * xn)
        yd = yn * radial + p1 * (r2 + 2.0 * yn * yn) + 2.0 * p2 * xn * yn
        return xd, yd

    def _rectified_coverage(self, new_K: np.ndarray) -> float:
        """
        Fraction of a candidate rectified frame that samples inside the source image.

        cv2.undistortPoints iterates an inverse distortion model that diverges for
        strongly barrel-distorted lenses, so candidate intrinsics are validated with
        the exact forward model instead of trusting the inverse.
        """
        w, h = float(self.data.width), float(self.data.height)
        u, v = np.meshgrid(np.linspace(0.0, w - 1.0, 96), np.linspace(0.0, h - 1.0, 54))
        xn = (u - new_K[0, 2]) / new_K[0, 0]
        yn = (v - new_K[1, 2]) / new_K[1, 1]
        xd, yd = self._distort_normalized(xn, yn)
        us = self.data.fx * xd + self.data.cx
        vs = self.data.fy * yd + self.data.cy
        inside = (us >= 0.0) & (us <= w - 1.0) & (vs >= 0.0) & (vs <= h - 1.0)
        return float(np.count_nonzero(inside)) / float(inside.size)

    def undistorted_model(self, min_coverage: float = 0.995) -> "CameraModel":
        """
        Returns the ideal pinhole camera corresponding to lens-corrected imagery.

        Candidate intrinsics are tried in order of preference and the first one whose
        rectified frame is almost entirely covered by real source pixels is kept, so
        the rectified images carry no black border and no invented content.
        """
        if np.allclose(self.data.distortion, 0):
            return CameraModel(self.data)

        w, h = int(self.data.width), int(self.data.height)
        candidates = [self.K.copy()]
        for alpha in (0.0, 0.25, 0.6, 1.0):
            try:
                cand, _ = cv2.getOptimalNewCameraMatrix(
                    self.K, self.data.distortion, (w, h), alpha, (w, h)
                )
                candidates.append(np.asarray(cand, dtype=np.float64))
            except cv2.error as exc:
                self.logger.debug(f"getOptimalNewCameraMatrix(alpha={alpha}) failed: {exc}")

        best_K, best_cov = candidates[0], -1.0
        for cand in candidates:
            cov = self._rectified_coverage(cand)
            if cov > best_cov:
                best_K, best_cov = cand, cov
            if cov >= min_coverage:
                best_K, best_cov = cand, cov
                break

        self.logger.info(
            f"Rectified pinhole intrinsics: fx={best_K[0, 0]:.2f} fy={best_K[1, 1]:.2f} "
            f"cx={best_K[0, 2]:.2f} cy={best_K[1, 2]:.2f} (valid-pixel coverage {best_cov * 100:.1f}%)"
        )

        new_data = CameraModelData(
            fx=float(best_K[0, 0]),
            fy=float(best_K[1, 1]),
            cx=float(best_K[0, 2]),
            cy=float(best_K[1, 2]),
            width=w,
            height=h,
            distortion=np.zeros(5, dtype=np.float64),
            model_type="pinhole",
            camera_to_gps_transform=self.data.camera_to_gps_transform.copy(),
            calibration_uncertainty=self.data.calibration_uncertainty,
        )
        return CameraModel(new_data)

    def undistort_maps(self, width: int, height: int, target: Optional["CameraModel"] = None):
        """
        Builds cv2.remap lookup tables that rectify imagery at the given resolution.

        Both this model and the target pinhole model are scaled to (width, height)
        so the maps can be applied directly to proxy or full-resolution frames.
        """
        src = self.scale_to_resolution(width, height)
        dst = (target or self.undistorted_model()).scale_to_resolution(width, height)

        if self.data.model_type == "fisheye":
            map1, map2 = cv2.fisheye.initUndistortRectifyMap(
                src.K, src.data.distortion[:4].reshape(4, 1), np.eye(3), dst.K, (width, height), cv2.CV_16SC2
            )
        else:
            map1, map2 = cv2.initUndistortRectifyMap(
                src.K, src.data.distortion, None, dst.K, (width, height), cv2.CV_16SC2
            )
        return map1, map2

    def undistort_points(self, uv: np.ndarray) -> np.ndarray:
        """
        Undistort 2D pixel coordinates (N, 2) to ideal pinhole pixel coordinates.
        """
        if np.allclose(self.data.distortion, 0):
            return uv
        pts = np.atleast_2d(uv).astype(np.float32).reshape(-1, 1, 2)
        undist_pts = cv2.undistortPoints(pts, self.K, self.data.distortion, P=self.K)
        return undist_pts.reshape(-1, 2)

    def project(self, points_3d_cam: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Project 3D points in camera coordinates (N, 3) to 2D pixel coordinates (N, 2).
        Returns:
            uv: (N, 2) pixel coordinates
            valid_mask: (N,) boolean mask (points in front of camera, Z > 0.01)
        """
        points = np.atleast_2d(points_3d_cam)
        z = points[:, 2]
        valid_mask = z > 1e-4
        
        safe_z = np.where(valid_mask, z, 1.0)
        x_norm = points[:, 0] / safe_z
        y_norm = points[:, 1] / safe_z
        
        # Apply lens distortion if non-zero
        k1, k2, p1, p2, k3 = self.data.distortion[:5]
        if abs(k1) > 1e-7 or abs(k2) > 1e-7 or abs(p1) > 1e-7 or abs(p2) > 1e-7:
            r2 = x_norm**2 + y_norm**2
            radial = 1.0 + k1 * r2 + k2 * (r2**2) + k3 * (r2**3)
            x_dist = x_norm * radial + 2.0 * p1 * x_norm * y_norm + p2 * (r2 + 2.0 * x_norm**2)
            y_dist = y_norm * radial + p1 * (r2 + 2.0 * y_norm**2) + 2.0 * p2 * x_norm * y_norm
        else:
            x_dist = x_norm
            y_dist = y_norm
            
        u = self.data.fx * x_dist + self.data.cx
        v = self.data.fy * y_dist + self.data.cy
        
        uv = np.stack([u, v], axis=1)
        # Check image bounds
        in_bounds = (u >= 0) & (u < self.data.width) & (v >= 0) & (v < self.data.height)
        valid = valid_mask & in_bounds
        return uv, valid

    def project_world_points(self, points_3d_world: np.ndarray, pose: Pose3D) -> Tuple[np.ndarray, np.ndarray]:
        """
        Project 3D points in world ENU frame into 2D camera pixel coordinates.
        """
        pts_w = np.atleast_2d(points_3d_world)
        # Transform World -> Camera: X_c = R_cw @ X_w + t_cw
        pts_c = (pose.R_cw @ pts_w.T).T + pose.t_cw
        return self.project(pts_c)

    def unproject(self, uv: np.ndarray, depth: np.ndarray) -> np.ndarray:
        """
        Unproject 2D pixel coordinates (N, 2) and depths (N,) to 3D points in camera frame (N, 3).
        """
        uv = np.atleast_2d(uv)
        depth = np.asarray(depth).reshape(-1)
        
        u = uv[:, 0]
        v = uv[:, 1]
        
        x_norm = (u - self.data.cx) / self.data.fx
        y_norm = (v - self.data.cy) / self.data.fy
        
        x_c = x_norm * depth
        y_c = y_norm * depth
        z_c = depth
        
        return np.stack([x_c, y_c, z_c], axis=1)

    def unproject_to_world(self, uv: np.ndarray, depth: np.ndarray, pose: Pose3D) -> np.ndarray:
        """
        Unproject 2D pixels and depth directly into 3D World ENU coordinates.
        """
        pts_c = self.unproject(uv, depth)
        # Transform Camera -> World: X_w = R_wc @ X_c + t_wc
        pts_w = (pose.R_wc @ pts_c.T).T + pose.t_wc
        return pts_w

    def get_ray_directions(self, uv: np.ndarray) -> np.ndarray:
        """
        Get unit 3D viewing ray directions in camera coordinates for given 2D pixel coords.
        """
        uv = np.atleast_2d(uv)
        x_norm = (uv[:, 0] - self.data.cx) / self.data.fx
        y_norm = (uv[:, 1] - self.data.cy) / self.data.fy
        z_norm = np.ones_like(x_norm)
        
        rays = np.stack([x_norm, y_norm, z_norm], axis=1)
        norms = np.linalg.norm(rays, axis=1, keepdims=True)
        return rays / np.maximum(1e-12, norms)

    def scale_to_resolution(self, new_width: int, new_height: int) -> CameraModel:
        """
        Returns a new CameraModel scaled to a proxy or target resolution.
        """
        sx = new_width / float(self.data.width)
        sy = new_height / float(self.data.height)
        
        new_data = CameraModelData(
            fx=self.data.fx * sx,
            fy=self.data.fy * sy,
            cx=self.data.cx * sx,
            cy=self.data.cy * sy,
            width=new_width,
            height=new_height,
            distortion=self.data.distortion.copy(),
            model_type=self.data.model_type,
            camera_to_gps_transform=self.data.camera_to_gps_transform.copy(),
            calibration_uncertainty=self.data.calibration_uncertainty
        )
        return CameraModel(new_data)
