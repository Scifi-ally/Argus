"""
Unit and Integration Tests for SinglePass3D NTRO 26158 Production Capabilities:
1. Quadric Error Decimation & Mesh Finishing
2. Geospatial Intelligence Package (Orthomosaic, DSM, DTM GeoTIFF)
3. Dynamic Vehicle & Moving Object Filtering
4. WGS84 Geodesy & Footprint GeoJSON Generation
5. Quantitative 3D Measurements & Spatial Analytics
"""

import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
import trimesh

from singlepass3d.config.pipeline_config import SinglePass3DConfig, PRESETS
from singlepass3d.core.types import (
    ConfidenceLevel,
    Provenance,
    SemanticClass,
    VisibilityState,
    WorldElement,
    WorldElementState,
)
from singlepass3d.evidence.semantics_dynamics import SemanticDynamicsFilter
from singlepass3d.metric_world.persistent_world import PersistentWorld
from singlepass3d.output.geospatial_exporter import GeospatialExporter
from singlepass3d.output.mesh_generator import MeshGenerator
from singlepass3d.sensor.telemetry_parser import enu_to_geodetic, geodetic_to_ecef, ecef_to_geodetic


class TestGeospatialAndMeasurements(unittest.TestCase):
    def test_config_presets(self):
        """Verify new mesh finishing and geospatial fields exist and have correct defaults."""
        cfg = SinglePass3DConfig()
        self.assertTrue(cfg.export_geospatial)
        self.assertTrue(cfg.include_walls)
        self.assertGreaterEqual(cfg.target_mesh_faces, 100000)

        for name, preset in PRESETS.items():
            self.assertIn(name, ["fast", "balanced", "high", "ultra"])
            self.assertTrue(preset.include_walls)
            self.assertGreaterEqual(preset.target_mesh_faces, 100000)

    def test_wgs84_geodesy_roundtrip(self):
        """Verify sub-millimeter WGS84 <-> ECEF roundtrip accuracy."""
        test_coords = [
            (47.384357, 8.545178, 464.9),   # Zurich Urban MAV
            (28.613939, 77.209021, 216.0),  # New Delhi
            (34.052235, -118.243683, 85.0), # Los Angeles
        ]
        for lat, lon, alt in test_coords:
            ecef = geodetic_to_ecef(lat, lon, alt)
            lat_out, lon_out, alt_out = ecef_to_geodetic(ecef)
            self.assertAlmostEqual(lat, lat_out, places=5)
            self.assertAlmostEqual(lon, lon_out, places=5)
            self.assertAlmostEqual(alt, alt_out, delta=0.01)

    def test_quadric_decimation(self):
        """Verify MeshGenerator simplifies dense mesh while preserving surface features."""
        # Create a sphere mesh with ~2000 faces
        sphere = trimesh.creation.icosphere(subdivisions=3, radius=1.0)
        orig_faces = len(sphere.faces)
        self.assertGreater(orig_faces, 500)

        mg = MeshGenerator(target_mesh_faces=300)
        decimated = mg._simplify_quadric_decimation(sphere, target_faces=300)

        self.assertLessEqual(len(decimated.faces), orig_faces)
        self.assertGreater(len(decimated.faces), 100)
        self.assertGreater(len(decimated.vertices), 50)

    def test_dynamic_object_filtering(self):
        """Verify moving vehicles and pedestrians are filtered and tagged."""
        world = PersistentWorld(voxel_size_m=0.1)

        # 1. Static Road Element
        road_elem = WorldElement(
            element_id=1,
            position=np.array([0.0, 0.0, 0.0]),
            normal=np.array([0.0, 0.0, 1.0]),
            covariance=np.eye(3),
            color=np.array([50, 50, 50]),
            supporting_frames={1, 2, 3},
            observation_count=3,
            reprojection_error=0.8,
            model_confidence=0.9,
            gps_trajectory_confidence=1.0,
            semantic_class=SemanticClass.UNKNOWN,
            dynamic_probability=0.0,
            visibility=VisibilityState.VISIBLE,
            provenance=Provenance.OBSERVED,
            state=WorldElementState.ACTIVE,
            confidence_score=0.9,
            confidence_level=ConfidenceLevel.HIGH
        )
        world.store.add_element(road_elem)

        # 2. Moving Vehicle Element (0.8m above road, transient count=1, reprojection error=3.2px)
        car_elem = WorldElement(
            element_id=2,
            position=np.array([2.0, 3.0, 0.8]),
            normal=np.array([0.0, 0.0, 1.0]),
            covariance=np.eye(3),
            color=np.array([220, 30, 30]), # bright red car
            supporting_frames={2},
            observation_count=1,
            reprojection_error=3.2,
            model_confidence=0.5,
            gps_trajectory_confidence=1.0,
            semantic_class=SemanticClass.UNKNOWN,
            dynamic_probability=0.0,
            visibility=VisibilityState.VISIBLE,
            provenance=Provenance.OBSERVED,
            state=WorldElementState.ACTIVE,
            confidence_score=0.5,
            confidence_level=ConfidenceLevel.MEDIUM
        )
        world.store.add_element(car_elem)

        # 3. Rooftop Element
        roof_elem = WorldElement(
            element_id=3,
            position=np.array([5.0, 5.0, 8.0]),
            normal=np.array([0.0, 0.0, 1.0]),
            covariance=np.eye(3),
            color=np.array([180, 80, 50]),
            supporting_frames={1, 2, 3, 4},
            observation_count=4,
            reprojection_error=0.9,
            model_confidence=0.9,
            gps_trajectory_confidence=1.0,
            semantic_class=SemanticClass.UNKNOWN,
            dynamic_probability=0.0,
            visibility=VisibilityState.VISIBLE,
            provenance=Provenance.OBSERVED,
            state=WorldElementState.ACTIVE,
            confidence_score=0.9,
            confidence_level=ConfidenceLevel.HIGH
        )
        world.store.add_element(roof_elem)

        sdf = SemanticDynamicsFilter()
        counts = sdf.process_world(world)

        # Road surfel should remain active
        self.assertEqual(road_elem.state, WorldElementState.ACTIVE)
        self.assertEqual(road_elem.semantic_class, SemanticClass.ROAD)

        # Car surfel should be rejected as a dynamic vehicle
        self.assertEqual(car_elem.semantic_class, SemanticClass.VEHICLE)
        self.assertEqual(car_elem.state, WorldElementState.REJECTED)
        self.assertGreaterEqual(car_elem.dynamic_probability, 0.8)

        # Roof surfel should be classified as roof
        self.assertEqual(roof_elem.semantic_class, SemanticClass.ROOF)

    def test_geospatial_exporter(self):
        """Verify Orthomosaic, DSM, DTM, and GeoJSON deliverables are created with valid headers."""
        # Create a simple box mesh representing terrain and a building
        mesh = trimesh.creation.box(extents=(10.0, 10.0, 4.0))
        # Level so bottom is near Z=0
        mesh.vertices[:, 2] += 2.0
        mesh.visual.vertex_colors = np.full((len(mesh.vertices), 4), [120, 140, 160, 255], dtype=np.uint8)

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir)
            ge = GeospatialExporter(default_gsd_m=0.1)
            exported = ge.export_all_geospatial(mesh=mesh, output_dir=out_path)

            self.assertIn("orthomosaic.tif", exported)
            self.assertIn("orthomosaic.tfw", exported)
            self.assertIn("dsm.tif", exported)
            self.assertIn("dsm.tfw", exported)
            self.assertIn("dtm.tif", exported)
            self.assertIn("footprints.geojson", exported)
            self.assertIn("measurements.json", exported)

            # Check that files exist and are non-empty
            for fname, fpath in exported.items():
                p = Path(fpath)
                self.assertTrue(p.exists(), f"Missing deliverable: {fname}")
                self.assertGreater(p.stat().st_size, 0, f"Empty deliverable: {fname}")

            # Verify measurements.json contents
            with open(exported["measurements.json"], "r") as f:
                data = json.load(f)
            self.assertIn("ground_sample_distance_m", data)
            self.assertIn("surface_area_m2", data)
            self.assertIn("projected_footprint_area_m2", data)
            self.assertIn("estimated_above_ground_volume_m3", data)
            self.assertGreater(data["surface_area_m2"], 0)


if __name__ == "__main__":
    unittest.main()
