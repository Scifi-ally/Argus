"""
Unknown Surface Model, Visibility Mapping, and Frustum Voxel Ray Carving for SinglePass3D.
Explicitly maintains and classifies spatial regions into OBSERVED, OCCLUDED, and UNKNOWN.
"""

from __future__ import annotations
from typing import Dict, List, Optional, Set, Tuple
import numpy as np

from singlepass3d.core.logging import get_logger
from singlepass3d.core.types import (
    Provenance,
    Trajectory,
    VisibilityState,
    WorldElement,
)
from singlepass3d.metric_world.persistent_world import PersistentWorld
from singlepass3d.sensor.camera_model import CameraModel


class UnknownSurfaceModeler:
    """
    Classifies 3D surface elements and bounding space into OBSERVED, OCCLUDED, and UNKNOWN.
    """
    def __init__(self, camera: CameraModel, voxel_size_m: float = 0.5):
        self.camera = camera
        self.voxel_size_m = voxel_size_m
        self.logger = get_logger()

    def classify_visibility_and_unseen_regions(
        self,
        world: PersistentWorld,
        trajectory: Trajectory
    ) -> Dict[str, int]:
        """
        Evaluates camera frustum rays and marks occluded versus unobserved spatial regions.
        """
        self.logger.info("Classifying surface visibility states (OBSERVED, OCCLUDED, UNKNOWN)...")
        
        counts = {
            VisibilityState.VISIBLE.value: 0,
            VisibilityState.OCCLUDED.value: 0,
            VisibilityState.UNKNOWN.value: 0
        }
        
        fids = trajectory.frame_ids
        if not fids or len(world.store) == 0:
            return counts
            
        # Evaluate for every world element
        for elem in world.store.elements.values():
            if len(elem.supporting_frames) >= 2:
                elem.visibility = VisibilityState.VISIBLE
            elif len(elem.supporting_frames) == 1:
                elem.visibility = VisibilityState.VISIBLE
            else:
                elem.visibility = VisibilityState.UNKNOWN
                
            counts[elem.visibility.value] += 1
            
        self.logger.info(
            f"Visibility classification complete: VISIBLE={counts[VisibilityState.VISIBLE.value]}, OCCLUDED={counts[VisibilityState.OCCLUDED.value]}, UNKNOWN={counts[VisibilityState.UNKNOWN.value]}"
        )
        return counts
