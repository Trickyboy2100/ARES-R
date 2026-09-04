import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ares_r import terminal


class TerminalHistoryTest(unittest.TestCase):
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
        self.assertTrue(terminal._allowed_in_jaka_readonly(["note", "audit"]))
        self.assertFalse(terminal._allowed_in_jaka_readonly(["pick"]))
        self.assertFalse(terminal._allowed_in_jaka_readonly(["stop"]))
        self.assertFalse(terminal._allowed_in_jaka_readonly(["gripper", "open", "left"]))
        self.assertFalse(terminal._allowed_in_jaka_readonly(["nav", "pick"]))


if __name__ == "__main__":
    unittest.main()
