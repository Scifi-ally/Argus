"""
Multi-Format 3D Geometry and Metadata Exporter for SinglePass3D.
Produces all 11 required output artifacts:
  1. model.glb
  2. model.ply
  3. model.obj (+ model.mtl + texture.png)
  4. trajectory.json
  5. cameras.json
  6. world.json
  7. uncertainty.json
  8. overlay.json (provenance, confidence, semantics, supporting frames)
  9. quality.json
  10. report.json
  11. diagnostics.json
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
import trimesh

from singlepass3d.core.logging import SinglePass3DLogger, get_logger
from singlepass3d.core.types import (
    CameraModelData,
    Pose3D,
    Trajectory,
    WorldElement,
    WorldElementState,
)
from singlepass3d.metric_world.persistent_world import PersistentWorld
from singlepass3d.output.appearance_splat import AppearanceSplatExporter
from singlepass3d.output.texture_synthesizer import TextureSynthesizer
from singlepass3d.sensor.camera_model import CameraModel


class ReconstructionExporter:
    """
    Exports complete reconstruction outputs, 3D models, provenance overlays, and QA reports.
    """
    def __init__(self, output_dir: str | Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger()
        self.splat_exporter = AppearanceSplatExporter()

    def export_all(
        self,
        mesh: trimesh.Trimesh,
        world: PersistentWorld,
        trajectory: Trajectory,
        camera: CameraModel,
        qa_report: Dict[str, Any],
        custom_logger: Optional[SinglePass3DLogger] = None,
        textured_mesh: Optional[trimesh.Trimesh] = None
    ) -> Dict[str, str]:
        """
        Writes all 11 required files to the output directory.
        Returns a dict of file names to absolute paths.
        """
        self.logger.info(f"Exporting all 11 output artifacts to: {self.output_dir.resolve()}")
        exported_files: Dict[str, str] = {}
        
        # 1. model.glb -- from the atlas mesh when one was baked, since a GLB embeds the
        # texture and a vertex palette would throw the atlas away.
        glb_path = self.output_dir / "model.glb"
        try:
            (textured_mesh or mesh).export(str(glb_path), file_type="glb")
            exported_files["model.glb"] = str(glb_path)
        except Exception as e:
            self.logger.warning(f"GLB export issue ({e}), exporting fallback GLB structure.")
            with open(glb_path, "wb") as f:
                f.write(mesh.export(file_type="glb"))
            exported_files["model.glb"] = str(glb_path)
            
        # 2. model.ply (Polygon Mesh PLY with vertex colors & normals)
        ply_path = self.output_dir / "model.ply"
        mesh.export(str(ply_path), file_type="ply")
        exported_files["model.ply"] = str(ply_path)
        
        # Also export Gaussian Splat PLY
        splat_path = self.output_dir / "splats.ply"
        self.splat_exporter.export_gaussian_splats_ply(world, splat_path)
        
        # 3. model.obj + texture.png + model.mtl
        obj_path = self.output_dir / "model.obj"
        tex_path = self.output_dir / "texture.png"
        wrote_atlas = False
        if textured_mesh is not None:
            # trimesh names the image after the material; the report expects texture.png,
            # so the material reference is rewritten rather than the file left dangling.
            try:
                obj_txt, files = textured_mesh.export(
                    file_type="obj", mtl_name="model.mtl", return_texture=True
                )
                mtl = files.pop("model.mtl", None)
                img = next(((k, v) for k, v in files.items()
                            if str(k).lower().endswith((".png", ".jpg", ".jpeg"))), None)
                if img is not None:
                    tex_path.write_bytes(img[1])
                    if mtl is not None:
                        txt = mtl.decode("utf-8") if isinstance(mtl, bytes) else str(mtl)
                        (self.output_dir / "model.mtl").write_text(
                            txt.replace(str(img[0]), "texture.png"), encoding="utf-8"
                        )
                    obj_txt = obj_txt.decode("utf-8") if isinstance(obj_txt, bytes) else obj_txt
                    obj_path.write_text(obj_txt, encoding="utf-8")
                    wrote_atlas = True
                    self.logger.info(
                        f"Exported OBJ with a baked UV atlas ({len(textured_mesh.faces)} faces, "
                        f"texture.png {tex_path.stat().st_size / 1e6:.1f} MB)."
                    )
            except Exception as exc:
                self.logger.warning(f"Atlas OBJ export failed ({exc}); falling back to vertex colour.")
                wrote_atlas = False
        if not wrote_atlas:
            tex_synth = TextureSynthesizer(camera=camera)
            tex_synth.generate_texture_image(
                mesh.visual.vertex_colors[:, :3] if hasattr(mesh.visual, "vertex_colors") and mesh.visual.vertex_colors is not None else np.empty((0, 3)),
                tex_path
            )
            mesh.export(str(obj_path), file_type="obj")
        exported_files["model.obj"] = str(obj_path)
        
        # 4. trajectory.json
        traj_path = self.output_dir / "trajectory.json"
        with open(traj_path, "w", encoding="utf-8") as f:
            json.dump(trajectory.to_dict(), f, indent=2)
        exported_files["trajectory.json"] = str(traj_path)
        
        # 5. cameras.json
        cam_path = self.output_dir / "cameras.json"
        cam_dict = {
            "camera_model": camera.data.to_dict(),
            "frames": {
                str(fid): trajectory.get_pose(fid).to_dict()
                for fid in trajectory.frame_ids
                if trajectory.get_pose(fid) is not None
            }
        }
        with open(cam_path, "w", encoding="utf-8") as f:
            json.dump(cam_dict, f, indent=2)
        exported_files["cameras.json"] = str(cam_path)
        
        # 6. world.json
        world_path = self.output_dir / "world.json"
        active_elements = [
            e.to_dict() for e in world.store.elements.values()
            if e.state != WorldElementState.REJECTED
        ]
        world_dict = {
            "total_elements": len(active_elements),
            "voxel_size_meters": world.voxel_size_m,
            "elements": active_elements
        }
        with open(world_path, "w", encoding="utf-8") as f:
            json.dump(world_dict, f, indent=2)
        exported_files["world.json"] = str(world_path)
        
        # 7. uncertainty.json
        unc_path = self.output_dir / "uncertainty.json"
        uncertainty_records = [
            {
                "element_id": e.element_id,
                "position": e.position.tolist(),
                "covariance_trace": float(np.trace(e.covariance)),
                "covariance_matrix": e.covariance.tolist(),
                "confidence_score": float(e.confidence_score),
                "confidence_level": e.confidence_level.value,
                "reprojection_error_px": float(e.reprojection_error),
            }
            for e in world.store.elements.values()
            if e.state != WorldElementState.REJECTED
        ]
        with open(unc_path, "w", encoding="utf-8") as f:
            json.dump({"elements": uncertainty_records}, f, indent=2)
        exported_files["uncertainty.json"] = str(unc_path)
        
        # 8. overlay.json (vertex/region provenance, confidence, semantic class, supporting frames)
        overlay_path = self.output_dir / "overlay.json"
        overlay_records = [
            {
                "element_id": e.element_id,
                "provenance": e.provenance.value,
                "confidence": e.confidence_level.value,
                "confidence_score": float(e.confidence_score),
                "semantic_class": e.semantic_class.value,
                "supporting_frames": list(e.supporting_frames),
                "observation_count": e.observation_count,
                "visibility": e.visibility.value,
            }
            for e in world.store.elements.values()
            if e.state != WorldElementState.REJECTED
        ]
        with open(overlay_path, "w", encoding="utf-8") as f:
            json.dump({
                "total_surfels": len(overlay_records),
                "provenance_summary": world.store.get_provenance_counts(),
                "confidence_summary": world.store.get_confidence_counts(),
                "elements": overlay_records
            }, f, indent=2)
        exported_files["overlay.json"] = str(overlay_path)
        
        # 9. quality.json
        qual_path = self.output_dir / "quality.json"
        with open(qual_path, "w", encoding="utf-8") as f:
            json.dump(qa_report, f, indent=2)
        exported_files["quality.json"] = str(qual_path)
        
        # 10. report.json
        rep_path = self.output_dir / "report.json"
        full_report = {
            "title": "SinglePass3D Continuous Drone Reconstruction Report",
            "status": qa_report.get("quality_status", "PASSED"),
            "qa_passed": qa_report.get("overall_qa_passed", True),
            "trajectory_metrics": qa_report.get("trajectory_gates", {}),
            "geometry_metrics": qa_report.get("geometry_gates", {}),
            "completeness": qa_report.get("completeness_breakdown", {}),
            "mesh_metrics": qa_report.get("mesh_gates", {}),
            "texture_metrics": qa_report.get("texture_gates", {}),
            "exported_artifacts": list(exported_files.keys())
        }
        with open(rep_path, "w", encoding="utf-8") as f:
            json.dump(full_report, f, indent=2)
        exported_files["report.json"] = str(rep_path)
        
        # 11. diagnostics.json
        diag_path = self.output_dir / "diagnostics.json"
        diag_logger = custom_logger or self.logger
        diag_logger.export_diagnostics(diag_path)
        exported_files["diagnostics.json"] = str(diag_path)
        
        self.logger.info("All 11 output files exported successfully.")
        return exported_files
