import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("golden_bench", ROOT / "scripts/benchmark_golden_frozen.py")
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


class FrozenBenchmarkTests(unittest.TestCase):
    def test_empty_manifest_not_mocked(self):
        with self.assertRaisesRegex(ValueError, "NO_REAL"):
            bench.verify({"cases": []})

    def test_hashes_and_explicit_no_execution_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model = root / "model.yml"
            urdf = root / "model.urdf"
            model.write_text("test-only")
            urdf.write_text("test-only")
            request = root / "request.json"
            value = {"planning_only": True, "execution_allowed": False,
                     "robot_yaml": str(model), "robot_yaml_urdf": str(urdf)}
            request.write_text(json.dumps(value))
            case = {"name": "test", "expected": "SUCCESS", "request": str(request),
                    "sha256": bench.sha(request),
                    "dependencies": [{"path": str(p), "sha256": bench.sha(p)} for p in (model, urdf)]}
            self.assertEqual(len(bench.verify({"cases": [case]})), 1)
            urdf.write_text("changed")
            with self.assertRaisesRegex(ValueError, "dependency hash"):
                bench.verify({"cases": [case]})
            urdf.write_text("test-only")
            value["execution_allowed"] = True
            request.write_text(json.dumps(value))
            case["sha256"] = bench.sha(request)
            with self.assertRaisesRegex(ValueError, "offline request"):
                bench.verify({"cases": [case]})
