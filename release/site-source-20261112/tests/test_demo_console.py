"""Non-motion tests for the additive Golden console and read-only monitor."""
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from ares_r.demos.console import DemoConsole
from ares_r.demos.console_monitor import ConsoleMonitor
from ares_r.demos.registry import DemoRegistry

ROOT=Path(__file__).resolve().parents[1]


class ConsoleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        (self.root/'demos').mkdir()
        (self.root/'demos/catalog_aliases.json').write_bytes((ROOT/'demos/catalog_aliases.json').read_bytes())
        self.backend=SimpleNamespace(root=self.root,_physical_guard=threading.Lock(),
            _base_running=False,_physical_process=None,roundtrip=Mock(),dispatcher=Mock(),
            physical_status=Mock(return_value={'state':'IDLE'}),operations_stop=Mock())
        self.console=DemoConsole(self.backend)
    def tearDown(self):self.tmp.cleanup()
    def body(self,alias='demo-2-branch-grasprptspdup'):
        return dict(alias=alias,authorization='RUN '+alias,onsite_observer_confirmed=True,
                    prepared_environment_confirmed=True,request_id='one-click')
    def test_catalog_preserves_three_original_goldens_and_adds_sift(self):
        values=self.console.catalog()['demos']
        goldens=[v for v in values if v['demo_type']=='GOLDEN']
        self.assertEqual(len(goldens),4)
        self.assertEqual(goldens[0]['alias'],'demo-3-branch-sift-graspreset')
        self.assertEqual(goldens[-1]['demo_id'],'right_arm_pick_lift_replace_reset_v1')
        # 2026-11-02: demo-4 (SIFT抓取抬升→底盘转场→DMP放置→回center) 以候选身份加入
        # 2026-11-06: demo-0 (右臂任意位姿→center) 以 UTILITY 身份加入
        # 2026-11-06: demo-5 (从 demo-4 抽出的 DMP放置→center) 以候选身份加入
        # 2026-11-09: demo-6 (demo-5 的料盘专机拷贝, 预放置=检测点+60mm, 放置=检测点)
        # 2026-11-11: demo-2-liaopan-placeto-hongganxiang (demo-6 拷贝, ID3 检测 + lower_middle 泊位)
        candidates=[v for v in values if v['demo_type']!='GOLDEN']
        self.assertEqual([v['alias'] for v in candidates],
                         ['demo-0-return-center','demo-4-main-siftgrasp-dmpplace','demo-5-main-dmpplace',
                          'demo-6-liaopan-placetoDMP','demo-2-liaopan-placeto-hongganxiang'])
        self.assertEqual([v['demo_id'] for v in candidates],
                         ['right_arm_return_center_v1','right_arm_sift_dmp_roundtrip_v1','right_arm_dmp_place_v1',
                          'right_arm_liaopan_dmp_place_v1','right_arm_liaopan_hongganxiang_place'])
        self.assertEqual(len(values),9)
    def test_creation_does_not_start_threads_or_motion(self):
        self.assertIsNone(self.console.thread);self.assertFalse(self.console.active())
        self.backend.operations_stop.assert_not_called()
    def test_requires_exact_auth_and_preparation(self):
        for field,value in [('authorization','RUN'),('prepared_environment_confirmed',False),('onsite_observer_confirmed',False)]:
            body=self.body();body[field]=value
            with self.assertRaises(PermissionError):self.console.start(body)
    def test_unknown_alias_rejected(self):
        with self.assertRaises(ValueError):self.console.start(self.body('unknown'))
    def test_historical_roundtrip_needs_ack(self):
        with self.assertRaises(PermissionError):self.console.start(self.body('demo-2-main-graspplace'))
    @patch('ares_r.demos.console.threading.Thread')
    def test_click_starts_once_and_isolates_evidence(self,thread):
        first=self.console.start(self.body());second=self.console.start(self.body())
        self.assertEqual(first['run_id'],second['run_id']);self.assertTrue(second['duplicate_suppressed'])
        thread.return_value.start.assert_called_once()
        self.assertTrue((Path(first['output'])/'authorization.json').exists())
        self.assertFalse(first['auto_resume'])
        with self.assertRaises(RuntimeError):self.console.start(dict(self.body(),request_id='new'))
    def test_other_physical_job_blocks_click(self):
        self.backend._base_running=True
        with self.assertRaises(RuntimeError):self.console.start(self.body())
    def test_restart_is_recovery_not_auto_resume(self):
        self.console.update(state='RUNNING')
        restored=DemoConsole(self.backend)
        self.assertEqual(restored.job['state'],'RECOVERY_REQUIRED');self.assertTrue(restored.active())
        restored.request_stop();self.assertTrue(restored.active())
    def test_console_token_not_accepted_empty(self):
        self.console.update(state='PREPARING');self.backend.roundtrip._meta.return_value={}
        self.assertFalse(self.console.permits({}));self.console.token='owner'
        self.assertFalse(self.console.permits({'demo_console_token':'other'}))
        self.assertTrue(self.console.permits({'demo_console_token':'owner'}))
    @patch('ares_r.demos.console.os.killpg')
    def test_stop_only_signals_owned_group(self,kill):
        self.console.child=Mock(pid=12345);self.console.child.poll.return_value=None
        self.console.request_stop();self.assertTrue(self.console.cancel.is_set());kill.assert_called_once()
        self.assertEqual(kill.call_args.args[0],12345)
    def test_warm_planner_reused_not_restarted(self):
        expected=self.console.root/'worklog/runtime/rc1-webui/planner.sock'
        self.console.update(output=str(self.root/'new'))
        with patch('ares_r.motion.planner_service_client.SOCKET',expected),patch('ares_r.motion.planner_service_client.status',return_value={'ok':True}),patch('ares_r.motion.planner_service_client.start') as start:
            self.console.resources();start.assert_not_called()
        self.assertEqual(self.console.job['events'][-1]['stage'],'RESOURCE_READY')
    def test_busy_planner_never_cleaned(self):
        expected=self.console.root/'worklog/runtime/rc1-webui/planner.sock'
        with patch('ares_r.motion.planner_service_client.SOCKET',expected),patch('ares_r.motion.planner_service_client.status',return_value={'ok':True,'active_job_id':'foreign'}),patch('ares_r.motion.planner_service_client.start') as start:
            self.console.update(output='new')
            with self.assertRaises(RuntimeError):self.console.resources()
            start.assert_not_called()
    def test_stop_before_prepare_does_not_run_command(self):
        self.console.cancel.set()
        with patch('ares_r.demos.console.subprocess.Popen') as popen:
            with self.assertRaises(RuntimeError):self.console.command(['false'],'prepare')
            popen.assert_not_called()
    def test_active_monitor_does_not_open_more_sdk_sessions(self):
        self.console.update(state='RUNNING');monitor=ConsoleMonitor(self.console)
        result=monitor._feedback(self.console.job,None)
        self.assertEqual(result['arms'],{});self.backend.dispatcher.robot_telemetry.assert_not_called()
    def test_scene_cache_refreshes_when_capture_files_arrive(self):
        import numpy as np
        scene=self.root/'prepared/epoch/live_scene';(scene/'scene').mkdir(parents=True)
        self.console.update(prepared=str(self.root/'prepared'))
        monitor=ConsoleMonitor(self.console)
        self.assertEqual(monitor.scene_payload()['pointcloud'],[])
        np.savez(scene/'scene/clean_residual.npz',points_body_m=np.array([[.4,-.2,.8]]))
        (scene/'scene/scene_report.json').write_text(json.dumps({'snapshot_id':'fresh','objects':[]}))
        self.assertEqual(monitor.scene_payload()['scene_snapshot'],'fresh')
        self.assertEqual(len(monitor.scene_payload()['pointcloud']),1)
    def test_missed_feedback_not_labelled_fresh(self):
        self.console.update(state='RUNNING');monitor=ConsoleMonitor(self.console)
        monitor.telemetry={'captured_at_unix':1,'arms':{'left':{'joints_rad':[0]*6}}}
        self.assertFalse(monitor._feedback(self.console.job,None)['arms']['left']['fresh'])
    def test_external_physical_task_prevents_extra_sdk_polling(self):
        self.backend._base_running=True;monitor=ConsoleMonitor(self.console)
        monitor._feedback({},None)
        self.backend.dispatcher.robot_telemetry.assert_not_called()
    def test_alias_registry_keeps_original_ids(self):
        registry=DemoRegistry(ROOT/'demos',self.root/'selection.json')
        for row in self.console.catalog()['demos']:
            self.assertEqual(registry.inspect(row['alias'])['demo_id'],row['demo_id'])
            self.assertEqual(registry.select(row['alias'])['selected_demo_id'],row['demo_id'])
    def test_static_page_never_posts_on_load(self):
        html=(ROOT/'src/ares_r/webui/demo_console.html').read_text()
        self.assertIn("el('start').onclick",html)
        self.assertIn('globalThis.crypto?.randomUUID?.()',html)
        self.assertIn('disabled>一键准备',html)

    def prepare_fake_job(self,strategy):
        definition=next(d for d in self.console.catalog()['demos'] if d['strategy']==strategy)
        out=self.root/'run';out.mkdir()
        self.console.update(state='PREPARING',strategy=strategy,run_id='fake',output=str(out))
        return definition

    def test_pick_reset_adapter_runs_existing_pipeline_only(self):
        definition=self.prepare_fake_job('pick_reset')
        self.backend.start_pick_reset_timing=Mock()
        self.backend.physical_status.return_value={'state':'SUCCEEDED','study_state':'COMPLETED'}
        with patch.object(self.console,'resources'),patch.object(self.console,'command') as command,patch('runpy.run_path',return_value={'verify_pinned_inputs':Mock()}):
            self.console._run(definition)
        self.assertEqual(self.console.job['state'],'SUCCEEDED')
        self.assertEqual(command.call_count,2)
        self.assertIn('prepare_pick_reset_bundle.py',str(command.call_args_list[0]))
        self.backend.start_pick_reset_timing.assert_called_once()

    def test_sift_adapter_delegates_verified_client_and_requires_full_cycle_proof(self):
        definition=self.prepare_fake_job('sift_pick_reset')
        prepared=self.root/'sift-run';(prepared/'execution').mkdir(parents=True)
        result=dict(result='PICK_LIFT_REPLACE_RESET_COMPLETE',reset_complete=True)
        (prepared/'execution/result.json').write_text(json.dumps(result))
        self.backend.physical_status.return_value=dict(state='SUCCEEDED',task_demo_id='right_arm_shaiwang_pick_reset_v1',study_output=str(prepared/'execution'))
        with patch.object(self.console,'resources'),patch.object(self.console,'command') as command:
            self.console._run(definition)
        self.assertEqual(self.console.job['state'],'SUCCEEDED')
        self.assertEqual(command.call_count,1)
        self.assertIn('scripts/run_sift_pick_reset_demo.py',command.call_args.args[0])
        self.assertEqual(self.console.job['prepared'],str(prepared))

    def test_dmp_place_adapter_requires_full_chain_proof(self):
        definition=self.prepare_fake_job('dmp_place')
        run_dir=self.root/'worklog/evidence/demo-runs/right_arm_dmp_place_v1';run_dir.mkdir(parents=True)
        (run_dir/'last-run.json').write_text(json.dumps(dict(result='PLACE_CENTER_COMPLETE',
            states={'place':'PLACED_AND_RELEASED','center':'AT_CENTER'},run_dir=str(run_dir))))
        with patch.object(self.console,'resources'),patch.object(self.console,'command') as command:
            self.console._run(definition)
        self.assertEqual(self.console.job['state'],'SUCCEEDED')
        self.assertIn('scripts/run_dmp_place_demo.py',command.call_args.args[0])
        self.assertEqual(self.console.job['prepared'],str(run_dir))

    def test_liaopan_dmp_place_adapter_uses_its_own_demo_id_and_evidence(self):
        definition=next(d for d in self.console.catalog()['demos'] if d['alias']=='demo-6-liaopan-placetoDMP')
        out=self.root/'run6';out.mkdir()
        self.console.update(state='PREPARING',strategy='dmp_place',run_id='fake6',output=str(out))
        run_dir=self.root/'worklog/evidence/demo-runs/right_arm_liaopan_dmp_place_v1';run_dir.mkdir(parents=True)
        (run_dir/'last-run.json').write_text(json.dumps(dict(result='PLACE_CENTER_COMPLETE',
            states={'place':'PLACED_AND_RELEASED','center':'AT_CENTER'},run_dir=str(run_dir))))
        with patch.object(self.console,'resources'),patch.object(self.console,'command') as command:
            self.console._run(definition)
        self.assertEqual(self.console.job['state'],'SUCCEEDED')
        args=command.call_args.args[0]
        self.assertIn('scripts/run_dmp_place_demo.py',args)
        self.assertEqual(args[args.index('--demo-id')+1],'right_arm_liaopan_dmp_place_v1')
        self.assertEqual(self.console.job['prepared'],str(run_dir))
        self.assertEqual(definition['demo_id'],'right_arm_liaopan_dmp_place_v1')

    def test_sift_golden_freeze_and_station_are_verified_without_motion(self):
        import runpy,shutil
        helper=runpy.run_path(str(ROOT/'scripts/run_sift_pick_reset_demo.py'))
        self.assertTrue(helper['verify_pinned_inputs'](ROOT)['verified'])
        definition=ROOT/'demos/right_arm_sift_pick_lift_replace_reset_v1'
        golden=self.root/'demos/right_arm_sift_pick_lift_replace_reset_v1'
        shutil.copytree(definition,golden)
        pins=json.loads((definition/'pinned_inputs.json').read_text())['sha256']
        for name in pins:
            dst=self.root/name;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes((ROOT/name).read_bytes())
        station=self.root/'config/manipulation_stations.json';station.parent.mkdir(exist_ok=True)
        station.write_bytes((ROOT/'config/manipulation_stations.json').read_bytes())
        helper['verify_pinned_inputs'](self.root)
        data=json.loads(station.read_text());data['stations']['SIFT-BLC-GRSP']['slam_pose']['x_m']+=.1
        station.write_text(json.dumps(data))
        with self.assertRaisesRegex(RuntimeError,'registration changed'):helper['verify_pinned_inputs'](self.root)

    def test_first_pick_adapter_uses_untouched_legacy_script(self):
        definition=self.prepare_fake_job('first_pick');(self.root/'logs').mkdir()
        def command(args,name,**kwargs):
            state={'prepared_run_dir':str(self.root/'legacy'),'last_run':{'result':'PASS_HOLD_AFTER_LIFT'}}
            (self.root/'logs/demo_runtime.json').write_text(json.dumps(state))
        with patch.object(self.console,'resources'),patch.object(self.console,'command',side_effect=command) as run:
            self.console._run(definition)
        self.assertEqual(self.console.job['state'],'SUCCEEDED')
        self.assertTrue(run.call_args.kwargs['tty'])
        self.assertIn('scripts/run_first_pick_demo.py',run.call_args.args[0])

    def test_roundtrip_adapter_uses_existing_launcher(self):
        definition=self.prepare_fake_job('roundtrip');self.backend.roundtrip_start=Mock()
        self.backend.roundtrip_status=Mock(side_effect=[{'contract_sha256':'bound'},
            {'state':'SUCCEEDED','running':False,'result':{'result':'RETURNED_GRASP'}}])
        with patch.object(self.console,'resources'):self.console._run(definition)
        self.assertEqual(self.console.job['state'],'SUCCEEDED')
        self.assertEqual(self.backend.roundtrip_start.call_args.args[0]['contract_sha256'],'bound')

    def test_legacy_execution_failure_keeps_uncertain_owner_locked(self):
        definition=self.prepare_fake_job('first_pick');self.console.update(state='RUNNING')
        with patch.object(self.console,'resources',side_effect=RuntimeError('native fault')):
            self.console._run(definition)
        self.assertEqual(self.console.job['state'],'RECOVERY_REQUIRED')
        self.assertTrue(self.console.active());self.backend.operations_stop.assert_called_once()


if __name__=='__main__':unittest.main()
