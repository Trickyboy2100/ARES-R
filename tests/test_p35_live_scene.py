import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ares_r.motion import live_scene


ROOT = Path(__file__).resolve().parents[1]


class LiveSceneTests(unittest.TestCase):
    def test_build_requires_matching_fresh_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "scan"

            def run(command, **_kwargs):
                output.mkdir()
                (output / "scene").mkdir()
                (output / "fresh_scene_summary.json").write_text(json.dumps({
                    "mode": "LIVE", "snapshot_id": "SCENE_FRESH",
                    "pointcloud_sha256": "CLOUD_NEW", "timing_s": {}, "total_s": 1.0}))
                (output / "scene/scene_report.json").write_text(json.dumps({
                    "mode": "LIVE", "snapshot_id": "SCENE_FRESH",
                    "pointcloud_sha256": "CLOUD_NEW", "compiled_scene_digest": "DIGEST",
                    "objects": [], "support_decomposition": {"supports": []}}))
                (output / "scene/compiled_scene.json").write_text(json.dumps({
                    "scene_snapshot_id": "SCENE_FRESH"}))
                return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()

            config = {"epic_pointcloud": {"body_cloud_viewer_python": "/python"}}
            with patch.object(live_scene.subprocess, "run", side_effect=run):
                result = live_scene.build_live_planning_scene(config, output)
            self.assertEqual(result["pointcloud_sha256"], "CLOUD_NEW")
            self.assertEqual(result["scene_snapshot_id"], "SCENE_FRESH")
            self.assertNotIn("obstacle_coordinates", result["runtime_inputs"])

    def test_static_runtime_hardcode_audit_passes(self):
        script = ROOT / "scripts/audit_p35_scene_runtime.py"
        spec = importlib.util.spec_from_file_location("p35_audit", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = module.audit()
        self.assertEqual(result["SCENE_RUNTIME_HARDCODE_AUDIT"], "PASS", result)
        self.assertTrue(result["NO_MANUAL_OBSTACLE_COORDINATES"])
        self.assertTrue(result["NO_OBJECT_SPECIFIC_AVOIDANCE_CODE"])


if __name__ == "__main__":
    unittest.main()
