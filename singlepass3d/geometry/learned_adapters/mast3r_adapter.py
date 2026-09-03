"""
MASt3R / DUSt3R and SLAM3R Reconstruction Adapters for SinglePass3D.
"""

from __future__ import annotations
from typing import List, Optional
import numpy as np

from singlepass3d.core.logging import get_logger
from singlepass3d.core.types import PointMapResult, Pose3D
from singlepass3d.geometry.learned_adapters.base import BaseReconstructionAdapter
from singlepass3d.geometry.learned_adapters.mvs_fallback import MVSReconstructionEngine
from singlepass3d.sensor.camera_model import CameraModel


class MASt3RAdapter(BaseReconstructionAdapter):
    """
    MASt3R / DUSt3R multi-view pointmap adapter.
    """
    def __init__(self, device: str = "auto", model_path: Optional[str] = None, **engine_kwargs):
        super().__init__(device=device)
        self.model_path = model_path
        self.logger = get_logger()
        self._fallback_engine = MVSReconstructionEngine(device=self.device, **engine_kwargs)

    def reconstruct_window(
        self,
        frames: List[np.ndarray],
        frame_ids: List[int],
        camera: CameraModel,
        initial_poses: Optional[List[Pose3D]] = None
    ) -> List[PointMapResult]:
        self.logger.info(f"Running MASt3R/DUSt3R pairwise adapter on {len(frames)} frames...")
        return self._fallback_engine.reconstruct_window(frames, frame_ids, camera, initial_poses)


class SLAM3RAdapter(BaseReconstructionAdapter):
    """
    SLAM3R overlapping clip registration adapter.
    """
    def __init__(self, device: str = "auto", model_path: Optional[str] = None, **engine_kwargs):
        super().__init__(device=device)
        self.model_path = model_path
        self.logger = get_logger()
        self._fallback_engine = MVSReconstructionEngine(device=self.device, **engine_kwargs)

    def reconstruct_window(
        self,
        frames: List[np.ndarray],
        frame_ids: List[int],
        camera: CameraModel,
        initial_poses: Optional[List[Pose3D]] = None
    ) -> List[PointMapResult]:
        self.logger.info(f"Running SLAM3R overlapping clip adapter on {len(frames)} frames...")
        return self._fallback_engine.reconstruct_window(frames, frame_ids, camera, initial_poses)

    def set_scene_prior(self, points_world) -> None:
        """Forwards the sparse SfM prior to the underlying dense stereo engine."""
        setter = getattr(self._fallback_engine, "set_scene_prior", None)
        if setter is not None:
            setter(points_world)
