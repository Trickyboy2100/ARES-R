import importlib.util
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('onsite_install', ROOT/'deploy/onsite-20261117/install.py')
INSTALLER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSTALLER)


class OnsiteInstallerTests(unittest.TestCase):
    def test_secondary_patch_preserves_unrelated_source_and_stays_in_memory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root/'src/ares_r/world/scene_compiler.py'
            path.parent.mkdir(parents=True)
            original = '# local coworker note\ndef compile_old(objects):\n    for item in objects:\n        print(item)\n'
            path.write_text(original)
            updates = INSTALLER.secondary_policy_updates(root)
            self.assertEqual(path.read_text(), original)
            self.assertIn('# local coworker note', updates[path])
            self.assertIn('is_chassis_geometry(item)', updates[path])
            compile(updates[path], str(path), 'exec')

    def test_disable_is_idempotent_and_preserves_other_geometry(self):
        model = dict(asset_root='/pinned', geometry_revision='old', custom_field={'value': 12},
            fixed_body_boxes=[dict(geometry_id='body/chassis', owner='chassis'),
                              dict(geometry_id='body/central_exclusion', owner='safety')])
        first = INSTALLER.disable_chassis(model)
        second = INSTALLER.disable_chassis(first)
        self.assertEqual(first, second)
        self.assertEqual(first['custom_field'], model['custom_field'])
        self.assertEqual(first['fixed_body_boxes'], [model['fixed_body_boxes'][1]])
        self.assertEqual(len(model['fixed_body_boxes']), 2)
        self.assertEqual(len(first['disabled_fixed_body_boxes']), 1)

    def test_installer_deduplicates_roots_and_preserves_site_offsets(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            bundle, root, sdk = base/'bundle', base/'site', base/'sdk'
            (bundle/'payload/native').mkdir(parents=True)
            (bundle/'payload/src/ares_r/perception').mkdir(parents=True)
            (bundle/'payload/native/jaka_joint_mirror.cpp').write_text('// test fixture')
            (bundle/'payload/src/ares_r/perception/chassis_policy.py').write_text('# test fixture')
            files = [{'path': str(p.relative_to(bundle)), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                     for p in (bundle/'payload').rglob('*') if p.is_file()]
            (bundle/'MANIFEST.json').write_text(json.dumps(dict(files=files)))
            (root/'config').mkdir(parents=True)
            (root/'.venv/bin').mkdir(parents=True)
            (root/'.venv/bin/python').touch()
            (root/'config/system.json').write_text('{}')
            (root/'config/robot_collision_model.json').write_text(json.dumps(dict(
                fixed_body_boxes=[dict(owner='chassis', geometry_id='body/chassis')], custom='keep')))
            offsets = root/'config/offsets.json'
            offsets.write_text('{"offset":123}')
            sdk.mkdir()
            (sdk/'JAKAZuRobot.h').write_text('get_robot_status_simple')
            calls = []

            def command(argv, **kwargs):
                calls.append(argv)
                if argv[0] == 'g++':
                    Path(argv[-1]).write_bytes(b'fixture-binary')
                code = 2 if len(argv) == 1 and Path(argv[0]).name == 'jaka_joint_mirror' else 0
                return subprocess.CompletedProcess(argv, code, '', '')

            args = SimpleNamespace(root=root, secondary_root=root, apply=True,
                sdk_include=sdk, sdk_lib=base, restart_services=False)
            with patch.object(INSTALLER, '__file__', str(bundle/'install.py')), \
                 patch.object(INSTALLER.platform, 'system', return_value='Linux'), \
                 patch.object(INSTALLER, 'api', side_effect=URLError('offline')), \
                 patch.object(INSTALLER.subprocess, 'run', side_effect=command):
                INSTALLER.install(args)
            model = json.loads((root/'config/robot_collision_model.json').read_text())
            self.assertFalse(model['geometry_policy']['chassis_collision_enabled'])
            self.assertEqual(model['custom'], 'keep')
            self.assertEqual(offsets.read_text(), '{"offset":123}')
            backup = next((root/'worklog/preservation').glob('onsite-ready-*'))
            changes = json.loads((backup/'changes.json').read_text())
            self.assertEqual(sum(row['path'].endswith('robot_collision_model.json') for row in changes), 1)
            self.assertFalse(any('--snapshot' in call or 'EXECUTE_MIRROR' in call for call in calls))
