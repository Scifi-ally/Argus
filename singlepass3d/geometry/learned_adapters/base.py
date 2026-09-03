"""
Abstract Base Class for Learned 3D Reconstruction Adapters in SinglePass3D.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import numpy as np

from singlepass3d.core.types import CameraModelData, PointMapResult, Pose3D
from singlepass3d.sensor.camera_model import CameraModel


class BaseReconstructionAdapter(ABC):
    """
    Interface for multi-view learned depth/pointmap estimators (VGGT, CUT3R, MASt3R, SLAM3R).
    All outputs are treated as geometric evidence to be verified, filtered, and fused.
    """
    def __init__(self, device: str = "auto"):
        self.device = device

    @abstractmethod
    def reconstruct_window(
        self,
        frames: List[np.ndarray],
        frame_ids: List[int],
        camera: CameraModel,
        initial_poses: Optional[List[Pose3D]] = None
    ) -> List[PointMapResult]:
        """
        Reconstructs a temporal window of frames into dense pointmaps, confidences, and camera estimates.
        """
        pass
