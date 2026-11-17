import json,sys,threading,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dual_center_restore.core import sequence
from dual_center_restore.console import definition


def poses():return {a:dict(arm=a,joints_rad=[0.]*6,T_body_tcp=[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]],tool_id=2 if a=='left' else 3) for a in ['left','right']}

class Provider:
    def __init__(self):self.barrier=threading.Barrier(2);self.executed=[];self.events=[];self.stopped=False
    def capabilities(self):return dict.fromkeys(['fresh_dual_state','fresh_scene','left_curobo','right_curobo','pair_swept_collision','pair_native_barrier','stop_both','verify_both_tcp'],True)
    def check_cancelled(self):pass
    def observe_both(self):return {'arms':poses()}
    def scan(self,state):self.events.append('scan');return {'id':len(self.events)}
    def centers(self):return poses()
    def plan(self,arm,*args):self.barrier.wait(timeout=2);return {'arm':arm}
    def validate_pair(self,*args):return {'passed':True}
    def execute_pair(self,plans,binding):self.executed.append(binding)
    def verify_both(self,goals):return {a:{'passed':True} for a in ['left','right']}
    def invalidate_scene(self,reason):self.events.append(reason)
    def stop_both(self):self.stopped=True

class ContractTests(unittest.TestCase):
    def test_two_concurrent_phases_and_fresh_scene_per_phase(self):
        p=Provider();r=sequence(p,poses(),True)
        self.assertTrue(r['success']);self.assertEqual(len(p.executed),2)
        self.assertEqual(p.events.count('scan'),2)
        self.assertNotEqual(p.executed[0],p.executed[1])
        self.assertTrue(r['return_to_saved_pose_verified'])
    def test_missing_left_provider_blocks_before_any_execution(self):
        p=Provider();p.capabilities=lambda:{};r=sequence(p,poses(),True)
        self.assertFalse(r['success']);self.assertEqual(p.executed,[])
    def test_one_arm_failure_is_not_pair_success_and_stops_both(self):
        p=Provider();p.verify_both=lambda _: {'left':{'passed':False},'right':{'passed':True}}
        r=sequence(p,poses(),True);self.assertFalse(r['success']);self.assertTrue(p.stopped);self.assertEqual(len(p.executed),1)
    def test_no_motion_in_prepare(self):
        p=Provider();r=sequence(p,poses(),False);self.assertTrue(r['success']);self.assertFalse(r['return_to_saved_pose_verified']);self.assertEqual(p.executed,[])
    def test_no_delivered_label(self):
        d=definition();self.assertEqual(d['tags'],['ROS','Utility']);self.assertFalse(d['delivered']);self.assertFalse(d['execution_ready'])
    def test_action_abi_matches_demo01(self):
        root=Path(__file__).resolve().parents[2]
        old=root/'ros1-blocks-center-restore/ros/ares_r_center_restore/action/CenterRestore.action'
        new=Path(__file__).resolve().parents[1]/'ros/ares_r_dual_center_restore/action/CenterRestore.action'
        if not old.exists():old=Path(__file__).resolve().parents[1]/'reference/Demo01_CenterRestore.action'
        self.assertEqual(old.read_bytes(),new.read_bytes())
