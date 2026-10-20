"""Read-only bounded monitor for one user-started run; never posts commands."""
import json,time,hashlib,sys
from pathlib import Path
from urllib.request import urlopen
R=Path('/home/yikun/ARES-R-RC1-20261019')
RUN=R/'worklog/evidence/demo-runs/right_arm_grasp_place_roundtrip_v1/web_1792382763337808664'
OUT=RUN/'observer';OUT.mkdir(exist_ok=True)
last=None;end=time.monotonic()+900
while time.monotonic()<end:
    try:
        s=json.load(urlopen('http://127.0.0.1:8775/api/demo/roundtrip/status',timeout=10))
        if Path(s.get('run_dir',''))!=RUN:raise RuntimeError('canonical run changed; stop observing this run')
        row={'observed_at_unix':time.time(),'state':s.get('state'),'stage':s.get('stage'),
          'completed_stages':s.get('completed_stages'),'failure':s.get('failure_message'),
          'event':s.get('current_event'),'running':s.get('running')}
        with (OUT/'status.jsonl').open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
        key=json.dumps([row['state'],row['stage'],row['event']],sort_keys=True)
        if key!=last:
            print(json.dumps(row,ensure_ascii=False),flush=True);last=key
        if not s.get('running'):
            (OUT/'terminal-status.json').write_text(json.dumps(s,indent=2,ensure_ascii=False)+'\n');break
    except Exception as e:
        print(json.dumps({'monitor_error':str(e),'at_unix':time.time()}),flush=True)
        with (OUT/'errors.jsonl').open('a') as f:f.write(json.dumps({'at_unix':time.time(),'error':str(e)})+'\n')
    time.sleep(3)
print(json.dumps({'observer_finished':True,'physical_commands_sent':False,'output':str(OUT)}),flush=True)
