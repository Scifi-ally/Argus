"""
Comprehensive Unit and Integration Test Suite for all 14 Section 32 Flight Scenarios.
Tests:
 1. Forward flight
 2. Lateral flight
 3. Orbit flight
 4. Altitude change
 5. Long flight
 6. GPS noise
 7. Motion blur
 8. Low-texture wall
 9. Repeated buildings
 10. Vegetation
 11. Vehicles
 12. Occlusion
 13. Loop closure
 14. Unseen surfaces
"""

from __future__ import annotations
import shutil
import tempfile
import unittest
from pathlib import Path

from singlepass3d.config.pipeline_config import SinglePass3DConfig
from singlepass3d.pipeline.runner import SinglePass3DPipeline
from tests.synthetic_generator import SyntheticFlightGenerator


class TestSinglePass3DScenarios(unittest.TestCase):
    """
    Tests SinglePass3D reconstruction across diverse flight topologies and challenges.
    """
    @classmethod
    def setUpClass(cls):
        cls.test_dir = Path(tempfile.mkdtemp(prefix="singlepass3d_test_"))
        cls.generator = SyntheticFlightGenerator(width=320, height=240, fps=15.0)

    @classmethod
    def tearDownClass(cls):
        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir, ignore_errors=True)

    def _run_scenario_test(self, scenario_name: str, num_frames: int = 15) -> None:
        video_p = self.test_dir / f"{scenario_name}.mp4"
        srt_p = self.test_dir / f"{scenario_name}.srt"
        out_dir = self.test_dir / f"out_{scenario_name}"

        self.generator.generate_flight(
            flight_type=scenario_name,
            num_frames=num_frames,
            output_video_path=video_p,
            output_srt_path=srt_p
        )

        config = SinglePass3DConfig(
            video_path=str(video_p),
            telemetry_path=str(srt_p),
            output_dir=str(out_dir),
            quality="fast",
            learned_adapter="mvs_fallback",
            enable_cache=False
        )

        pipeline = SinglePass3DPipeline(config)
        result = pipeline.run()

        self.assertIsNotNone(result)
        self.assertIn("qa_report", result)
        self.assertIn("exported_files", result)

        # Assert key artifacts are present
        self.assertTrue((out_dir / "model.glb").exists())
        self.assertTrue((out_dir / "model.ply").exists())
        self.assertTrue((out_dir / "model.obj").exists())
        self.assertTrue((out_dir / "trajectory.json").exists())
        self.assertTrue((out_dir / "world.json").exists())
        self.assertTrue((out_dir / "overlay.json").exists())
        self.assertTrue((out_dir / "quality.json").exists())
        self.assertTrue((out_dir / "report.json").exists())

    def test_01_forward_flight(self):
        self._run_scenario_test("forward", num_frames=12)

    def test_02_lateral_flight(self):
        self._run_scenario_test("lateral", num_frames=12)

    def test_03_orbit_flight(self):
        self._run_scenario_test("orbit", num_frames=16)

    def test_04_altitude_change(self):
        self._run_scenario_test("altitude", num_frames=12)

    def test_05_long_flight(self):
        self._run_scenario_test("long", num_frames=20)

    def test_06_gps_noise(self):
        self._run_scenario_test("gps_noise", num_frames=14)

    def test_07_motion_blur(self):
        self._run_scenario_test("motion_blur", num_frames=12)

    def test_08_low_texture_wall(self):
        self._run_scenario_test("low_texture", num_frames=12)

    def test_09_repeated_buildings(self):
        self._run_scenario_test("repeated", num_frames=14)

    def test_10_vegetation(self):
        self._run_scenario_test("vegetation", num_frames=12)

    def test_11_vehicles(self):
        self._run_scenario_test("vehicles", num_frames=12)

    def test_12_occlusion(self):
        self._run_scenario_test("occlusion", num_frames=12)

    def test_13_loop_closure(self):
        self._run_scenario_test("loop_closure", num_frames=16)

    def test_14_unseen_surfaces(self):
        self._run_scenario_test("unseen", num_frames=12)


if __name__ == "__main__":
    unittest.main()
