#!/usr/bin/env python3
"""One real GPU Stop-contract check through the same client as site Live."""
import json,os,sys,threading,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from ares_r.motion.persistent_planner_service import Server,Handler,PlannerSupervisor
from ares_r.motion import planner_service_client as client
from ares_r.manipulation.roundtrip_job import atomic

def main():
 if os.environ.get('ARES_R_OFFLINE_REPLAY')!='1':raise RuntimeError('offline isolation required')
 out=ROOT/'worklog/runtime/visual-site-client-stop';out.mkdir(exist_ok=False);cancel=threading.Event()
 source=next((ROOT/'worklog/runtime/visual-review-evidence/rc-final-normal').glob('plan_HOLD230*/request.json'))
 sock=Path('/tmp/ares_visual_stop.sock');client.SOCKET=sock
 with Server(str(sock),Handler) as server:
  server.supervisor=PlannerSupervisor(progress=lambda event:cancel.set() if event['phase']=='SOLVE_START' else None)
  thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();at=time.monotonic()
  try:
   client.plan(sys.executable,ROOT,source,out/'planning.json',out/'planner.log',45,autostart=False,cancelled=cancel.is_set)
   raise RuntimeError('cancel not observed')
  except client.PlannerJobError as exc:
   if 'JOB_CANCELLED' not in str(exc):raise
   status=server.supervisor.status();assert status['worker_pid'] is None and status['last_job']['worker_reaped']
   assert not (out/'planning.json').exists()
   atomic(out/'receipt.json',{'status':'PASS','entry':'site planner_service_client.plan(cancelled=...)','real_gpu_solve_start_observed':cancel.is_set(),'wall_s':time.monotonic()-at,'error':str(exc),'supervisor':status,'late_plan_published':False,'physical_motion':False})
  finally:server.shutdown();thread.join();server.supervisor.reap();sock.unlink(missing_ok=True)
if __name__=='__main__':main()
