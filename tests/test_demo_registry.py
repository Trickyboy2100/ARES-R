import json
from pathlib import Path
import tempfile
import unittest

from ares_r.demos import DemoRegistry


class DemoRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); root = Path(self.tmp.name)
        self.catalog = root / "demos"; definition = self.catalog / "sample"
        definition.mkdir(parents=True)
        (definition / "demo.json").write_text(json.dumps({
            "schema_version": 1, "demo_id": "sample", "name": "Sample",
            "version": "1.0.0", "category": "test", "commissioning_state": "OFFLINE",
            "freshness_policy": {"scene": "FRESH_EVERY_RUN"},
            "execution": {"entrypoint": "runner.py", "prepare_command": "prepare",
                          "run_command": "run", "stop_command": "demo stop",
                          "authorization_phrase": "RUN SAMPLE"}}))
        self.registry = DemoRegistry(self.catalog, root / "runtime.json")

    def tearDown(self): self.tmp.cleanup()

    def test_select_and_prepare_share_versioned_definition(self):
        self.assertEqual(self.registry.status()["state"], "NO_DEMO_SELECTED")
        selected = self.registry.select("sample")
        self.assertEqual(selected["selected_version"], "1.0.0")
        prepared = self.registry.prepare()
        self.assertEqual(prepared["state"], "READY_TO_PREPARE_FRESH_RUN")
        self.assertEqual(prepared["authorization_phrase"], "RUN SAMPLE")
        self.assertEqual(self.registry.list()[0]["selected"], True)

    def test_unknown_demo_fails_closed(self):
        with self.assertRaises(ValueError): self.registry.select("missing")


if __name__ == "__main__": unittest.main()
