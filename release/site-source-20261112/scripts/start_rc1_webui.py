#!/usr/bin/env python3
"""Start isolated RC1 services only; never starts or resumes a physical demo."""
import json,os,socket,subprocess,time
from pathlib import Path
from urllib.request import urlopen
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'worklog/runtime/rc1-webui'

def main():
    if ROOT!=Path('/home/yikun/ARES-R-RC1-20261019'):
        raise RuntimeError('this launcher is only for the isolated onsite RC1 directory')
    OUT.mkdir(parents=True,exist_ok=True)
    manifest=OUT/'services.json'
    if manifest.exists():
        raise RuntimeError('existing RC1 service manifest: inspect processes before starting a duplicate')
    for port in (8775,8776):
        with socket.socket() as s:s.bind(('0.0.0.0',port))
    planner_socket=OUT/'planner.sock'
    if planner_socket.exists():raise RuntimeError('planner socket already exists; no automatic deletion')
    env=dict(os.environ,PYTHONPATH=str(ROOT/'src'),
        ARES_R_BACKEND_URL='http://127.0.0.1:8776',
        ARES_R_ROUNDTRIP_API_URL='http://127.0.0.1:8775',
        ARES_R_PLANNER_SOCKET=str(planner_socket))
    python=ROOT/'.venv/bin/python'
    commands=[('planner',[str(python),'-m','ares_r.motion.persistent_planner_service','--socket',str(planner_socket)]),
      ('backend',[str(python),'-m','ares_r.canonical_backend','--host','127.0.0.1','--port','8776']),
      ('webui',[str(python),'-m','ares_r.webui.server','--host','0.0.0.0','--port','8775'])]
    processes=[]
    for name,argv in commands:
        with (OUT/(name+'.log')).open('ab') as log:
            p=subprocess.Popen(argv,cwd=ROOT,env=env,stdin=subprocess.DEVNULL,
                stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        processes.append({'service':name,'pid':p.pid,'argv':argv})
        manifest.write_text(json.dumps({'repository_root':str(ROOT),'processes':processes,
            'demo_auto_start':False,'production_services_changed':False},indent=2)+'\n')
    end=time.monotonic()+30
    while time.monotonic()<end:
        try:
            status=json.load(urlopen('http://127.0.0.1:8775/api/demo/roundtrip/status',timeout=2))
            if status.get('runtime_binding',{}).get('repository_root')!=str(ROOT):
                raise RuntimeError('unexpected backend repository')
            if status.get('running'):raise RuntimeError('unexpected running demo')
            if not planner_socket.exists():raise RuntimeError('isolated planner not ready')
            (OUT/'startup-status.json').write_text(json.dumps(status,indent=2,ensure_ascii=False)+'\n')
            print(json.dumps({'webui':'http://192.168.99.32:8775/','revision':status['revision'],
                'runtime_binding':status['runtime_binding'],'blockers':status['blockers'],
                'demo_running':False,'physical_motion_started':False},ensure_ascii=False));return
        except (OSError,ValueError):time.sleep(.25)
    raise RuntimeError('RC1 services not ready; inspect service logs; no demo started')

if __name__=='__main__':main()
