"""Read-only monitor. Never starts, resumes or overrides a robot command."""
import json,time,urllib.request
from pathlib import Path
ROOT=Path('/home/yikun/ARES-R-RC1-20261019')
RUN=ROOT/'worklog/evidence/demo-runs/right_arm_grasp_place_roundtrip_v1/web_1792401640042994085'
OUT=RUN/'operator-readonly-monitor';OUT.mkdir(exist_ok=False)
def save(n,v):
    p=OUT/n;t=p.with_suffix('.tmp');t.write_text(json.dumps(v,indent=2,ensure_ascii=False));t.replace(p)
last=None;failures=0;start=time.monotonic()
save('authorization-context.json',{'lower_middle_slot_empty_confirmed':True,
     'source':'operator reply 已移走','automatic_resume':False,'monitor_motion_commands':False})
while time.monotonic()-start<1800:
    try:
        s=json.load(urllib.request.urlopen('http://127.0.0.1:8775/api/demo/roundtrip/status',timeout=15));failures=0
        if s.get('run_dir')!=str(RUN):raise RuntimeError('canonical run changed; monitor will not attach to another run')
        row={k:s.get(k) for k in ('run_id','state','running','stage','completed_stages','failure_message','current_event','result','elapsed_s')}
        row['observed_at_unix']=time.time();save('latest-status.json',s)
        key=(s.get('run_id'),s.get('state'),s.get('stage'),s.get('completed_stages'),s.get('current_event',{}).get('state'))
        if key!=last:
            with (OUT/'changes.jsonl').open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
            print(json.dumps(row,ensure_ascii=False),flush=True);last=key
        if not s.get('running'):
            save('terminal-status.json',s)
            summary={'state':s.get('state'),'stage':s.get('stage'),'completed_stages':s.get('completed_stages'),
                 'run_id':s.get('run_id'),'run_dir':str(RUN),'error':s.get('failure_message'),
                 'monitor_wall_s':time.monotonic()-start,'automatic_retry':False}
            try:
                req=urllib.request.Request('http://127.0.0.1:8775/api/operations/telemetry',data=b'{}',headers={'Content-Type':'application/json'})
                save('terminal-telemetry.json',json.load(urllib.request.urlopen(req,timeout=20)))
            except Exception as e:summary['telemetry_error']=str(e)
            save('REPORT.json',summary);print(json.dumps(summary,ensure_ascii=False),flush=True);break
    except Exception as e:
        failures+=1;save('monitor-error.json',{'error':str(e),'consecutive_errors':failures,'at_unix':time.time()})
        print(json.dumps({'monitor_error':str(e),'consecutive_errors':failures}),flush=True)
        if failures>=5:raise
    time.sleep(2)
else:raise RuntimeError('read-only monitoring deadline; no automatic robot command issued')
