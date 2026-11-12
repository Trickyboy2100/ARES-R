"""Explicit 2026-10-21 center operation; unique evidence, no gripper/base action."""
import argparse,json,os,socket,subprocess,time
from pathlib import Path
from urllib.request import Request,urlopen
import numpy as np
from scipy.spatial.transform import Rotation
R=Path('/home/yikun/ARES-R-RC1-20261019')
O=R/'worklog/evidence/20261021-center-grasp-planner-study'
os.environ.update(ARES_R_ROUNDTRIP_API_URL='http://127.0.0.1:8775',ARES_R_BACKEND_URL='http://127.0.0.1:8776',ARES_R_PLANNER_SOCKET=str(R/'worklog/runtime/rc1-webui/planner.sock'))
def write(name,value):
    O.mkdir(parents=True,exist_ok=True)
    (O/name).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
def get(path):return json.load(urlopen('http://127.0.0.1:8775'+path,timeout=20))
def post(path,body,timeout=330):return json.load(urlopen(Request('http://127.0.0.1:8775'+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'}),timeout=timeout))
def idle():
    if get('/api/demo/roundtrip/status').get('running') or get('/api/operations/run-status').get('state')=='RUNNING':raise RuntimeError('another physical operation active')
def bootstrap():
    for port in (8775,8776):
        with socket.socket() as s:
            if s.connect_ex(('127.0.0.1',port))==0:raise RuntimeError('RC1 already has active listener; inspect before bootstrap')
    state=R/'worklog/runtime/rc1-webui'; manifest=state/'services.json'
    if manifest.exists():
        old=json.loads(manifest.read_text())
        for p in old['processes']:
            path=Path('/proc')/str(p['pid'])/'cmdline'
            if path.exists() and [x.decode() for x in path.read_bytes().split(b'\0') if x]==p['argv']:raise RuntimeError('owned RC1 process still alive')
        manifest.rename(state/('services-before-20261021-'+str(time.time_ns())+'.json'))
    sock=state/'planner.sock'
    if sock.exists():
        with socket.socket(socket.AF_UNIX) as s:
            if s.connect_ex(str(sock))==0:raise RuntimeError('planner socket alive')
        sock.rename(state/('planner-stale-'+str(time.time_ns())+'.sock'))
    subprocess.run([str(R/'.venv/bin/python'),'scripts/start_rc1_webui.py'],cwd=R,check=True)
def center_plan():
    idle();before=post('/api/operations/telemetry',{});write('before.json',before)
    p=json.loads((R/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json').read_text())
    named=json.loads((R/'config/named_poses.json').read_text())['poses']['center']['arms']['right']
    from ares_r.manipulation.task_tcp_offset import apply_task_pose,demo_local_rotation
    center=named['body_tcp_target_m_rad'];xyz,rot=apply_task_pose(center[:3],Rotation.from_euler('xyz',center[3:]).as_matrix(),p.get('task_tcp_offset_m_rad',[0]*6))
    rot=demo_local_rotation(rot,p)
    q=np.asarray(before['arms']['right']['joints_rad']);seed=np.asarray(named['ik_joint_rad']);seed+=2*np.pi*np.round((q-seed)/(2*np.pi))
    body=dict(arm='right',position_m=xyz.tolist(),orientation='TERMINAL_EXPLICIT',explicit_rotation=rot.tolist(),environment_avoidance='ON',scene_policy='FORCE_RESCAN',planning_mode='FAST',speed_profile='right_scene_aware_0_20',ik_seed_joints_rad=[seed.tolist()],source='OPERATOR_CENTER_20261021',request_label='CENTER_BEFORE_FROZEN_PLANNER_STUDY')
    write('center-request.json',body);at=time.monotonic()
    handle=post('/api/motion/plan',body);write('center-handle.json',handle)
    write('center-planning-wall.json',dict(wall_s=time.monotonic()-at));print(json.dumps(handle),flush=True)
def center_execute():
    idle();h=json.loads((O/'center-handle.json').read_text());state=get('/api/motion/status')
    if state.get('plan_id')!=h['plan_id'] or state.get('state')!='READY':raise RuntimeError('exact current center plan not READY')
    marker=O/'center-dispatch-once.json'
    with marker.open('x') as f:json.dump(dict(plan_id=h['plan_id'],trajectory_hash=h['trajectory_hash'],at_unix=time.time(),authorization='operator: first retract to center, then GRASP'),f)
    response=post('/api/operations/execute',dict(plan_id=h['plan_id'],trajectory_hash=h['trajectory_hash'],authorization='RIGHT SCENE_AWARE SUPERVISED',onsite_observer_confirmed=True,command_id='CENTER_PLANNER_STUDY_20261021'),40)
    write('center-dispatch.json',response);until=time.monotonic()+240
    while time.monotonic()<until:
        value=get('/api/operations/run-status');write('center-last-status.json',value)
        if value.get('state')!='RUNNING':
            write('center-result.json',value)
            if value.get('state')!='SUCCEEDED' or not (value.get('execution_result') or {}).get('target_reached'):raise RuntimeError('center did not arrive; no automatic replay')
            write('after-center.json',post('/api/operations/telemetry',{}));print(json.dumps(value),flush=True);return
        time.sleep(.5)
    post('/api/operations/stop',{});raise RuntimeError('center monitoring deadline; stopped')
def main():
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['bootstrap','plan-center','execute-center']);a=parser.parse_args()
    os.chdir(R)
    {'bootstrap':bootstrap,'plan-center':center_plan,'execute-center':center_execute}[a.command]()
if __name__=='__main__':main()
