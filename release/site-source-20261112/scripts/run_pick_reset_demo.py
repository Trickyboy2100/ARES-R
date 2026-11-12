"""Thin formal-demo client for the already tested stationary pick/reset backend.

No new motion algorithm: fresh preparation, partial Native packaging, canonical
start/monitor/stop. The original first-pick and roundtrip demos stay untouched.
"""
import argparse,hashlib,json,os,subprocess,sys,time
from pathlib import Path
from urllib.request import Request,urlopen

ROOT=Path(__file__).resolve().parents[1]
SITE_ROOT=Path('/home/yikun/ARES-R-RC1-20261019')
DEMO='right_arm_pick_lift_replace_reset_v1'
AUTH='RIGHT PICK RESET TIMING'

def load(path):return json.loads(Path(path).read_text())

def verify_pinned_inputs(root):
    definition=root/'demos'/DEMO
    expected=load(definition/'source_parameters.json')
    if load(root/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json')!=expected:
        raise RuntimeError('formal demo parameters differ; explicit new-version review required')
    for name,wanted in load(definition/'pinned_inputs.json')['sha256'].items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=wanted:
            raise RuntimeError('formal demo pinned input changed: '+name)

def request(path,body=None):
    url=os.environ.get('ARES_R_ROUNDTRIP_API_URL','http://127.0.0.1:8775').rstrip('/')+path
    req=Request(url,data=None if body is None else json.dumps(body).encode(),
                headers={'Content-Type':'application/json'})
    with urlopen(req,timeout=20) as stream:return json.load(stream)

def main():
    p=argparse.ArgumentParser();group=p.add_mutually_exclusive_group(required=True)
    group.add_argument('--prepare',action='store_true');group.add_argument('--execute',action='store_true');group.add_argument('--stop',action='store_true')
    p.add_argument('--prepared',type=Path);p.add_argument('--authorization');p.add_argument('--onsite-observer-confirmed',action='store_true')
    a=p.parse_args()
    if ROOT!=SITE_ROOT:raise RuntimeError('commissioned isolated RC1 root required')
    if a.stop:print(json.dumps(request('/api/operations/stop',{})));return
    if a.execute and (a.authorization!=AUTH or not a.onsite_observer_confirmed):
        raise PermissionError('supervised authorization required before preparation or execution')
    verify_pinned_inputs(ROOT)
    status=request('/api/demo/roundtrip/status')
    if status.get('runtime_binding',{}).get('repository_root')!=str(ROOT):raise RuntimeError('canonical backend root mismatch')
    base=ROOT/'worklog/evidence/demo-runs'/DEMO
    if a.prepared:
        prepared=a.prepared.resolve()
        if base not in prepared.parents:raise ValueError('prepared candidate must belong to this demo')
    else:
        prepared=base/('run_'+str(time.time_ns()));prepared.parent.mkdir(parents=True,exist_ok=True)
        env=dict(os.environ,PYTHONPATH=str(ROOT/'src'))
        subprocess.run([sys.executable,'scripts/studies/20261022-pick-reset/prepare_pick_reset_bundle.py',
            '--output-root',str(prepared)],cwd=ROOT,env=env,check=True,timeout=240)
        subprocess.run([sys.executable,'scripts/package_pick_reset_timing.py','--prepared',str(prepared),
            '--segments','pregrasp,contact,retreat,center','--settle-tail',
            str(int(load(ROOT/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json').get('native_settle_tail_samples') or 0))],
            cwd=ROOT,env=env,check=True,timeout=120)
    if a.prepare:
        print(json.dumps(dict(state='PREPARED',prepared=str(prepared),physical_motion=False)));return
    verify_pinned_inputs(ROOT)
    started=request('/api/operations/pick-reset-timing/start',dict(prepared=str(prepared),
        authorization=AUTH,onsite_observer_confirmed=True))
    if started.get('state')!='RUNNING':raise RuntimeError('canonical start rejected: '+str(started))
    try:
        last=None
        while True:
            state=request('/api/operations/run-status')
            if state.get('study_output')!=str(prepared/'execution'):raise RuntimeError('canonical execution ownership changed')
            label=(state.get('state'),state.get('current_stage'))
            if label!=last:print(json.dumps(state),flush=True);last=label
            if state.get('state')!='RUNNING':
                if state.get('state')!='SUCCEEDED' or state.get('study_state')!='COMPLETED':
                    raise RuntimeError('demo did not complete: '+str(state))
                break
            time.sleep(.5)
    except BaseException:
        request('/api/operations/stop',{});raise

if __name__=='__main__':main()
