"""Recover dead owned planner with stale socket; no device calls."""
import json,os,socket,subprocess,time
from pathlib import Path
R=Path('/home/yikun/ARES-R-RC1-20261019');S=R/'worklog/runtime/rc1-webui';path=S/'services.json';m=json.loads(path.read_text());p=next(x for x in m['processes'] if x['service']=='planner');sock=S/'planner.sock'
if (Path('/proc')/str(p['pid'])/'cmdline').exists():raise RuntimeError('planner PID still exists; inspect instead')
if sock.exists():
 with socket.socket(socket.AF_UNIX) as client:
  if client.connect_ex(str(sock))==0:raise RuntimeError('planner socket still active')
 sock.rename(S/('planner-stale-'+str(time.time_ns())+'.sock'))
env=dict(os.environ,PYTHONPATH=str(R/'src'))
with (S/'planner.log').open('ab') as log:
 child=subprocess.Popen(p['argv'],cwd=R,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
p['pid']=child.pid;path.write_text(json.dumps(m,indent=2)+'\n')
for _ in range(80):
 try:
  with socket.socket(socket.AF_UNIX) as client:
   client.settimeout(2);client.connect(str(sock));client.sendall(b'{"command":"status"}\n');response=json.loads(client.recv(65536))
  if response.get('ok'):print(json.dumps(response));break
 except OSError:time.sleep(.1)
else:raise RuntimeError('planner readiness failed')
