"""Current held-object->BODY center, planning then exact supervised execution."""
import json,os,sys,time
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import numpy as np
R=Path('/home/yikun/ARES-R-RC1-20261019');O=R/'worklog/evidence/operations-single/20261019-center-with-payload-after-return'
def load(p):return json.loads(p.read_text())
def save(n,v):(O/n).write_text(json.dumps(v,indent=2)+'\n')
def get(p):return json.load(urlopen('http://127.0.0.1:8775'+p,timeout=20))
def post(p,v,timeout=300):
    try:return json.load(urlopen(Request('http://127.0.0.1:8775'+p,data=json.dumps(v).encode(),headers={'Content-Type':'application/json'}),timeout=timeout))
    except HTTPError as e:raise RuntimeError(str(e.code)+': '+e.read().decode()) from e
try:
    if get('/api/demo/roundtrip/status').get('running') or get('/api/operations/run-status').get('state')=='RUNNING':raise RuntimeError('another task active')
    returned=load(R/'worklog/evidence/operations-single/20261019-authorized-payload-return-grasp-v2/REPORT.json')
    if returned['state']!='RETURNED_GRASP_WITH_PAYLOAD':raise RuntimeError('base return not complete')
    if '--execute' not in sys.argv:
        O.mkdir(parents=True,exist_ok=False)
        t=post('/api/operations/telemetry',{});save('before.json',t)
        if t.get('errors'):raise RuntimeError('telemetry invalid')
        job=load(R/'worklog/evidence/demo-runs/right_arm_grasp_place_roundtrip_v1/web_1792401640042994085/job.json')
        attached=job['completed'][-1]['snapshot']['context']['attached']
        target=load(R/'config/named_poses.json')['poses']['center']['arms']['right']['body_tcp_target_m_rad'][:3]
        body={'arm':'right','position_m':target,'orientation':'EXPLICIT',
              'explicit_rotation':np.asarray(t['arms']['right']['T_body_tcp'])[:3,:3].tolist(),
              'environment_avoidance':'ON','scene_policy':'FORCE_RESCAN','planning_mode':'QUALITY',
              'attached_object_geometry':attached,'attached_object_revision':attached['revision'],
              'speed_profile':'right_scene_aware_0_20','request_label':'CENTER_BODY_POSITION_KEEP_HELD_LEVEL',
              'source':'OPERATOR_RETURN_GRASP_AND_CENTER_WITH_PAYLOAD'}
        save('request.json',body);h=post('/api/motion/plan',body);save('handle.json',h);print(json.dumps(h),flush=True)
    else:
        h=load(O/'handle.json');s=get('/api/motion/status')
        if s.get('state')!='READY' or s.get('plan_id')!=h['plan_id']:raise RuntimeError('exact candidate not ready')
        plan=load(R/h['plan_artifact']/'planning.json');request=load(R/h['plan_artifact']/'planner_request.json')
        from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
        from ares_r.manipulation.task_tcp_offset import demo_local_rotation
        from ares_r.motion.tcp_orientation import validate_level_path
        ik=RuntimeGoalIK(request['robot_yaml_urdf'],request['T_body_model'],request['T_link6_tcp'])
        p=load(R/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json')
        def physical(q):
            t=ik.fk(q);t[:3,:3]=demo_local_rotation(t[:3,:3],p,inverse=True);return t
        proof=validate_level_path(physical,plan['trajectory_points_rad'],tolerance_deg=3,subdivisions=4)
        save('physical-level-proof.json',proof)
        if not proof['passed'] or not plan['independent_dense_validation']['collision_free']:raise RuntimeError('held center path validation failed')
        with (O/'dispatch-once.json').open('x') as f:json.dump({'plan_id':h['plan_id'],'hash':h['trajectory_hash'],'at_unix':time.time()},f)
        result=post('/api/operations/execute',{'plan_id':h['plan_id'],'trajectory_hash':h['trajectory_hash'],
            'authorization':'RIGHT SCENE_AWARE SUPERVISED','onsite_observer_confirmed':True,'command_id':'OPERATOR_CENTER_WITH_PAYLOAD_AFTER_RETURN_20261019'},30)
        save('dispatch.json',result);print(json.dumps(result),flush=True)
        end=time.monotonic()+300
        while time.monotonic()<end:
            s=get('/api/operations/run-status');save('execution-status.json',s)
            if s.get('state')!='RUNNING':
                if s.get('state')!='SUCCEEDED' or not s.get('execution_result',{}).get('target_reached'):raise RuntimeError('center not reached')
                actual=post('/api/operations/telemetry',{});save('after.json',actual)
                save('REPORT.json',{'state':'GRASP_AND_CENTER_REACHED_WITH_PAYLOAD','release':False,'center_orientation':'keep compensated level; BODY center XYZ',
                     'actual_body_tcp':actual['arms']['right']['T_body_tcp'],'execution':s})
                print(json.dumps({'state':'GRASP_AND_CENTER_REACHED_WITH_PAYLOAD','xyz':actual['arms']['right']['position_m']}),flush=True);break
            time.sleep(.5)
        else:raise RuntimeError('center monitoring timeout')
except BaseException as e:
    if O.exists():save('FAULT.json',{'error':str(e),'automatic_retry':False})
    raise
