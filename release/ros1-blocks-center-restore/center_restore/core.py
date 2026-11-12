"""Pure target binding and two-leg sequencing. No SDK or ROS imports."""
import hashlib,json,math
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def validate_pose(pose):
    if pose.get('arm')!='right':raise ValueError('RIGHT_ARM_ONLY')
    q=pose.get('joints_rad',[]);t=pose.get('T_body_tcp',[])
    if len(q)!=6 or not all(math.isfinite(float(x)) for x in q):raise ValueError('INVALID_SAVED_JOINTS')
    if len(t)!=4 or any(len(row)!=4 for row in t) or not all(math.isfinite(float(x)) for row in t for x in row):raise ValueError('INVALID_SAVED_TCP')
    if not isinstance(pose.get('tool_id'),int):raise ValueError('MISSING_TOOL_BINDING')
    return pose


def resolve_target(root,goal,telemetry):
    mode=goal.get('target_mode')
    if mode=='CAPTURE_START':
        a=telemetry['arms']['right']
        return validate_pose(dict(arm='right',pose_id='right/captured_start/'+goal['request_id'],joints_rad=a['joints_rad'],T_body_tcp=a['T_body_tcp'],tool_id=a['tool_id'],captured_at_unix=telemetry['captured_at_unix'])),None
    if mode!='SAVED_POSE_REF':raise ValueError('INVALID_TARGET_MODE')
    registry=json.loads((Path(root)/'config/arm_pose_registry.json').read_text())
    pose=registry['poses'].get(goal.get('saved_pose_id'))
    if not pose:raise ValueError('SAVED_POSE_NOT_FOUND')
    validate_pose(pose)
    if pose.get('source_path'):
        path=(Path(root)/pose['source_path']).resolve()
    else:
        candidates=[]
        for f in (Path(root)/pose['evidence']).glob('*.json'):
            try:
                if digest(json.loads(f.read_text()))==digest(pose):candidates.append(f.resolve())
            except (ValueError,OSError):pass
        if len(candidates)!=1:raise ValueError('SAVED_POSE_SOURCE_AMBIGUOUS')
        path=candidates[0]
    if Path(root).resolve() not in path.parents:raise ValueError('SAVED_POSE_SOURCE_OUTSIDE_ROOT')
    sha=hashlib.sha256(path.read_bytes()).hexdigest()
    if not goal.get('expected_saved_pose_sha') or sha!=goal['expected_saved_pose_sha']:raise ValueError('SAVED_POSE_REVISION_CHANGED')
    if digest(json.loads(path.read_text()))!=digest(pose):raise ValueError('REGISTRY_RECORD_DISAGREEMENT')
    return pose,dict(path=str(path),sha256=sha,registry_pose_digest=digest(pose))


def unchanged_source(root,goal,pin):
    if pin:
        if hashlib.sha256(Path(pin["path"]).read_bytes()).hexdigest()!=pin["sha256"]:
            raise ValueError("SAVED_POSE_REVISION_CHANGED")
        pose,current=resolve_target(root,goal,{})
        if current!=pin:raise ValueError('SAVED_POSE_REVISION_CHANGED')


def sequence(adapter,target,execute):
    results={}
    try:
        for leg in ('center_leg','restore_leg'):
            adapter.event(leg,'PRECHECK')
            adapter.bindings_valid(target)
            plan=adapter.plan(leg,target)
            results[leg]={'plan':plan}
            if not execute:continue
            adapter.event(leg,'EXECUTE')
            arrival=adapter.execute(leg,plan,target)
            results[leg]['arrival']=arrival
            if not arrival.get('passed'):raise RuntimeError(leg+'_ARRIVAL_UNCONFIRMED')
        return dict(success=True,terminal_state='CENTER_RESTORE_COMPLETED' if execute else 'PREPARED_ONLY',return_to_saved_pose_verified=execute,legs=results)
    except BaseException as exc:
        center=bool(results.get('center_leg',{}).get('arrival',{}).get('passed'))
        return dict(success=False,terminal_state='CENTER_ARRIVED_RESTORE_FAILED' if center else 'FAULT',return_to_saved_pose_verified=False,error_code=str(exc),legs=results)
