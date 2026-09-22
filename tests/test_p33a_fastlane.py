"""P3.3A backend has no physical execution entry point."""

import unittest
from unittest.mock import patch
from pathlib import Path
import tempfile

from ares_r.motion import ab_fastlane


class FastLaneTests(unittest.TestCase):
    def test_execute_next_remains_locked(self):
        with self.assertRaises(PermissionError):
            ab_fastlane.execute_next()

    def test_failed_scan_invalidates_old_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state.json"
            with patch.object(ab_fastlane, "STATE", state), \
                    patch.object(ab_fastlane, "_run", side_effect=RuntimeError("camera failed")):
                ab_fastlane.write_json(state, {"state": "PLANNED", "candidate_id": "old"})
                with self.assertRaisesRegex(RuntimeError, "camera failed"):
                    ab_fastlane.scan({"epic_pointcloud": {"body_cloud_viewer_python": "python"}})
                self.assertEqual(ab_fastlane.status()["state"], "SCENE_INVALID")
                self.assertIsNone(ab_fastlane.status()["candidate_id"])

    def test_future_keyboard_callbacks_abort_disable_invalidate(self):
        calls = []
        controls = ab_fastlane.FutureSupervisedKeyboardAbort(
            lambda: calls.append("abort"), lambda: calls.append("disable"),
            lambda reason: calls.append(reason))
        self.assertFalse(controls.handle("x"))
        self.assertTrue(controls.handle(" "))
        self.assertEqual(calls, ["abort", "disable", "controlled_abort_hold"])
        calls.clear()
        self.assertTrue(controls.handle("B"))
        self.assertEqual(calls, ["abort", "disable", "software_emergency_abort"])

    def test_base_stationarity_needs_idle_and_low_drift(self):
        responses = [
            {"info": {"x": 1.0, "y": 2.0, "yawNumber": 3.0, "mapId": 1},
             "state": {"current": {"state": "IDLE"}}},
            {"info": {"x": 1.001, "y": 2.001, "yawNumber": 3.01, "mapId": 1},
             "state": {"current": {"state": "IDLE"}}},
            {"info": {"x": 1.002, "y": 2.002, "yawNumber": 3.02, "mapId": 1},
             "state": {"current": {"state": "IDLE"}}},
        ]
        class Response:
            def __init__(self, value):
                import json
                self.value = json.dumps(value).encode()
            def __enter__(self):
                return self
            def __exit__(self, *_):
                return False
            def read(self):
                return self.value
        with patch.object(ab_fastlane, "urlopen", side_effect=[Response(v) for v in responses]), \
                patch.object(ab_fastlane.time, "sleep"):
            result = ab_fastlane.base_stationarity({"base": {"base_url": "http://example"}})
        self.assertTrue(result["stationary"])
        responses[-1]["state"]["current"]["state"] = "MOVING"
        with patch.object(ab_fastlane, "urlopen", side_effect=[Response(v) for v in responses]), \
                patch.object(ab_fastlane.time, "sleep"):
            result = ab_fastlane.base_stationarity({"base": {"base_url": "http://example"}})
        self.assertFalse(result["stationary"])
