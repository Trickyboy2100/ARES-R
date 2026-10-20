"""Reload only idle isolated RC1 UI/backend; never touches robot services."""
import json,os,signal,subprocess,time
from pathlib import Path
from urllib.request import urlopen
R=Path(__file__).resolve().parents[1];O=R/'worklog/runtime/rc1-webui'
if R!=Path('/home/yikun/ARES-R-RC1-20261019'):raise RuntimeError('isolated RC1 only')
def get(p):return json.load(urlopen('http://127.0.0.1:8775'+p,timeout=10))
if get('/api/demo/roundtrip/status').get('running') or get('/api/operations/run-status').get('state')=='RUNNING':
    raise RuntimeError('physical job active: no restart')
manifest=O/'services.json';value=json.loads(manifest.read_text())
selected=[next(x for x in value['processes'] if x['service']==name) for name in ('webui','backend')]
for item in selected:
    actual=(Path('/proc')/str(item['pid'])/'cmdline').read_bytes().split(b'\0')[:-1]
    if [x.decode() for x in actual]!=item['argv']:raise RuntimeError('RC1 service ownership mismatch')
(O/('services-before-ui-reload-'+str(time.time_ns())+'.json')).write_text(manifest.read_text())
for item in selected:os.kill(item['pid'],signal.SIGTERM)
time.sleep(.5)
env=dict(os.environ,PYTHONPATH=str(R/'src'),ARES_R_BACKEND_URL='http://127.0.0.1:8776',
    ARES_R_ROUNDTRIP_API_URL='http://127.0.0.1:8775',ARES_R_PLANNER_SOCKET=str(O/'planner.sock'))
for item in reversed(selected):
    with (O/(item['service']+'.log')).open('ab') as log:
        p=subprocess.Popen(item['argv'],cwd=R,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    item['previous_pid']=item['pid'];item['pid']=p.pid
manifest.write_text(json.dumps(value,indent=2)+'\n')
until=time.monotonic()+20
while time.monotonic()<until:
    try:
        s=get('/api/demo/roundtrip/status')
        if s.get('running'):raise RuntimeError('unexpected auto-start')
        print(json.dumps({'stage_count':s['stage_count'],'revision':s['revision'],
          'offset':s['parameters'].get('task_tcp_offset_m_rad'),'physical_motion_started':False,
          'blockers':s['blockers']}));break
    except OSError:time.sleep(.25)
else:raise RuntimeError('RC1 UI failed to restart; inspect logs')
