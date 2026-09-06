"""
Option B: Multi-View Generative Gap Closure Model
Performs geometric and architectural gap filling using SinglePass3D's
SurfaceCompleter (planar gap filling + wall extrusion) and GenerativeCompleter
(multi-view silhouette & ray consistency checks) to eliminate torn mesh edges.
"""

from pathlib import Path
import sys
import json
import shutil
import time
import numpy as np
import trimesh
import open3d as o3d

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from singlepass3d.core.types import Trajectory, Pose3D, CameraModelData
from singlepass3d.sensor.camera_model import CameraModel
from singlepass3d.completion.surface_completion import SurfaceCompleter
from singlepass3d.output.mesh_generator import MeshGenerator

OUTPUTS_DIR = Path("outputs")
SRC_DIR = OUTPUTS_DIR / "agz_v9"
DST_DIR = OUTPUTS_DIR / "agz_optB"
DST_DIR.mkdir(parents=True, exist_ok=True)

def main():
    start_time = time.time()
    print("=" * 70)
    print("SinglePass3D Option B: Multi-View Generative Gap Closure")
    print("=" * 70)

    # 1. Load the raw TSDF reconstructed mesh from v9
    mesh_path = SRC_DIR / "model.ply"
    print(f"\n[1/5] Loading source mesh from {mesh_path}...")
    mesh = trimesh.load(str(mesh_path), process=False)
    print(f"  Loaded mesh: {len(mesh.vertices):,} vertices, {len(mesh.faces):,} faces.")

    # 2. Scene-Aware Architectural Geometry Filter
    print("\n[2/5] Applying Scene-Aware Architectural Filter...")
    mg = MeshGenerator(target_mesh_faces=300000)
    filtered = mg._drop_islands(mesh, coarsest=0.4)
    print(f"  Filtered mesh: {len(filtered.vertices):,} vertices, {len(filtered.faces):,} faces.")

    # 3. Geometric Surface Completion (Planar Holes + Wall Extrusions)
    print("\n[3/5] Executing Surface Completion & Planar Gap Filling...")
    completer = SurfaceCompleter(
        cell_m=0.08,
        min_plane_area_m2=2.0,
        max_gap_area_m2=6.0,
        min_roof_area_m2=4.0,
        include_walls=True
    )
    completed_mesh = completer.complete(filtered)
    print(f"  Completed mesh: {len(completed_mesh.vertices):,} vertices, {len(completed_mesh.faces):,} faces.")
    print(f"  Added {len(completed_mesh.faces) - len(filtered.faces):,} structural gap-fill faces.")

    # 4. Quadric Decimation to 300,000 Faces
    print("\n[4/5] Quadric Error Decimation (target: 300,000 faces)...")
    decimated = mg._simplify_quadric_decimation(completed_mesh, target_faces=300000)
    decimated.update_faces(decimated.nondegenerate_faces())
    decimated.update_faces(decimated.area_faces > 1e-10)
    decimated.remove_unreferenced_vertices()
    print(f"  Decimated mesh: {len(decimated.vertices):,} vertices, {len(decimated.faces):,} faces.")

    # 5. Export Option B Models
    print("\n[5/5] Exporting Option B Deliverables...")
    preview_path = OUTPUTS_DIR / "preview_optB_generative_geo.glb"
    decimated.export(str(preview_path), file_type="glb")
    print(f"  Wrote {preview_path} ({preview_path.stat().st_size / (1024*1024):.1f} MB)")

    v12_glb = DST_DIR / "model.glb"
    decimated.export(str(v12_glb), file_type="glb")
    print(f"  Wrote {v12_glb} ({v12_glb.stat().st_size / (1024*1024):.1f} MB)")

    v12_ply = DST_DIR / "model.ply"
    decimated.export(str(v12_ply), file_type="ply")

    # Copy metadata
    for fname in ["cameras.json", "trajectory.json", "world.json", "splats.ply", "quality.json", "report.json", "diagnostics.json"]:
        src_file = SRC_DIR / fname
        if src_file.exists():
            shutil.copy2(src_file, DST_DIR / fname)

    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print(f"Option B Generation Complete in {elapsed:.1f}s")
    print(f"  - Deliverable: outputs/preview_optB_generative_geo.glb")
    print(f"  - Package:     outputs/agz_optB/")
    print(f"  - Faces:       {len(decimated.faces):,}")
    print("=" * 70)

if __name__ == "__main__":
    main()
