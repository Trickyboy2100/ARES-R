import copy,fcntl,hashlib,json,math,os,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from ares_r.manipulation.task_contract import TASK_ID,load_contract,task_config,check_epoch,check_task_start
from ares_r.manipulation.task_contract import TASK_SOURCES,bind_task,verify_task,center_goal,check_center
from ares_r.motion.controller_read_lease import controller_read_lease

ROOT=Path(__file__).resolve().parents[1]

class ShaiwangContractTests(unittest.TestCase):
    def setUp(self):self.task=load_contract(ROOT)
    def test_profile_is_task_local_not_global_mutation(self):
        original={'epic':{'task_profiles':{'right_pick':{'command':'320,2,1,1,1,0','space_id':2,'object_id':1,'camera_id':1}}}}
        before=copy.deepcopy(original);result=task_config(original,self.task)
        self.assertEqual(original,before);self.assertEqual(result['epic']['task_profiles']['right_pick']['object_id'],6)
        self.assertEqual(result['epic']['task_profiles']['right_pick']['command'],'320,2,6,1,1,0')
    def test_global_center_and_compensation_are_readonly(self):
        import numpy as np
        params=ROOT/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json'
        poses=ROOT/'config/named_poses.json';before=(params.read_bytes(),poses.read_bytes())
        goal=center_goal(ROOT);t=np.eye(4);t[:3,3]=goal['position_m'];t[:3,:3]=goal['explicit_rotation']
        telemetry={'arms':{'right':{'T_body_tcp':t.tolist()}},'errors':{}}
        self.assertTrue(check_center(ROOT,telemetry,self.task)['passed'])
        self.assertAlmostEqual(goal['position_m'][0],.3583093030168863)
        self.assertEqual((params.read_bytes(),poses.read_bytes()),before)
        t[2,3]-=.032;telemetry['arms']['right']['T_body_tcp']=t.tolist()
        with self.assertRaisesRegex(ValueError,'START_NOT_GLOBAL_CENTER'):check_center(ROOT,telemetry,self.task)
    def test_separate_body_target_translation_and_demo_yaw_roundtrip(self):
        import numpy as np
        from scipy.spatial.transform import Rotation
        from ares_r.manipulation.task_tcp_offset import apply_task_pose,demo_local_rotation
        raw=Rotation.from_euler('xyz',[.4,-.3,1.2]).as_matrix();xyz=[.6,-.2,1.0]
        params=json.loads((ROOT/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json').read_text())
        comp=dict(params['demo_tcp_orientation_compensation']);comp.update(self.task['demo_tcp_orientation_compensation_override'])
        p,r=apply_task_pose(xyz,raw,self.task['task_tcp_offset_m_rad_override'])
        self.assertTrue(np.allclose(p,[.605,-.2,.993]));self.assertTrue(np.allclose(r,raw))
        adjusted=demo_local_rotation(r,{'demo_tcp_orientation_compensation':comp})
        expected=Rotation.from_euler('z',4,degrees=True).as_matrix()@raw@Rotation.from_euler('z',-10,degrees=True).as_matrix()
        self.assertTrue(np.allclose(adjusted,expected))
        self.assertTrue(np.allclose(demo_local_rotation(adjusted,{'demo_tcp_orientation_compensation':comp},inverse=True),raw))
        center=center_goal(ROOT)
        self.assertAlmostEqual(center['position_m'][2],1.0278356006116391)
        self.assertNotEqual(self.task['task_tcp_offset_m_rad_override'][:3],center['position_m'])
    def test_yesterday_measured_start_difference_passes_new_task_only(self):
        q=[0]*6;q[3]=math.radians(.022619)
        self.assertLess(check_task_start(q,[0]*6,self.task)['max_joint_difference_deg'],.1)
        self.assertGreater(abs(q[3]),math.radians(.02))
    def test_start_difference_over_task_bound_rejected(self):
        with self.assertRaises(ValueError):check_task_start([math.radians(.101)]+[0]*5,[0]*6,self.task)
        with self.assertRaises(ValueError):check_task_start([float('nan')]+[0]*5,[0]*6,self.task)
    def test_epoch_id1_not_accepted_for_task_id6(self):
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/'epic_5700_detection.json';meta={'space_id':2,'object_id':1,'robot_arm':'right','request_command':'320,2,1,1,1,0'}
            file.write_text(json.dumps({'success':True,'meta':meta}))
            with self.assertRaises(ValueError):check_epoch(d,self.task)
            meta.update(object_id=6,request_command='320,2,6,1,1,0');file.write_text(json.dumps({'success':True,'meta':meta}))
            self.assertTrue(check_epoch(d,self.task)['success'])
    def test_invalid_task_scope_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'demos'/TASK_ID/'params.json';path.parent.mkdir(parents=True)
            value=dict(self.task,base_motion_allowed=True);path.write_text(json.dumps(value))
            with self.assertRaises(ValueError):load_contract(d)
    def test_original_golden_motion_sources_not_changed(self):
        pinned=json.loads((ROOT/'demos/right_arm_pick_lift_replace_reset_v1/pinned_inputs.json').read_text())['sha256']
        for path,expected in pinned.items():
            if path.startswith('scripts/') or path.endswith('pick_reset_pipeline.py'):
                self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),expected,path)
    def test_native_source_keeps_old_mode_tolerance_and_controller_protection(self):
        source=(ROOT/'demos'/TASK_ID/'native_sender.cpp').read_text()
        self.assertIn('task_path?.1:.02',source);self.assertIn('status.errcode',source)
        self.assertIn('isInCollision',source);self.assertIn('isOnLimit',source);self.assertIn('parent',source)
    def test_new_runner_uses_explicit_task_profile_and_new_sender_mode(self):
        source=(ROOT/'scripts/run_task_pick_reset_timing.py').read_text()
        self.assertIn("live=make_task_live(legacy.Live",source)
        self.assertIn("client._detect_profile(task['epic_profile']",source)
        self.assertIn("'task_supervised_path'",source)
        self.assertNotIn("'ID1 target confirmation failed'",source)
    def test_stage1_live_does_not_depend_on_old_place_profile(self):
        from ares_r.manipulation.task_live import make_task_live
        class ExistingLive:
            def __init__(self,*args):raise AssertionError('old ID1/ID3 constructor must not run')
            def inherited_io(self):return 'existing'
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'config').mkdir();out=root/'execution';out.mkdir()
            config={'epic':{'task_profiles':{'right_pick':{'arm':'right','command':'320,2,1,1,1,0'}}}}
            (root/'config/system.json').write_text(json.dumps(config))
            value=make_task_live(ExistingLive,{},out,lambda *x:None,root,self.task)
            try:
                self.assertEqual(value.config['epic']['task_profiles']['right_pick']['object_id'],6)
                self.assertEqual(value.inherited_io(),'existing')
                self.assertNotIn('right_place_rightmost',value.config['epic']['task_profiles'])
            finally:value.pool.shutdown()
    def test_monitor_never_logs_in_on_idle_status_page(self):
        from ares_r.demos.console_monitor import ConsoleMonitor
        backend=SimpleNamespace(_base_running=False,_physical_process=None,_robot_cache=None,
            roundtrip=SimpleNamespace(_running=lambda _:False,_meta=lambda:{}),dispatcher=Mock())
        console=SimpleNamespace(backend=backend,active=lambda:False)
        result=ConsoleMonitor(console)._feedback({},None)
        self.assertEqual(result['arms'],{});backend.dispatcher.robot_telemetry.assert_not_called()
    def test_monitor_displays_cached_actual_without_updating_timestamp(self):
        from ares_r.demos.console_monitor import ConsoleMonitor
        backend=SimpleNamespace(_base_running=False,_physical_process=None,
            _robot_cache={'captured_at_unix':1,'arms':{'right':{'joints_rad':[0]*6}}},
            roundtrip=SimpleNamespace(_running=lambda _:False,_meta=lambda:{}),dispatcher=Mock())
        console=SimpleNamespace(backend=backend,active=lambda:False)
        result=ConsoleMonitor(console)._feedback({},None)
        self.assertEqual(result['captured_at_unix'],1);self.assertFalse(result['arms']['right']['fresh'])
    def test_native_exclusive_owner_defers_sdk_reader(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'owner.lock'
            with path.open('w') as owner:
                fcntl.flock(owner,fcntl.LOCK_EX|fcntl.LOCK_NB)
                with self.assertRaisesRegex(RuntimeError,'SDK_READ_DEFERRED'):
                    with controller_read_lease(path):self.fail('must not read SDK')
            with controller_read_lease(path):pass
    def test_reader_holds_exclusive_lease_until_sdk_batch_finishes(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'owner.lock'
            with controller_read_lease(path),path.open('r+') as owner:
                with self.assertRaises(BlockingIOError):fcntl.flock(owner,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with path.open('r+') as owner:fcntl.flock(owner,fcntl.LOCK_EX|fcntl.LOCK_NB)
    def test_two_sdk_readers_are_also_serialized(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'owner.lock'
            with controller_read_lease(path):
                with self.assertRaisesRegex(RuntimeError,'SDK_READ_DEFERRED'):
                    with controller_read_lease(path):self.fail('must not open second SDK batch')
    def test_level_env_does_not_change_unrelated_golden(self):
        import numpy as np
        from ares_r.motion.tcp_orientation import validate_level_path
        with patch.dict(os.environ,{'ARES_R_LEVEL_TOLERANCE_DEG':'90','ARES_R_ACTIVE_MANIPULATION_TASK':''}):
            # Missing/invalid context must not turn the prior global override on.
            a=validate_level_path(lambda q:np.eye(4),[[0]*6,[0]*6],tolerance_deg=3)
            self.assertEqual(a['tolerance_deg'],3)
    def fake_binding(self,root):
        definition=root/'demos'/TASK_ID;definition.mkdir(parents=True)
        (definition/'params.json').write_text(json.dumps(self.task))
        for name in TASK_SOURCES:
            file=root/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_text('task source')
        params={'task_tcp_offset_m_rad':[0]*6,'demo_tcp_orientation_compensation':{'enabled':True,'angle_deg':-10}}
        original=root/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json';original.parent.mkdir(parents=True)
        original.write_text(json.dumps(params))
        golden=root/'demos/right_arm_pick_lift_replace_reset_v1/pinned_inputs.json';golden.parent.mkdir(parents=True)
        golden.write_text(json.dumps({'sha256':{}}))
        prepared=root/'prepared';(prepared/'epoch').mkdir(parents=True);(prepared/'package').mkdir()
        detection={'success':True,'meta':{'space_id':2,'object_id':6,'robot_arm':'right','request_command':'320,2,6,1,1,0'}}
        (prepared/'epoch/epic_5700_detection.json').write_text(json.dumps(detection))
        (prepared/'package/first_pick_execution_package.json').write_text(json.dumps({'package_sha256':'package'}))
        manifest={'parameters':params,'package_sha256':'package','scene_snapshot_id':'scene','pointcloud_sha256':'cloud'}
        (prepared/'native-manifest.json').write_text(json.dumps(manifest));bind_task(prepared,root)
        return prepared,original
    def test_binding_rejects_code_change_after_preview(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);prepared,_=self.fake_binding(root)
            self.assertEqual(verify_task(prepared,root)['demo_id'],TASK_ID)
            (root/TASK_SOURCES[0]).write_text('changed code')
            with self.assertRaisesRegex(ValueError,'task source changed'):verify_task(prepared,root)
    def test_binding_rejects_offset_change_after_preview(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);prepared,original=self.fake_binding(root)
            original.write_text(json.dumps({'task_tcp_offset_m_rad':[.01,0,0,0,0,0]}))
            with self.assertRaisesRegex(ValueError,'offsets/parameters changed'):verify_task(prepared,root)

if __name__=='__main__':unittest.main()
