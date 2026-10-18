"""Site adapter contracts with fake I/O, never a claim of SDK/GPU commissioning."""
import copy,importlib.util,json,math,tempfile,time,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from ares_r.manipulation.live_roundtrip_contract import validate_hold_readback,validate_resume_telemetry,perception_profile_contract
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('roundtrip_site',ROOT/'scripts/run_grasp_place_roundtrip.py');site=importlib.util.module_from_spec(spec);spec.loader.exec_module(site)
class LiveContracts(unittest.TestCase):
 def setUp(self):
  self.p=json.loads((ROOT/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json').read_text());self.tmp=tempfile.TemporaryDirectory();self.out=Path(self.tmp.name)
  self.live=object.__new__(site.Live);self.live.p=self.p;self.live.out=self.out;self.live.attached={'revision':'test'};self.live.preland_arrived=True;self.live.release_confirmed=False
 def tearDown(self):self.tmp.cleanup()
 def telemetry(self):return {'arms':{s:{'joints_rad':[0]*6,'tool_id':1} for s in ('left','right')},'base':{'info':{'mapId':'map','x':0.,'y':0.,'yawNumber':0.}}}
 def test_actual_live_resume_uses_existing_release_key(self):
  self.assertNotIn('gripper_open_raw',self.p);v=self.telemetry();self.live.resume_snapshot={'telemetry':v};self.live.telemetry=lambda:v;self.live.grasp_state='GRASP_CONFIRMED'
  def command(args,path,timeout):Path(path).write_text(json.dumps({'position_raw':37,'captured_at_unix':time.time()}))
  self.live.command=command;self.live.validate_resume({})
  self.live.command=lambda args,path,timeout:Path(path).write_text(json.dumps({'position_raw':400,'captured_at_unix':time.time()}))
  with self.assertRaisesRegex(RuntimeError,'HELD_OBJECT_UNCERTAIN'):self.live.validate_resume({})
 def test_hold_thresholds_and_timestamps_fail_closed(self):
  for raw,stamp in [(0,100),(400,100),(37,90),(float('nan'),100),(37,float('nan'))]:
   with self.assertRaises(RuntimeError):validate_hold_readback(self.p,{'position_raw':raw,'captured_at_unix':stamp},now=101)
  validate_hold_readback(self.p,{'position_raw':37,'captured_at_unix':100},now=101)
 def test_release_confirmed_checkpoint_does_not_recheck_empty_gripper_as_hold(self):
  self.live._mark_dispatch=Mock();self.live.check_cancelled=Mock();self.live.grasp_state='GRASP_CONFIRMED'
  def command(args,path,timeout):Path(path).write_text(json.dumps({'position_raw':400,'captured_at_unix':time.time()}))
  self.live.command=command
  with patch.object(site.time,'sleep'):result=self.live.gripper(400)
  self.assertTrue(result['release_confirmed']);self.assertEqual(self.live.grasp_state,'RELEASE_CONFIRMED')
  v=self.telemetry();self.live.resume_snapshot={'telemetry':v};self.live.telemetry=lambda:v;self.live.command=Mock(side_effect=AssertionError('no extra gripper command'))
  self.live.validate_resume({});self.live.invalidate=Mock();self.live.detach();self.assertIsNone(self.live.attached)
 def test_unsafe_release_and_detach_never_dispatch(self):
  self.live.preland_arrived=False;self.live._mark_dispatch=Mock();self.live.command=Mock()
  with self.assertRaisesRegex(RuntimeError,'PRELAND'):self.live.gripper(400)
  self.live.command.assert_not_called()
  with self.assertRaisesRegex(RuntimeError,'RELEASE_NOT_CONFIRMED'):self.live.detach()
 def test_profile_id_binding_and_map_finite(self):
  cfg=json.loads((ROOT/'config/system.json').read_text());perception_profile_contract(self.p,cfg)
  cfg['epic']['task_profiles']['right_place_rightmost']['object_id']=2
  with self.assertRaisesRegex(RuntimeError,'PROFILE_MISMATCH'):perception_profile_contract(self.p,cfg)
  expected=self.telemetry();actual=copy.deepcopy(expected);actual['base']['info']['x']=float('nan')
  with self.assertRaisesRegex(RuntimeError,'NONFINITE'):validate_resume_telemetry(actual,expected)
 def test_live_attach_preland_and_scene_metadata_path(self):
  self.live.package={'coarse_attached_object_collision':{'revision':'rev','object_id':'tray'}}
  self.live.verify_grasp=Mock(return_value={'verification':{'state':'GRASP_CONFIRMED'}});self.live.attach();self.live.verify_grasp.assert_called_once_with('POST_LIFT')
  self.assertEqual(self.live.attached['revision'],'rev')
  self.live.preland=[.7,-.2,1.1];self.live.free_move=Mock(return_value={'state':'SUCCEEDED'});self.live.preland_arrived=False
  self.live.move_preland();self.assertTrue(self.live.preland_arrived)
 def test_uncertain_physical_receipt_is_never_reissued(self):
  self.live.command_records=self.out;self.live.command_id='job:CLOSE';self.live._mark_dispatch('gripper:0')
  result=self.live.reconcile({'call':'gripper'},self.live.command_id)
  self.assertEqual(result['outcome'],'UNCERTAIN')
 def test_formal_telemetry_retries_actual_minimal_left_reads(self):
  from ares_r.scene_aware_dispatch import SceneAwareDispatcher
  from types import SimpleNamespace
  dispatcher=object.__new__(SceneAwareDispatcher);dispatcher.config=json.loads((ROOT/'config/system.json').read_text());dispatcher.operations=SimpleNamespace(root=ROOT)
  left=Mock();right=Mock();d={'joint_position_rad':[0]*6,'tcp_position_mm_rad':[0,0,1000,0,0,0],'tool_id':1,'robot_status':{}}
  left.planning_state.side_effect=[SystemError('transient'),SystemError('transient'),d];right.diagnostics.return_value=d
  with patch('ares_r.adapters.jaka_sdk.JakaSdkArm',side_effect=[left,right]),patch('ares_r.adapters.amr_http.AmrHttpBase') as base,patch('ares_r.motion.arrival_contract.time.sleep'):
   base.return_value._request.return_value={'info':{'mapId':'m'}};result=dispatcher.robot_telemetry()
  self.assertEqual(left.planning_state.call_count,3);self.assertEqual(result['arms']['left']['joints_rad'],[0]*6);self.assertFalse(result['errors'])
 def test_formal_free_move_passes_attached_identity_to_fresh_planner(self):
  plan=self.out/'plan';plan.mkdir();(plan/'planning.json').write_text(json.dumps({'trajectory_points_rad':[[0]*6,[.1]*6]}));(plan/'planner_request.json').write_text('{}')
  self.live.config={'curobo':{'timeout_s':30}};self.live.event=Mock();self.live.check_cancelled=Mock();self.live._level=Mock(return_value={'passed':True});self.live._settle=Mock(return_value={'state':'ARRIVED'})
  self.live.get=lambda p:{'base_pose_revision':3} if p.endswith('/status') else {'state':'SUCCEEDED','execution_result':{'target_reached':True}}
  # run-status is a different suffix and returns the actual completion contract.
  self.live.get=lambda p:({'base_pose_revision':3} if p=='/api/scene/status' else {'state':'SUCCEEDED','execution_result':{'target_reached':True}})
  calls=[]
  def post(path,payload,**kwargs):
   calls.append((path,payload))
   if path=='/api/motion/plan':return {'plan_id':'P','trajectory_hash':'h','execution_package_ready':True,'plan_artifact':str(plan)}
   return {'state':'RUNNING'}
  self.live.post=post;self.live.free_move([.7,-.2,1.1],'HOLD230')
  request=calls[0][1];self.assertEqual(request['scene_policy'],'AUTO_FRESH');self.assertIs(request['attached_object_geometry'],self.live.attached);self.assertEqual(request['attached_object_revision'],'test')
