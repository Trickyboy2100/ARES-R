import json
import threading
import unittest
from pathlib import Path

from ares_r.manipulation.pick_reset_pipeline import (
    bind_geometry_proof,reuse_geometry_proof,collect_during_scene,
    stationary_window,StationaryBaseMonitor)
from ares_r.manipulation.grasp_verification import verify_grasp_phase


class PickResetPipelineTests(unittest.TestCase):
    def test_slow_scene_keeps_genuine_recent_window(self):
        lock=threading.Lock();scene_ready=threading.Event();clock=[1000.];count=[0]
        def read(index):
            with lock:
                clock[0]+=.5;count[0]+=1
                result=dict(action='read',position_raw=36,captured_at_unix=clock[0])
                if count[0]>=20:scene_ready.set()
                return result
        def scene():
            if not scene_ready.wait(2):raise RuntimeError('reader did not run')
            return 'real-scene-artifact'
        result,rows=collect_during_scene(scene,read,interval_s=.001,clock=lambda:clock[0])
        self.assertEqual(result,'real-scene-artifact');self.assertEqual(len(rows),3)
        self.assertGreaterEqual(clock[0],1010.)
        self.assertLessEqual(clock[0]-rows[-1]['captured_at_unix'],.5)
        params=json.loads((Path(__file__).resolve().parents[1]/'config/tray_to_groove_v2.json').read_text())
        delta=dict(before_voxels=100,after_voxels=30,removed_voxels=80,removed_fraction=.8,
                   added_fraction=.1,revision='genuine-test-window')
        proof=verify_grasp_phase(delta,rows,params,phase='POST_LIFT',initial_lift_arrived=True,
            lift_displacement_m=.23,expected_lift_m=.23,now=clock[0])
        self.assertEqual(proof['result'],'PASS')
        # The original early window still fails the unchanged five-second rule.
        old=[dict(r,captured_at_unix=1000.+i*.5) for i,r in enumerate(rows)]
        self.assertFalse(verify_grasp_phase(delta,old,params,phase='POST_LIFT',initial_lift_arrived=True,
            lift_displacement_m=.23,expected_lift_m=.23,now=clock[0])['gates']['SAMPLE_TIMESTAMPS_VALID'])

    def test_old_or_non_increasing_samples_rejected(self):
        with self.assertRaisesRegex(RuntimeError,'fresh genuine'):
            collect_during_scene(lambda:None,lambda i:dict(captured_at_unix=1.),clock=lambda:10.,interval_s=.001)
        with self.assertRaisesRegex(RuntimeError,'must increase'):
            collect_during_scene(lambda:None,lambda i:dict(captured_at_unix=10.),clock=lambda:10.,interval_s=.001)

    def test_scene_failure_and_cancel_propagate(self):
        def failed():raise RuntimeError('camera failed')
        with self.assertRaisesRegex(RuntimeError,'camera failed'):
            collect_during_scene(failed,lambda i:dict(captured_at_unix=10.+i),clock=lambda:10.,interval_s=.001)
        def cancel():raise RuntimeError('STOP_REQUESTED')
        with self.assertRaisesRegex(RuntimeError,'STOP_REQUESTED'):
            collect_during_scene(lambda:None,lambda i:None,check_cancelled=cancel)

    def test_bound_proof_reuses_only_identical_inputs(self):
        points=[[0.]*6,[.1]*6];request={'scene_snapshot_id':'s1'};package={'tool':'t1'}
        proof=bind_geometry_proof({'passed':True},points,request,package)
        self.assertTrue(reuse_geometry_proof(proof,points,request,package)['reused_exact_bound_source'])
        for args in (([[0.]*6,[.2]*6],request,package),(points,{'scene_snapshot_id':'s2'},package),
                     (points,request,{'tool':'t2'})):
            with self.assertRaisesRegex(ValueError,'binding mismatch'):reuse_geometry_proof(proof,*args)
        with self.assertRaises(ValueError):bind_geometry_proof({'passed':False},points,request,package)
        request['diagnostic_unbounded_limit']=float('inf')
        proof=bind_geometry_proof({'passed':True},points,request,package)
        self.assertTrue(reuse_geometry_proof(proof,points,request,package)['passed'])

    def test_full_fresh_stationarity_window_required(self):
        rows=[dict(at_monotonic=t,state='IDLE',map_id=1,motion_log_id=2,motion_queue_id=3)
              for t in (0.,1.,2.)]
        self.assertTrue(stationary_window(rows,2.1)['stationary'])
        with self.assertRaisesRegex(RuntimeError,'WARMING'):stationary_window(rows[1:],2.1)
        with self.assertRaisesRegex(RuntimeError,'STALE'):stationary_window(rows,3.)
        for changed in (dict(state='MOVING'),dict(motion_queue_id=4),dict(map_id=2)):
            bad=[*rows[:-1],dict(rows[-1],**changed)]
            with self.assertRaisesRegex(RuntimeError,'MOVED'):stationary_window(bad,2.1)
        observer=StationaryBaseMonitor(lambda:None);observer.error=RuntimeError('network unavailable')
        with self.assertRaisesRegex(RuntimeError,'network unavailable'):observer.snapshot()
