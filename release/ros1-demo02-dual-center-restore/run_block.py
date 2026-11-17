#!/usr/bin/env python3
import argparse,json,os,signal,sys,time
from pathlib import Path
ROOT=Path(os.environ.get('ARES_R_SITE_ROOT','/home/yikun/ARES-R-RC1-20261019'))
sys.path.insert(0,str(ROOT/'src'))
from dual_center_restore.core import sequence,validate_pair
from dual_center_restore.live import LiveProvider,save
from ares_r.perception.robot_collision import transform_xyz_rpy
import numpy as np


def make_targets(provider,goal,live,out):
    right=json.loads((ROOT/'config/named_poses.json').read_text())['poses']['center']['arms']['right']
    centers={}
    def mirrored_pair(source):
        pair={'right':source}
        telemetry={'arms':{a:dict(joints_rad=live['arms'][a]['joints_rad'],T_body_tcp=live['arms'][a]['T_body_tcp']) for a in ('left','right')}}
        telemetry['arms']['right'].update(joints_rad=source['joints_rad'],T_body_tcp=source['T_body_tcp'])
        plan=provider.model.solve('right','left',telemetry,match_tcp=True)
        pair['left']=dict(arm='left',joints_rad=plan['target_rad'],T_body_tcp=plan['tcp_target_body'],tool_id=live['arms']['left']['tool_id'])
        return validate_pair(pair)
    pose=right['body_tcp_target_m_rad'];centers=mirrored_pair(dict(arm='right',joints_rad=right['ik_joint_rad'],T_body_tcp=transform_xyz_rpy(pose[:3],pose[3:]).tolist(),tool_id=live['arms']['right']['tool_id']))
    provider.center_targets=centers
    if goal['target_mode']=='CAPTURE_START':targets=live['arms']
    elif goal['target_mode']=='SAVED_POSE_REF':
        registry=json.loads((ROOT/'config/arm_pose_registry.json').read_text())
        source=registry['poses']['right/front_right_high_axes_aligned']
        if source['tool_id']!=live['arms']['right']['tool_id']:raise ValueError('SAVED_TOOL_CHANGED')
        predicted=provider.model.tcp('right',source['joints_rad']);stored=np.asarray(source['T_body_tcp'])
        from scipy.spatial.transform import Rotation
        if np.linalg.norm(predicted[:3,3]-stored[:3,3])>.003 or Rotation.from_matrix(predicted[:3,:3].T@stored[:3,:3]).magnitude()>np.deg2rad(1):raise ValueError('SAVED_TARGET_TOOL_FK_MISMATCH')
        targets=mirrored_pair(source)
        if goal.get('saved_pose_id') not in ('dual/front_high','dual/front_high_mirrored'):raise ValueError('PAIR_SAVED_POSE_ID_REQUIRED')
        # Client pins the right source; the generated left target and tool
        # bindings are frozen in this run before any movement.
        import hashlib
        if source.get('source_path'):
            source_file=ROOT/source['source_path']
        else:
            candidates=[]
            for path in (ROOT/source['evidence']).glob('*.json'):
                try:
                    if json.loads(path.read_text())==source:candidates.append(path)
                except (ValueError,OSError):pass
            if len(candidates)!=1:raise ValueError('SAVED_SOURCE_AMBIGUOUS')
            source_file=candidates[0]
        actual=hashlib.sha256(source_file.read_bytes()).hexdigest()
        if actual!=goal.get('expected_saved_pose_sha'):raise ValueError('SAVED_SOURCE_REVISION_CHANGED')
    else:raise ValueError('INVALID_TARGET_MODE')
    save(out/'target-pair.json',targets);save(out/'center-pair.json',centers);return targets


def main():
    p=argparse.ArgumentParser();p.add_argument('--goal',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--execute',action='store_true');args=p.parse_args()
    goal=json.loads(args.goal.read_text());out=args.output;out.mkdir(parents=True,exist_ok=False)
    if args.execute:
        import hashlib
        ready=ROOT/'worklog/runtime/demo02/readiness.json'
        proof=json.loads(ready.read_text()) if ready.exists() else {}
        if proof.get('planning_preflight_passed') is not True:raise ValueError('DUAL_SITE_PREFLIGHT_PENDING')
        if proof.get('native_sha256')!=hashlib.sha256((ROOT/'native/jaka_dual_arm_supervised').read_bytes()).hexdigest():raise ValueError('DUAL_NATIVE_REVISION_CHANGED')
    if not all(goal.get(k) is True for k in ('onsite_observer_confirmed','prepared_environment_confirmed','empty_hand_confirmed')):raise ValueError('NOT_CONFIRMED')
    provider=LiveProvider(ROOT,out)
    registry=json.loads((ROOT/'config/operations.json').read_text()) if (ROOT/'config/operations.json').exists() else None
    from ares_r.operations import OperationsRegistry
    provider.central=OperationsRegistry(ROOT).read()['policy']['central_exclusion']
    def stop(signum,frame):provider.stop.write_text('OPERATOR_STOP\n')
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,stop)
    try:
        live=provider.observe_both();save(out/'initial-state.json',live)
        targets=make_targets(provider,goal,live,out)
        if goal['target_mode']=='SAVED_POSE_REF':
            from dual_center_restore.fixed_sequence import fixed_sequence
            result=fixed_sequence(provider,targets,args.execute)
        else:result=sequence(provider,targets,args.execute)
    except BaseException as exc:result=dict(success=False,terminal_state='FAULT',return_to_saved_pose_verified=False,error_code=str(exc))
    save(out/'result.json',result);print(json.dumps(result,ensure_ascii=False));return 0 if result['success'] else 1
if __name__=='__main__':raise SystemExit(main())
