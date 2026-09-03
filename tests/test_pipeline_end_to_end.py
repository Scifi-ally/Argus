"""
End-to-End Integration and Regression Test Suite for SinglePass3D Pipeline and CLI Scripts.
"""

from __future__ import annotations
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.synthetic_generator import SyntheticFlightGenerator


class TestPipelineEndToEnd(unittest.TestCase):
    """
    Validates the complete execution flow including CLI tools and all 11 output files.
    """
    @classmethod
    def setUpClass(cls):
        cls.test_dir = Path(tempfile.mkdtemp(prefix="singlepass3d_e2e_"))
        cls.generator = SyntheticFlightGenerator(width=640, height=480, fps=20.0)
        cls.video_path = cls.test_dir / "flight_e2e.mp4"
        cls.srt_path = cls.test_dir / "flight_e2e.srt"
        cls.output_dir = cls.test_dir / "job_e2e_output"

        # Generate realistic synthetic orbit flight
        cls.generator.generate_flight(
            flight_type="orbit",
            num_frames=24,
            output_video_path=cls.video_path,
            output_srt_path=cls.srt_path
        )

    @classmethod
    def tearDownClass(cls):
        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir, ignore_errors=True)

    def test_01_cli_run_reconstruction(self):
        """Test scripts/run_reconstruction.py CLI execution."""
        script = Path(__file__).resolve().parent.parent / "scripts" / "run_reconstruction.py"
        cmd = [
            sys.executable,
            str(script),
            "--video", str(self.video_path),
            "--telemetry", str(self.srt_path),
            "--output", str(self.output_dir),
            "--quality", "fast"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"run_reconstruction failed: {res.stderr}\n{res.stdout}")

    def test_02_verify_all_11_output_artifacts(self):
        """Verify presence and validity of all 11 required output files."""
        expected_files = [
            "model.glb",
            "model.ply",
            "model.obj",
            "texture.png",
            "trajectory.json",
            "cameras.json",
            "world.json",
            "uncertainty.json",
            "overlay.json",
            "quality.json",
            "report.json",
            "diagnostics.json"
        ]
        for fname in expected_files:
            fpath = self.output_dir / fname
            self.assertTrue(fpath.exists(), f"Missing expected output file: {fname}")
            self.assertGreater(fpath.stat().st_size, 0, f"File is empty: {fname}")

        # Check world.json structure
        with open(self.output_dir / "world.json", "r", encoding="utf-8") as f:
            world_data = json.load(f)
            self.assertIn("elements", world_data)
            self.assertGreater(world_data["total_elements"], 0)

        # Check overlay.json structure
        with open(self.output_dir / "overlay.json", "r", encoding="utf-8") as f:
            overlay_data = json.load(f)
            self.assertIn("provenance_summary", overlay_data)
            self.assertIn("confidence_summary", overlay_data)

        # Check quality.json structure
        with open(self.output_dir / "quality.json", "r", encoding="utf-8") as f:
            quality_data = json.load(f)
            self.assertIn("quality_status", quality_data)
            self.assertIn("trajectory_gates", quality_data)
            self.assertIn("geometry_gates", quality_data)
            self.assertIn("completeness_breakdown", quality_data)

    def test_03_cli_inspect_job(self):
        """Test scripts/inspect_job.py CLI execution."""
        script = Path(__file__).resolve().parent.parent / "scripts" / "inspect_job.py"
        cmd = [sys.executable, str(script), str(self.output_dir)]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"inspect_job failed: {res.stderr}\n{res.stdout}")
        self.assertIn("SinglePass3D Job Inspector", res.stdout)
        self.assertIn("Quality Assurance Gates", res.stdout)

    def test_04_cli_benchmark(self):
        """Test scripts/benchmark.py CLI execution."""
        script = Path(__file__).resolve().parent.parent / "scripts" / "benchmark.py"
        cmd = [sys.executable, str(script), str(self.output_dir)]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"benchmark failed: {res.stderr}\n{res.stdout}")
        self.assertIn("SinglePass3D Performance & Benchmark", res.stdout)


if __name__ == "__main__":
    unittest.main()
