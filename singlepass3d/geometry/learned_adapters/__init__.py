"""
Learned 3D reconstruction adapters (VGGT, CUT3R, MASt3R, SLAM3R, MVS Fallback).
"""

from singlepass3d.geometry.learned_adapters.base import BaseReconstructionAdapter
from singlepass3d.geometry.learned_adapters.vggt_adapter import VGGTAdapter
from singlepass3d.geometry.learned_adapters.cut3r_adapter import CUT3RAdapter
from singlepass3d.geometry.learned_adapters.mast3r_adapter import MASt3RAdapter, SLAM3RAdapter
from singlepass3d.geometry.learned_adapters.mvs_fallback import MVSReconstructionEngine

__all__ = [
    "BaseReconstructionAdapter",
    "VGGTAdapter",
    "CUT3RAdapter",
    "MASt3RAdapter",
    "SLAM3RAdapter",
    "MVSReconstructionEngine",
]


def get_adapter(name: str = "vggt", device: str = "auto", **engine_kwargs) -> BaseReconstructionAdapter:
    """
    Instantiates the requested adapter, forwarding dense-stereo tuning options.

    The transformer adapters (VGGT/CUT3R/MASt3R/SLAM3R) need PyTorch weights. When
    torch is unavailable there is nothing to run, so the deterministic plane-sweep
    MVS engine is returned directly instead of a wrapper that silently delegates.
    """
    name_lower = name.lower()
    try:
        import torch  # noqa: F401
        torch_available = True
    except ImportError:
        torch_available = False

    if not torch_available and name_lower in ("vggt", "cut3r", "mast3r", "dust3r", "slam3r"):
        from singlepass3d.core.logging import get_logger
        get_logger().info(
            f"'{name}' requires PyTorch, which is not installed - using the plane-sweep MVS engine."
        )
        return MVSReconstructionEngine(device=device, **engine_kwargs)

    if name_lower == "vggt":
        return VGGTAdapter(device=device, **engine_kwargs)
    elif name_lower == "cut3r":
        return CUT3RAdapter(device=device, **engine_kwargs)
    elif name_lower in ["mast3r", "dust3r"]:
        return MASt3RAdapter(device=device, **engine_kwargs)
    elif name_lower == "slam3r":
        return SLAM3RAdapter(device=device, **engine_kwargs)
    else:
        return MVSReconstructionEngine(device=device, **engine_kwargs)
