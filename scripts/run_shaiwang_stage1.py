"""Stage1 client: preparation/preflight are non-motion; execute needs new auth."""
import argparse,json,os,subprocess,sys,time
from pathlib import Path
from urllib.request import Request,urlopen

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from ares_r.manipulation.task_contract import TASK_ID,load_contract,bind_task,verify_task,task_sender,inspect_offsets,check_center
AUTH='RIGHT SHAIWANG STAGE1 PICK RESET'

def request(path,body=None):
    base=os.environ.get('ARES_R_ROUNDTRIP_API_URL','http://127.0.0.1:8775')
    req=Request(base+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    with urlopen(req,timeout=25) as stream:return json.load(stream)

def main():
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True)
    for flag in ('inspect','prepare','preflight','execute','stop'):g.add_argument('--'+flag,action='store_true')
    p.add_argument('--prepared',type=Path);p.add_argument('--authorization');p.add_argument('--onsite-observer-confirmed',action='store_true');a=p.parse_args()
    if a.stop:print(json.dumps(request('/api/operations/stop',{})));return
    if a.inspect:print(json.dumps(inspect_offsets(ROOT),indent=2,ensure_ascii=False));return
    task=load_contract(ROOT)
    if a.execute and (a.authorization!=AUTH or not a.onsite_observer_confirmed):raise PermissionError('new task-specific supervised authorization required')
    binary=task_sender(ROOT)
    base=ROOT/'worklog/evidence/demo-runs'/TASK_ID
    if a.prepared:
        prepared=a.prepared.resolve()
        if base not in prepared.parents:raise ValueError('candidate outside task directory')
    elif a.preflight:raise ValueError('--preflight requires --prepared')
    else:
        check_center(ROOT,request('/api/operations/telemetry',{}),task)
        prepared=base/('run_'+str(time.time_ns()));prepared.parent.mkdir(parents=True,exist_ok=True)
        env=dict(os.environ,PYTHONPATH=str(ROOT/'src'),ARES_R_ACTIVE_MANIPULATION_TASK=TASK_ID,
            ARES_R_LEVEL_TOLERANCE_DEG=str(task['level_gate_tolerance_deg']),
            ARES_R_BACKEND_URL='http://127.0.0.1:8776',ARES_R_ROUNDTRIP_API_URL='http://127.0.0.1:8775',
            ARES_R_PLANNER_SOCKET=str(ROOT/'worklog/runtime/rc1-webui/planner.sock'))
        subprocess.run([sys.executable,str(ROOT/'demos'/TASK_ID/'prepare_bundle.py'),'--output-root',str(prepared)],cwd=ROOT,env=env,check=True,timeout=240)
        subprocess.run([sys.executable,'scripts/package_pick_reset_timing.py','--prepared',str(prepared),
            '--segments','pregrasp,contact,retreat,center'],cwd=ROOT,env=env,check=True,timeout=120)
        bind_task(prepared,ROOT)
    verified=verify_task(prepared,ROOT)
    if a.prepare or a.preflight:
        print(json.dumps(dict(state='PREPARED' if a.prepare else 'STATIC_PREFLIGHT_PASS',prepared=str(prepared),
            task_id=TASK_ID,epic_command=verified['epic_command'],sender=str(binary),physical_motion=False,
            execution_authorized=False,remaining='fresh actual-state/target/onsite confirmation at execution')));return
    launched=request('/api/operations/pick-reset-timing/start',dict(prepared=str(prepared),task_demo_id=TASK_ID,
        authorization=AUTH,onsite_observer_confirmed=True))
    if launched.get('state')!='RUNNING':raise RuntimeError('canonical launch refused')
    try:
        last=None
        while True:
            state=request('/api/operations/run-status')
            if state.get('study_output')!=str(prepared/'execution'):raise RuntimeError('task ownership changed')
            label=(state.get('state'),state.get('current_stage'))
            if label!=last:print(json.dumps(state),flush=True);last=label
            if state.get('state')!='RUNNING':
                if state.get('state')!='SUCCEEDED' or state.get('study_state')!='COMPLETED':raise RuntimeError('task did not complete: '+str(state))
                return
            time.sleep(.5)
    except BaseException:request('/api/operations/stop',{});raise

if __name__=='__main__':main()
