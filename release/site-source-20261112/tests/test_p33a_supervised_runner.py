"""A chat authorization does not remove the runner's local commissioning gates."""

import importlib.util
from pathlib import Path
import sys
import tempfile
from unittest import TestCase
from unittest.mock import patch


class SupervisedRunnerTests(TestCase):
    def test_execute_requires_exact_scope_and_observer_before_any_io(self):
        path = Path(__file__).resolve().parents[1] / "scripts/run_p33a_supervised_once.py"
        spec = importlib.util.spec_from_file_location("p33a_supervised_runner_test", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            with patch.object(sys, "argv", [str(path), "--expected-trajectory-hash", "H",
                                            "--execute", "--output", str(output)]):
                with self.assertRaises(PermissionError):
                    module.main()
            self.assertFalse(output.exists())
