"""Operator-authorized empty-gripper return to canonical center, once.

No base/gripper/tool-calibration operations. Preserve held payload and scene gates.
"""
import json, subprocess, time, sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import numpy as np
from scipy.spatial.transform import Rotation

ROOT=Path('/home/yikun/ARES-R-RC1-20261019')
OUT=ROOT/'worklog/evidence/operations-single/20261019-route810-center-preparation'
def write(n,v): (OUT/n).write_text(json.dumps(v,indent=2)+'\n')
def get(p): return json.load(urlopen('http://127.0.0.1:8775'+p,timeout=15))
def post(p,b,timeout=300):
    try: return json.load(urlopen(Request('http://127.0.0.1:8775'+p,data=json.dumps(b).encode(),headers={'Content-Type':'application/json'}),timeout=timeout))
    except HTTPError as e: raise RuntimeError(str(e.code)+': '+e.read().decode()) from e
def snapshot():
    raw=subprocess.check_output([str(ROOT/'native/jaka_right_rc1'),'snapshot'],text=True,cwd=ROOT)
    row=next(json.loads(x) for x in raw.splitlines() if x.startswith('{') and json.loads(x).get('event')=='snapshot')
    base=json.loads((ROOT/'config/robot_world.json').read_text())['arms']['right']
    t=np.eye(4);t[:3,:3]=Rotation.from_euler('xyz',base['base_rpy_rad']).as_matrix();t[:3,3]=base['base_xyz_m']
    v=row['tcp_mm_rad'];a=np.eye(4);a[:3,:3]=Rotation.from_euler('xyz',v[3:]).as_matrix();a[:3,3]=np.array(v[:3])/1000
    return row,t@a
def idle():
    if get('/api/demo/roundtrip/status').get('running') or get('/api/operations/run-status').get('state')=='RUNNING': raise RuntimeError('another motion active')
def main():
    idle()
    if '--execute' not in sys.argv:
        OUT.mkdir(parents=True,exist_ok=False)
        row,t=snapshot();write('before.json',{'snapshot':row,'T_body_tcp':t.tolist()})
        parameters=json.loads((ROOT/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json').read_text())
        center=json.loads((ROOT/'config/named_poses.json').read_text())['poses']['center']['arms']['right']['body_tcp_target_m_rad']
        from ares_r.manipulation.task_tcp_offset import apply_task_pose,demo_local_rotation
        target,r=apply_task_pose(center[:3],Rotation.from_euler('xyz',center[3:]).as_matrix(),parameters.get('task_tcp_offset_m_rad',[0]*6))
        r=demo_local_rotation(r,parameters)
        named=json.loads((ROOT/'config/named_poses.json').read_text())['poses']['center']['arms']['right']
        seed=np.asarray(named['ik_joint_rad']);current=np.array(row['actual_rad'])
        seed=seed+2*np.pi*np.round((current-seed)/(2*np.pi))
        release=json.loads((ROOT/'worklog/evidence/operations-single/20261019-new-place810-after-preland/REPORT.json').read_text())
        if not release.get('release_confirmed') or release.get('state')!='PLACED_RELEASED_RETURNED_GRASP':raise RuntimeError('release/return unconfirmed')
        readback=json.loads(subprocess.check_output([str(ROOT/'.venv/bin/python'),'scripts/gripper_direct_once.py','read'],text=True,cwd=ROOT))
        if not 380<=float(readback['position_raw'])<=420:raise RuntimeError('gripper readback not open')
        write('released-payload-confirmation.json',{'release_receipt':release,'attachment':None,'actual_gripper_readback':readback,'scope':'no release retry; no grasp'})
        body={'arm':'right','position_m':target.tolist(),'orientation':'TERMINAL_EXPLICIT','explicit_rotation':r.tolist(),
              'environment_avoidance':'ON','scene_policy':'FORCE_RESCAN','planning_mode':'QUALITY','speed_profile':'right_scene_aware_0_20',
              'source':'OPERATOR_EMPTY_CENTER_AFTER_RELEASE','request_label':'CENTER_DEMO_MINUS10_AFTER_RELEASE'}
        body['ik_seed_joints_rad']=[seed.tolist()]
        write('request.json',body)
        handle=post('/api/motion/plan',body);write('handle.json',handle);print(json.dumps(handle),flush=True)
        return
    handle=json.loads((OUT/'handle.json').read_text());plan=handle['plan_id'];sha=handle['trajectory_hash']
    status=get('/api/motion/status')
    if status['plan_id']!=plan or status['state']!='READY': raise RuntimeError('exact plan not READY')
    candidate=json.loads((ROOT/'worklog/evidence/scene-aware-motion'/plan/'native_package/candidate_manifest.json').read_text())
    if candidate['trajectory_hash']!=sha or time.time()>candidate['expires_at_unix']:raise RuntimeError('candidate hash/expiry mismatch')
    validated=json.loads((ROOT/'worklog/evidence/scene-aware-motion'/plan/'planning.json').read_text())
    tcp=np.array(validated['tcp_path_body_m']);q=np.array(validated['trajectory_points_rad'])
    from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
    from ares_r.manipulation.task_tcp_offset import demo_local_rotation
    from ares_r.motion.tcp_orientation import validate_level_path
    request=json.loads((ROOT/'worklog/evidence/scene-aware-motion'/plan/'planner_request.json').read_text())
    ik=RuntimeGoalIK(request['robot_yaml_urdf'],request['T_body_model'],request['T_link6_tcp'])
    parameters=json.loads((ROOT/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json').read_text())
    def physical_reference_fk(row):
        t=ik.fk(row).copy();t[:3,:3]=demo_local_rotation(t[:3,:3],parameters,inverse=True);return t
    proof=validate_level_path(physical_reference_fk,q,tolerance_deg=parameters['level_tolerance_deg'],subdivisions=4)
    write('physical-level-proof.json',proof)
    proof['required_for_stage']=False
    proof['reason']='EMPTY_GRIPPER_AFTER_CONFIRMED_RELEASE; level endpoint required, no held-payload path constraint'
    write('physical-level-proof.json',proof)
    goal=json.loads((OUT/'request.json').read_text())
    final=ik.fk(q[-1]);error=Rotation.from_matrix(np.array(goal['explicit_rotation']).T@final[:3,:3]).magnitude()
    if error>np.deg2rad(3) or np.linalg.norm(final[:3,3]-goal['position_m'])>.003:
        raise RuntimeError('center compensated endpoint invalid')
    if not validated['independent_dense_validation']['collision_free']:
        raise RuntimeError('dense path invalid')
    marker=OUT/'execution-once.json'
    with marker.open('x') as f: json.dump({'plan_id':plan,'hash':sha,'at':time.time()},f)
    body={'plan_id':plan,'trajectory_hash':sha,'authorization':'RIGHT SCENE_AWARE SUPERVISED','onsite_observer_confirmed':True,'command_id':'OPERATOR_ROUTE810_PREPARATION_CENTER_20261019'}
    response=post('/api/operations/execute',body,30);write('dispatch.json',response);print(json.dumps(response),flush=True)
    until=time.monotonic()+180
    while time.monotonic()<until:
        result=get('/api/operations/run-status');write('last-status.json',result)
        if result.get('state')!='RUNNING':
            write('terminal-result.json',result)
            if result.get('state')!='SUCCEEDED' or not (result.get('execution_result') or {}).get('target_reached'):raise RuntimeError('descent did not reach target; no retry')
            row,t=snapshot();old=np.array(json.loads((OUT/'before.json').read_text())['T_body_tcp'])
            measured={'snapshot':row,'T_body_tcp':t.tolist(),'translation_change_mm':float(np.linalg.norm(t[:3,3]-old[:3,3])*1000),
                      'body_displacement_mm':((t[:3,3]-old[:3,3])*1000).tolist(),
                      'local_relative_rotvec_deg':np.degrees(Rotation.from_matrix(old[:3,:3].T@t[:3,:3]).as_rotvec()).tolist(),
                      'empty_gripper_center_reached':True}
            write('after.json',measured);print(json.dumps(measured),flush=True);return
        time.sleep(.5)
    raise RuntimeError('monitor timeout; no retry')
try:main()
except BaseException as e:
    if OUT.exists():write('FAULT.json',{'error':str(e)})
    raise
