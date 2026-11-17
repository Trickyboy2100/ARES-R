#!/usr/bin/env python3
"""Arm both native workers but never release the start gate: no servo enable."""
import argparse,json,os,subprocess,time
from pathlib import Path
import sys

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('/home/yikun/ARES-R-RC1-20261019'));p.add_argument('--phase',type=Path,required=True);a=p.parse_args();sys.path.insert(0,str(a.root/'src'))
 from ares_r.motion.mirror_native import snapshot
 binary=a.root/'native/jaka_dual_arm_supervised';out=a.phase/('arming-only-'+str(time.time_ns()));out.mkdir();processes=[];logs=[];passed=False
 try:
  for side in ['left','right']:
   # Rewrite only the start-only test package; never reuse an expired motion
   # package. Both workers receive a hold path from fresh actual state.
   state=snapshot(a.root/'native/jaka_joint_mirror',side);q=state['actual_rad'];f=out/(side+'.txt');tool=state['tool_mm_rad']
   f.write_text('ARES_R_RIGHT_V2 2 0.08 %d %d 0.08 0.1 1.5\n'%(int(time.time()),state['tool_id'])+' '.join(map(str,tool))+'\n-6.9 -6.9 -6.9 -6.9 -6.9 -6.9\n6.9 6.9 6.9 6.9 6.9 6.9\n'+' '.join(map(str,q))+'\n'+' '.join(map(str,q))+'\n')
   log=(out/(side+'.jsonl')).open('w');logs.append(log)
   processes.append(subprocess.Popen([str(binary),side,'supervised_path',str(f),'CONFIRMED_DUAL_ARM_CLEAR',str(out/'NEVER_CREATED.gate'),str(out/'stop'),str(out/(side+'.ready'))],stdout=log,stderr=subprocess.STDOUT))
  end=time.monotonic()+12
  while not all((out/(s+'.ready')).exists() for s in ['left','right']):
   if any(p.poll() is not None for p in processes) or time.monotonic()>end:raise RuntimeError('DUAL_ARMING_PREFLIGHT_FAILED')
   time.sleep(.02)
  passed=True
  print('BOTH_CONTROLLERS_ARMING_READY_WITHOUT_SERVO_ENABLE')
 finally:
  (out/'stop').write_text('NO_MOTION_PREFLIGHT_END\n')
  for process in processes:
   try:process.wait(timeout=5)
   except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=5)
  for log in logs:log.close()
 summary={'passed':passed,'motion_dispatched':False,'gate_created':(out/'NEVER_CREATED.gate').exists(),'evidence':str(out)}
 (out/'summary.json').write_text(json.dumps(summary,indent=2))
 print('NO_START_GATE_CREATED; no motion dispatched. Evidence='+str(out))
if __name__=='__main__':main()
