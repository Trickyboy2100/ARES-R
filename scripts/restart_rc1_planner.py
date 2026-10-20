"""Restart only the idle, manifest-owned RC1 planner. No device access."""
import json,os,subprocess,time
from pathlib import Path
from ares_r.motion.planner_service_client import _call,SOCKET
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'worklog/runtime/rc1-webui'
if ROOT!=Path('/home/yikun/ARES-R-RC1-20261019') or SOCKET!=OUT/'planner.sock':
    raise RuntimeError('isolated RC1 only')
manifest=OUT/'services.json';services=json.loads(manifest.read_text())
owned=next(x for x in services['processes'] if x['service']=='planner')
actual=(Path('/proc')/str(owned['pid'])/'cmdline').read_bytes().split(b'\0')[:-1]
if [x.decode() for x in actual]!=owned['argv']:raise RuntimeError('planner ownership mismatch')
state=_call({'command':'status'},5)
if state.get('active_job_id'):raise RuntimeError('planner busy; no interruption')
_call({'command':'stop'},5)
until=time.monotonic()+10
while SOCKET.exists() and time.monotonic()<until:time.sleep(.1)
if SOCKET.exists():raise RuntimeError('planner failed to stop cleanly; no socket deletion')
with (OUT/'planner.log').open('ab') as log:
    process=subprocess.Popen(owned['argv'],cwd=ROOT,env=dict(os.environ,PYTHONPATH=str(ROOT/'src')),
        stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
owned['previous_pid']=owned['pid'];owned['pid']=process.pid
manifest.write_text(json.dumps(services,indent=2)+'\n')
until=time.monotonic()+10
while not SOCKET.exists() and time.monotonic()<until:time.sleep(.1)
if not SOCKET.exists():raise RuntimeError('new planner failed to start')
print(json.dumps({'restarted':'RC1 planner only','pid':process.pid,'physical_motion':False}))
