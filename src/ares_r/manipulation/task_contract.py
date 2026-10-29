"""Immutable, task-local overrides. Never write production configuration."""
import copy,hashlib,json,math
from pathlib import Path

TASK_ID='right_arm_shaiwang_pick_reset_v1'
TASK_SOURCES=('scripts/run_task_pick_reset_timing.py','scripts/run_shaiwang_stage1.py',
    'src/ares_r/manipulation/task_contract.py','src/ares_r/motion/controller_read_lease.py',
    'src/ares_r/manipulation/task_live.py',
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

def load_contract(root):
    path=Path(root)/'demos'/TASK_ID/'params.json'
    value=json.loads(path.read_text())
    if value.get('demo_id')!=TASK_ID or value.get('base_motion_allowed') is not False or value.get('place_phase_enabled') is not False:
        raise ValueError('stage1 task identity/scope changed')
    ids=[value[k] for k in ('epic_space_id','epic_object_id','epic_camera_id')]
    if value.get('epic_profile')!='right_pick' or value.get('epic_command')!='320,%d,%d,%d,1,0'%tuple(ids):
        raise ValueError('Epic task command/profile identifiers disagree')
    if ids!=[2,6,1]:raise ValueError('this candidate is scoped to space2/object6/camera1')
    if not 0<float(value['native_start_tolerance_deg'])<=.1:raise ValueError('native start tolerance out of task bounds')
    if not 0<float(value['level_gate_tolerance_deg'])<=4.5:raise ValueError('level tolerance out of task bounds')
    if value.get('payload_policy')!='DEMO_EXPOSED160_WIDTH100_REAR20_RETAINED_V2':raise ValueError('payload policy requires review')
    if any(value.get(k) is not None for k in ('task_tcp_offset_m_rad_override','demo_tcp_orientation_compensation_override')):
        raise ValueError('offsets are read-only in this stage')
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
