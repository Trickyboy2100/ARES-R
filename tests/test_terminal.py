import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ares_r import terminal


class TerminalHistoryTest(unittest.TestCase):
    @unittest.skipIf(terminal.readline is None, "readline unavailable")
    def test_history_file_is_under_ignored_logs(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.object(terminal.atexit, "register") as register:
                terminal.setup_command_history(Path(root))
                expected = str(Path(root) / "logs" / ".terminal_history")
                register.assert_called_once_with(terminal.readline.write_history_file, expected)


if __name__ == "__main__":
    unittest.main()
