"""
Continuous Geometry Layer: visual tracking, trajectory optimization, keyframe selection,
classical SfM, learned reconstruction adapters, and window management.
"""

from singlepass3d.geometry.visual_tracker import VisualTracker
from singlepass3d.geometry.trajectory_fusion import TrajectoryOptimizer, rot_matrix_to_vec, rot_vec_to_matrix
from singlepass3d.geometry.keyframe_selector import KeyframeSelector
from singlepass3d.geometry.classical_sfm import ClassicalSfMVerifier
from singlepass3d.geometry.window_manager import WindowManager
from singlepass3d.geometry.learned_adapters import get_adapter

__all__ = [
    "VisualTracker",
    "TrajectoryOptimizer",
    "rot_matrix_to_vec",
    "rot_vec_to_matrix",
    "KeyframeSelector",
    "ClassicalSfMVerifier",
    "WindowManager",
    "get_adapter",
]
