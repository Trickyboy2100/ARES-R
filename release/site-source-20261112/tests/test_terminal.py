import builtins
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from ares_r import terminal


class TerminalHistoryTest(unittest.TestCase):
    def test_named_pose_speed_has_explicit_units_and_bounds(self):
        self.assertAlmostEqual(terminal._pose_speed("curobo"),2.0)
        self.assertEqual(terminal._pose_speed("curobo","3x"),3.0)
        self.assertAlmostEqual(terminal._pose_speed("direct","5deg/s"),5*3.141592653589793/180)
        for route,value in (("curobo","4x"),("direct","6deg/s"),("direct","3")):
            with self.assertRaises(ValueError): terminal._pose_speed(route,value)

    def test_motion_plan_xyz_forwards_the_full_command_text(self):
        # Regression: this branch used to call dispatch(line) with an undefined
        # name, so ART's `motion plan ... --xyz` raised NameError instead of
        # planning.  The dispatcher re-splits the text itself, so the exact
        # reconstruction is what must be forwarded.
        controller = SimpleNamespace(mode="hardware-enabled",
                                     config={"hardware_devices": "all", "team": {}})
        dispatcher = MagicMock()
        dispatcher.dispatch.return_value = {"plan_id": "PLAN_TEST"}
        command = ("motion plan right --xyz 0.604866 -0.094151 1.222342 "
                   "--orientation LEVEL_YAW_TARGET --yaw 2.567")
        with patch.object(terminal, "setup_command_history"), \
                patch.object(terminal, "render"), \
                patch.object(terminal, "WorkLog"), \
                patch("ares_r.scene_aware_dispatch.shared_dispatcher",
                      return_value=dispatcher), \
                patch.object(builtins, "input", side_effect=[command, "quit"]):
            terminal.run_terminal(controller)
        dispatcher.dispatch.assert_called_once_with(command)

    @unittest.skipIf(terminal.readline is None, "readline unavailable")
    def test_history_file_is_under_ignored_logs(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.object(terminal.atexit, "register") as register, \
                    patch.object(terminal.readline, "read_history_file", side_effect=FileNotFoundError):
                terminal.setup_command_history(Path(root))
                register.assert_called_once()

    def test_jaka_readonly_command_allowlist(self):
        self.assertTrue(terminal._allowed_in_jaka_readonly(["jaka", "status", "left"]))
        self.assertTrue(terminal._allowed_in_jaka_readonly(["jaka", "joints", "left"]))
        self.assertTrue(terminal._allowed_in_jaka_readonly(
            ["jaka", "plan", "left", "deg", "0", "0", "0", "0", "0", "0"]))
        self.assertTrue(terminal._allowed_in_jaka_readonly(["motion", "validate", "path.json"]))
        self.assertTrue(terminal._allowed_in_jaka_readonly(["world", "status"]))
        self.assertTrue(terminal._allowed_in_jaka_readonly(
            ["calib", "body-camera", "handeye", "compare"]))
        self.assertTrue(terminal._allowed_in_jaka_readonly(["scene", "body-cloud", "inspect"]))
        self.assertTrue(terminal._allowed_in_jaka_readonly(["scene", "body-cloud", "show", "--robot"]))
        self.assertTrue(terminal._allowed_in_jaka_readonly(["robot", "collision", "inspect"]))
        self.assertTrue(terminal._allowed_in_jaka_readonly(["scene", "arm-obstacle", "show", "right"]))
        self.assertTrue(terminal._allowed_in_jaka_readonly(["note", "audit"]))
        self.assertFalse(terminal._allowed_in_jaka_readonly(["pick"]))
        self.assertFalse(terminal._allowed_in_jaka_readonly(["stop"]))
        self.assertFalse(terminal._allowed_in_jaka_readonly(["gripper", "open", "left"]))
        self.assertFalse(terminal._allowed_in_jaka_readonly(["nav", "pick"]))

    def test_gripper_delay_flag_is_parsed_and_bounded(self):
        self.assertEqual(terminal._pop_delay(["gripper", "close", "right", "--delay", "3"]),
                         (["gripper", "close", "right"], 3.0))
        self.assertEqual(terminal._pop_delay(["gripper", "close", "right"]),
                         (["gripper", "close", "right"], 0.0))
        self.assertEqual(terminal._pop_delay(["gripper", "set", "left", "500", "--delay", "2.5"]),
                         (["gripper", "set", "left", "500"], 2.5))
        # A pasted help line keeps the optional-argument brackets; still understood.
        self.assertEqual(terminal._pop_delay(["gripper", "close", "right", "[--delay", "5]"]),
                         (["gripper", "close", "right"], 5.0))
        self.assertEqual(terminal._pop_delay(["gripper", "close", "right", "--delay=4"]),
                         (["gripper", "close", "right"], 4.0))
        for bad in (["gripper", "close", "right", "--delay"],
                    ["gripper", "close", "right", "--delay", "abc"],
                    ["gripper", "close", "right", "--delay", "-1"]):
            with self.assertRaises(ValueError): terminal._pop_delay(bad)
        self.assertTrue(terminal._allowed_in_hardware(
            ["gripper", "close", "right", "--delay", "3"]))

    def test_hardware_allowlist_blocks_unfinished_orchestration(self):
        self.assertTrue(terminal._allowed_in_hardware(["jaka", "move-step", "left", "J2", "deg", "1"]))
        self.assertTrue(terminal._allowed_in_hardware(["gripper", "open", "right"]))
        self.assertTrue(terminal._allowed_in_hardware(["epic", "detect", "pick"]))
        self.assertTrue(terminal._allowed_in_hardware(["pose", "show", "ready", "right"]))
        self.assertTrue(terminal._allowed_in_hardware(["pose", "go", "ready", "right", "curobo"]))
        self.assertTrue(terminal._allowed_in_hardware(["amr", "status"]))
        self.assertTrue(terminal._allowed_in_hardware(["amr", "move-relative", "0.1", "0", "0"]))
        self.assertTrue(terminal._allowed_in_hardware(["nav", "pick"]))
        self.assertTrue(terminal._allowed_in_hardware(["world", "status"]))
        self.assertTrue(terminal._allowed_in_hardware(
            ["calib", "body-camera", "handeye", "board-check"]))
        self.assertTrue(terminal._allowed_in_hardware(["scene", "body-cloud", "show"]))
        self.assertTrue(terminal._allowed_in_hardware(
            ["scene", "body-cloud", "live", "--interval", "2.0"]))
        self.assertFalse(terminal._allowed_in_hardware(["cycle", "1"]))


if __name__ == "__main__":
    unittest.main()
