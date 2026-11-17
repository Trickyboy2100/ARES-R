import json,os,shutil,subprocess,tempfile,time,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
CC=shutil.which('clang++') or shutil.which('g++')

@unittest.skipUnless(CC,'compiler required')
class NativePairTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory();cls.binary=Path(cls.temp.name)/'native_pair'
  subprocess.run([CC,'-std=c++17','-pthread','-I'+str(Path(__file__).parent/'native_stub'),str(Path(__file__).resolve().parents[1]/'native/jaka_dual_arm_supervised.cpp'),'-o',str(cls.binary)],check=True,capture_output=True)
 @classmethod
 def tearDownClass(cls):cls.temp.cleanup()
 def launch(self,d,side,env=None):
  p=Path(d);values=p/(side+'.txt');tool=2 if side=='left' else 3
  values.write_text('ARES_R_RIGHT_V2 5 0.08 %d %d 0.08 0.1 1.5\n'%(int(time.time()),tool)+'0 0 0 0 0 0\n-6 -6 -6 -6 -6 -6\n6 6 6 6 6 6\n'+'\n'.join(' '.join([str(x)]+['0']*5) for x in [0,.0001,.0002,.0001,0])+'\n')
  log=(p/(side+'.log')).open('w')
  process=subprocess.Popen([str(self.binary),side,'supervised_path',str(values),'CONFIRMED_DUAL_ARM_CLEAR',str(p/'gate'),str(p/'stop'),str(p/(side+'.ready'))],stdout=log,stderr=subprocess.STDOUT,env=env)
  return process,log
 def events(self,d,side):return [json.loads(line) for line in (Path(d)/(side+'.log')).read_text().splitlines() if line.startswith('{')]
 def test_two_controllers_wait_at_gate_and_finish_both(self):
  with tempfile.TemporaryDirectory() as d:
   pair=[self.launch(d,a) for a in ['left','right']]
   try:
    end=time.monotonic()+4
    while not all((Path(d)/(a+'.ready')).exists() for a in ['left','right']):
     self.assertLess(time.monotonic(),end);time.sleep(.01)
    for a in ['left','right']:self.assertFalse(any(e['event']=='sample' for e in self.events(d,a)))
    (Path(d)/'gate').write_text(str(time.clock_gettime(time.CLOCK_MONOTONIC)+.25))
    for process,log in pair:
     rc=process.wait(timeout=5);log.flush();self.assertEqual(rc,0,Path(log.name).read_text());log.close()
    first=[]
    for a in ['left','right']:
     rows=self.events(d,a);self.assertTrue(any(e['event']=='target_reached' for e in rows));self.assertTrue(any(e['event']=='servo_disabled' and e['code']==0 for e in rows));first.append(next(e['wall_unix_ns'] for e in rows if e['event']=='sample'))
    self.assertLess(abs(first[0]-first[1])/1e9,.04)
   finally:
    for process,log in pair:
     if process.poll() is None:process.terminate();process.wait(timeout=3)
     log.close()
 def test_left_fault_sets_shared_stop_and_neither_reports_pair_success(self):
  with tempfile.TemporaryDirectory() as d:
   pair=[self.launch(d,a,dict(os.environ,DEMO02_FAIL_LEFT='1')) for a in ['left','right']]
   try:
    end=time.monotonic()+4
    while not all((Path(d)/(a+'.ready')).exists() for a in ['left','right']):
     self.assertLess(time.monotonic(),end);time.sleep(.01)
    (Path(d)/'gate').write_text(str(time.clock_gettime(time.CLOCK_MONOTONIC)+.25))
    for process,log in pair:self.assertNotEqual(process.wait(timeout=5),0);log.close()
    self.assertTrue((Path(d)/'stop').exists())
    for a in ['left','right']:self.assertFalse(any(e['event']=='target_reached' for e in self.events(d,a)))
   finally:
    for process,log in pair:
     if process.poll() is None:process.terminate();process.wait(timeout=3)
     log.close()
