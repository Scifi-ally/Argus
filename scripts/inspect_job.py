#!/usr/bin/env python3
"""
SinglePass3D — Job Inspector CLI
Usage:
    python scripts/inspect_job.py outputs/job_001
"""

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path


def format_bytes(size_bytes: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect a completed SinglePass3D reconstruction job.")
    parser.add_argument("job_dir", type=str, help="Path to the output job directory")
    args = parser.parse_args()

    job_dir = Path(args.job_dir)
    if not job_dir.exists():
        print(f"Error: Job directory not found: {job_dir}", file=sys.stderr)
        return 1

    report_file = job_dir / "report.json"
    quality_file = job_dir / "quality.json"
    overlay_file = job_dir / "overlay.json"
    diag_file = job_dir / "diagnostics.json"

    print("=" * 65)
    print(f" SinglePass3D Job Inspector: {job_dir.resolve().name}")
    print("=" * 65)

    # 1. Output Files Status
    expected_files = [
        "model.glb", "model.ply", "model.obj", "texture.png",
        "trajectory.json", "cameras.json", "world.json", "uncertainty.json",
        "overlay.json", "quality.json", "report.json", "diagnostics.json"
    ]
    print("\n[Output Artifacts]")
    present_count = 0
    for fname in expected_files:
        fpath = job_dir / fname
        if fpath.exists():
            size_str = format_bytes(fpath.stat().st_size)
            print(f"  [OK] {fname:<18} ({size_str})")
            present_count += 1
        else:
            print(f"  [MISSING] {fname:<18}")

    print(f"\nArtifact completeness: {present_count}/{len(expected_files)} files present.")

    # 2. Quality & QA Status
    if quality_file.exists():
        with open(quality_file, "r", encoding="utf-8") as f:
            qa = json.load(f)
        status = qa.get("quality_status", "UNKNOWN")
        passed = qa.get("overall_qa_passed", False)
        status_symbol = "[PASSED]" if passed else "[FLAGGED]"
        print(f"\n[Quality Assurance Gates: {status_symbol}]")
        
        # Trajectory
        traj = qa.get("trajectory_gates", {})
        print(f"  Trajectory Drift:        {traj.get('mean_gps_residual_meters', 0.0):.2f}m residual (Allowed: <={traj.get('max_allowed_drift_meters', 2.5)}m) -> {'PASS' if traj.get('passed') else 'FAIL'}")
        print(f"  Optimized Poses:         {traj.get('total_optimized_poses', 0)}")
        
        # Geometry
        geo = qa.get("geometry_gates", {})
        print(f"  Mean Reprojection Error: {geo.get('mean_reprojection_error_pixels', 0.0):.2f}px (Allowed: <={geo.get('max_allowed_reprojection_error', 3.5)}px) -> {'PASS' if geo.get('passed') else 'FAIL'}")
        print(f"  Multi-View Support:      {geo.get('multi_view_support_ratio', 0.0)*100:.1f}%")
        print(f"  Surface Elements:        {geo.get('total_surface_elements', 0)}")
        
        # Completeness
        comp = qa.get("completeness_breakdown", {})
        print("\n[Provenance & Completeness Breakdown]")
        print(f"  Observed:                {comp.get('observed_percent', 0.0):.1f}%")
        print(f"  Multi-View Supported:    {comp.get('multi_view_supported_percent', 0.0):.1f}%")
        print(f"  Structural Inferred:     {comp.get('structural_inferred_percent', 0.0):.1f}%")
        print(f"  Generative Inferred:     {comp.get('generative_inferred_percent', 0.0):.1f}%")
        print(f"  Unknown / Unseen:        {comp.get('unknown_percent', 0.0):.1f}%")
        
        # Mesh
        mesh = qa.get("mesh_gates", {})
        print(f"\n[3D Polygonal Mesh]")
        print(f"  Vertices:                {mesh.get('vertex_count', 0):,}")
        print(f"  Faces:                   {mesh.get('face_count', 0):,}")
        print(f"  Degenerate Triangles:    {mesh.get('degenerate_faces_count', 0)}")

    # 3. Stage Timings
    if diag_file.exists():
        with open(diag_file, "r", encoding="utf-8") as f:
            diag = json.load(f)
        timings = diag.get("stage_durations", {})
        if timings:
            print("\n[Pipeline Execution Timings]")
            for stage, dur in sorted(timings.items()):
                print(f"  {stage:<36} {dur:.2f}s")
            print(f"  {'-'*45}")
            print(f"  Total Pipeline Time:                 {diag.get('total_pipeline_time_seconds', 0.0):.2f}s")

    print("\n" + "=" * 65)
    return 0


if __name__ == "__main__":
    sys.exit(main())
