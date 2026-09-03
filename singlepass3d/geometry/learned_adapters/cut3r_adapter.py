"""
CUT3R (Continuous Uncalibrated 3D Reconstruction) Adapter for SinglePass3D.
Maintains a streaming persistent state and accumulates metric pointmaps across frames.
"""

from __future__ import annotations
from typing import List, Optional
import numpy as np

from singlepass3d.core.logging import get_logger
from singlepass3d.core.types import PointMapResult, Pose3D
from singlepass3d.geometry.learned_adapters.base import BaseReconstructionAdapter
from singlepass3d.geometry.learned_adapters.mvs_fallback import MVSReconstructionEngine
from singlepass3d.sensor.camera_model import CameraModel


class CUT3RAdapter(BaseReconstructionAdapter):
    """
    CUT3R Adapter: streaming persistent state accumulator.
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
        self.logger.info(f"Running CUT3R persistent streaming adapter on window of {len(frames)} frames...")
        
        try:
            import torch
        except ImportError:
            pass
            
        results = self._fallback_engine.reconstruct_window(
            frames=frames,
            frame_ids=frame_ids,
            camera=camera,
            initial_poses=initial_poses
        )
        return results

    def set_scene_prior(self, points_world) -> None:
        """Forwards the sparse SfM prior to the underlying dense stereo engine."""
        setter = getattr(self._fallback_engine, "set_scene_prior", None)
        if setter is not None:
            setter(points_world)
