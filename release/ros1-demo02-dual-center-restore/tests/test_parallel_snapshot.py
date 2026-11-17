import sys,tempfile,threading,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));sys.path.insert(0,str(BASE.parents[1]/'src'))
from dual_center_restore.live import LiveProvider
class ParallelSnapshotTests(unittest.TestCase):
 def test_two_independent_sdk_reads_overlap_and_join_before_return(self):
  barrier=threading.Barrier(2,timeout=2);completed=[]
  def read(binary,arm):
   barrier.wait();completed.append(arm)
   return dict(actual_rad=[0]*6,tcp_mm_rad=[0]*6,tool_id=1,tool_mm_rad=[0]*6)
  p=LiveProvider.__new__(LiveProvider);p.check_cancelled=lambda:None;p.root=Path('/tmp');p.config={'base':{}}
  p.world={'arms':{a:{'base_xyz_m':[0]*3,'base_rpy_rad':[0]*3} for a in ('left','right')}}
  p.model=SimpleNamespace(audits={a:{'diagnostics':{}} for a in ('left','right')})
  with patch('dual_center_restore.live.snapshot',side_effect=read),patch('ares_r.adapters.amr_http.AmrHttpBase') as amr:
   amr.return_value._request.return_value={'state':{'current':{'state':'IDLE'}}}
   result=p.observe_both()
  self.assertEqual(set(completed),{'left','right'});self.assertEqual(set(result['arms']),{'left','right'})
