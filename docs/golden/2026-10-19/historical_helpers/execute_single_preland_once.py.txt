"""Execute exactly the operator-approved preland path; no base/gripper/demo API."""
import json,time,subprocess
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import numpy as np
from scipy.spatial.transform import Rotation
R=Path('/home/yikun/ARES-R-RC1-20261019')
PLAN='PLAN_8edf09f1a99c41cbabec2843022ec31e'
HASH='sha256:feb1330ed71c0759f534c92a2780d3ff20b15882f9c03c98188dcc13c7903d49'
O=R/'worklog/evidence/operations-single'/('20261019-preland-'+PLAN)
def write(n,v):(O/n).write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
def get(path):return json.load(urlopen('http://127.0.0.1:8775'+path,timeout=10))
def main():
    O.mkdir(parents=True,exist_ok=False)
    state=get('/api/motion/status')
    if state['plan_id']!=PLAN or state['state']!='READY':raise RuntimeError('approved plan is no longer READY')
    candidate=json.loads((R/'worklog/evidence/scene-aware-motion'/PLAN/'native_package/candidate_manifest.json').read_text())
    if candidate['trajectory_hash']!=HASH:raise RuntimeError('exact trajectory hash mismatch')
    if time.time()>candidate['expires_at_unix']:raise RuntimeError('approved candidate expired; no automatic replan or motion')
    if get('/api/demo/roundtrip/status').get('running'):raise RuntimeError('full Demo still running')
    if get('/api/operations/run-status').get('state')=='RUNNING':raise RuntimeError('another motion active')
    body={'plan_id':PLAN,'trajectory_hash':HASH,'authorization':'RIGHT SCENE_AWARE SUPERVISED',
      'onsite_observer_confirmed':True,'command_id':'OPERATOR_SINGLE_PRELAND_20261019_8edf09f1'}
    write('authorization.json',{'at_unix':time.time(),'operator_scope':'Execute only this preland motion; no release, no base move, no Demo resume',
      'request':body,'automatic_retry':False})
    request=Request('http://127.0.0.1:8775/api/operations/execute',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    try:
        response=json.load(urlopen(request,timeout=20));write('dispatch.json',response)
    except HTTPError as e:raise RuntimeError('HTTP '+str(e.code)+': '+e.read().decode(errors='replace')) from e
    print(json.dumps(response),flush=True)
    until=time.monotonic()+90
    while time.monotonic()<until:
        result=get('/api/operations/run-status')
        write('last-status.json',result)
        if result.get('command_id') not in (None,body['command_id']):raise RuntimeError('physical command identity changed')
        if result.get('state')!='RUNNING':
            write('terminal-result.json',result);print(json.dumps(result),flush=True)
            if result.get('state')!='SUCCEEDED' or not (result.get('execution_result') or {}).get('target_reached'):
                raise RuntimeError('single motion did not reach target; no retry')
            raw=subprocess.check_output([str(R/'native/jaka_right_rc1'),'snapshot'],text=True,cwd=R)
            row=next(json.loads(x) for x in raw.splitlines() if x.startswith('{') and json.loads(x).get('event')=='snapshot')
            base=json.loads((R/'config/robot_world.json').read_text())['arms']['right']
            def T(x,r):
                t=np.eye(4);t[:3,:3]=Rotation.from_euler('xyz',r).as_matrix();t[:3,3]=x;return t
            v=row['tcp_mm_rad'];pose=T(base['base_xyz_m'],base['base_rpy_rad'])@T(np.asarray(v[:3])/1000,v[3:])
            target=candidate['runtime_motion_goal']['position_m']
            measured={'sdk_snapshot':row,'T_body_tcp':pose.tolist(),'xyz_body_m':pose[:3,3].tolist(),
                'position_error_to_target_mm':float(np.linalg.norm(pose[:3,3]-target)*1000),
                'rpy_body_deg':Rotation.from_matrix(pose[:3,:3]).as_euler('xyz',degrees=True).tolist(),
                'forward_tilt_deg':float(np.degrees(np.arcsin(abs(pose[2,2])))),
                'finger_tilt_deg':float(np.degrees(np.arcsin(abs(pose[2,0])))),
                'base_or_gripper_command_sent':False,'demo_resumed':False}
            write('arrived-tcp.json',measured);print(json.dumps(measured),flush=True);return
        time.sleep(.5)
    raise RuntimeError('monitor deadline exceeded; native watchdog independent; do not retry')
try:main()
except BaseException as e:
    if O.exists():write('FAULT.json',{'error':str(e),'automatic_retry':False})
    raise
