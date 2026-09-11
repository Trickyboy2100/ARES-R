import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ares_r import terminal


class TerminalHistoryTest(unittest.TestCase):
    def test_named_pose_speed_has_explicit_units_and_bounds(self):
        self.assertAlmostEqual(terminal._pose_speed("curobo"),2.0)
        self.assertEqual(terminal._pose_speed("curobo","3x"),3.0)
        self.assertAlmostEqual(terminal._pose_speed("direct","5deg/s"),5*3.141592653589793/180)
        for route,value in (("curobo","4x"),("direct","6deg/s"),("direct","3")):
            with self.assertRaises(ValueError): terminal._pose_speed(route,value)

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
        self.assertTrue(terminal._allowed_in_jaka_readonly(["note", "audit"]))
        self.assertFalse(terminal._allowed_in_jaka_readonly(["pick"]))
        self.assertFalse(terminal._allowed_in_jaka_readonly(["stop"]))
        self.assertFalse(terminal._allowed_in_jaka_readonly(["gripper", "open", "left"]))
        self.assertFalse(terminal._allowed_in_jaka_readonly(["nav", "pick"]))

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
        self.assertFalse(terminal._allowed_in_hardware(["cycle", "1"]))


if __name__ == "__main__":
    unittest.main()
