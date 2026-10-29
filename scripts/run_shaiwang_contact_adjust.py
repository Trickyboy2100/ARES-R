"""One supervised, bounded adjustment from a completed open-gripper inspection.

Uses that held, stationary task's bound target-contact geometry; never edits the
world or disables non-target/link/self/controller checks. No closing or lift.
"""
import argparse,json,os,subprocess,time,math
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation,Slerp
from ares_r.canonical_backend import CanonicalBackendClient
from ares_r.manipulation.task_contract import task_sender,load_contract
from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
from ares_r.motion.short_motion import validate_short_motion
from ares_r.motion.native_execution_package import package_native_preview
from ares_r.motion.native_demo import native_environment

ROOT=Path(__file__).resolve().parents[1]
AUTH='RIGHT CONTACT BACK3 LEFT2 PITCHDOWN1'
YAW_AUTH='RIGHT CONTACT YAW CLOCKWISE1'
RETREAT_AUTH='RIGHT RELEASE RETREAT55'

def main():
    a=argparse.ArgumentParser();a.add_argument('--prepared',type=Path,required=True)
    a.add_argument('--execute',action='store_true');a.add_argument('--authorization')
    a.add_argument('--adjustment',choices=('back-left-pitch','yaw-right','release-retreat'),default='back-left-pitch')
    a.add_argument('--checkpoint',type=Path);a.add_argument('--retreat-distance-m',type=float,default=.055);args=a.parse_args()
    if not .025<=args.retreat_distance_m<=.10:raise ValueError('retreat must be25..100mm')
    expected_auth={'back-left-pitch':AUTH,'yaw-right':YAW_AUTH,'release-retreat':RETREAT_AUTH}[args.adjustment]
    if args.execute and args.authorization!=expected_auth:
        raise PermissionError('scoped adjustment authorization required')
    p=args.prepared.resolve()
    if ROOT/'worklog/evidence/demo-runs/right_arm_shaiwang_pick_reset_v1' not in p.parents:
        raise ValueError('task inspection evidence required')
    load=lambda path:json.loads(Path(path).read_text())
    previous=load(p/'execution/result.json')
    if previous.get('result')!='CONTACT_INSPECTION_BEFORE_CLOSE' or previous.get('gripper_close_command_sent') is not False:
        raise ValueError('completed open inspection required')
    c=CanonicalBackendClient('http://127.0.0.1:8776')
    if c.physical_status().get('state')=='RUNNING':raise RuntimeError('physical owner active')
    state=c.robot_telemetry();arm=state['arms']['right']
    if state.get('errors') or state['base']['state']['current']['state']!='IDLE':raise RuntimeError('trusted stationary state required')
    prior=previous['final']
    if args.checkpoint:
        checkpoint=args.checkpoint.resolve()
        if ROOT/'worklog/evidence/shaiwang-contact-adjust' not in checkpoint.parents:
            raise ValueError('task contact adjustment checkpoint required')
        if load(checkpoint/'result.json').get('success') is not True or Path(load(checkpoint/'request.json')['source_inspection']).resolve()!=p:
            raise ValueError('completed adjustment from same inspection required')
        prior=load(checkpoint/'after.json')
    if args.adjustment!='back-left-pitch' and not args.checkpoint:raise ValueError('accepted pitch/position checkpoint required')
    for side in ('left','right'):
        if max(abs(x-y) for x,y in zip(state['arms'][side]['joints_rad'],prior['arms'][side]['joints_rad']))>math.radians(.1):
            raise RuntimeError('inspection arm state changed')
        if state['arms'][side]['tool_id']!=prior['arms'][side]['tool_id']:raise RuntimeError('tool changed')
    for key in ('id','queueId'):
        if state['base'].get('log',{}).get(key)!=prior['base'].get('log',{}).get(key):raise RuntimeError('base motion history changed')
    gripper=subprocess.run([str(ROOT/'.venv/bin/python'),'scripts/gripper_direct_once.py','status'],cwd=ROOT,capture_output=True,text=True,check=True)
    gripper=json.loads(gripper.stdout)
    if gripper['fault_code']:raise RuntimeError('gripper fault')
    if args.adjustment!='release-retreat' and abs(gripper['position_raw']-400)>20:raise RuntimeError('open40 feedback required')
    out=ROOT/'worklog/evidence/shaiwang-contact-adjust'/str(time.time_ns());out.mkdir(parents=True)
    save=lambda name,value:(out/name).write_text(json.dumps(value,indent=2)+'\n')
    save('before.json',state);save('gripper-before.json',gripper)
    request=load(p/'pregrasp/planner_request.json');request['contact_inspection_adjustment']=args.adjustment!='release-retreat'
    os.environ['ARES_R_ACTIVE_MANIPULATION_TASK']='right_arm_shaiwang_pick_reset_v1'
    os.environ['ARES_R_LEVEL_TOLERANCE_DEG']=str(load_contract(ROOT)['level_gate_tolerance_deg'])
    ik=RuntimeGoalIK(request['robot_yaml_urdf'],request['T_body_model'],request['T_link6_tcp'])
    q=arm['joints_rad'];start=ik.fk(q)
    if args.adjustment=='release-retreat':
        delta=-args.retreat_distance_m*start[:3,2];axis=np.array([0.,0.,1.]);angle_deg=0.
    elif args.adjustment=='yaw-right':
        delta=np.zeros(3);axis=np.array([0.,0.,1.]);angle_deg=-1.
    else:
        delta=np.array([-.003,.002,0.]);forward=start[:3,2]
        axis=np.cross([0.,0.,1.],forward);axis/=np.linalg.norm(axis);angle_deg=1.
    end_rotation=Rotation.from_rotvec(axis*np.deg2rad(angle_deg)).as_matrix()@start[:3,:3]
    rotations=Slerp([0,1],Rotation.from_matrix([start[:3,:3],end_rotation]))
    points=[q]
    for u in np.linspace(0,1,17)[1:]:
        solved=ik.solve(start[:3,3]+u*delta,rotations(u).as_matrix(),points[-1],position_tolerance_m=.0002,orientation_tolerance_deg=.1)
        points.append(list(solved.joints_rad))
    if args.adjustment!='release-retreat' and max(abs(x-y) for row in points for x,y in zip(row,q))>math.radians(3):raise RuntimeError('micro joint excursion exceeds3deg')
    direction=delta/np.linalg.norm(delta) if np.linalg.norm(delta)>0 else np.array([1.,0.,0.])
    def validate(rows):return validate_short_motion(rows,request,segment='contact',
        observation_id=load(p/'package/first_pick_execution_package.json')['observation_id'],direction=direction,
        central_exclusion=request['motion_constraints'].get('central_exclusion',False))
    save('geometry-proof.json',validate(points))
    package=load(p/'package/first_pick_execution_package.json');site=load(ROOT/'config/jaka_mini2_motion.site.json')
    text,audit=package_native_preview(points,.008,site,tool_id=1,
        controller_tool_pose_mm_rad=package['controller_tool_pose_mm_rad'],captured_at_unix=time.time(),
        speed_ceiling_rad_s=.05 if args.adjustment=='release-retreat' else .03,accel_ceiling_rad_s2=.1,tracking_stop_threshold_deg=1.5,
        max_excursion_rad=math.radians(220 if args.adjustment=='release-retreat' else 3),retiming_policy='VERIFIED_SHORT_V1',geometry_validator=validate)
    path=out/'adjust.native.txt';path.write_text(text);save('audit.json',audit)
    save('request.json',dict(delta_body_m=delta.tolist(),adjustment=args.adjustment,rotation_deg=angle_deg,axis_body=axis.tolist(),
        source_inspection=str(p),source_snapshot=request['scene_snapshot_id'],world_policy='SAME_HELD_STATIONARY_CONTACT_CONTEXT',
        source_data_modified=False,persistent_offsets_modified=False))
    sender=task_sender(ROOT);check=subprocess.run([str(sender),'validate-supervised-path',str(path)],env=native_environment(),capture_output=True,text=True,check=True)
    save('native-validation.json',dict(stdout=check.stdout))
    print(json.dumps(dict(output=str(out),duration_s=audit['duration_s'],geometry_pass=True,execution=args.execute)),flush=True)
    if not args.execute:return
    if args.adjustment=='release-retreat':
        command=[str(ROOT/'.venv/bin/python'),'scripts/gripper_direct_once.py']
        opened=subprocess.check_output(command+['move','--raw','400'],text=True,cwd=ROOT)
        save('release-command.json',json.loads(opened));time.sleep(.75)
        opened=json.loads(subprocess.check_output(command+['read'],text=True,cwd=ROOT));save('release-readback.json',opened)
        if abs(opened['position_raw']-400)>20:raise RuntimeError('release not confirmed; no retreat')
    try:
        with (out/'native.jsonl').open('x') as stream:
            result=subprocess.run([str(sender),'task_supervised_path',str(path),'CONFIRMED_RIGHT_CLEAR'],
                env=native_environment(),stdout=stream,stderr=subprocess.STDOUT,timeout=audit['duration_s']+20)
        events=[]
        for line in (out/'native.jsonl').read_text().splitlines():
            if line.startswith('{'):
                try:events.append(json.loads(line))
                except ValueError:pass
        success=(result.returncode==0 and any(e.get('event')=='target_reached' for e in events)
            and any(e.get('event')=='servo_disabled' and e.get('code')==0 for e in events))
        save('result.json',dict(success=success,returncode=result.returncode,events=events))
        if not success:raise RuntimeError('native adjustment failed; stopped')
    finally:c.motion_stop()
    after=c.robot_telemetry();save('after.json',after)
    print(json.dumps(dict(success=True,output=str(out),actual_delta_body_m=(np.array(after['arms']['right']['position_m'])-arm['position_m']).tolist(),final_xyz=after['arms']['right']['position_m'])),flush=True)

if __name__=='__main__':main()
