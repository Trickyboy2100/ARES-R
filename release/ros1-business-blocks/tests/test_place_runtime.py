import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from blocks.place_runtime import execute_with_payload
from blocks.runner import PayloadSessions

class PlaceRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.sessions=PayloadSessions(self.root/'payload.sqlite')
        self.sid=self.sessions.create('sieve','tool','geometry',{'verified':True})
        self.requests=[]
        self.params=dict(demo_id='test-place',platform=dict(arrival_tolerance_m=.005),
            stages=dict(dmp_place=dict(release_raw=400,release_readback_tolerance_raw=20,
                post_release_retreat=dict(enabled=True,distance_m=.04,axis_body=[-1,0,0]))))
        def save(path,value):Path(path).write_text(json.dumps(value))
        def plan(payload,*args,**kwargs):self.requests.append(payload)
        self.existing=types.SimpleNamespace(DEMO_ID='original',save=save,plan_leg=plan)
        self.fail_retreat=False;self.raw=400
        def place(params,out,execute,stop_after):
            out.mkdir(parents=True)
            self.existing.plan_leg({'position_m':[1,0,1]})
            self.existing.save(out/'release.json',{'readback_raw':self.raw})
            if self.fail_retreat:raise RuntimeError('RETREAT_FAILED')
            self.existing.save(out/'retreat-check.json',dict(delta_m=[-.04,0,0],requested_body_vector_m=[-.04,0,0]))
            return dict(state='PLACED_AND_RELEASED',retreat={'actual':True})
        def center(params,out,execute):
            self.existing.plan_leg({'position_m':[0,0,1]})
            return dict(state='AT_CENTER')
        self.existing.stage_place=place;self.existing.stage_center=center
    def tearDown(self):self.sessions.close();self.tmp.cleanup()
    def run_place(self):
        return execute_with_payload(self.existing,self.params,self.root/'out',self.sessions,self.sid,
            validate_payload=lambda:dict(validated=True,geometry={'revision':'g1','cuboids':[]}))
    def test_geometry_stays_until_release_center_empty(self):
        result=self.run_place()
        self.assertTrue(result['success'])
        self.assertIn('attached_object_geometry',self.requests[0])
        self.assertNotIn('attached_object_geometry',self.requests[1])
        self.assertEqual(self.existing.DEMO_ID,'original')
        self.assertEqual(self.sessions.get(self.sid)['state'],'RELEASED_CONFIRMED')
    def test_retreat_fault_does_not_erase_confirmed_release(self):
        self.fail_retreat=True
        with self.assertRaisesRegex(RuntimeError,'RETREAT_FAILED'):self.run_place()
        self.assertEqual(self.sessions.get(self.sid)['state'],'RELEASED_CONFIRMED')
        self.assertEqual(len(self.requests),1)
    def test_bad_release_marks_uncertain_and_no_center(self):
        self.raw=100
        with self.assertRaisesRegex(ValueError,'RELEASE'):self.run_place()
        self.assertEqual(self.sessions.get(self.sid)['state'],'UNCERTAIN')
        self.assertEqual(len(self.requests),1)
    def test_pick_in_progress_reservation(self):
        sid=self.sessions.create('tray','tool','g',{'prepared':'x'},state='PICK_IN_PROGRESS')
        self.assertIn((sid,'PICK_IN_PROGRESS'),self.sessions.active())
        self.sessions.confirm_pick(sid,{'verified':True})
        self.assertEqual(self.sessions.get(sid)['state'],'HELD_CONFIRMED')
