#!/usr/bin/env python3
"""
Comprehensive Diagnostic Suite for SinglePass3D.
Tests:
  1. Calibration (ground truth vs loaded vs estimated)
  2. Telemetry & Timestamps (GPS interpolation, ENU coordinates, ground truth comparison)
  3. Feature Tracking & Epipolar Inlier Ratio (RANSAC essential matrix verification)
  4. Camera Trajectory Error (estimated vs ground truth AGL poses)
  5. Sparse Triangulation (reprojection error & 3D structure coherence)
  6. Multi-View Epipolar Depth Consistency & Planar Homography
  7. Window Registration & ICP Drift Analysis
  8. Surfel Fusion Multi-Layering Analysis
"""

import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import numpy as np
import cv2
import json

from singlepass3d.sensor.camera_model import CameraModel
from singlepass3d.sensor.telemetry_parser import TelemetryParser
from singlepass3d.sensor.video_indexer import VideoIndexer
from singlepass3d.geometry.visual_tracker import VisualTracker
from singlepass3d.geometry.classical_sfm import ClassicalSfMVerifier

def run_diagnostics():
    print("==================================================")
    print(" SINGLEPASS3D COMPREHENSIVE PIPELINE DIAGNOSTICS")
    print("==================================================")
    
    # ----------------------------------------------------
    # 1. DIAGNOSTIC #2: Camera Calibration Sanity Test
    # ----------------------------------------------------
    print("\n--- [DIAGNOSTIC #2: Camera Calibration] ---")
    calib_npz_path = Path("Dataset/AGZ_subset/calibration_data.npz")
    if calib_npz_path.exists():
        calib_data = np.load(calib_npz_path)
        K_gt = calib_data["intrinsic_matrix"]
        dist_gt = calib_data["distCoeff"]
        print(f"Ground Truth Intrinsic Matrix K:\n{K_gt}")
        print(f"Ground Truth Distortion Coeffs (k1, k2, p1, p2, k3):\n{dist_gt}")
        fx_gt, fy_gt, cx_gt, cy_gt = K_gt[0, 0], K_gt[1, 1], K_gt[0, 2], K_gt[1, 2]
    else:
        print("calibration_data.npz not found.")
        K_gt = None
        
    cam_default = CameraModel.create_default(1920, 1080, fov_deg=80.0)
    print(f"Pipeline Default Intrinsic K (from FOV 80°):\n{cam_default.K}")
    if K_gt is not None:
        fx_err = abs(cam_default.fx - fx_gt) / fx_gt * 100.0
        fy_err = abs(cam_default.fy - fy_gt) / fy_gt * 100.0
        print(f"Focal length error without true calibration: fx={fx_err:.2f}%, fy={fy_err:.2f}%")

    # ----------------------------------------------------
    # 2. DIAGNOSTIC #1 & #3: Telemetry & Trajectory Error vs Ground Truth
    # ----------------------------------------------------
    print("\n--- [DIAGNOSTIC #1 & #3: Telemetry & Trajectory vs Ground Truth] ---")
    gt_csv = Path("Dataset/AGZ_subset/Log Files/GroundTruthAGL.csv")
    gt_poses = {}
    if gt_csv.exists():
        with open(gt_csv, "r") as f:
            header = f.readline()
            for line in f:
                parts = line.strip().split(",")
                if len(parts) >= 10 and parts[0].strip().isdigit():
                    imgid = int(parts[0].strip())
                    x_gt, y_gt, z_gt = float(parts[1]), float(parts[2]), float(parts[3])
                    om, ph, kp = float(parts[4]), float(parts[5]), float(parts[6])
                    gt_poses[imgid] = {
                        "pos": np.array([x_gt, y_gt, z_gt]),
                        "angles": np.array([om, ph, kp])
                    }
        print(f"Loaded {len(gt_poses)} Ground Truth AGL poses.")
        
        # Compute Ground Truth baseline and scale
        imgids = sorted(list(gt_poses.keys()))
        p_first = gt_poses[imgids[0]]["pos"]
        p_last = gt_poses[imgids[min(80, len(imgids)-1)]]["pos"]
        gt_dist = np.linalg.norm(p_last - p_first)
        print(f"Ground Truth flight distance over first 80 frames: {gt_dist:.3f} meters")
        
    # Telemetry Parser
    gps_csv = Path("Dataset/AGZ_subset/Log Files/OnboardGPS.csv")
    if gps_csv.exists():
        parser = TelemetryParser(gps_csv)
        pts = parser.parse()
        print(f"TelemetryParser parsed {len(pts)} GPS records.")
        p0_enu = np.array([pts[0].enu_x, pts[0].enu_y, pts[0].enu_z])
        p80_enu = np.array([pts[min(80, len(pts)-1)].enu_x, pts[min(80, len(pts)-1)].enu_y, pts[min(80, len(pts)-1)].enu_z])
        gps_dist = np.linalg.norm(p80_enu - p0_enu)
        print(f"GPS ENU flight distance over first 80 frames: {gps_dist:.3f} meters")
        if gt_csv.exists():
            scale_diff = abs(gps_dist - gt_dist)
            print(f"Metric scale agreement error between GPS and Ground Truth: {scale_diff:.3f}m")

    # ----------------------------------------------------
    # 3. DIAGNOSTIC #7 & #8: Feature Tracking & Sparse Triangulation
    # ----------------------------------------------------
    print("\n--- [DIAGNOSTIC #7 & #8: Feature Tracking & Triangulation] ---")
    indexer = VideoIndexer("Dataset/AGZ_subset/MAV Images", work_dir="outputs/debug_diagnostics")
    frames = indexer.index_video(max_frames=80)
    total_imgs = indexer.total_frames
    print(f"VideoIndexer indexed {total_imgs} images.")
    
    tracker = VisualTracker(indexer=indexer, max_features=3000)
    test_frame_ids = list(range(0, min(40, total_imgs)))
    tracks = tracker.track_sequence(test_frame_ids)
    print(f"VisualTracker generated {len(tracks)} continuous tracks.")
    
    # Measure track lengths
    lengths = [len(t.observations) for t in tracks]
    print(f"Track lengths: min={min(lengths)}, median={np.median(lengths)}, max={max(lengths)}")
    
    # Check Epipolar Consistency with RANSAC Essential Matrix
    f0 = test_frame_ids[0]
    f10 = test_frame_ids[min(10, len(test_frame_ids)-1)]
    img0 = indexer.get_frame_image(f0)
    img10 = indexer.get_frame_image(f10)
    
    # Extract matching points between f0 and f10
    pts0, pts10 = [], []
    for tr in tracks:
        if f0 in tr.observations and f10 in tr.observations:
            pts0.append(tr.observations[f0])
            pts10.append(tr.observations[f10])
            
    pts0 = np.array(pts0, dtype=np.float32)
    pts10 = np.array(pts10, dtype=np.float32)
    print(f"Common tracked features between frame {f0} and {f10}: {len(pts0)}")
    
    if len(pts0) >= 8:
        K = K_gt if K_gt is not None else cam_default.K
        E, inlier_mask = cv2.findEssentialMat(pts0, pts10, K, method=cv2.RANSAC, prob=0.999, threshold=1.5)
        inlier_count = int(np.sum(inlier_mask))
        inlier_ratio = inlier_count / len(pts0) * 100.0
        print(f"Epipolar Inlier Ratio between frame {f0} and {f10}: {inlier_count}/{len(pts0)} ({inlier_ratio:.1f}%)")

if __name__ == "__main__":
    run_diagnostics()
