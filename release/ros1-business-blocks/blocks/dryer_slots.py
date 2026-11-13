"""Read-only slot target binding shared by ROS and canonical clients.

The result is a preparation artifact. Dispatch requires a commissioned contact
adapter and a fresh scene/state check by the existing motion owner.
"""
import copy
import hashlib
import json
from pathlib import Path
import time

from ares_r.operations import matrix, vector
from ares_r.perception.robot_collision import transform_xyz_rpy
from .contracts import resolve


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False,
                                    separators=(',', ':')).encode()).hexdigest()


def bind_target(block_id, state, task_config, *, observation_epoch,
                base_pose_revision, now=None):
    profile = resolve(block_id)
    if profile.get('family') != 'dryer_six_slots':
        raise ValueError('DRYER_SLOT_BLOCK_REQUIRED')
    if not observation_epoch or not base_pose_revision:
        raise ValueError('OBSERVATION_AND_BASE_REVISION_REQUIRED')
    state, task_config = copy.deepcopy(state), copy.deepcopy(task_config)
    dryer = state['dryer']
    anchor = dryer.get('anchor')
    if not anchor:
        raise ValueError('FRESH_CORNER_OBSERVATION_REQUIRED')
    now = time.time() if now is None else now
    age = now - float(anchor['captured_at_unix'])
    if (not 0 <= age <= 300 or anchor['observation_epoch'] != observation_epoch
            or anchor['base_pose_revision'] != base_pose_revision):
        raise ValueError('ANCHOR_SCENE_BINDING_STALE')
    slot_id, kind = profile['slot_id'], profile['kind']
    slot = dryer['slots'][slot_id]
    if slot.get('offset_m_rad') is None:
        raise ValueError('SLOT_OFFSET_NOT_CONFIGURED')
    # The existing registry stores DETECTION values. BODY is only a display
    # conversion; accepting a BODY vector here would rotate it twice.
    if slot.get('offset_frame', 'DETECTION') != 'DETECTION':
        raise ValueError('REGISTRY_OFFSET_FRAME_MUST_BE_DETECTION')
    offset = vector(slot['offset_m_rad'], 6)
    body_slot = matrix(anchor['T_body_corner']) @ transform_xyz_rpy(offset[:3], offset[3:])
    action = task_config['slots'][slot_id][kind]
    tcp = action.get('tcp_offset_m_rad')
    body_tcp = None
    if tcp is not None:
        tcp = vector(tcp, 6)
        body_tcp = body_slot @ transform_xyz_rpy(tcp[:3], tcp[3:])
    required = 'OCCUPIED' if kind == 'pick' else 'EMPTY'
    binding = dict(schema_version=1, block_id=block_id, slot_id=slot_id,
        operation=kind.upper(), profile_revision=profile['profile_revision'],
        registry_revision=state['revision'], registry_sha256=digest(state),
        task_revision=task_config['revision'], task_config_sha256=digest(task_config),
        anchor_revision=dryer.get('anchor_revision'), anchor_sha256=digest(anchor),
        observation_epoch=observation_epoch, base_pose_revision=base_pose_revision,
        captured_at_unix=anchor['captured_at_unix'], offset_frame='DETECTION',
        offset_m_rad=offset, action_parameters=action,
        T_body_slot=body_slot.tolist(),
        T_body_tcp=None if body_tcp is None else body_tcp.tolist(),
        occupancy=slot.get('occupancy', 'UNKNOWN'), required_occupancy=required,
        occupancy_matches=slot.get('occupancy') == required,
        reservation=slot.get('reservation'),
        geometry_configured=body_tcp is not None,
        slot_acceptance=slot.get('calibration_state', 'UNCOMMISSIONED'),
        physical_motion=False, execution_package_ready=False)
    binding['binding_sha256'] = digest(binding)
    return binding


def read_target(site, block_id, observation_epoch, base_pose_revision):
    site = Path(site)
    state_path = site / 'worklog/runtime/operations/state.json'
    config_path = site / 'config/ros_dryer_tasks.json'
    # Existing registry writes are atomic. Check both files again so a UI save
    # during resolution cannot create an unnoticed mixed-version preparation.
    state_bytes, config_bytes = state_path.read_bytes(), config_path.read_bytes()
    binding = bind_target(block_id, json.loads(state_bytes), json.loads(config_bytes),
                          observation_epoch=observation_epoch, base_pose_revision=base_pose_revision)
    if state_path.read_bytes() != state_bytes or config_path.read_bytes() != config_bytes:
        raise ValueError('CONFIG_CHANGED_DURING_RESOLUTION')
    return binding


def assert_binding_current(binding, site, observation_epoch, base_pose_revision):
    current = read_target(site, binding['block_id'], observation_epoch, base_pose_revision)
    if current['binding_sha256'] != binding['binding_sha256']:
        raise ValueError('DRYER_TARGET_BINDING_CHANGED')
    return current


def save_binding(binding, output):
    # Exclusive creation protects an already reviewed artifact from replacement.
    with Path(output).open('x') as stream:
        json.dump(binding, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
