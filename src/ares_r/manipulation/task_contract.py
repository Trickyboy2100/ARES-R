"""Immutable, task-local overrides. Never write production configuration."""
import copy,hashlib,json,math
from pathlib import Path

TASK_ID='right_arm_shaiwang_pick_reset_v1'
TASK_SOURCES=('scripts/run_task_pick_reset_timing.py','scripts/run_shaiwang_stage1.py',
    'src/ares_r/manipulation/task_contract.py','src/ares_r/motion/controller_read_lease.py',
    'src/ares_r/manipulation/task_live.py','src/ares_r/manipulation/task_tcp_offset.py',
    'config/named_poses.json',
    'src/ares_r/motion/tcp_orientation.py','demos/'+TASK_ID+'/capture_epoch.py',
    'demos/'+TASK_ID+'/prepare_bundle.py','demos/'+TASK_ID+'/native_sender.cpp',
    'demos/'+TASK_ID+'/native_sender.build.json')

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def inspect_offsets(root):
    root=Path(root);p=json.loads((root/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json').read_text())
    file=root/'worklog/runtime/operations/state.json'
    operations=json.loads(file.read_text()) if file.exists() else {}
    return dict(read_only=True,source_parameters=str(root/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json'),
        task_tcp_offset_frame=p.get('task_tcp_offset_frame'),task_tcp_offset_m_rad=p.get('task_tcp_offset_m_rad'),
        demo_tcp_orientation_compensation=p.get('demo_tcp_orientation_compensation'),
        operations_revision=operations.get('revision'),old_dryer_slots=(operations.get('dryer') or {}).get('slots',{}),
        new_machine_offsets_commissioned=False,old_machine_offsets_used_in_stage1=False)

def center_goal(root):
    import numpy as np
    from ares_r.perception.robot_collision import transform_xyz_rpy
    from .task_tcp_offset import apply_task_pose,demo_local_rotation
    root=Path(root)
    pose=json.loads((root/'config/named_poses.json').read_text())['poses']['center']['arms']['right']['body_tcp_target_m_rad']
    parameters=json.loads((root/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json').read_text())
    xyz,rotation=apply_task_pose(pose[:3],transform_xyz_rpy([0]*3,pose[3:])[:3,:3],parameters.get('task_tcp_offset_m_rad',[0]*6))
    parameters=copy.deepcopy(parameters)
    parameters['demo_tcp_orientation_compensation'].update(load_contract(root).get('demo_tcp_orientation_compensation_override') or {})
    rotation=demo_local_rotation(rotation,parameters)
    return dict(position_m=np.asarray(xyz).tolist(),explicit_rotation=rotation.tolist(),
        source='config/named_poses.json:poses.center.arms.right.body_tcp_target_m_rad',
        nominal_pose_m_rad=pose,offsets_read_only=inspect_offsets(root))

def check_center(root,telemetry,task):
    import numpy as np
    goal=center_goal(root);arm=telemetry.get('arms',{}).get('right')
    if not arm or telemetry.get('errors'):raise ValueError('trusted robot state required for center admission')
    actual=np.asarray(arm['T_body_tcp']);position=float(np.linalg.norm(actual[:3,3]-goal['position_m']))
    angle=float(np.degrees(np.arccos(np.clip((np.trace(actual[:3,:3].T@np.asarray(goal['explicit_rotation']))-1)/2,-1,1))))
    if position>task['center_position_tolerance_m'] or angle>task['center_orientation_tolerance_deg']:
        raise ValueError('START_NOT_GLOBAL_CENTER: position %.3fmm / orientation %.3fdeg; plan center first'%(position*1000,angle))
    return dict(passed=True,position_error_m=position,orientation_error_deg=angle,goal=goal)

def load_contract(root):
    path=Path(root)/'demos'/TASK_ID/'params.json'
    value=json.loads(path.read_text())
    if value.get('demo_id')!=TASK_ID or value.get('base_motion_allowed') is not False or value.get('place_phase_enabled') is not False:
        raise ValueError('stage1 task identity/scope changed')
    if value.get('center_reference_policy')!='GLOBAL_NAMED_CENTER':raise ValueError('global center contract required')
    ids=[value[k] for k in ('epic_space_id','epic_object_id','epic_camera_id')]
    if value.get('epic_profile')!='right_pick' or value.get('epic_command')!='320,%d,%d,%d,1,0'%tuple(ids):
        raise ValueError('Epic task command/profile identifiers disagree')
    if ids!=[2,6,1]:raise ValueError('this candidate is scoped to space2/object6/camera1')
    if not 0<float(value['native_start_tolerance_deg'])<=.1:raise ValueError('native start tolerance out of task bounds')
    if not 0<float(value['level_gate_tolerance_deg'])<=4.5:raise ValueError('level tolerance out of task bounds')
    if value.get('payload_policy')!='DEMO_EXPOSED160_WIDTH100_REAR20_RETAINED_V2':raise ValueError('payload policy requires review')
    from .task_tcp_offset import validate_offset
    offset=value.get('task_tcp_offset_m_rad_override')
    if offset is not None:
        offset=validate_offset(offset)
        if value.get('task_tcp_offset_frame')!='BODY' or any(offset[3:]) or max(abs(v) for v in offset[:3])>.02:
            raise ValueError('task target correction must be BODY translation within20mm')
    comp=value.get('demo_tcp_orientation_compensation_override') or {}
    if set(comp)-{'body_yaw_correction_deg','body_yaw_scope'} or (comp and comp.get('body_yaw_scope')!=TASK_ID):
        raise ValueError('task orientation override scope invalid')
    yaw=comp.get('body_yaw_correction_deg',0)
    if isinstance(yaw,bool) or not isinstance(yaw,(int,float)) or not math.isfinite(yaw) or abs(yaw)>10:
        raise ValueError('invalid task yaw correction')
    if not isinstance(value.get('inspection_stop_before_close',False),bool):raise ValueError('inspection flag must be boolean')
    return value

def task_config(config,contract):
    result=copy.deepcopy(config);profile=result['epic']['task_profiles'][contract['epic_profile']]
    for target,source in (('command','epic_command'),('space_id','epic_space_id'),('object_id','epic_object_id'),('camera_id','epic_camera_id')):
        profile[target]=contract[source]
    return result

def check_epoch(epoch,contract):
    detection=json.loads((Path(epoch)/'epic_5700_detection.json').read_text())
    meta=detection.get('meta',{})
    if not detection.get('success') or any(meta.get(k)!=contract['epic_'+k] for k in ('space_id','object_id')):
        raise ValueError('epoch detection does not belong to selected task')
    if meta.get('request_command')!=contract['epic_command'] or meta.get('robot_arm')!='right':
        raise ValueError('epoch command/arm mismatch')
    return detection

def bind_task(prepared,root):
    prepared=Path(prepared);contract=load_contract(root);check_epoch(prepared/'epoch',contract)
    manifest=json.loads((prepared/'native-manifest.json').read_text())
    package=json.loads((prepared/'package/first_pick_execution_package.json').read_text())
    params=json.loads((Path(root)/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json').read_text())
    if digest(params)!=digest(manifest['parameters']):raise ValueError('source motion parameters changed')
    pinned=json.loads((Path(root)/'demos/right_arm_pick_lift_replace_reset_v1/pinned_inputs.json').read_text())['sha256']
    for file,expected in pinned.items():
        if hashlib.sha256((Path(root)/file).read_bytes()).hexdigest()!=expected:raise ValueError('golden source changed: '+file)
    binding=dict(schema_version=1,task_id=TASK_ID,task_digest=digest(contract),contract=contract,
        golden_pinned_inputs=pinned,
        task_source_sha256={file:hashlib.sha256((Path(root)/file).read_bytes()).hexdigest() for file in TASK_SOURCES},
        source_parameters_digest=digest(params),package_sha256=package['package_sha256'],
        scene_snapshot_id=manifest['scene_snapshot_id'],pointcloud_sha256=manifest['pointcloud_sha256'],
        source_offsets_read_only=dict(task_tcp_offset_m_rad=params.get('task_tcp_offset_m_rad'),
            demo_tcp_orientation_compensation=params.get('demo_tcp_orientation_compensation')))
    with (prepared/'task-binding.json').open('x') as stream:json.dump(binding,stream,indent=2)
    return binding

def verify_task(prepared,root):
    prepared=Path(prepared);binding=json.loads((prepared/'task-binding.json').read_text());task=load_contract(root)
    if binding.get('task_id')!=TASK_ID or binding.get('task_digest')!=digest(task):raise ValueError('task changed since preparation')
    if set(binding.get('task_source_sha256',{}))!=set(TASK_SOURCES):raise ValueError('task source binding missing')
    for file,expected in binding['task_source_sha256'].items():
        if hashlib.sha256((Path(root)/file).read_bytes()).hexdigest()!=expected:raise ValueError('task source changed: '+file)
    check_epoch(prepared/'epoch',task)
    manifest=json.loads((prepared/'native-manifest.json').read_text())
    current=json.loads((Path(root)/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json').read_text())
    if binding['source_parameters_digest']!=digest(current):raise ValueError('current source offsets/parameters changed')
    for file,expected in binding.get('golden_pinned_inputs',{}).items():
        if hashlib.sha256((Path(root)/file).read_bytes()).hexdigest()!=expected:raise ValueError('pinned input changed: '+file)
    if (binding['scene_snapshot_id']!=manifest['scene_snapshot_id'] or binding['pointcloud_sha256']!=manifest['pointcloud_sha256']
        or binding['package_sha256']!=manifest['package_sha256'] or binding['source_parameters_digest']!=digest(manifest['parameters'])):
        raise ValueError('prepared task/scene/native binding changed')
    return task

def check_task_start(actual,expected,task):
    if len(actual)!=6 or len(expected)!=6 or not all(math.isfinite(v) for v in list(actual)+list(expected)):
        raise ValueError('six finite joint positions required')
    gap=max(abs(a-b) for a,b in zip(actual,expected))*180/math.pi
    if gap>task['native_start_tolerance_deg']:raise ValueError('task native start mismatch %.6fdeg'%gap)
    return dict(max_joint_difference_deg=gap,tolerance_deg=task['native_start_tolerance_deg'])

def task_sender(root):
    root=Path(root);base=root/'demos'/TASK_ID;proof=json.loads((base/'native_sender.build.json').read_text())
    source=base/'native_sender.cpp';binary=root/proof['binary_relative_path']
    if root.resolve() not in binary.resolve().parents:raise ValueError('sender outside task root')
    if proof.get('mode')!='task_supervised_path' or proof.get('start_tolerance_deg')!=.1:raise ValueError('sender mode contract mismatch')
    if load_contract(root)['native_start_tolerance_deg']!=proof['start_tolerance_deg']:raise ValueError('task/native start policy mismatch')
    for path,key in ((source,'source_sha256'),(binary,'binary_sha256')):
        if hashlib.sha256(path.read_bytes()).hexdigest()!=proof[key]:raise ValueError('task sender build changed: '+str(path))
    if hashlib.sha256(Path(proof['sdk_library']).read_bytes()).hexdigest()!=proof['sdk_library_sha256']:
        raise ValueError('task sender SDK library changed')
    return binary
