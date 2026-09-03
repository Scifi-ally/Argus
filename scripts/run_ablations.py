#!/usr/bin/env python3
"""
SinglePass3D Ablation and Comparative Root-Cause Evaluation Suite.
Runs controlled comparative tests on the Zurich Urban MAV dataset:
  - Test A: Baseline existing configuration (uncalibrated FOV 80, empirical flow depth)
  - Test B: Corrected calibration & trajectory + baseline depth
  - Test C: Baseline trajectory + corrected epipolar depth
  - Test D: Corrected trajectory + corrected epipolar depth
  - Test E: Full corrected pipeline (Calibrated Intrinsics + Trajectory BA + Epipolar Triangulation + Metric Fusion + 12 Diagnostic Stages)
"""

import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import json
import time
import numpy as np
import trimesh

from singlepass3d.config.pipeline_config import SinglePass3DConfig
from singlepass3d.pipeline.runner import SinglePass3DPipeline


def evaluate_mesh_metrics(mesh_path: Path) -> dict:
    """Calculates geometric metrics on reconstructed mesh."""
    if not mesh_path.exists():
        return {"exists": False}
    try:
        mesh = trimesh.load(str(mesh_path), process=False)
        num_vertices = len(mesh.vertices)
        num_faces = len(mesh.faces)
        bounds = mesh.bounds
        extents = mesh.extents
        return {
            "exists": True,
            "vertices": num_vertices,
            "faces": num_faces,
            "extents_xyz_m": [round(float(x), 3) for x in extents],
            "bounds_z_range_m": [round(float(bounds[0, 2]), 3), round(float(bounds[1, 2]), 3)]
        }
    except Exception as e:
        return {"exists": True, "error": str(e)}


def run_single_ablation(test_name: str, config: SinglePass3DConfig, max_frames: int = 40):
    print(f"\n=======================================================")
    print(f" RUNNING ABLATION: {test_name}")
    print(f"=======================================================")
    t0 = time.time()
    pipeline = SinglePass3DPipeline(config)
    result = pipeline.run(max_frames=max_frames)
    t1 = time.time()
    
    out_dir = Path(config.output_dir)
    mesh_metrics = evaluate_mesh_metrics(out_dir / "model.ply")
    
    qa = result.get("qa_report", {})
    traj_gates = qa.get("trajectory_gates", {})
    geo_gates = qa.get("geometry_gates", {})
    
    report = {
        "test_name": test_name,
        "runtime_s": round(t1 - t0, 2),
        "qa_status": qa.get("quality_status", "UNKNOWN"),
        "gps_residual_m": round(float(traj_gates.get("mean_gps_residual_meters", 0.0)), 4),
        "mean_reproj_error_px": round(float(geo_gates.get("mean_reprojection_error_pixels", 0.0)), 3),
        "multi_view_support_ratio": round(float(geo_gates.get("multi_view_support_ratio", 0.0)), 4),
        "total_surfels": int(geo_gates.get("total_surface_elements", 0)),
        "mesh_metrics": mesh_metrics
    }
    print(f"\n[{test_name} Summary]:")
    print(json.dumps(report, indent=2))
    return report


def main():
    print("==========================================================")
    print(" SINGLEPASS3D CONTROLLED ABLATION & ROOT-CAUSE TEST SUITE")
    print("==========================================================")
    
    results = {}
    
    # Test A: Baseline Existing Pipeline (Uncalibrated, No landmark BA, unconstrained ICP)
    cfg_a = SinglePass3DConfig(
        job_name="ablation_test_a",
        video_path="Dataset/AGZ_subset/MAV Images",
        telemetry_path="Dataset/AGZ_subset/Log Files/OnboardGPS.csv",
        calibration_path=None, # uncalibrated default
        output_dir="outputs/ablation_test_a",
        quality="fast",
        learned_adapter="mvs_fallback",
        enable_cache=False,
        debug_reconstruction=False
    )
    results["Test_A_Baseline"] = run_single_ablation("Test_A_Baseline", cfg_a, max_frames=30)

    # Test B: Calibrated Trajectory Fusion + Baseline Depth
    cfg_b = SinglePass3DConfig(
        job_name="ablation_test_b",
        video_path="Dataset/AGZ_subset/MAV Images",
        telemetry_path="Dataset/AGZ_subset/Log Files/OnboardGPS.csv",
        calibration_path="Dataset/AGZ_subset/calibration_data.npz",
        output_dir="outputs/ablation_test_b",
        quality="fast",
        learned_adapter="mvs_fallback",
        enable_cache=False,
        debug_reconstruction=False
    )
    results["Test_B_Calibrated_Trajectory"] = run_single_ablation("Test_B_Calibrated_Trajectory", cfg_b, max_frames=30)

    # Test D: Calibrated Trajectory + Epipolar Triangulation
    cfg_d = SinglePass3DConfig(
        job_name="ablation_test_d",
        video_path="Dataset/AGZ_subset/MAV Images",
        telemetry_path="Dataset/AGZ_subset/Log Files/OnboardGPS.csv",
        calibration_path="Dataset/AGZ_subset/calibration_data.npz",
        output_dir="outputs/ablation_test_d",
        quality="balanced",
        learned_adapter="mvs_fallback",
        enable_cache=False,
        debug_reconstruction=False
    )
    results["Test_D_Traj_And_Filtering"] = run_single_ablation("Test_D_Traj_And_Filtering", cfg_d, max_frames=30)

    # Test E: Full Corrected Pipeline with 12-Stage Diagnostic Export
    cfg_e = SinglePass3DConfig(
        job_name="ablation_test_e",
        video_path="Dataset/AGZ_subset/MAV Images",
        telemetry_path="Dataset/AGZ_subset/Log Files/OnboardGPS.csv",
        calibration_path="Dataset/AGZ_subset/calibration_data.npz",
        output_dir="outputs/ablation_test_e",
        quality="balanced",
        learned_adapter="mvs_fallback",
        enable_cache=False,
        debug_reconstruction=True
    )
    results["Test_E_Full_Corrected"] = run_single_ablation("Test_E_Full_Corrected", cfg_e, max_frames=40)

    # Save summary table
    summary_path = Path("outputs/ablation_summary.json")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nAblation summary saved to: {summary_path}")


if __name__ == "__main__":
    main()
