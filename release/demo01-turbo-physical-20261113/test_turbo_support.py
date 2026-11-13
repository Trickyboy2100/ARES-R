import importlib.util,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
spec=importlib.util.spec_from_file_location('turbo_support',Path(__file__).with_name('turbo_support.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class InstrumentationTest(unittest.TestCase):
    def test_scoped_fast_preserves_motion_inputs(self):
        calls=[]
        with tempfile.TemporaryDirectory() as d:
            old=SimpleNamespace(api=lambda path,*a,**kw:(calls.append((path,a,kw)) or {'plan_id':'test'}))
            m.instrument(old,Path(d));body={'request_label':'CENTER_RESTORE_SAVED','planning_mode':'QUALITY','goal_joints_rad':[0]*6,'environment_avoidance':'ON'}
            old.api('/api/motion/plan',body,timeout=300)
            got=calls[0][1][0]
            self.assertEqual(got,dict(body,planning_mode='FAST'));self.assertEqual(body['planning_mode'],'QUALITY')
            row=json.loads((Path(d)/'api-timings.jsonl').read_text());self.assertTrue(row['success']);self.assertGreaterEqual(row['wall_s'],0)
    def test_other_calls_and_failures_unchanged(self):
        def failure(*a,**kw):raise RuntimeError('original fault')
        with tempfile.TemporaryDirectory() as d:
            old=SimpleNamespace(api=failure);m.instrument(old,Path(d))
            with self.assertRaisesRegex(RuntimeError,'original fault'):old.api('/api/operations/execute',{'x':1})
            row=json.loads((Path(d)/'api-timings.jsonl').read_text());self.assertFalse(row['success'])
if __name__=='__main__':unittest.main()
