import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

import numpy as np

from ares_r.demos.console_monitor import ConsoleMonitor
from ares_r.webui.server import scene_payload


class WebSceneCloudTests(unittest.TestCase):
    def test_both_viewers_show_raw_cloud_when_planning_residual_is_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scene").mkdir()
            raw = root / "body_cloud.npz"
            points = np.array([[0.5, 0.1, 0.02], [1.0, -0.1, 0.03]])
            np.savez(raw, points_body_m=points)
            np.savez(root / "scene/clean_residual.npz", points_body_m=np.empty((0, 3)))
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"artifact_npz": str(raw)}))
            (root / "capture_pointer.json").write_text(json.dumps({"manifest": str(manifest)}))
            (root / "scene/scene_report.json").write_text(json.dumps({"objects": []}))
            dispatcher = SimpleNamespace(
                scene_status=lambda: {"scene_dir": str(root)},
                motion_status=lambda: {})
            main = scene_payload(dispatcher)
            console = ConsoleMonitor(SimpleNamespace(job={}, backend=SimpleNamespace(dispatcher=dispatcher)))
            monitor = console.scene_payload()
            for payload in [main, monitor]:
                self.assertEqual(payload["pointcloud_kind"], "RAW_BODY")
                np.testing.assert_allclose(payload["pointcloud"], points)


if __name__ == "__main__":
    unittest.main()
