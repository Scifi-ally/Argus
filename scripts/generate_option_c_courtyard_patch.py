"""
Option C: Targeted Courtyard Patch Completion Model
Surgically repairs and seals the torn edges and hollow gaps around the courtyard
sign ("ARK") and background column. Detects open boundary loops, closes them along
local fitted architectural planes, and projects reference colors from Frame 62.
"""

from pathlib import Path
import sys
import json
import shutil
import time
import numpy as np
import trimesh
from scipy.spatial import Delaunay

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from singlepass3d.core.types import Trajectory, Pose3D, CameraModelData
from singlepass3d.sensor.camera_model import CameraModel
from singlepass3d.sensor.video_indexer import VideoIndexer

OUTPUTS_DIR = Path("outputs")
SRC_DIR = OUTPUTS_DIR / "agz_v12"
DST_DIR = OUTPUTS_DIR / "agz_optC"
DST_DIR.mkdir(parents=True, exist_ok=True)

def fill_planar_hole(loop_verts, normal, origin):
    """Triangulates a boundary loop projected onto its local best-fit plane."""
    if len(loop_verts) < 3:
        return np.empty((0, 3), dtype=np.float64), np.empty((0, 3), dtype=np.int32)
    
    # Construct orthonormal basis on the plane
    normal = normal / np.maximum(1e-6, np.linalg.norm(normal))
    up = np.array([0, 0, 1], dtype=np.float64) if abs(normal[2]) < 0.9 else np.array([0, 1, 0], dtype=np.float64)
    u_axis = np.cross(up, normal)
    u_axis /= np.linalg.norm(u_axis)
    v_axis = np.cross(normal, u_axis)

    # 2D coordinates
    rel = loop_verts - origin
    u = rel @ u_axis
    v = rel @ v_axis
    pts_2d = np.column_stack([u, v])

    # Delaunay triangulation in 2D
    try:
        tri = Delaunay(pts_2d)
        faces = tri.simplices
        return loop_verts, faces
    except Exception:
        return np.empty((0, 3), dtype=np.float64), np.empty((0, 3), dtype=np.int32)

def main():
    start_time = time.time()
    print("=" * 70)
    print("SinglePass3D Option C: Targeted Courtyard Patch Completion")
    print("=" * 70)

    # 1. Load baseline v12 model
    mesh_path = SRC_DIR / "model.ply"
    print(f"\n[1/4] Loading v12 mesh from {mesh_path}...")
    mesh = trimesh.load(str(mesh_path), process=False)
    V = np.asarray(mesh.vertices, dtype=np.float64)
    F = np.asarray(mesh.faces, dtype=np.int32)
    C = np.asarray(mesh.visual.vertex_colors)[:, :3].copy()
    print(f"  Loaded mesh: {len(V):,} vertices, {len(F):,} faces.")

    # 2. Load Reference Frame & Calibration
    print("\n[2/4] Loading reference Frame 62 for photographic color projection...")
    indexer = VideoIndexer("Dataset/AGZ_subset/MAV Images", str(SRC_DIR))
    indexer.index_video(max_frames=350)
    ref_img = indexer.get_frame_image(62, full_resolution=True)
    H_ref, W_ref = ref_img.shape[:2]

    with open(SRC_DIR / "trajectory.json") as f:
        t_data = json.load(f)
    p62 = t_data["poses"]["62"]
    pose62 = Pose3D(
        frame_id=62, timestamp=float(p62.get("timestamp", 0.0)),
        R_wc=np.array(p62["R_wc"], dtype=np.float64),
        t_wc=np.array(p62["t_wc"], dtype=np.float64)
    )

    with open(SRC_DIR / "cameras.json") as f:
        c_data = json.load(f)
    cd = c_data["camera_model"]
    cam_data = CameraModelData(
        fx=cd["fx"], fy=cd["fy"], cx=cd["cx"], cy=cd["cy"],
        width=cd["width"], height=cd["height"],
        distortion=np.array(cd.get("distortion", np.zeros(5))),
        model_type=cd.get("model_type", "brown_conrady")
    )
    camera = CameraModel(cam_data)
    cam_full = camera.scale_to_resolution(W_ref, H_ref)

    # 3. Detect Boundary Edges in the Courtyard Region
    print("\n[3/4] Detecting open boundary loops in courtyard sign & column area...")
    # Mask vertices in courtyard
    c_mask = (V[:, 0] > -11.0) & (V[:, 0] < 1.0) & (V[:, 1] > -5.0) & (V[:, 1] < 10.0) & (V[:, 2] > 0.0) & (V[:, 2] < 14.0)
    
    # Find boundary edges (edges shared by only 1 face)
    edges = mesh.edges_sorted
    unique_edges, counts = np.unique(edges, axis=0, return_counts=True)
    boundary_edges = unique_edges[counts == 1]
    
    # Filter boundary edges where at least one vertex is in courtyard
    c_b_edges = [e for e in boundary_edges if c_mask[e[0]] or c_mask[e[1]]]
    print(f"  Found {len(c_b_edges):,} open boundary edges in courtyard region.")

    # Group connected boundary edges into loops
    adj = {}
    for u, v in c_b_edges:
        adj.setdefault(u, []).append(v)
        adj.setdefault(v, []).append(u)

    visited = set()
    loops = []
    for start in adj:
        if start in visited:
            continue
        loop = [start]
        visited.add(start)
        curr = start
        while True:
            nxts = [n for n in adj[curr] if n not in visited]
            if not nxts:
                break
            curr = nxts[0]
            loop.append(curr)
            visited.add(curr)
        # Only consider meaningful boundary loops (4 to 60 vertices, perimeter < 4.0m)
        if 4 <= len(loop) <= 60:
            loop_pts = V[loop]
            perimeter = float(np.sum(np.linalg.norm(np.diff(loop_pts, axis=0), axis=1)))
            if perimeter < 4.0:
                loops.append(loop)

    print(f"  Extracted {len(loops)} candidate hole loops for surgical closure.")

    # Fill each hole loop along fitted plane
    new_vertices = []
    new_faces = []
    new_colors = []
    base_v_offset = len(V)

    for loop in loops:
        pts = V[loop]
        origin = pts.mean(axis=0)
        # SVD plane fit
        uu, dd, vv = np.linalg.svd(pts - origin)
        normal = vv[2]

        l_verts, l_faces = fill_planar_hole(pts, normal, origin)
        if len(l_faces) == 0:
            continue

        # Project new vertices to Frame 62 to sample true image color
        pt_c = (l_verts - pose62.t_wc) @ pose62.R_cw.T
        z = pt_c[:, 2]
        u_p = (cam_full.fx * (pt_c[:, 0] / np.maximum(z, 1e-4)) + cam_full.cx).astype(np.int32)
        v_p = (cam_full.fy * (pt_c[:, 1] / np.maximum(z, 1e-4)) + cam_full.cy).astype(np.int32)
        
        valid_px = (z > 0.5) & (u_p >= 0) & (u_p < W_ref) & (v_p >= 0) & (v_p < H_ref)
        l_colors = np.zeros((len(l_verts), 3), dtype=np.uint8)
        for i in range(len(l_verts)):
            if valid_px[i]:
                l_colors[i] = ref_img[v_p[i], u_p[i]]
            else:
                l_colors[i] = C[loop].mean(axis=0).astype(np.uint8)

        cur_offset = base_v_offset + len(new_vertices)
        new_vertices.extend(l_verts)
        new_colors.extend(l_colors)
        new_faces.extend(l_faces + cur_offset)

    print(f"  Synthesized {len(new_vertices):,} patch vertices and {len(new_faces):,} gap-closure faces.")

    # 4. Combine into final repaired mesh
    if new_vertices:
        all_V = np.vstack([V, np.array(new_vertices)])
        all_F = np.vstack([F, np.array(new_faces)])
        all_C = np.vstack([C, np.array(new_colors)])
    else:
        all_V, all_F, all_C = V, F, C

    repaired_mesh = trimesh.Trimesh(
        vertices=all_V,
        faces=all_F,
        vertex_colors=np.hstack([all_C, np.full((len(all_C), 1), 255, dtype=np.uint8)]),
        process=False
    )
    repaired_mesh.update_faces(repaired_mesh.nondegenerate_faces())
    repaired_mesh.remove_unreferenced_vertices()

    # 5. Export Option C Deliverables
    print("\n[5/5] Exporting Option C Deliverables...")
    preview_path = OUTPUTS_DIR / "preview_optC_courtyard_patch.glb"
    repaired_mesh.export(str(preview_path), file_type="glb")
    print(f"  Wrote {preview_path} ({preview_path.stat().st_size / (1024*1024):.1f} MB)")

    v12_glb = DST_DIR / "model.glb"
    repaired_mesh.export(str(v12_glb), file_type="glb")
    print(f"  Wrote {v12_glb} ({v12_glb.stat().st_size / (1024*1024):.1f} MB)")

    v12_ply = DST_DIR / "model.ply"
    repaired_mesh.export(str(v12_ply), file_type="ply")

    for fname in ["cameras.json", "trajectory.json", "quality.json", "report.json", "diagnostics.json"]:
        src_file = SRC_DIR / fname
        if src_file.exists():
            shutil.copy2(src_file, DST_DIR / fname)

    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print(f"Option C Generation Complete in {elapsed:.1f}s")
    print(f"  - Deliverable: outputs/preview_optC_courtyard_patch.glb")
    print(f"  - Package:     outputs/agz_optC/")
    print(f"  - Faces:       {len(repaired_mesh.faces):,}")
    print("=" * 70)

if __name__ == "__main__":
    main()
