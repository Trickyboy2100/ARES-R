"""Reload only proven-owned RC1 backend/WebUI; keep persistent planner hot."""
import json,os,signal,subprocess,time,argparse
from pathlib import Path
from urllib.request import urlopen
R=Path('/home/yikun/ARES-R-RC1-20261019');S=R/'worklog/runtime/rc1-webui';m=json.loads((S/'services.json').read_text());before=json.load(urlopen('http://127.0.0.1:8775/api/operations/run-status',timeout=10))
parser=argparse.ArgumentParser();parser.add_argument('--planner-only',action='store_true');chosen={'planner'} if parser.parse_args().planner_only else {'backend','webui'}
if before.get('state')=='RUNNING':raise RuntimeError('cannot reload during physical operation')
for p in m['processes']:
 if p['service'] not in chosen:continue
 actual=[x.decode() for x in (Path('/proc')/str(p['pid'])/'cmdline').read_bytes().split(b'\0') if x]
 if actual!=p['argv']:raise RuntimeError('service PID identity mismatch')
backup=R/'worklog/preservation/20261022-canonical-obb'/('services-before-'+str(time.time_ns())+'.json');backup.write_text(json.dumps(m,indent=2)+'\n')
for p in reversed(m['processes']):
 if p['service'] in chosen:os.kill(p['pid'],signal.SIGTERM)
time.sleep(1)
env=dict(os.environ,PYTHONPATH=str(R/'src'),ARES_R_BACKEND_URL='http://127.0.0.1:8776',ARES_R_ROUNDTRIP_API_URL='http://127.0.0.1:8775',ARES_R_PLANNER_SOCKET=str(S/'planner.sock'))
for p in m['processes']:
 if p['service'] not in chosen:continue
 with (S/(p['service']+'.log')).open('ab') as log:
  child=subprocess.Popen(p['argv'],cwd=R,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 p['pid']=child.pid
(S/'services.json').write_text(json.dumps(m,indent=2)+'\n')
for _ in range(40):
 try:
  status=json.load(urlopen('http://127.0.0.1:8775/api/operations/run-status',timeout=2));print(json.dumps(dict(state=status.get('state'),physical_motion_started=False,planner_preserved=True)));break
 except OSError:time.sleep(.25)
else:raise RuntimeError('RC1 services failed readiness')
