import hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
from ares_r.demos import DemoRegistry

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('formal_pick_reset',ROOT/'scripts/run_pick_reset_demo.py')
client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client)

class FormalPickResetDemoTests(unittest.TestCase):
    def test_catalog_contains_separate_formal_demo_without_replacing_golden(self):
        with tempfile.TemporaryDirectory() as d:
            registry=DemoRegistry(ROOT/'demos',Path(d)/'state.json')
            formal=registry.inspect(client.DEMO)
            self.assertEqual(formal['version'],'1.0.0')
            self.assertEqual(registry.inspect('right_arm_epic_pick_lift_v1')['execution']['entrypoint'],
                             'scripts/run_first_pick_demo.py')
            registry.select(client.DEMO)
            self.assertIn('run_pick_reset_demo.py',registry.prepare()['run_command'])
    def test_pinned_inputs_and_parameter_drift_are_checked(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);formal=root/'demos'/client.DEMO;formal.mkdir(parents=True)
            original=root/'demos/right_arm_grasp_place_roundtrip_v1';original.mkdir()
            (formal/'source_parameters.json').write_text('{"speed":1}')
            source=original/'parameters.json';source.write_text('{"speed":1}')
            file=root/'runner.py';file.write_text('preserved source')
            (formal/'pinned_inputs.json').write_text(json.dumps({'sha256':{'runner.py':hashlib.sha256(file.read_bytes()).hexdigest()}}))
            client.verify_pinned_inputs(root)
            file.write_text('changed source')
            with self.assertRaisesRegex(RuntimeError,'pinned input changed'):client.verify_pinned_inputs(root)
            source.write_text('{"speed":2}')
            with self.assertRaisesRegex(RuntimeError,'parameters differ'):client.verify_pinned_inputs(root)
    def test_no_authorization_means_no_prepare_or_start(self):
        with patch.object(client,'ROOT',client.SITE_ROOT),patch('sys.argv',['demo','--execute']),\
             patch.object(client,'request') as api,patch.object(client.subprocess,'run') as process:
            with self.assertRaises(PermissionError):client.main()
            api.assert_not_called();process.assert_not_called()
    def test_client_reuses_existing_preparation_and_canonical_execution(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);started={}
            def api(path,body=None):
                if path=='/api/demo/roundtrip/status':return {'runtime_binding':{'repository_root':str(root)}}
                if path.endswith('/start'):
                    started.update(body);return {'state':'RUNNING'}
                if path.endswith('/run-status'):
                    return dict(state='SUCCEEDED',study_state='COMPLETED',study_output=str(Path(started['prepared'])/'execution'))
                raise AssertionError(path)
            with patch.object(client,'ROOT',root),patch.object(client,'SITE_ROOT',root),\
                 patch('sys.argv',['demo','--execute','--authorization',client.AUTH,'--onsite-observer-confirmed']),\
                 patch.object(client,'verify_pinned_inputs'),patch.object(client,'request',side_effect=api),\
                 patch.object(client.subprocess,'run') as command:
                client.main()
            self.assertEqual(command.call_count,2)
            self.assertIn('prepare_pick_reset_bundle.py',str(command.call_args_list[0].args[0]))
            self.assertEqual(command.call_args_list[1].args[0][-2:],['--segments','pregrasp,contact,retreat,center'])
            self.assertEqual(started['authorization'],client.AUTH)
