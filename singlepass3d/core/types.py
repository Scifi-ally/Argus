"""
Core data structures, enums, and types for SinglePass3D.
Preserves provenance, confidence, visibility, and surface elements throughout all stages.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Any
import numpy as np


class Provenance(str, Enum):
    OBSERVED = "OBSERVED"
    MULTI_VIEW_SUPPORTED = "MULTI_VIEW_SUPPORTED"
    STRUCTURAL_INFERRED = "STRUCTURAL_INFERRED"
    GENERATIVE_INFERRED = "GENERATIVE_INFERRED"


class VisibilityState(str, Enum):
    VISIBLE = "VISIBLE"
    OCCLUDED = "OCCLUDED"
    UNKNOWN = "UNKNOWN"


class SemanticClass(str, Enum):
    GROUND = "ground"
    ROAD = "road"
    BUILDING = "building"
    FACADE = "facade"
    ROOF = "roof"
    VEGETATION = "vegetation"
    WATER = "water"
    VEHICLE = "vehicle"
    PERSON = "person"
    UNKNOWN = "unknown"


class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class WorldElementState(str, Enum):
    ACTIVE = "ACTIVE"
    HYPOTHESIS = "HYPOTHESIS"
    REJECTED = "REJECTED"


@dataclass
class WorldElement:
    """
    Persistent 3D surface element (surfel).
    This representation is the central state of the SinglePass3D system.
    """
    element_id: int
    position: np.ndarray  # (3,) float64 in world ENU metric coordinates
    normal: np.ndarray = field(default_factory=lambda: np.array([0.0, 0.0, 1.0], dtype=np.float64))
    covariance: np.ndarray = field(default_factory=lambda: np.eye(3, dtype=np.float64) * 0.01)
    color: np.ndarray = field(default_factory=lambda: np.array([128.0, 128.0, 128.0], dtype=np.float64))  # RGB [0..255]
    color_observations: List[Tuple[int, np.ndarray]] = field(default_factory=list)  # (frame_id, RGB)
    supporting_frames: Set[int] = field(default_factory=set)
    supporting_rays: List[np.ndarray] = field(default_factory=list)  # (3,) viewing ray directions
    observation_count: int = 1
    reprojection_error: float = 0.0
    model_confidence: float = 1.0
    gps_trajectory_confidence: float = 1.0
    semantic_class: SemanticClass = SemanticClass.UNKNOWN
    dynamic_probability: float = 0.0
    visibility: VisibilityState = VisibilityState.VISIBLE
    provenance: Provenance = Provenance.OBSERVED
    state: WorldElementState = WorldElementState.ACTIVE
    confidence_score: float = 0.5
    confidence_level: ConfidenceLevel = ConfidenceLevel.MEDIUM
    last_updated_frame: int = -1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "element_id": self.element_id,
            "position": self.position.tolist(),
            "normal": self.normal.tolist(),
            "covariance": self.covariance.tolist(),
            "color": self.color.tolist(),
            "supporting_frames": list(self.supporting_frames),
            "observation_count": self.observation_count,
            "reprojection_error": float(self.reprojection_error),
            "model_confidence": float(self.model_confidence),
            "gps_trajectory_confidence": float(self.gps_trajectory_confidence),
            "semantic_class": self.semantic_class.value,
            "dynamic_probability": float(self.dynamic_probability),
            "visibility": self.visibility.value,
            "provenance": self.provenance.value,
            "state": self.state.value,
            "confidence_score": float(self.confidence_score),
            "confidence_level": self.confidence_level.value,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> WorldElement:
        elem = cls(
            element_id=d["element_id"],
            position=np.array(d["position"], dtype=np.float64),
            normal=np.array(d.get("normal", [0.0, 0.0, 1.0]), dtype=np.float64),
            covariance=np.array(d.get("covariance", np.eye(3).tolist()), dtype=np.float64),
            color=np.array(d.get("color", [128.0, 128.0, 128.0]), dtype=np.float64),
            supporting_frames=set(d.get("supporting_frames", [])),
            observation_count=d.get("observation_count", 1),
            reprojection_error=d.get("reprojection_error", 0.0),
            model_confidence=d.get("model_confidence", 1.0),
            gps_trajectory_confidence=d.get("gps_trajectory_confidence", 1.0),
            semantic_class=SemanticClass(d.get("semantic_class", "unknown")),
            dynamic_probability=d.get("dynamic_probability", 0.0),
            visibility=VisibilityState(d.get("visibility", "VISIBLE")),
            provenance=Provenance(d.get("provenance", "OBSERVED")),
            state=WorldElementState(d.get("state", "ACTIVE")),
            confidence_score=d.get("confidence_score", 0.5),
            confidence_level=ConfidenceLevel(d.get("confidence_level", "MEDIUM")),
        )
        return elem


@dataclass
class TelemetryPoint:
    """Normalized flight telemetry measurement (GPS / IMU)."""
    timestamp: float  # seconds from start or UTC epoch
    latitude: float   # WGS84 degrees
    longitude: float  # WGS84 degrees
    altitude: float   # WGS84 ellipsoidal / MSL meters
    relative_altitude: float = 0.0
    yaw: float = 0.0    # degrees
    pitch: float = 0.0  # degrees
    roll: float = 0.0   # degrees
    velocity: np.ndarray = field(default_factory=lambda: np.zeros(3, dtype=np.float64))  # vx, vy, vz in m/s
    heading: float = 0.0
    uncertainty: float = 1.0  # estimated horizontal standard deviation in meters
    # Vertical standard deviation, kept separate because the two channels are rarely
    # comparable: a barometer fixes height to centimetres while the same receiver's
    # horizontal fix is metres out, and vice versa on a long horizontal transect.
    vertical_uncertainty: float = 0.0  # 0 = fall back to `uncertainty`
    # Some flight logs (the Zurich AGZ set among them) carry one record per captured
    # image and name it explicitly, which is an exact frame correspondence and far
    # better than inferring one from clock arithmetic. 0 = the log did not say.
    image_id: int = 0
    # Local East-North-Up (ENU) coordinates relative to local datum origin
    enu_x: float = 0.0
    enu_y: float = 0.0
    enu_z: float = 0.0


@dataclass
class FrameMetadata:
    """Indexed video frame metadata."""
    frame_id: int
    timestamp: float
    original_index: int
    width: int
    height: int
    sharpness: float = 0.0
    blur: float = 0.0
    exposure: float = 0.0
    saturation: float = 0.0
    feature_count: int = 0
    optical_flow_magnitude: float = 0.0
    dynamic_probability: float = 0.0
    is_tracking_frame: bool = True
    is_reconstruction_frame: bool = False
    is_refinement_frame: bool = False
    proxy_path: Optional[str] = None
    fullres_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "frame_id": int(self.frame_id),
            "timestamp": float(self.timestamp),
            "original_index": int(self.original_index),
            "width": int(self.width),
            "height": int(self.height),
            "sharpness": float(self.sharpness),
            "blur": float(self.blur),
            "feature_count": int(self.feature_count),
            "is_tracking_frame": bool(self.is_tracking_frame),
            "is_reconstruction_frame": bool(self.is_reconstruction_frame),
            "is_refinement_frame": bool(self.is_refinement_frame)
        }


@dataclass
class CameraModelData:
    """Camera intrinsic and extrinsic calibration model."""
    fx: float
    fy: float
    cx: float
    cy: float
    width: int
    height: int
    distortion: np.ndarray = field(default_factory=lambda: np.zeros(5, dtype=np.float64))  # k1, k2, p1, p2, k3
    model_type: str = "brown_conrady"  # "pinhole", "brown_conrady", "fisheye"
    camera_to_gps_transform: np.ndarray = field(default_factory=lambda: np.eye(4, dtype=np.float64))
    calibration_uncertainty: float = 0.05  # fraction uncertainty

    @property
    def K(self) -> np.ndarray:
        return np.array([
            [self.fx, 0.0, self.cx],
            [0.0, self.fy, self.cy],
            [0.0, 0.0, 1.0]
        ], dtype=np.float64)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fx": float(self.fx),
            "fy": float(self.fy),
            "cx": float(self.cx),
            "cy": float(self.cy),
            "width": int(self.width),
            "height": int(self.height),
            "distortion": self.distortion.tolist(),
            "model_type": self.model_type,
            "camera_to_gps_transform": self.camera_to_gps_transform.tolist(),
            "calibration_uncertainty": float(self.calibration_uncertainty),
        }


@dataclass
class Pose3D:
    """Camera pose in world coordinate frame (World-to-Camera or Camera-to-World)."""
    frame_id: int
    timestamp: float
    R_wc: np.ndarray  # (3, 3) rotation from camera to world
    t_wc: np.ndarray  # (3,) camera position in world coordinates (ENU)
    covariance: np.ndarray = field(default_factory=lambda: np.eye(6, dtype=np.float64) * 0.01)

    @property
    def R_cw(self) -> np.ndarray:
        return self.R_wc.T

    @property
    def t_cw(self) -> np.ndarray:
        return -self.R_wc.T @ self.t_wc

    @property
    def T_wc(self) -> np.ndarray:
        T = np.eye(4, dtype=np.float64)
        T[:3, :3] = self.R_wc
        T[:3, 3] = self.t_wc
        return T

    @property
    def T_cw(self) -> np.ndarray:
        T = np.eye(4, dtype=np.float64)
        T[:3, :3] = self.R_cw
        T[:3, 3] = self.t_cw
        return T

    def to_dict(self) -> Dict[str, Any]:
        return {
            "frame_id": self.frame_id,
            "timestamp": float(self.timestamp),
            "R_wc": self.R_wc.tolist(),
            "t_wc": self.t_wc.tolist(),
            "covariance": self.covariance.tolist(),
        }


@dataclass
class Trajectory:
    """Continuous camera trajectory across time."""
    poses: Dict[int, Pose3D] = field(default_factory=dict)
    timestamps: List[float] = field(default_factory=list)
    frame_ids: List[int] = field(default_factory=list)

    def add_pose(self, pose: Pose3D) -> None:
        self.poses[pose.frame_id] = pose
        if pose.frame_id not in self.frame_ids:
            self.frame_ids.append(pose.frame_id)
            self.timestamps.append(pose.timestamp)
            # sort by timestamp
            order = np.argsort(self.timestamps)
            self.timestamps = [self.timestamps[i] for i in order]
            self.frame_ids = [self.frame_ids[i] for i in order]

    def get_pose(self, frame_id: int) -> Optional[Pose3D]:
        return self.poses.get(frame_id)

    def get_pose_at_time(self, t: float) -> Optional[Pose3D]:
        if not self.timestamps:
            return None
        if len(self.timestamps) == 1:
            return self.poses[self.frame_ids[0]]
        
        idx = np.searchsorted(self.timestamps, t)
        if idx == 0:
            return self.poses[self.frame_ids[0]]
        if idx >= len(self.timestamps):
            return self.poses[self.frame_ids[-1]]
        
        t0, t1 = self.timestamps[idx - 1], self.timestamps[idx]
        p0, p1 = self.poses[self.frame_ids[idx - 1]], self.poses[self.frame_ids[idx]]
        alpha = (t - t0) / max(1e-6, t1 - t0)
        
        # Linear interpolation for position
        t_interp = (1 - alpha) * p0.t_wc + alpha * p1.t_wc
        
        # Slerp / rotation interpolation
        # Simple geodesic rotation interpolation via matrix log/exp or quaternion
        q0 = rot_to_quat(p0.R_wc)
        q1 = rot_to_quat(p1.R_wc)
        q_interp = quat_slerp(q0, q1, alpha)
        R_interp = quat_to_rot(q_interp)
        
        return Pose3D(frame_id=-1, timestamp=t, R_wc=R_interp, t_wc=t_interp)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "frame_ids": self.frame_ids,
            "timestamps": self.timestamps,
            "poses": {str(k): v.to_dict() for k, v in self.poses.items()}
        }


def rot_to_quat(R: np.ndarray) -> np.ndarray:
    """Convert 3x3 rotation matrix to quaternion [w, x, y, z]."""
    trace = np.trace(R)
    if trace > 0:
        s = 0.5 / np.sqrt(trace + 1.0)
        w = 0.25 / s
        x = (R[2, 1] - R[1, 2]) * s
        y = (R[0, 2] - R[2, 0]) * s
        z = (R[1, 0] - R[0, 1]) * s
    else:
        if R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
            s = 2.0 * np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2])
            w = (R[2, 1] - R[1, 2]) / s
            x = 0.25 * s
            y = (R[0, 1] + R[1, 0]) / s
            z = (R[0, 2] + R[2, 0]) / s
        elif R[1, 1] > R[2, 2]:
            s = 2.0 * np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2])
            w = (R[0, 2] - R[2, 0]) / s
            x = (R[0, 1] + R[1, 0]) / s
            y = 0.25 * s
            z = (R[1, 2] + R[2, 1]) / s
        else:
            s = 2.0 * np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1])
            w = (R[1, 0] - R[0, 1]) / s
            x = (R[0, 2] + R[2, 0]) / s
            y = (R[1, 2] + R[2, 1]) / s
            z = 0.25 * s
    q = np.array([w, x, y, z], dtype=np.float64)
    norm = np.linalg.norm(q)
    return q / (norm if norm > 1e-12 else 1.0)


def quat_to_rot(q: np.ndarray) -> np.ndarray:
    """Convert quaternion [w, x, y, z] to 3x3 rotation matrix."""
    w, x, y, z = q
    return np.array([
        [1 - 2 * (y**2 + z**2), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x**2 + z**2), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x**2 + y**2)]
    ], dtype=np.float64)


def quat_slerp(q0: np.ndarray, q1: np.ndarray, alpha: float) -> np.ndarray:
    """Spherical linear interpolation between two unit quaternions."""
    dot = np.dot(q0, q1)
    if dot < 0.0:
        q1 = -q1
        dot = -dot
    if dot > 0.9995:
        result = q0 + alpha * (q1 - q0)
        return result / np.linalg.norm(result)
    theta_0 = np.arccos(np.clip(dot, -1.0, 1.0))
    sin_theta_0 = np.sin(theta_0)
    theta = theta_0 * alpha
    sin_theta = np.sin(theta)
    s0 = np.cos(theta) - dot * sin_theta / sin_theta_0
    s1 = sin_theta / sin_theta_0
    return (s0 * q0) + (s1 * q1)


@dataclass
class PointMapResult:
    """Result of learned / MVS reconstruction on a frame or pair."""
    frame_id: int
    points: np.ndarray        # (H, W, 3) in camera/local coordinate frame
    normals: np.ndarray       # (H, W, 3)
    colors: np.ndarray        # (H, W, 3) uint8 or float [0..255]
    confidences: np.ndarray   # (H, W) float [0..1]
    mask: np.ndarray          # (H, W) bool valid mask
    camera_pose: Optional[Pose3D] = None
    tracks_3d: List[Dict[str, Any]] = field(default_factory=list)
    depth: Optional[np.ndarray] = None   # (H, W) float32 metric depth in the camera frame, 0 = invalid
    K: Optional[np.ndarray] = None       # (3, 3) intrinsics matching the pointmap resolution


@dataclass
class Track3D:
    """Continuous 2D-3D visual feature track across frames."""
    track_id: int
    observations: Dict[int, np.ndarray] = field(default_factory=dict)  # frame_id -> (2,) [u, v]
    point_3d: Optional[np.ndarray] = None  # (3,) in world ENU
    reprojection_error: float = 0.0
    is_inlier: bool = True
    semantic_class: SemanticClass = SemanticClass.UNKNOWN


@dataclass
class LoopConstraint:
    """Loop closure geometric constraint between two non-adjacent frames."""
    frame_id_1: int
    frame_id_2: int
    relative_R: np.ndarray   # (3, 3)
    relative_t: np.ndarray   # (3,)
    weight: float = 1.0
    inlier_matches: int = 0
    reprojection_error: float = 0.0


@dataclass
class ReconstructionWindow:
    """Overlapping temporal window of video frames."""
    window_id: int
    frame_ids: List[int]
    start_timestamp: float
    end_timestamp: float
    overlap_with_previous: List[int] = field(default_factory=list)
    overlap_with_next: List[int] = field(default_factory=list)
