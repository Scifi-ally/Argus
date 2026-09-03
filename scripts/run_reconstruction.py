#!/usr/bin/env python3
"""
SinglePass3D — Main Reconstruction CLI
Usage:
    python scripts/run_reconstruction.py \
      --video input.mp4 \
      --telemetry flight.srt \
      --output outputs/job_001 \
      --quality ultra
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from singlepass3d.config.pipeline_config import SinglePass3DConfig
from singlepass3d.pipeline.runner import SinglePass3DPipeline


def main() -> int:
    parser = argparse.ArgumentParser(
        description="SinglePass3D: Continuous Multi-View Drone-Video-to-3D Reconstruction"
    )
    parser.add_argument("--video", "-v", required=True, type=str, help="Path to input drone video (MP4/MOV)")
    parser.add_argument("--telemetry", "-t", type=str, default=None, help="Path to flight telemetry (SRT/CSV/JSON)")
    parser.add_argument("--output", "-o", required=True, type=str, help="Directory to save reconstruction outputs")
    parser.add_argument(
        "--quality", "-q",
        type=str,
        default="balanced",
        choices=["fast", "balanced", "high", "ultra"],
        help="Reconstruction quality preset (fast, balanced, high, ultra)"
    )
    parser.add_argument(
        "--adapter",
        type=str,
        default="vggt",
        choices=["vggt", "cut3r", "mast3r", "slam3r", "mvs_fallback"],
        help="Learned multi-view reconstruction adapter"
    )
    parser.add_argument("--fov", type=float, default=80.0, help="Camera Field of View in degrees (default: 80)")
    parser.add_argument("--focal-length", type=float, default=None, help="Known focal length in pixels")
    parser.add_argument("--max-frames", type=int, default=None, help="Maximum number of frames to process (for subsets)")
    parser.add_argument("--calibration", "-c", type=str, default=None, help="Path to camera calibration file (.npz or .json)")
    parser.add_argument("--no-debug", action="store_true", help="Disable intermediate 12-stage diagnostic output export")
    parser.add_argument("--no-cache", action="store_true", help="Disable stage result caching")
    parser.add_argument("--device", type=str, default="auto", help="Compute device ('cpu', 'cuda', 'auto')")

    args = parser.parse_args()

    config = SinglePass3DConfig(
        video_path=args.video,
        telemetry_path=args.telemetry,
        calibration_path=args.calibration,
        debug_reconstruction=not args.no_debug,
        output_dir=args.output,
        quality=args.quality,
        learned_adapter=args.adapter,
        default_fov_deg=args.fov,
        known_focal_length_px=args.focal_length,
        enable_cache=not args.no_cache,
        device=args.device
    )

    try:
        pipeline = SinglePass3DPipeline(config)
        result = pipeline.run(max_frames=args.max_frames)
        print(f"\n[SUCCESS] Reconstruction completed successfully.")
        print(f"Artifacts saved in: {result['output_dir']}")
        print(f"Overall QA Status: {result['qa_report']['quality_status']}")
        return 0
    except Exception as e:
        print(f"\n[ERROR] Pipeline failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
