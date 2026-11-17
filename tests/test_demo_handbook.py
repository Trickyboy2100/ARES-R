"""Documentation regression checks; no device or backend is constructed."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('demo_handbook_builder', ROOT / 'scripts/build_demo_handbook.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class DemoHandbookTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads((ROOT / 'docs/demo-handbook/catalog.json').read_text())

    def test_codes_and_six_slot_pairs(self):
        builder.validate(self.catalog)
        slots = [e for e in self.catalog['entries'] if e['station'].startswith('B')]
        self.assertEqual(len(slots), 12)
        for operation in ('F', 'P'):
            self.assertEqual({e['slot'] for e in slots if e['function'] == operation}, set(range(1, 7)))

    def test_duplicate_code_rejected(self):
        self.catalog['entries'].append(copy.deepcopy(self.catalog['entries'][0]))
        with self.assertRaises(ValueError):
            builder.validate(self.catalog)

    def test_wrong_dryer_station_rejected(self):
        entry = next(e for e in self.catalog['entries'] if e['native_code'] == 'AB2F2')
        entry['station'] = 'B1'
        with self.assertRaises(AssertionError):
            builder.validate(self.catalog)

    def test_lower_middle_native_success_preserved(self):
        entry = next(e for e in self.catalog['entries'] if e['native_code'] == 'AB2P5')
        self.assertIn('完整通过', entry['native_status'])
        self.assertIn('待完成', entry['ros_status'])
        self.assertTrue(any('run_1794383252441911735' in path for path in entry['evidence_paths']))

    def test_unknown_markdown_link_rejected(self):
        with self.assertRaises(ValueError):
            builder.inline('[missing](missing.md)')

    def test_source_text_escaped(self):
        self.assertIn('&lt;script&gt;', builder.render_markdown('<script>alert(1)</script>'))

    def test_generated_files_current(self):
        builder.build(check=True)

    def test_documentation_has_no_execution_client(self):
        document = builder.OUTPUT.read_text()
        self.assertNotIn('fetch(', document)
        self.assertNotIn('XMLHttpRequest', document)
        self.assertIn('data-route="page-2"', document)
        self.assertNotIn('id="page-2"', document)


if __name__ == '__main__':
    unittest.main()
