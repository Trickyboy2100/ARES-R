"""Read-only monitor; never sends start/stop/resume/controller commands."""
import json,time
from pathlib import Path
from urllib.request import urlopen
R=Path('/home/yikun/ARES-R-RC1-20261019')
RUN=Path(json.loads((R/'worklog/evidence/20261019-authorized-full-demo-restart-v3/start-result.json').read_text())['run_dir']).name
O=R/'worklog/evidence/demo-runs/right_arm_grasp_place_roundtrip_v1'/RUN
last=None;errors=0;started=time.monotonic()
while time.monotonic()-started<1800:
    try:
        x=json.load(urlopen('http://127.0.0.1:8775/api/demo/roundtrip/status',timeout=15))
        if Path(x['run_dir']).name!=RUN:raise RuntimeError('run changed; stop monitoring wrong job')
        errors=0;entry={k:x.get(k) for k in ('run_id','running','state','stage','completed_stages','failure_message','current_event','result')}
        entry.update(observed_at_unix=time.time(),monitor_monotonic_s=time.monotonic())
        with (O/'readonly-monitor.jsonl').open('a') as f:f.write(json.dumps(entry)+'\n')
        marker=json.dumps([entry.get(k) for k in ('state','stage','completed_stages','failure_message','current_event')],sort_keys=True)
        if marker!=last:
            print(json.dumps(entry),flush=True);last=marker
            (O/'readonly-monitor-latest.json').write_text(json.dumps(x,indent=2)+'\n')
        if not x.get('running'):
            (O/'readonly-monitor-terminal.json').write_text(json.dumps(x,indent=2)+'\n');break
    except Exception as e:
        errors+=1;print(json.dumps({'monitor_error':str(e),'consecutive_errors':errors}),flush=True)
        if errors>=5:raise
    time.sleep(2)
else:raise RuntimeError('monitor deadline reached; demo not automatically stopped')
