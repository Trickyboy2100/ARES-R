"""Uses current RC1 center helpers and canonical scene-aware plan/execute APIs."""
import importlib.util,json,os,sys,time,hashlib,subprocess,math
from pathlib import Path
from .core import resolve_target,unchanged_source,digest,sequence


def run(root,out,goal,execute):
    spec=importlib.util.spec_from_file_location('existing_center',str(root/'scripts/run_return_center_demo.py'))
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    out.mkdir(parents=True,exist_ok=False)
    def save(name,value):old.save_json(out/name,value)
    params=old.load(old.PARAMETERS)
    live=old.preflight(out);old.site_ceiling(params['required_site_max_velocity_rad_s'])
    if execute and goal.get('empty_hand_confirmed') is not True:raise ValueError('EMPTY_HAND_NOT_CONFIRMED')
    if not old.base_stationary().get('stationary'):raise ValueError('BASE_NOT_STATIONARY')
    target,pin=resolve_target(root,goal,live)
    def raw_tool():
        from ares_r.motion.scene_aware_execution import SENDER
        p=subprocess.run([str(SENDER),'snapshot'],capture_output=True,text=True,timeout=10)
        if p.returncode:raise RuntimeError('READONLY_NATIVE_SNAPSHOT_FAILED: '+p.stderr[-300:])
        return next(json.loads(x) for x in p.stdout.splitlines() if x.startswith('{') and json.loads(x).get('event')=='snapshot')
    tool=raw_tool()
    config_files=['config/system.json','config/robot_world.json','config/jaka_tools.site.json','config/robot_collision_model.json','config/named_poses.json',
                  'demos/right_arm_grasp_place_roundtrip_v1/parameters.json',
                  'demos/right_arm_shaiwang_pick_reset_v1/params.json',
                  'worklog/evidence/2026-09-20-p2-collision-model/right_fk_audit.json',
                  '/home/yikun/ares-r-curobo-assets/robot/robot.yml']
    hashes={f:hashlib.sha256((root/f).read_bytes()).hexdigest() for f in config_files}
    def base_marker(t):
        b=t['base'];return [b['info']['mapId'],b['log'].get('id'),b['log'].get('queueId')]
    marker=base_marker(live);left=live['arms']['left']['joints_rad']
    binding=dict(target=target,source=pin,target_digest=digest(target),mode=goal['target_mode'],actual_before=live,tool=tool,config_hashes=hashes,base_marker=marker,left_joints=left)
    save('saved_pose_record.json',target);save('goal_binding.json',binding);save('goal.json',goal)
    # Legacy measured snapshot: verify its joints/TCP under current calibrated FK+active tool.
    import numpy as np
    from ares_r.perception.robot_collision import arm_link_transforms,_world_arm_transform,transform_xyz_rpy
    model=old.load(root/'config/robot_collision_model.json');world=old.load(root/'config/robot_world.json')
    audit=old.load(root/'worklog/evidence/2026-09-20-p2-collision-model/right_fk_audit.json')
    T=(_world_arm_transform(world,'right')@np.asarray(audit['T_controller_model'])@
       arm_link_transforms(Path(model['asset_root'])/model['urdf'],target['joints_rad'])['link6']@
       transform_xyz_rpy(np.asarray(tool['tool_mm_rad'][:3])*.001,tool['tool_mm_rad'][3:]))
    saved_goal=dict(position_m=np.asarray(target['T_body_tcp'])[:3,3].tolist(),explicit_rotation=np.asarray(target['T_body_tcp'])[:3,:3].tolist())
    fk_error=old.center_error({'arms':{'right':{'T_body_tcp':T.tolist()}}},saved_goal)
    save('saved-fk-validation.json',fk_error)
    if fk_error['position_m']>.003 or fk_error['orientation_deg']>3:raise ValueError('SAVED_POSE_CURRENT_FK_DISAGREEMENT')
    if tool['tool_id']!=target['tool_id']:raise ValueError('TOOL_REVISION_CHANGED')
    class Adapter:
        def event(self,leg,phase):
            row=dict(stage=leg,phase=phase,at_unix=time.time(),progress='START')
            print(json.dumps(row),flush=True)
            with (out/'events.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
        def bindings_valid(self,target):
            unchanged_source(root,goal,pin)
            for f,sha in hashes.items():
                if hashlib.sha256((root/f).read_bytes()).hexdigest()!=sha:raise ValueError('CALIBRATION_MODEL_REVISION_CHANGED')
            t=old.api('/api/operations/telemetry',{},timeout=10)
            if t.get('errors') or base_marker(t)!=marker:raise ValueError('BASE_OR_STATE_BINDING_CHANGED')
            if max(abs(a-b) for a,b in zip(left,t['arms']['left']['joints_rad']))>math.radians(.1):raise ValueError('INACTIVE_LEFT_MOVED')
            if not old.base_stationary().get('stationary'):raise ValueError('BASE_NOT_STATIONARY')
            now=raw_tool()
            if now['tool_id']!=tool['tool_id'] or now['user_id']!=tool['user_id'] or max(abs(a-b) for a,b in zip(now['tool_mm_rad'],tool['tool_mm_rad']))>1e-6:raise ValueError('TOOL_REVISION_CHANGED')
        def plan(self,leg,target):
            dest=out/leg;dest.mkdir()
            state=old.api('/api/operations/telemetry',{})
            old.save_json(dest/'telemetry-before.json',state)
            g=old.center_goal(root) if hasattr(old,'center_goal') else None
            if leg=='center_leg':
                from ares_r.manipulation.task_contract import center_goal
                g=center_goal(root)
                err=old.center_error(state,g)
                if err['position_m']<=.003 and err['orientation_deg']<=3:
                    return dict(no_motion=True,goal=g)
                self.center_record=old.plan_and_verify(dest,g,params,params['required_site_max_velocity_rad_s'],True)[0]
                return dict(no_motion=False,goal=g,record=self.center_record)
            # Rehearsal uses predicted center endpoint, never publishes executable old-scene path.
            if not execute and not result_center_current:
                from ares_r.motion.planner_service_client import plan as persistent_plan
                h=self.center_record['handle'];a=root/h['plan_artifact']
                request=old.load(a/'planner_request.json');planned=old.load(a/'planning.json')
                request.update(physical_state='SIMULATED_FOR_SCHEME_REHEARSAL',execution_allowed=False,planning_only=True,start_rad=planned['trajectory_points_rad'][-1],goal_rad=target['joints_rad'],goal_candidates_rad=[target['joints_rad']],orientation_lock=None,runtime_motion_goal=None)
                req=dest/'simulated_planner_request.json';old.save_json(req,request)
                response=persistent_plan(sys.executable,root,req,dest/'simulated_result.json',dest/'simulated_planner.log',timeout_s=180,autostart=False)
                output=old.load(response,{})
                if output.get('observed_result')!='SUCCESS':raise RuntimeError('SIMULATED_RESTORE_PLAN_FAILED')
                return dict(rehearsal='SIMULATED_CENTER_START_NOT_EXECUTABLE',fresh_execution_replan_required=True,artifact=str(response))
            g=saved_goal
            attempts=[]
            for mode in params['planning_modes']:
                payload=dict(arm='right',goal_joints_rad=target['joints_rad'],orientation='FREE',scene_policy='FORCE_RESCAN',speed_profile=params['speed_profile'],planning_mode=mode,environment_avoidance=params['environment_avoidance'],request_label='CENTER_RESTORE_SAVED')
                try:
                    h=old.api('/api/motion/plan',payload,timeout=300)
                    attempts.append(dict(mode=mode,plan_id=h.get('plan_id')))
                    if h.get('execution_package_ready'):
                        artifact=root/h['plan_artifact'];planning=old.load(artifact/'planning.json')
                        if max(abs(a-b) for a,b in zip(planning['trajectory_points_rad'][-1],target['joints_rad']))>math.radians(.05):raise ValueError('SAVED_JOINT_BRANCH_MISMATCH')
                        old.save_json(dest/'plan_handle.json',h)
                        return dict(no_motion=False,goal=g,record=dict(handle=h,mode=mode,attempts=attempts))
                except old.ApiError as exc:
                    attempts.append(dict(mode=mode,error=str(exc)))
            old.save_json(dest/'planning-attempts.json',attempts);raise RuntimeError('RESTORE_CUROBO_PLAN_FAILED')
        def execute(self,leg,plan,target):
            dest=out/leg
            if plan.get('no_motion'):
                from ares_r.motion.arrival_confirmation import inspect_sample
                rows=[]
                for i in range(3):
                    t=old.api('/api/operations/telemetry',{})
                    row=inspect_sample(t,plan['goal'],live,params['arrival_tolerance'],time.time());rows.append(row);time.sleep(.2)
                a=dict(passed=all(x['passed'] for x in rows) and len({x['state_timestamp'] for x in rows})==3,no_motion=True,samples=rows)
            else:
                a=old.dispatch(plan['record'],params,dest,plan['goal'])
            if leg=='restore_leg':
                t=old.api('/api/operations/telemetry',{});old.save_json(dest/'final-telemetry.json',t)
                err=max(abs(a-b) for a,b in zip(t['arms']['right']['joints_rad'],target['joints_rad']))
                a.update(max_joint_error_deg=math.degrees(err));a['passed']=a['passed'] and err<=math.radians(.05)
            old.save_json(dest/'arrival.json',a);return a
    from ares_r.manipulation.task_contract import center_goal
    e=old.center_error(live,center_goal(root));result_center_current=e['position_m']<=.003 and e['orientation_deg']<=3
    result=sequence(Adapter(),target,execute)
    if not execute and result.get('legs',{}).get('restore_leg',{}).get('plan',{}).get('executable') is False:
        result.update(success=False,terminal_state='PREPARE_PARTIAL_SIMULATED_REHEARSAL_PENDING')
    result.update(target_id=target['pose_id'],target_revision=digest(target),source_sha=pin['sha256'] if pin else None,evidence_uri=str(out),request_id=goal['request_id'])
    save('result.json',result);print(json.dumps(result),flush=True)
    return result


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--goal',required=True);p.add_argument('--output',required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
    goal=json.loads(Path(a.goal).read_text())
    try:
        result=run(Path(os.environ['ARES_R_SITE_ROOT']),Path(a.output),goal,a.execute)
    except BaseException as exc:
        output=Path(a.output);output.mkdir(parents=True,exist_ok=True)
        result=dict(success=False,terminal_state='FAULT',return_to_saved_pose_verified=False,
                    error_code=str(exc),request_id=goal.get('request_id'),target_id=goal.get('saved_pose_id'),
                    expected_source_sha=goal.get('expected_saved_pose_sha'),evidence_uri=str(output),
                    dispatch_markers=[str(p) for p in output.glob('*/dispatched-once.json')])
        (output/'result.json').write_text(json.dumps(result,indent=2))
        print(json.dumps(result),flush=True)
    raise SystemExit(0 if result['success'] else 1)
