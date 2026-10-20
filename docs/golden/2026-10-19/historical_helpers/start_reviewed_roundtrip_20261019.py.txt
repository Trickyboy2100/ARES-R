"""Explicit one-time start after preparation-only failure; never resets controller."""
import json,subprocess,time
from pathlib import Path
from urllib.request import Request,urlopen
from ares_r.adapters.amr_http import AmrHttpBase
R=Path('/home/yikun/ARES-R-RC1-20261019')
O=R/'worklog/evidence/20261019-authorized-full-demo-restart-v3';O.mkdir(exist_ok=False)
def write(n,v):(O/n).write_text(json.dumps(v,indent=2)+'\n')
def get(p):return json.load(urlopen('http://127.0.0.1:8775'+p,timeout=20))
def post(p,v):return json.load(urlopen(Request('http://127.0.0.1:8775'+p,data=json.dumps(v).encode(),
                         headers={'Content-Type':'application/json'}),timeout=30))
test=(R/'worklog/runtime/rc1-webui/demo-start-final-tests.log').read_text()
if 'OK (skipped=1)' not in test or 'FAILED' in test:raise RuntimeError('final tests not passed')
ready=json.loads((R/'worklog/evidence/demo-runs/right_arm_grasp_place_roundtrip_v1/web_1792398755608150576/association10mm-preflight/REPORT.json').read_text())
if not ready['LIFT230_DEMO_PRECHECK_PASS']:raise RuntimeError('lift precheck not passed')
status=get('/api/demo/roundtrip/status');write('before-demo-status.json',status)
if status.get('running') or get('/api/operations/run-status').get('state')=='RUNNING':raise RuntimeError('task already active')
if (status.get('run_id')!='fe91ef9313f741e09db6af9311486016' or status.get('stage')!='PICK_PREPARE' or
    status.get('completed_stages')!=1 or not str(status.get('failure_message','')).startswith('continuous230 full loaded-world collision:')):
    raise RuntimeError('unexpected prior failure: no automatic recovery')
telemetry=post('/api/operations/telemetry',{});write('before-telemetry.json',telemetry)
if telemetry.get('errors'):raise RuntimeError('live state unavailable')
stable=0
for attempt in range(4):
    snapshot=subprocess.run([str(R/'native/jaka_right_rc1'),'snapshot'],cwd=R,capture_output=True,text=True,timeout=15)
    raw=snapshot.stdout+snapshot.stderr;(O/('right-snapshot-'+str(attempt)+'.log')).write_text(raw)
    if snapshot.returncode:
        # Known transient recorded in site reports; retry reads only, no clear.
        stable=0
        if 'errcode=4128769 power=1 enabled=1 estop=0 collision=0 limit=0 drag=0' not in raw:
            raise RuntimeError('right controller not healthy')
        check=post('/api/operations/telemetry',{});write('transient-telemetry-'+str(attempt)+'.json',check)
        if check.get('errors') or check['arms']['right']['controller_status']['errcode']:
            raise RuntimeError('right error confirmed')
    else:
        stable+=1
        if stable>=2:break
    time.sleep(.2)
if stable<2:raise RuntimeError('right status not stable; no start')
config=json.loads((R/'config/system.json').read_text())
base=AmrHttpBase(config['base'])._request('GET','/robot/status');write('base-before-start.json',base)
if base.get('state',{}).get('current',{}).get('state')!='IDLE':raise RuntimeError('base not IDLE')
stop=R/'worklog/runtime/right_arm_grasp_place_roundtrip_v1/stop.request'
if stop.exists():
    if stop.read_text().strip()!='CANONICAL_OPERATOR_STOP':raise RuntimeError('unexpected stop reason')
    stop.rename(stop.with_name('stop-preserved-before-authorized-restart-'+str(time.time_ns())+'.request'))
write('operator-authorization.json',{'at_unix':time.time(),'source':'EXPLICIT_CHAT_START_FULL_DEMO_AND_MONITOR',
    'lower_middle_slot_empty_confirmed':True,'on_site_monitor_and_estop_confirmed':True,
    'restart_from_beginning':True,'no_controller_fault_reset':True,'no_automatic_retry_after_physical_fault':True})
status=get('/api/demo/roundtrip/status')
if status['blockers']:raise RuntimeError('remaining blockers: '+str(status['blockers']))
result=post('/api/demo/roundtrip/start',{'authorization':'RIGHT GRASP PLACE ROUNDTRIP','execution_mode':'SITE',
    'onsite_observer_confirmed':True,'contract_sha256':status['contract_sha256'],'cache_start_join_authorized':True})
write('start-result.json',result)
print(json.dumps({k:result.get(k) for k in ('run_id','running','state','stage','run_dir','log','failure_message')}),flush=True)
