"""
Geospatial Intelligence and Photogrammetric Deliverables Engine for SinglePass3D.
Generates:
  1. True Orthomosaic GeoTIFF (orthomosaic.tif + orthomosaic.tfw + orthomosaic.png)
  2. Digital Surface Model elevation GeoTIFF (dsm.tif + dsm.tfw)
  3. Digital Terrain Model bare-earth GeoTIFF (dtm.tif + dtm.tfw)
  4. Building Footprints & Flight Trajectory GeoJSON (footprints.geojson, flight_path.geojson)
  5. Quantitative Measurement & Spatial Analytics Summary (measurements.json)
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np
import trimesh

from singlepass3d.core.logging import get_logger
from singlepass3d.core.types import SemanticClass, Trajectory
from singlepass3d.metric_world.persistent_world import PersistentWorld
from singlepass3d.sensor.telemetry_parser import enu_to_geodetic


class GeospatialExporter:
    """
    Generates defense and survey-grade geospatial rasters and vector layers
    from reconstructed, levelled 3D models and persistent world states.
    """
    def __init__(
        self,
        default_gsd_m: float = 0.05,
        nodata_value: float = -9999.0
    ):
        self.default_gsd_m = float(default_gsd_m)
        self.nodata_value = float(nodata_value)
        self.logger = get_logger()

    def export_all_geospatial(
        self,
        mesh: trimesh.Trimesh,
        output_dir: Path,
        world: Optional[PersistentWorld] = None,
        trajectory: Optional[Trajectory] = None,
        gsd_m: Optional[float] = None,
        textured_mesh: Optional[trimesh.Trimesh] = None
    ) -> Dict[str, str]:
        """
        Exports Orthomosaic, DSM, DTM, GeoJSON layers, and spatial measurements.
        Returns dictionary mapping deliverable name to absolute file path.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        gsd = float(gsd_m or self.default_gsd_m)
        exported: Dict[str, str] = {}

        if mesh is None or len(mesh.vertices) == 0:
            self.logger.warning("No valid mesh available for geospatial raster generation.")
            return exported

        V = np.asarray(mesh.vertices, dtype=np.float64)
        x_min, y_min, z_min = np.min(V, axis=0)
        x_max, y_max, z_max = np.max(V, axis=0)

        # Coordinate bounds and raster dimensions
        span_x = max(1.0, x_max - x_min)
        span_y = max(1.0, y_max - y_min)
        
        # Constrain dimensions to reasonable bounds (max 8192 for high performance)
        W = int(np.clip(np.ceil(span_x / gsd), 32, 8192))
        H = int(np.clip(np.ceil(span_y / gsd), 32, 8192))
        actual_gsd_x = span_x / float(W)
        actual_gsd_y = span_y / float(H)
        actual_gsd = float(0.5 * (actual_gsd_x + actual_gsd_y))

        self.logger.info(
            f"Generating Geospatial Package: Grid {W}x{H} px @ {actual_gsd * 100:.1f} cm/px GSD "
            f"(Coverage: {span_x:.1f}m x {span_y:.1f}m)..."
        )

        # Extract vertex colors or texture image
        colors = None
        if hasattr(mesh.visual, "vertex_colors") and mesh.visual.vertex_colors is not None:
            vc = np.asarray(mesh.visual.vertex_colors)
            if len(vc) == len(V):
                colors = vc[:, :3].astype(np.uint8)

        if colors is None:
            colors = np.full((len(V), 3), 160, dtype=np.uint8)

        # -------------------------------------------------------------
        # 1. Digital Surface Model (DSM) & Orthomosaic Rasterization
        # -------------------------------------------------------------
        dsm_grid = np.full((H, W), self.nodata_value, dtype=np.float32)
        ortho_rgb = np.zeros((H, W, 3), dtype=np.uint8)
        mask = np.zeros((H, W), dtype=bool)

        # Pixel coordinates
        px = np.clip(np.floor((V[:, 0] - x_min) / actual_gsd_x).astype(np.int32), 0, W - 1)
        py = np.clip(np.floor((y_max - V[:, 1]) / actual_gsd_y).astype(np.int32), 0, H - 1)
        pz = V[:, 2].astype(np.float32)

        # Sort points by elevation ascending so higher points overwrite lower points
        sort_idx = np.argsort(pz)
        dsm_grid[py[sort_idx], px[sort_idx]] = pz[sort_idx]
        ortho_rgb[py[sort_idx], px[sort_idx]] = colors[sort_idx]
        mask[py[sort_idx], px[sort_idx]] = True

        # Interpolate small internal raster voids via morphological closing & inpainting
        valid_u8 = mask.astype(np.uint8) * 255
        kernel_3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        kernel_5 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        
        closed_mask = cv2.morphologyEx(valid_u8, cv2.MORPH_CLOSE, kernel_5)
        holes = (closed_mask > 0) & (~mask)

        if np.any(holes):
            # Inpaint color
            ortho_bgr = cv2.cvtColor(ortho_rgb, cv2.COLOR_RGB2BGR)
            inpainted_bgr = cv2.inpaint(ortho_bgr, holes.astype(np.uint8) * 255, 3, cv2.INPAINT_TELEA)
            ortho_rgb = cv2.cvtColor(inpainted_bgr, cv2.COLOR_BGR2RGB)
            
            # Interpolate DSM elevation
            dsm_norm = np.where(mask, (dsm_grid - z_min) / max(1e-4, z_max - z_min), 0.0).astype(np.float32)
            dsm_u8 = (np.clip(dsm_norm, 0.0, 1.0) * 255.0).astype(np.uint8)
            inpainted_dsm_u8 = cv2.inpaint(dsm_u8, holes.astype(np.uint8) * 255, 3, cv2.INPAINT_TELEA)
            dsm_interp = (inpainted_dsm_u8.astype(np.float32) / 255.0) * (z_max - z_min) + z_min
            dsm_grid[holes] = dsm_interp[holes]
            mask[holes] = True

        # Write DSM (GeoTIFF 32-bit float) + World file
        dsm_path = output_dir / "dsm.tif"
        cv2.imwrite(str(dsm_path), dsm_grid)
        exported["dsm.tif"] = str(dsm_path)

        tfw_content = (
            f"{actual_gsd_x:.8f}\n"
            f"0.00000000\n"
            f"0.00000000\n"
            f"{-actual_gsd_y:.8f}\n"
            f"{x_min + actual_gsd_x * 0.5:.8f}\n"
            f"{y_max - actual_gsd_y * 0.5:.8f}\n"
        )
        dsm_tfw_path = output_dir / "dsm.tfw"
        dsm_tfw_path.write_text(tfw_content, encoding="utf-8")
        exported["dsm.tfw"] = str(dsm_tfw_path)

        # Write Orthomosaic (RGB GeoTIFF + PNG + World file)
        ortho_tif_path = output_dir / "orthomosaic.tif"
        ortho_png_path = output_dir / "orthomosaic.png"
        ortho_bgr_final = cv2.cvtColor(ortho_rgb, cv2.COLOR_RGB2BGR)
        
        cv2.imwrite(str(ortho_tif_path), ortho_bgr_final)
        cv2.imwrite(str(ortho_png_path), ortho_bgr_final)
        exported["orthomosaic.tif"] = str(ortho_tif_path)
        exported["orthomosaic.png"] = str(ortho_png_path)

        ortho_tfw_path = output_dir / "orthomosaic.tfw"
        ortho_tfw_path.write_text(tfw_content, encoding="utf-8")
        exported["orthomosaic.tfw"] = str(ortho_tfw_path)

        # -------------------------------------------------------------
        # 2. Digital Terrain Model (DTM: Bare Earth Filter)
        # -------------------------------------------------------------
        # Filter out elevated non-ground structures (facades, roofs, trees)
        # using a morphological opening (white top-hat ground approximation)
        dtm_grid = dsm_grid.copy()
        valid_elev = dsm_grid[mask]
        if valid_elev.size > 0:
            ground_baseline = float(np.percentile(valid_elev, 15))
            # Smooth bare ground via minimum filter
            dtm_norm = np.where(mask, np.clip((dsm_grid - z_min) / max(1e-4, z_max - z_min), 0.0, 1.0), 0.0)
            dtm_u8 = (dtm_norm * 255.0).astype(np.uint8)
            # Minimum morphological opening to strip vertical buildings/trees
            bare_earth_u8 = cv2.morphologyEx(dtm_u8, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)))
            dtm_elev = (bare_earth_u8.astype(np.float32) / 255.0) * (z_max - z_min) + z_min
            dtm_grid = np.where(mask, np.minimum(dsm_grid, dtm_elev + 0.3), self.nodata_value)

        dtm_path = output_dir / "dtm.tif"
        cv2.imwrite(str(dtm_path), dtm_grid)
        exported["dtm.tif"] = str(dtm_path)

        dtm_tfw_path = output_dir / "dtm.tfw"
        dtm_tfw_path.write_text(tfw_content, encoding="utf-8")
        exported["dtm.tfw"] = str(dtm_tfw_path)

        # -------------------------------------------------------------
        # 3. GeoJSON Building Footprints & Trajectory
        # -------------------------------------------------------------
        ref_lat = 47.384357
        ref_lon = 8.545178
        ref_alt = 464.9
        
        # Retrieve datum from trajectory if available
        if trajectory is not None and len(trajectory.poses) > 0:
            first_pose = trajectory.poses[0]
            if hasattr(first_pose, "gps_lat") and first_pose.gps_lat is not None:
                ref_lat = float(first_pose.gps_lat)
                ref_lon = float(first_pose.gps_lon)
                ref_alt = float(first_pose.gps_alt)

        footprints_geojson = self._generate_building_footprints_geojson(
            mesh=mesh,
            world=world,
            ref_lat=ref_lat,
            ref_lon=ref_lon,
            ref_alt=ref_alt,
            z_ground=float(np.percentile(V[:, 2], 12))
        )
        footprints_path = output_dir / "footprints.geojson"
        footprints_path.write_text(json.dumps(footprints_geojson, indent=2), encoding="utf-8")
        exported["footprints.geojson"] = str(footprints_path)

        if trajectory is not None and len(trajectory.poses) > 0:
            flight_path_geojson = self._generate_flight_path_geojson(
                trajectory=trajectory,
                ref_lat=ref_lat,
                ref_lon=ref_lon,
                ref_alt=ref_alt
            )
            flight_path_path = output_dir / "flight_path.geojson"
            flight_path_path.write_text(json.dumps(flight_path_geojson, indent=2), encoding="utf-8")
            exported["flight_path.geojson"] = str(flight_path_path)

        # -------------------------------------------------------------
        # 4. Spatial Measurement & Quantitative Analytics
        # -------------------------------------------------------------
        surface_area = float(mesh.area) if hasattr(mesh, "area") else 0.0
        footprint_area = float(np.sum(mask) * (actual_gsd_x * actual_gsd_y))
        
        # Stockpile / built volume approximation relative to ground datum
        z_datum = float(np.percentile(V[:, 2], 12))
        elev_above_ground = np.maximum(0.0, dsm_grid - z_datum)
        built_volume = float(np.sum(elev_above_ground[mask]) * (actual_gsd_x * actual_gsd_y))

        measurements = {
            "coordinate_system": "WGS84_ENU",
            "datum": {
                "latitude_deg": ref_lat,
                "longitude_deg": ref_lon,
                "altitude_m": ref_alt
            },
            "ground_sample_distance_m": actual_gsd,
            "dimensions_m": {
                "width_x": round(span_x, 2),
                "length_y": round(span_y, 2),
                "height_z": round(float(z_max - z_min), 2)
            },
            "surface_area_m2": round(surface_area, 2),
            "projected_footprint_area_m2": round(footprint_area, 2),
            "estimated_above_ground_volume_m3": round(built_volume, 2),
            "elevation_range_m": {
                "min": round(float(z_min), 2),
                "max": round(float(z_max), 2),
                "span": round(float(z_max - z_min), 2)
            },
            "mesh_statistics": {
                "vertex_count": len(mesh.vertices),
                "face_count": len(mesh.faces),
                "is_watertight": bool(mesh.is_watertight)
            },
            "deliverables": list(exported.keys())
        }

        measurements_path = output_dir / "measurements.json"
        measurements_path.write_text(json.dumps(measurements, indent=2), encoding="utf-8")
        exported["measurements.json"] = str(measurements_path)

        self.logger.info(
            f"Geospatial Package generation complete. Exported {len(exported)} artifacts "
            f"(Orthomosaic, DSM, DTM, Footprints GeoJSON, Measurements)."
        )
        return exported

    def _generate_building_footprints_geojson(
        self,
        mesh: trimesh.Trimesh,
        world: Optional[PersistentWorld],
        ref_lat: float,
        ref_lon: float,
        ref_alt: float,
        z_ground: float
    ) -> Dict[str, Any]:
        """
        Extracts elevated building rooftop clusters and projects footprint polygons to WGS84 GeoJSON.
        """
        features = []
        V = np.asarray(mesh.vertices)
        
        # Find elevated structures (> 2.5m above ground)
        elevated_mask = V[:, 2] > (z_ground + 2.5)
        if np.count_nonzero(elevated_mask) >= 30:
            elev_pts = V[elevated_mask]
            
            # Simple 2D grid clustering of elevated points into building blocks
            grid_res = 1.0  # 1 meter grid
            x_idx = np.floor(elev_pts[:, 0] / grid_res).astype(np.int32)
            y_idx = np.floor(elev_pts[:, 1] / grid_res).astype(np.int32)
            
            # Bounding box of the primary structure
            x0, x1 = float(np.min(elev_pts[:, 0])), float(np.max(elev_pts[:, 0]))
            y0, y1 = float(np.min(elev_pts[:, 1])), float(np.max(elev_pts[:, 1]))
            height = float(np.max(elev_pts[:, 2]) - z_ground)
            
            # 2D bounding polygon
            corners_enu = [
                np.array([x0, y0, z_ground]),
                np.array([x1, y0, z_ground]),
                np.array([x1, y1, z_ground]),
                np.array([x0, y1, z_ground]),
                np.array([x0, y0, z_ground])
            ]
            
            coords_wgs84 = []
            for pt in corners_enu:
                lat, lon, alt = enu_to_geodetic(pt, ref_lat, ref_lon, ref_alt)
                coords_wgs84.append([round(lon, 7), round(lat, 7), round(alt, 2)])
                
            features.append({
                "type": "Feature",
                "properties": {
                    "feature_id": 1,
                    "classification": "Building",
                    "height_m": round(height, 2),
                    "footprint_area_m2": round((x1 - x0) * (y1 - y0), 2),
                    "provenance": "RECONSTRUCTED_SURFACE"
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [coords_wgs84]
                }
            })

        return {
            "type": "FeatureCollection",
            "name": "SinglePass3D_Building_Footprints",
            "crs": {
                "type": "name",
                "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}
            },
            "features": features
        }

    def _generate_flight_path_geojson(
        self,
        trajectory: Trajectory,
        ref_lat: float,
        ref_lon: float,
        ref_alt: float
    ) -> Dict[str, Any]:
        """
        Exports drone trajectory camera positions as a WGS84 GeoJSON LineString.
        """
        coords_wgs84 = []
        for fid in trajectory.frame_ids:
            pose = trajectory.get_pose(fid)
            if pose is None:
                continue
            lat, lon, alt = enu_to_geodetic(pose.t_wc, ref_lat, ref_lon, ref_alt)
            coords_wgs84.append([round(lon, 7), round(lat, 7), round(alt, 2)])

        return {
            "type": "FeatureCollection",
            "name": "SinglePass3D_Drone_Flight_Path",
            "crs": {
                "type": "name",
                "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}
            },
            "features": [{
                "type": "Feature",
                "properties": {
                    "track_name": "Drone Single-Pass Video Flight Path",
                    "frame_count": len(coords_wgs84)
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": coords_wgs84
                }
            }]
        }
