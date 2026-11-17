import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import MagicMock,patch
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE));sys.path.insert(0,str(BASE.parents[1]/'src'))
from dual_center_restore.live import LiveProvider

class ArrivalTests(unittest.TestCase):
 def test_transient_first_failure_can_recover_only_after_three_fresh_passes(self):
  goal={a:dict(joints_rad=[0.]*6,T_body_tcp=[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]) for a in ['left','right']}
  good={'arms':copy.deepcopy(goal)};bad=copy.deepcopy(good);bad['arms']['right']['joints_rad'][0]=.01
  p=LiveProvider.__new__(LiveProvider);p.phase=2;p.observe_both=MagicMock(side_effect=[bad,good,good,good])
  with tempfile.TemporaryDirectory() as d,patch('dual_center_restore.live.time.sleep'):
   p.phase_dir=Path(d);r=p.verify_both(goal);samples=json.loads((Path(d)/'arrival-samples.json').read_text())
  self.assertTrue(r['left']['passed'] and r['right']['passed']);self.assertEqual(len(samples),4)
  self.assertEqual(r['right']['consecutive_passes'],3);self.assertFalse(samples[0]['arms']['right']['passed'])

 def test_center_contract_and_restore_joint_binding(self):
  goal={a:dict(joints_rad=[0.]*6,T_body_tcp=[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]) for a in ['left','right']}
  actual={'arms':copy.deepcopy(goal)};actual['arms']['right']['joints_rad'][0]=0.0014
  p=LiveProvider.__new__(LiveProvider);p.observe_both=MagicMock(return_value=actual)
  with tempfile.TemporaryDirectory() as d,patch('dual_center_restore.live.time.sleep'):
   p.phase_dir=Path(d);p.phase=1;r=p.verify_both(goal)
   self.assertTrue(r['right']['passed']);self.assertFalse(r['right']['joint_check_required'])
   p.phase=2;r=p.verify_both(goal)
   self.assertFalse(r['right']['passed']);self.assertTrue(r['right']['joint_check_required'])
