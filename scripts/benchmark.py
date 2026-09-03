#!/usr/bin/env python3
"""
SinglePass3D — Benchmark and Performance Profiling CLI
Usage:
    python scripts/benchmark.py outputs/job_001
"""

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
import psutil


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark SinglePass3D execution timings and memory profiling.")
    parser.add_argument("job_dir", type=str, help="Path to the output job directory")
    args = parser.parse_args()

    job_dir = Path(args.job_dir)
    if not job_dir.exists():
        print(f"Error: Directory not found: {job_dir}", file=sys.stderr)
        return 1

    diag_file = job_dir / "diagnostics.json"
    quality_file = job_dir / "quality.json"

    if not diag_file.exists():
        print(f"Error: diagnostics.json not found in {job_dir}", file=sys.stderr)
        return 1

    with open(diag_file, "r", encoding="utf-8") as f:
        diag = json.load(f)

    timings = diag.get("stage_durations", {})
    total_time = diag.get("total_pipeline_time_seconds", sum(timings.values()))

    # Process Memory Info
    process = psutil.Process()
    mem_info = process.memory_info()
    ram_mb = mem_info.rss / (1024 * 1024)

    print("=" * 65)
    print(f" SinglePass3D Performance & Benchmark Analysis")
    print("=" * 65)
    print(f"System Memory Usage:        {ram_mb:.1f} MB (Resident Set)")
    print(f"Total Pipeline Runtime:     {total_time:.2f} seconds")
    print(f"Total Recorded Stages:      {len(timings)}")
    print("\n[Stage Breakdown by Duration & Bottleneck %]")

    sorted_timings = sorted(timings.items(), key=lambda x: x[1], reverse=True)
    for stage, dur in sorted_timings:
        pct = (dur / max(1e-4, total_time)) * 100.0
        bar_len = int(round(pct / 4))
        bar = "#" * bar_len
        print(f"  {stage:<35} {dur:>6.2f}s ({pct:>5.1f}%) | {bar}")

    if quality_file.exists():
        with open(quality_file, "r", encoding="utf-8") as f:
            qa = json.load(f)
        geo = qa.get("geometry_gates", {})
        mesh = qa.get("mesh_gates", {})
        print("\n[Reconstruction Throughput]")
        surfels = geo.get("total_surface_elements", 0)
        faces = mesh.get("face_count", 0)
        if total_time > 0:
            print(f"  Surfel Integration Rate:  {surfels / total_time:.1f} elements/sec")
            print(f"  Mesh Triangle Rate:       {faces / total_time:.1f} faces/sec")

    print("=" * 65)
    return 0


if __name__ == "__main__":
    sys.exit(main())
