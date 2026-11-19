"""V1.5 changes preparation latency, not the commissioned grasp motion."""
import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'demos/right_arm_tray_fetch_hold_biased_v1/versions'


class V15ProfileTest(unittest.TestCase):
    def test_physical_parameters_match_v14(self):
        old = json.loads((BASE / '1.4/parameters.json').read_text())
        new = json.loads((BASE / '1.5/parameters.json').read_text())
        for key in ('capability_version', 'revision', 'planner_initialization_source_run_id', 'performance_profile'):
            old.pop(key, None)
            new.pop(key, None)
        self.assertEqual(old, new)

    def test_profile_is_bound_and_opt_in(self):
        from ares_r.demos.capability_versions import resolve_version, versions
        current = versions(ROOT, 'AA0F0-B')
        self.assertEqual(current['default_version'], '1.4')
        selected = resolve_version(ROOT, 'AA0F0-B', '1.5')
        profile = Path(selected['profile_dir'])
        self.assertEqual(selected['parameters_sha256'], hashlib.sha256((profile / 'parameters.json').read_bytes()).hexdigest())
        self.assertEqual(json.loads((profile / 'parameters.json').read_text())['planner_initialization_source_run_id'],
                         'e2ede7bef25a42faa2a24c81abb50cd6')


if __name__ == '__main__':
    unittest.main()
