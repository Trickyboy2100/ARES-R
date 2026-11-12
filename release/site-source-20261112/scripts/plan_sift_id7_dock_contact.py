"""Fresh ID7 dock-contact candidate. Planning only; never creates an execution handle."""
import copy,json,math,os,sys,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from ares_r.canonical_backend import CanonicalBackendClient
from ares_r.adapters.epic import EpicClient
from ares_r.manipulation.observation_transaction import detection_dict
from ares_r.perception.robot_collision import transform_xyz_rpy
from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
from ares_r.motion.independent_path_validation import validate_dense_world,_quaternion_rotation
from ares_r.motion.tcp_orientation import level_rotation,validate_level_path
from ares_r.manipulation.task_tcp_offset import demo_local_rotation
from ares_r.manipulation.dock_contact_planning import validate_dock_path
from ares_r.motion.planner_service_client import plan

def main():
    os.chdir(ROOT);out=ROOT/'worklog/evidence/sift-id7-dock-contact'/str(time.time_ns());out.mkdir(parents=True)
    def save(n,v):(out/n).write_text(json.dumps(v,indent=2)+'\n')
    c=CanonicalBackendClient('http://127.0.0.1:8776');config=json.loads((ROOT/'config/system.json').read_text())
    if c.physical_status().get('state')=='RUNNING':raise RuntimeError('physical job active')
    before=c.robot_telemetry();save('before.json',before)
    if before['errors']:raise RuntimeError(str(before['errors']))
    ec=copy.deepcopy(config['epic']);ec['task_profiles']['right_place_rightmost'].update(command='320,2,7,1,1,0',space_id=2,object_id=7,camera_id=1)
    detections=[]
    for attempt in range(3):
        e=EpicClient(ec)
        try:d=e._detect_profile('right_place_rightmost','place:ID7_DOCK_CONTACT_PLANNING_ONLY')
        finally:e.close()
        detections.append(detection_dict(d));save('detection-attempts.json',detections)
        if d.success:break
        time.sleep(.5)
    save('detection.json',detection_dict(d))
    if not d.success:raise RuntimeError(d.error)
    b=json.loads((ROOT/'config/robot_world.json').read_text())['arms']['right'];T=transform_xyz_rpy(b['base_xyz_m'],b['base_rpy_rad'])
    goal=(T@np.r_[d.pose.values()[:3],1])[:3]
    params=json.loads((ROOT/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json').read_text());task=json.loads((ROOT/'demos/right_arm_shaiwang_pick_reset_v1/params.json').read_text());params['demo_tcp_orientation_compensation'].update(task['demo_tcp_orientation_compensation_override'])
    rotation=demo_local_rotation(level_rotation(0),params)
    attachment=json.loads((ROOT/'worklog/evidence/demo-runs/right_arm_shaiwang_pick_reset_v1/run_1793267659325311826/package/first_pick_execution_package.json').read_text())['coarse_attached_object_collision']
    payload=dict(arm='right',position_m=goal.tolist(),orientation='TERMINAL_EXPLICIT',explicit_rotation=rotation.tolist(),attached_object_geometry=attachment,attached_object_revision=attachment['revision'],active_sphere_cell_m=.020,speed_profile='right_scene_aware_0_20',scene_policy='FORCE_RESCAN',planning_mode='FAST',environment_avoidance='ON',request_label='ID7_DOCK_CONTACT_FRESH_WORLD_SOURCE')
    parent=ROOT/'worklog/evidence/scene-aware-motion';prior=set(parent.glob('PLAN_*'))
    try:c.motion_plan(payload)
    except Exception as exc:save('normal_free_space_result.json',dict(error=str(exc)))
    new=set(parent.glob('PLAN_*'))-prior
    if len(new)!=1:raise RuntimeError('cannot bind source request')
    original=json.loads((new.pop()/'planner_request.json').read_text());save('full-world-request.json',original)
    after=c.robot_telemetry();save('after-scan.json',after)
    for side in ('left','right'):
        if max(abs(a-b) for a,b in zip(before['arms'][side]['joints_rad'],after['arms'][side]['joints_rad']))>math.radians(.02):raise RuntimeError('robot changed during planning observation')
    ik=RuntimeGoalIK(original['robot_yaml_urdf'],original['T_body_model'],original['T_link6_tcp']);site=json.loads((ROOT/'config/jaka_mini2_motion.site.json').read_text());ik.lower=np.maximum(ik.lower,np.array(site['lower_rad'])+site['soft_limit_margin_rad']);ik.upper=np.minimum(ik.upper,np.array(site['upper_rad'])-site['soft_limit_margin_rad'])
    q=ik.solve(goal,rotation,original['start_rad']).joints_rad
    # Bind only endpoint-intersecting observed dock primitives inside 200mm.
    # The optimizer gets a relaxed search world. Acceptance below ALWAYS uses
    # the original complete world, with per-component, terminal-only contact.
    ids=[];body=np.asarray(original['T_body_model']);proofs=[]
    for name,box in original['compiled_scene']['cuboids'].items():
        if not name.startswith(('observed_support_','observed_remaining_structure_')):continue
        center=body[:3,:3]@np.array(box['pose'][:3])+body[:3,3]
        rot=body[:3,:3]@_quaternion_rotation(box['pose'][3:]);delta=np.abs((goal-center)@rot)-np.array(box['dims'])/2
        if np.linalg.norm(np.maximum(delta,0))>.20:continue
        trial=copy.deepcopy(original);trial['compiled_scene']['cuboids']={name:box}
        proof=validate_dense_world([q,q],trial,subdivisions=2)
        if not proof['collision_free']:
            if proof['limiting_robot_component_id'] not in ('gripper_union','attached_object'):raise RuntimeError('dock overlaps ARM LINK at endpoint')
            ids.append(name);proofs.append(proof)
    if not ids:raise RuntimeError('no dock contact primitives bound')
    policy=dict(policy_id='ID7_DOCK_CONTACT_PLANNING_ONLY_V1',detection_id=d.request_id,scene_snapshot_id=original['scene_snapshot_id'],goal_body_m=goal.tolist(),radius_m=.20,target_ids=ids,endpoint_proofs=proofs,physical_motion=False,execution_enabled=False)
    save('contact-policy.json',policy);print(json.dumps(dict(output=str(out),target_body_m=goal.tolist(),contact_target_ids=ids)),flush=True)
    base=copy.deepcopy(original);base.update(runtime_motion_goal=None,goal_rad=list(q),goal_candidates_rad=[list(q)],goal_candidate_metadata=None,orientation_lock=None,hard_level_manifold=None)
    base['motion_constraints']['ignore_cuboid_ids']=ids
    attempts=[]
    for mode in ('FAST','QUALITY'):
        folder=out/mode.lower();folder.mkdir();request=copy.deepcopy(base)
        if mode=='QUALITY':request.update(solver_policy=None,latency_contract=None)
        request['warmup_policy']='NONE';rp=folder/'planner_request.json';rp.write_text(json.dumps(request,indent=2));at=time.monotonic()
        try:
            plan(config['curobo']['python'],ROOT,rp,folder/'planning.json',folder/'planner.log',120,autostart=False)
            result=json.loads((folder/'planning.json').read_text());points=result['trajectory_points_rad']
            if result['observed_result']!='SUCCESS' or len(points)<2:raise RuntimeError('cuRobo returned no accepted trajectory')
            hard=validate_dock_path(points,original,target_ids=ids,goal_body_m=goal,radius_m=.20,detection_id=d.request_id);save(mode.lower()+'-full-world-contact-validation.json',hard)
            if not hard['passed']:raise RuntimeError('full-world terminal-contact validation failed: '+str(hard))
            def physical(q):
                pose=ik.fk(q).copy();pose[:3,:3]=demo_local_rotation(pose[:3,:3],params,inverse=True);return pose
            level=validate_level_path(physical,points,tolerance_deg=4.5,subdivisions=4);end=physical(points[-1]);tilt=max(math.degrees(math.asin(min(1,abs(end[2,i])))) for i in (0,2))
            save('orientation-audit.json',dict(full_path=level,terminal_level_error_deg=tilt,initial_nonlevel_recovery=True))
            if tilt>4.5 or np.linalg.norm(ik.fk(points[-1])[:3,3]-goal)>.003:raise RuntimeError('terminal pose invalid')
            a=np.array(points)
            if np.any(a<ik.lower) or np.any(a>ik.upper):raise RuntimeError('site soft limit along path')
            import hashlib
            summary=dict(planning_passed=True,mode=mode,elapsed_s=time.monotonic()-at,trajectory_hash='sha256:'+hashlib.sha256(json.dumps(points,separators=(',',':')).encode()).hexdigest(),target_body_m=goal.tolist(),trajectory_points=len(points),hard_validation=hard,terminal_level_error_deg=tilt,full_path_level_passed=level['passed'],initial_nonlevel_recovery=True,physical_motion=False,execution_package_ready=False,output=str(out))
            save('result.json',summary);print(json.dumps(summary),flush=True);return
        except Exception as exc:
            attempts.append(dict(mode=mode,error=str(exc),elapsed_s=time.monotonic()-at));save('attempts.json',attempts);print(json.dumps(attempts[-1]),flush=True)
    raise RuntimeError('no valid dock-contact candidate; see attempts')

if __name__=='__main__':main()
