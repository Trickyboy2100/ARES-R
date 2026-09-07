import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ares_r.motion.curobo import finite_joints, run_plan, slow_sample_period, summarize
from ares_r.factory import build_controller
from ares_r.adapters.mock import DisabledDevice
from ares_r.terminal import _allowed_in_hardware


class CuroboTest(unittest.TestCase):
    def test_time_dilation_preserves_points_and_caps_derivatives(self):
        points = [[0.0] * 6, [math.radians(0.25)] + [0.0] * 5, [math.radians(0.5)] + [0.0] * 5]
        original = json.dumps(points)
        dt = slow_sample_period(points)
        summary = summarize(points, dt)
        self.assertLessEqual(max(summary["peak_velocity_deg_s"]), 0.5)
        self.assertLessEqual(max(summary["peak_acceleration_deg_s2"]), 1.0)
        self.assertAlmostEqual(dt / 0.008, round(dt / 0.008))
        self.assertEqual(json.dumps(points), original)

    def test_nonfinite_and_wrong_shape_blocked(self):
        for values in ([0.0] * 5, [float("nan")] * 6, [float("inf")] * 6):
            with self.assertRaises(ValueError): finite_joints(values)

    def test_large_target_blocked_before_worker(self):
        with patch("ares_r.motion.curobo.subprocess.run") as process:
            with self.assertRaisesRegex(ValueError, "0.5 degree"):
                run_plan({}, [0] * 6, [0.1] + [0] * 5)
            process.assert_not_called()

    def test_no_execution_command_exposed(self):
        self.assertTrue(_allowed_in_hardware(["curobo", "plan", "right", "J6", "deg", "0.5"]))
        self.assertFalse(_allowed_in_hardware(["curobo", "execute", "file.json"]))

    def test_right_only_factory_never_constructs_other_adapters(self):
        with tempfile.TemporaryDirectory() as directory:
            config = {"hardware_devices": "right-arm", "jaka": {"arms": {"right": {"ip": "right"}}},
                      "logging": {"directory": directory}}
            with patch("ares_r.adapters.jaka_sdk.JakaSdkArm") as arm, \
                    patch("ares_r.factory.EpicClient") as epic, \
                    patch("ares_r.factory.SerialGripper") as gripper, \
                    patch("ares_r.adapters.jaka_sdk.build_jaka_arms") as both:
                controller = build_controller(config, "hardware-enabled")
                arm.assert_called_once_with("right", {"ip": "right"}, config["jaka"], True)
                epic.assert_not_called(); gripper.assert_not_called(); both.assert_not_called()
                self.assertIsInstance(controller.arms["left"], DisabledDevice)
                self.assertEqual(controller.active_arm, "right")
                with self.assertRaises(RuntimeError): controller.arms["left"].move_to_pose(None)


if __name__ == "__main__":
    unittest.main()
