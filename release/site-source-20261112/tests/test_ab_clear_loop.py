"""The bounded A/B supervisor is testable without a controller connection."""

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/run_ab_clear_loop.py"
spec = importlib.util.spec_from_file_location("ab_clear_loop_under_test", SCRIPT)
loop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loop)


class BoundedLoopTest(unittest.TestCase):
    def test_rejects_unbounded_run(self):
        with self.assertRaises(ValueError):
            loop.run(4, 600)
        with self.assertRaises(ValueError):
            loop.run(1, 601)
        with self.assertRaises(ValueError):
            loop.run(1, 180, legs=7)

    def test_plan_only_never_starts_native_runner(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(loop, "LOCK", root / "loop.lock"), \
                    patch.object(loop, "MANIFEST", root / "loop.json"), \
                    patch.object(loop.ab_fastlane, "EVIDENCE", root / "evidence"), \
                    patch.object(loop, "load_config", return_value={}), \
                    patch.object(loop.signal, "signal"), \
                    patch.object(loop.ab_fastlane, "scan", return_value={
                        "state": "SCENE_READY", "scene_snapshot_id": "fresh"}), \
                    patch.object(loop.ab_fastlane, "plan_next", return_value={
                        "direction": "B_to_A", "dense_clearance_m": .04,
                        "native_speed_rad_s": .20, "trajectory_hash": "sha256:test"}) as plan, \
                    patch.object(loop.ab_fastlane, "preflight", return_value={
                        "blockers": sorted(loop.EXPECTED_BLOCKERS)}), \
                    patch.object(loop, "_run_leg") as native:
                loop._stop_requested = False
                loop.run(1, 180, plan_only=True)
                native.assert_not_called()
                status = loop.ab_fastlane.read_json(root / "loop.json")
                self.assertEqual(status["state"], "PLAN_ONLY_VALIDATED")
                self.assertEqual(status["direction"], "B_to_A")
                self.assertEqual(plan.call_args.args[1], .20)

    def test_one_leg_accepts_live_endpoint_direction(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(loop, "LOCK", root / "loop.lock"), \
                    patch.object(loop, "MANIFEST", root / "loop.json"), \
                    patch.object(loop.ab_fastlane, "EVIDENCE", root / "evidence"), \
                    patch.object(loop, "load_config", return_value={}), \
                    patch.object(loop.signal, "signal"), \
                    patch.object(loop.ab_fastlane, "scan", return_value={
                        "state": "SCENE_READY", "scene_snapshot_id": "fresh"}), \
                    patch.object(loop.ab_fastlane, "plan_next", return_value={
                        "direction": "A_to_B", "dense_clearance_m": .04,
                        "native_speed_rad_s": .20, "trajectory_hash": "sha256:test"}), \
                    patch.object(loop.ab_fastlane, "preflight", return_value={
                        "blockers": sorted(loop.EXPECTED_BLOCKERS)}), \
                    patch.object(loop, "_run_leg") as native:
                loop._stop_requested = False
                loop.run(1, 180, legs=1)
                native.assert_called_once()
                status = loop.ab_fastlane.read_json(root / "loop.json")
                self.assertEqual(status["state"], "COMPLETED")
                self.assertEqual(status["last_destination"], "B")

    def test_stop_does_not_signal_unverified_process(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "loop.json"
            loop.ab_fastlane.write_json(path, {"pid": 123, "start_ticks": 9})
            with patch.object(loop, "MANIFEST", path), \
                    patch.object(loop, "_service_identity", return_value=False), \
                    patch.object(loop.os, "kill") as kill:
                self.assertFalse(loop.stop()["stopped"])
                kill.assert_not_called()


if __name__ == "__main__":
    unittest.main()
