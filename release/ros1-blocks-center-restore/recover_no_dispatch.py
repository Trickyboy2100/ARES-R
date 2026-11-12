"""Manual application-only recovery of a zero-dispatch block, never controller clear.
Requires exact failed run ID and explicit operator authorization; preserves old state.
Run with the onsite RC1 Python. Restarts only the verified overlay backend.
"""
import argparse,json,time,os,signal,subprocess
from pathlib import Path
from urllib.request import Request,urlopen
p=argparse.ArgumentParser();p.add_argument('--run-id',required=True);p.add_argument('--operator-confirmed',action='store_true');a=p.parse_args()
if not a.operator_confirmed:raise SystemExit('Explicit operator confirmation required')
r=Path(os.environ.get('ARES_R_SITE_ROOT','/home/yikun/ARES-R-RC1-20261019'));overlay=Path(__file__).resolve().parent
out=overlay.parent/('recovery-'+str(time.time_ns()));out.mkdir()
def get(path,post=False):
 return json.load(urlopen(Request('http://127.0.0.1:8775/api/'+path,data=b'{}' if post else None,headers={'Content-Type':'application/json'}),timeout=15))
s=get('demo-console/status')
if s.get('run_id')!=a.run_id or s.get('state')!='RECOVERY_REQUIRED' or s.get('strategy')!='center_restore':raise SystemExit('Unexpected job identity/state')
if list((Path(s['output'])/'block').glob('*/dispatched-once.json')):raise SystemExit('Cannot use zero-dispatch recovery: movement may have occurred')
if get('operations/run-status').get('state')=='RUNNING':raise SystemExit('Motion active')
rows=[];prev=None
for attempt in range(10):
 t=get('operations/telemetry',True);arm=t.get('arms',{}).get('right') or {};c=arm.get('controller_status',{});q=arm.get('joints_rad',[])
 if t.get('errors') or len(q)!=6:
  rows=[];prev=None;time.sleep(.3);continue
 if any(c.get(k) for k in ('errcode','protective_stop','emergency_stop','on_soft_limit','drag_mode')) or not c.get('in_position') or not c.get('enabled'):raise SystemExit('Controller not healthy')
 if prev is not None and max(abs(x-y) for x,y in zip(prev,q))>.0009:raise SystemExit('Arm moving')
 rows.append(t);prev=q
 if len(rows)==3:break
 time.sleep(.3)
if len(rows)!=3:raise SystemExit('No trusted stationary readbacks')
(out/'telemetry.json').write_text(json.dumps(rows,indent=2));(out/'job-before.json').write_text(json.dumps(s,indent=2))
p=r/'worklog/runtime/rc1-webui/services.json';m=json.loads(p.read_text());b=next(x for x in m['processes'] if x['service']=='backend');pid=b['pid']
if b'run_backend_overlay.py' not in Path('/proc/%s/cmdline'%pid).read_bytes():raise SystemExit('Backend ownership changed')
os.kill(pid,signal.SIGTERM);time.sleep(.6)
jpath=r/'worklog/runtime/demo-console/job.json';j=json.loads(jpath.read_text())
if j['run_id']!=a.run_id:raise SystemExit('Job changed; inspect before restarting')
j.update(state='STOPPED',recovered_from_state='RECOVERY_REQUIRED',recovery_reason='Operator confirmed interference removed; zero dispatch; three healthy stationary reads; no controller fault cleared',recovery_at_unix=time.time())
jpath.write_text(json.dumps(j,indent=2));(out/'job-after.json').write_text(json.dumps(j,indent=2))
env=dict(os.environ,PYTHONPATH=str(r/'src'),ARES_R_SITE_ROOT=str(r),ARES_R_BACKEND_URL='http://127.0.0.1:8776',ARES_R_ROUNDTRIP_API_URL='http://127.0.0.1:8775',ARES_R_PLANNER_SOCKET=str(r/'worklog/runtime/rc1-webui/planner.sock'))
with (out/'backend.log').open('ab') as f:child=subprocess.Popen(b['argv'],cwd=r,env=env,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
b.update(previous_pid=pid,pid=child.pid);p.write_text(json.dumps(m,indent=2))
print('APPLICATION_ONLY_RECOVERED',a.run_id,'PID',child.pid,'EVIDENCE',out)
