"""Document catalog-to-runtime selection regression checks, without devices."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('demo_wall_builder', ROOT / 'scripts/build_demo_wall.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class DemoWallTests(unittest.TestCase):
    def test_catalog_covers_business_and_utility(self):
        document = builder.build_document()
        entries = document['entries']
        self.assertEqual(len(entries), 30)
        self.assertEqual(sum(e['category'] == 'F' for e in entries), 10)
        self.assertEqual(sum(e['category'] == 'P' for e in entries), 10)
        self.assertEqual(sum(e['category'] == 'U' for e in entries), 5)
        self.assertEqual(sum(e['category'] == 'S' for e in entries), 2)

    def test_only_exact_semantics_have_aliases(self):
        entries = {e['native_code']: e for e in builder.build_document()['entries']}
        self.assertFalse(entries['AA0F0']['launch_alias'])
        self.assertFalse(entries['AC0F0']['launch_alias'])
        self.assertFalse(entries['S-C0-D1-01']['launch_alias'])
        self.assertEqual(entries['AB2P5']['launch_alias'], 'demo-2-liaopan-placeto-hongganxiang')
        self.assertEqual(entries['AC0F0-02']['launch_alias'], 'demo-3-branch-sift-graspreset')

    def test_all_launch_aliases_unique(self):
        aliases = [e['launch_alias'] for e in builder.build_document()['entries'] if e['launch_alias']]
        self.assertEqual(len(aliases), len(set(aliases)))

    def test_generated_directory_current(self):
        builder.build(check=True)

    def test_frontend_selection_contract(self):
        if not shutil.which('node'):
            self.skipTest('Node.js unavailable')
        javascript = '''
const assert = require('node:assert/strict');
const wall = require('./src/ares_r/webui/demo_wall.js');
const entries = require('./src/ares_r/webui/demo_wall_catalog.json').entries;
const lower = entries.find(e => e.native_code === 'AB2P5');
assert.equal(wall.resolve(lower, []).runnable, false);
assert.equal(wall.resolve(lower, [{alias:lower.launch_alias, execution_ready:false}]).runnable, false);
assert.equal(wall.resolve(lower, [{alias:lower.launch_alias}]).runnable, true);
assert.equal(wall.resolve(lower, [{alias:lower.launch_alias}], 'delivery', 'native').runnable, true);
assert.equal(wall.resolve(lower, [{alias:lower.launch_alias}], 'delivery', 'ros').runnable, false);
const candidate = entries.find(e => e.native_code === 'AA0P0');
assert.equal(wall.resolve(candidate, [{alias:candidate.launch_alias}], 'delivery').runnable, false);
assert.equal(wall.resolve(candidate, [{alias:candidate.launch_alias}], 'development').runnable, true);
const hold = entries.find(e => e.native_code === 'AC0F0');
assert.equal(wall.resolve(hold, [{alias:hold.legacy_alias}]).runnable, false);
assert.equal(wall.matches(lower, {category:'P',station:'B2',query:'RB2P5'}),true);
assert.equal(wall.matches(lower, {category:'F',station:'',query:''}),false);
assert.equal(wall.combine(entries,[{alias:'future-demo'}]).at(-1).category,'X');
'''
        subprocess.run(['node', '-e', javascript], cwd=ROOT, check=True, capture_output=True)

    def test_web_hooks_exist(self):
        page = (ROOT / 'src/ares_r/webui/demo_console.html').read_text()
        server = (ROOT / 'src/ares_r/webui/server.py').read_text()
        self.assertIn('id="capabilityWall"', page)
        self.assertEqual(page.count('id="wallRevision"'), 1)
        self.assertIn('demo-started', page)
        self.assertIn('/api/demo-console/capabilities', server)
        self.assertIn('/static/demo-wall.css', page)
        self.assertIn("selected=''", page)


if __name__ == '__main__':
    unittest.main()
