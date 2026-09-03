"""
Diagnostic Mode Exporter for SinglePass3D.
Exports all 12 intermediate pipeline representations into dedicated debug folders:
    01_frames/
    02_selected_frames/
    03_tracks/
    04_camera_trajectory/
    05_gps_trajectory/
    06_sparse_cloud/
    07_local_pointmaps/
    08_registered_windows/
    09_fused_world/
    10_filtered_world/
    11_validated_world/
    12_mesh/
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Optional
import cv2
import json
import numpy as np

from singlepass3d.core.logging import get_logger
from singlepass3d.core.types import PointMapResult, Pose3D, Track3D, Trajectory, WorldElement
from singlepass3d.metric_world.persistent_world import PersistentWorld
from singlepass3d.sensor.video_indexer import VideoIndexer
from singlepass3d.sensor.telemetry_parser import TelemetryParser


def write_ply_pointcloud(filepath: Path | str, points: np.ndarray, colors: Optional[np.ndarray] = None, normals: Optional[np.ndarray] = None):
    """Write standard ASCII/Binary PLY point cloud."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    pts = np.atleast_2d(points).reshape(-1, 3)
    N = len(pts)
    if N == 0:
        return
        
    has_colors = colors is not None and len(colors) == N
    has_normals = normals is not None and len(normals) == N
    
    cols = np.clip(colors, 0, 255).astype(np.uint8) if has_colors else np.full((N, 3), 200, dtype=np.uint8)
    
    header = [
        "ply",
        "format ascii 1.0",
        f"element vertex {N}",
        "property float x",
        "property float y",
        "property float z",
    ]
    if has_normals:
        header.extend([
            "property float nx",
            "property float ny",
            "property float nz",
        ])
    header.extend([
        "property uchar red",
        "property uchar green",
        "property uchar blue",
        "end_header\n"
    ])
    
    with open(filepath, "w") as f:
        f.write("\n".join(header))
        for i in range(N):
            p = pts[i]
            c = cols[i]
            if has_normals:
                n = normals[i]
                f.write(f"{p[0]:.4f} {p[1]:.4f} {p[2]:.4f} {n[0]:.4f} {n[1]:.4f} {n[2]:.4f} {c[0]} {c[1]} {c[2]}\n")
            else:
                f.write(f"{p[0]:.4f} {p[1]:.4f} {p[2]:.4f} {c[0]} {c[1]} {c[2]}\n")


class DiagnosticsExporter:
    """
    Manages structured diagnostic artifact export across the 12 intermediate pipeline stages.
    """
    def __init__(self, debug_root: Path | str):
        self.debug_root = Path(debug_root)
        self.debug_root.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger()

    def export_01_frames(self, indexer: VideoIndexer, sample_rate: int = 5):
        """01_frames/: Export sample decoded frames."""
        out_dir = self.debug_root / "01_frames"
        out_dir.mkdir(parents=True, exist_ok=True)
        
        meta_list = []
        for fid in indexer.frame_index:
            if fid % sample_rate == 0:
                meta = indexer.frame_index[fid]
                img = indexer.get_frame_image(fid, full_resolution=False)
                cv2.imwrite(str(out_dir / f"frame_{fid:05d}.jpg"), cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
                meta_list.append(meta.to_dict())
                
        with open(out_dir / "frames_metadata.json", "w") as f:
            json.dump(meta_list, f, indent=2)

    def export_02_selected_frames(self, indexer: VideoIndexer, keyframe_ids: List[int]):
        """02_selected_frames/: Export selected keyframes."""
        out_dir = self.debug_root / "02_selected_frames"
        out_dir.mkdir(parents=True, exist_ok=True)
        
        for k_idx, fid in enumerate(keyframe_ids):
            img = indexer.get_frame_image(fid, full_resolution=False)
            cv2.imwrite(str(out_dir / f"keyframe_{k_idx:03d}_frame_{fid:05d}.jpg"), cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
            
        with open(out_dir / "keyframes_index.json", "w") as f:
            json.dump({"keyframe_ids": keyframe_ids, "count": len(keyframe_ids)}, f, indent=2)

    def export_03_tracks(self, tracks: List[Track3D]):
        """03_tracks/: Export visual feature tracks summary."""
        out_dir = self.debug_root / "03_tracks"
        out_dir.mkdir(parents=True, exist_ok=True)
        
        summary = {
            "total_tracks": len(tracks),
            "track_lengths": [len(t.observations) for t in tracks[:200]],
            "inlier_tracks": sum(1 for t in tracks if t.is_inlier),
        }
        with open(out_dir / "tracks_summary.json", "w") as f:
            json.dump(summary, f, indent=2)

    def export_04_camera_trajectory(self, trajectory: Trajectory):
        """04_camera_trajectory/: Export estimated camera trajectory and PLY path."""
        out_dir = self.debug_root / "04_camera_trajectory"
        out_dir.mkdir(parents=True, exist_ok=True)
        
        poses_data = [p.to_dict() for p in trajectory.poses.values()]
        with open(out_dir / "camera_trajectory.json", "w") as f:
            json.dump(poses_data, f, indent=2)
            
        positions = np.array([p.t_wc for p in trajectory.poses.values()])
        if len(positions) > 0:
            colors = np.full((len(positions), 3), [0, 220, 255], dtype=np.uint8) # Cyan path
            write_ply_pointcloud(out_dir / "camera_path.ply", positions, colors)

    def export_05_gps_trajectory(self, telemetry: Optional[TelemetryParser]):
        """05_gps_trajectory/: Export GPS trajectory in local ENU frame."""
        out_dir = self.debug_root / "05_gps_trajectory"
        out_dir.mkdir(parents=True, exist_ok=True)
        
        if telemetry and telemetry.points:
            pts_enu = np.array([[p.enu_x, p.enu_y, p.enu_z] for p in telemetry.points])
            colors = np.full((len(pts_enu), 3), [255, 180, 0], dtype=np.uint8) # Orange path
            write_ply_pointcloud(out_dir / "gps_path.ply", pts_enu, colors)
            
            summary = {
                "datum_origin": telemetry.datum_origin,
                "total_records": len(telemetry.points),
                "flight_distance_m": float(np.sum(np.linalg.norm(np.diff(pts_enu, axis=0), axis=1))) if len(pts_enu) > 1 else 0.0
            }
            with open(out_dir / "gps_summary.json", "w") as f:
                json.dump(summary, f, indent=2)

    def export_06_sparse_cloud(self, landmarks: Dict[int, np.ndarray]):
        """06_sparse_cloud/: Export independent triangulated SfM landmark cloud."""
        out_dir = self.debug_root / "06_sparse_cloud"
        out_dir.mkdir(parents=True, exist_ok=True)
        
        if landmarks:
            pts = np.array(list(landmarks.values()))
            colors = np.full((len(pts), 3), [255, 50, 50], dtype=np.uint8) # Red sparse landmarks
            write_ply_pointcloud(out_dir / "sparse_landmarks.ply", pts, colors)

    def export_07_local_pointmaps(self, pointmaps: List[PointMapResult], window_id: int):
        """07_local_pointmaps/: Export per-window dense pointmaps."""
        out_dir = self.debug_root / "07_local_pointmaps"
        out_dir.mkdir(parents=True, exist_ok=True)
        
        all_pts, all_cols = [], []
        for pmap in pointmaps:
            valid = pmap.mask
            if np.any(valid):
                pts = pmap.points[valid].reshape(-1, 3)
                cols = pmap.colors[valid].reshape(-1, 3)
                all_pts.append(pts)
                all_cols.append(cols)
                
        if all_pts:
            pts_cat = np.vstack(all_pts)
            cols_cat = np.vstack(all_cols)
            # Subsample for export if large
            if len(pts_cat) > 30000:
                idx = np.random.choice(len(pts_cat), 30000, replace=False)
                pts_cat = pts_cat[idx]
                cols_cat = cols_cat[idx]
            write_ply_pointcloud(out_dir / f"window_{window_id:02d}_local.ply", pts_cat, cols_cat)

    def export_08_registered_windows(self, pointmaps: List[PointMapResult], window_id: int, T_reg: np.ndarray):
        """08_registered_windows/: Export registered window with window_id color coding."""
        out_dir = self.debug_root / "08_registered_windows"
        out_dir.mkdir(parents=True, exist_ok=True)
        
        # Color code by window ID
        palette = [
            [255, 0, 0], [0, 255, 0], [0, 0, 255], [255, 255, 0],
            [255, 0, 255], [0, 255, 255], [255, 128, 0], [128, 0, 255]
        ]
        win_color = palette[window_id % len(palette)]
        
        all_pts = []
        for pmap in pointmaps:
            valid = pmap.mask
            if np.any(valid):
                pts = pmap.points[valid].reshape(-1, 3)
                if not np.allclose(T_reg, np.eye(4)):
                    pts = (T_reg[:3, :3] @ pts.T).T + T_reg[:3, 3]
                all_pts.append(pts)
                
        if all_pts:
            pts_cat = np.vstack(all_pts)
            if len(pts_cat) > 30000:
                idx = np.random.choice(len(pts_cat), 30000, replace=False)
                pts_cat = pts_cat[idx]
            cols = np.full((len(pts_cat), 3), win_color, dtype=np.uint8)
            write_ply_pointcloud(out_dir / f"window_{window_id:02d}_registered.ply", pts_cat, cols)

    def export_09_fused_world(self, world: PersistentWorld):
        """09_fused_world/: Export persistent world surfel cloud."""
        out_dir = self.debug_root / "09_fused_world"
        out_dir.mkdir(parents=True, exist_ok=True)
        
        pts = world.store.get_all_positions()
        normals = world.store.get_all_normals()
        colors = world.store.get_all_colors()
        write_ply_pointcloud(out_dir / "fused_world.ply", pts, colors, normals)

    def export_10_filtered_world(self, world: PersistentWorld):
        """10_filtered_world/: Export filtered world elements."""
        out_dir = self.debug_root / "10_filtered_world"
        out_dir.mkdir(parents=True, exist_ok=True)
        
        pts = world.store.get_all_positions()
        normals = world.store.get_all_normals()
        colors = world.store.get_all_colors()
        write_ply_pointcloud(out_dir / "filtered_world.ply", pts, colors, normals)

    def export_11_validated_world(self, world: PersistentWorld):
        """11_validated_world/: Export multi-view validated world elements."""
        out_dir = self.debug_root / "11_validated_world"
        out_dir.mkdir(parents=True, exist_ok=True)
        
        pts = world.store.get_all_positions()
        normals = world.store.get_all_normals()
        colors = world.store.get_all_colors()
        write_ply_pointcloud(out_dir / "validated_world.ply", pts, colors, normals)

    def export_12_mesh(self, mesh_ply_path: Path):
        """12_mesh/: Copy final mesh into diagnostic directory."""
        out_dir = self.debug_root / "12_mesh"
        out_dir.mkdir(parents=True, exist_ok=True)
        if mesh_ply_path.exists():
            import shutil
            shutil.copy(mesh_ply_path, out_dir / "model.ply")
