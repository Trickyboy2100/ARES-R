"""Persistent operations registry shared by ART, HTTP and task clients.

Writes are serialized across processes and use optimistic revisions. Occupancy
is an assertion, never inferred from a successful detection or motion plan.
"""
from contextlib import contextmanager
import copy
import fcntl
import hashlib
import json
import math
from pathlib import Path
import re
import tempfile
import time
import os
import uuid

import numpy as np

from .perception.robot_collision import transform_xyz_rpy


SLOTS = tuple('%s_%s' % (level, side) for level in ('lower', 'upper')
              for side in ('left', 'middle', 'right'))


def vector(value, count):
    result = [float(x) for x in value]
    if len(result) != count or not all(math.isfinite(x) for x in result):
        raise ValueError('expected %d finite numbers' % count)
    return result


def matrix(value):
    m = np.asarray(value, dtype=float)
    if (m.shape != (4, 4) or not np.isfinite(m).all() or
            not np.allclose(m[3], [0, 0, 0, 1]) or
            not np.allclose(m[:3, :3].T @ m[:3, :3], np.eye(3), atol=1e-5) or
            not np.isclose(np.linalg.det(m[:3, :3]), 1, atol=1e-5)):
        raise ValueError('proper finite SE(3) matrix required')
    return m


def initial_state():
    return {'schema_version': 1, 'revision': 0, 'updated_at_unix': None,
            'policy': {'environment_avoidance': 'AUTO', 'central_exclusion': False},
            'dryer': {'anchor_profile': 'dryer_place_corner',
                      'anchor_semantics': 'T_BODY_DRYER_CORNER',
                      'anchor_revision': None, 'anchor': None,
                      'selection_order': list(SLOTS),
                      'slots': {s: {'occupancy': 'UNKNOWN', 'offset_m_rad': None,
                                    'calibration_state': 'UNCOMMISSIONED',
                                    'reservation': None} for s in SLOTS}},
            'speed_drafts': {}, 'keypoints': {}, 'recordings': {},
            'software_limits': {'joint_lower_rad': None, 'joint_upper_rad': None,
                                'max_joint_delta_rad': None}}


class OperationsRegistry:
    def __init__(self, root='.'):
        self.root = Path(root).resolve()
        self.path = self.root / 'worklog/runtime/operations/state.json'

    @contextmanager
    def _locked(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.with_suffix('.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield

    def read(self):
        with self._locked():
            return json.loads(self.path.read_text()) if self.path.exists() else initial_state()

    def _write(self, state):
        state['revision'] += 1
        state['updated_at_unix'] = time.time()
        fd, name = tempfile.mkstemp(dir=str(self.path.parent), prefix='.state-')
        try:
            with os.fdopen(fd, 'w') as stream:
                json.dump(state, stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.flush(); os.fsync(stream.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name): os.unlink(name)

    def update(self, action, body):
        with self._locked():
            state = json.loads(self.path.read_text()) if self.path.exists() else initial_state()
            if body.get('expected_revision') != state['revision']:
                raise ValueError('configuration changed; refresh before saving')
            result = self._apply(state, action, body)
            self._write(state)
            # State and audit are written under the same process lock.
            with self.path.with_name('events.jsonl').open('a') as events:
                events.write(json.dumps({'at_unix': time.time(), 'revision': state['revision'],
                    'action': action, 'input': body, 'result': result}, ensure_ascii=False,
                    allow_nan=False) + '\n')
            return {'state': state, 'result': result}

    def _apply(self, state, action, body):
        dryer = state['dryer']
        if action == 'policy':
            mode = body.get('environment_avoidance', state['policy']['environment_avoidance'])
            central = body.get('central_exclusion', state['policy']['central_exclusion'])
            if mode not in ('AUTO', 'ON', 'OFF') or type(central) is not bool:
                raise ValueError('avoidance AUTO/ON/OFF and boolean central exclusion required')
            state['policy'] = {'environment_avoidance': mode, 'central_exclusion': central}
            return state['policy']
        if action == 'slot':
            slot = dryer['slots'][body['slot_id']]
            if slot['reservation']: raise ValueError('slot is reserved')
            if 'occupancy' in body:
                if body['occupancy'] not in ('UNKNOWN', 'EMPTY', 'OCCUPIED'):
                    raise ValueError('invalid occupancy')
                slot['occupancy'] = body['occupancy']
            if 'offset_m_rad' in body:
                slot['offset_m_rad'] = vector(body['offset_m_rad'], 6)
                slot['calibration_state'] = 'CANDIDATE'
            slot['note'] = str(body.get('note', 'operator update'))
            return copy.deepcopy(slot)
        if action == 'dryer_config':
            if any(s['reservation'] for s in dryer['slots'].values()):
                raise ValueError('cannot edit layout while slots are reserved')
            order = body.get('selection_order', dryer['selection_order'])
            if len(order) != 6 or set(order) != set(SLOTS):
                raise ValueError('selection order must contain all six slots once')
            profile = str(body.get('anchor_profile', dryer['anchor_profile'])).strip()
            if not profile: raise ValueError('anchor profile required')
            dryer.update(selection_order=list(order), anchor_profile=profile,
                         anchor=None, anchor_revision=None)
            if body.get('detection_profile') is not None:
                from .adapters.epic_profiles import EpicTaskProfile
                raw = dict(body['detection_profile'])
                # Editing matching semantics does not inherit the former
                # rightmost-point profile's commissioning claim.
                raw['state'] = 'UNCOMMISSIONED'
                EpicTaskProfile.from_mapping(profile, raw)
                dryer['detection_profile'] = raw
            return copy.deepcopy(dryer)
        if action == 'anchor':
            transform = matrix(body['T_body_corner'])
            if body.get('profile') != dryer['anchor_profile']:
                raise ValueError('detection profile is not the configured dryer corner profile')
            if not body.get('observation_epoch') or not body.get('base_pose_revision'):
                raise ValueError('fresh observation epoch and base revision required')
            captured = float(body['captured_at_unix'])
            if not math.isfinite(captured) or not 0 <= time.time() - captured <= 300:
                raise ValueError('anchor detection is stale')
            dryer['anchor'] = {'T_body_corner': transform.tolist(),
                'observation_epoch': body['observation_epoch'],
                'base_pose_revision': body['base_pose_revision'],
                'captured_at_unix': captured}
            dryer['anchor_revision'] = 'sha256:' + hashlib.sha256(
                json.dumps(dryer['anchor'], sort_keys=True).encode()).hexdigest()
            return dryer['anchor_revision']
        if action == 'reserve':
            selected = self.select(body['operation'], state)
            slot_id = body.get('slot_id', selected['slot_id'])
            slot = dryer['slots'][slot_id]
            required = 'EMPTY' if body['operation'] == 'PLACE' else 'OCCUPIED'
            if slot['reservation'] or slot['occupancy'] != required:
                raise ValueError('slot not available for operation')
            token = uuid.uuid4().hex
            slot['reservation'] = {'token': token, 'operation': body['operation'],
                                   'created_at_unix': time.time()}
            return {'slot_id': slot_id, **slot['reservation']}
        if action in ('complete', 'cancel'):
            slot = dryer['slots'][body['slot_id']]
            reservation = slot['reservation']
            if not reservation or body.get('token') != reservation['token']:
                raise ValueError('reservation token mismatch')
            if action == 'complete':
                if not body.get('evidence_id'): raise ValueError('completion evidence required')
                slot['occupancy'] = 'OCCUPIED' if reservation['operation'] == 'PLACE' else 'EMPTY'
                slot['last_evidence_id'] = str(body['evidence_id'])
            slot['reservation'] = None
            return copy.deepcopy(slot)
        if action == 'speed':
            name = str(body['name'])
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', name): raise ValueError('invalid profile name')
            velocity, acceleration = vector([body['max_velocity_rad_s'],
                                            body['max_acceleration_rad_s2']], 2)
            if not 0 < velocity <= 3 or not 0 < acceleration <= 10:
                raise ValueError('invalid speed draft range')
            state['speed_drafts'][name] = {'max_velocity_rad_s': velocity,
                'max_acceleration_rad_s2': acceleration, 'state': 'UNCOMMISSIONED',
                'scope': str(body.get('scope', 'SCENE_AWARE_FREE_SPACE')),
                'revision': 'draft-' + uuid.uuid4().hex}
            return state['speed_drafts'][name]
        if action == 'software_limits':
            low = body.get('joint_lower_rad'); high = body.get('joint_upper_rad')
            if (low is None) != (high is None): raise ValueError('both lower and upper limits required')
            if low is not None:
                low, high = vector(low, 6), vector(high, 6)
                if any(a >= b for a,b in zip(low, high)): raise ValueError('lower must be below upper')
            cap = body.get('max_joint_delta_rad')
            if cap is not None and (not math.isfinite(float(cap)) or float(cap) <= 0):
                raise ValueError('positive maximum joint delta or null required')
            state['software_limits'] = {'joint_lower_rad': low, 'joint_upper_rad': high,
                'max_joint_delta_rad': None if cap is None else float(cap)}
            return state['software_limits']
        if action == 'keypoint':
            name = str(body['name'])
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', name): raise ValueError('invalid keypoint name')
            state['keypoints'][name] = {'frame': 'BODY', 'pose_m_rad': vector(body['pose_m_rad'], 6),
                'arm': body.get('arm', 'right'), 'created_at_unix': time.time(),
                'base_pose_revision': body.get('base_pose_revision'),
                'source': str(body.get('source', 'operator'))}
            return state['keypoints'][name]
        raise ValueError('unknown operations action: ' + action)

    def select(self, operation, state=None):
        if operation not in ('PLACE', 'PICK'): raise ValueError('operation must be PLACE or PICK')
        state = state or self.read()
        required = 'EMPTY' if operation == 'PLACE' else 'OCCUPIED'
        for slot_id in state['dryer']['selection_order']:
            slot = state['dryer']['slots'][slot_id]
            if slot['occupancy'] == required and not slot['reservation']:
                return {'slot_id': slot_id, 'operation': operation, 'revision': state['revision'],
                        'offset_ready': slot['offset_m_rad'] is not None}
        raise ValueError('no confirmed %s slot; UNKNOWN slots require confirmation' % required)

    def target(self, slot_id, base_pose_revision, observation_epoch):
        state = self.read(); dryer = state['dryer']; anchor = dryer['anchor']
        slot = dryer['slots'][slot_id]
        if anchor is None or slot['offset_m_rad'] is None:
            raise ValueError('corner observation and slot offset required')
        if (anchor['base_pose_revision'] != base_pose_revision or
                anchor['observation_epoch'] != observation_epoch or
                not 0 <= time.time() - anchor['captured_at_unix'] <= 300):
            raise ValueError('corner anchor invalid after base/observation change or timeout')
        offset = slot['offset_m_rad']
        target = matrix(anchor['T_body_corner']) @ transform_xyz_rpy(offset[:3], offset[3:])
        return {'slot_id': slot_id, 'T_body_target': target.tolist(),
                'position_m': target[:3, 3].tolist(), 'explicit_rotation': target[:3, :3].tolist(),
                'anchor_revision': dryer['anchor_revision'], 'registry_revision': state['revision'],
                'calibration_state': slot['calibration_state']}


def planning_world(compiled, environment_avoidance):
    """Filter only provenance-proven camera objects; retain unknown protection."""
    if environment_avoidance not in ('AUTO', 'ON', 'OFF'):
        raise ValueError('invalid environment avoidance mode')
    result = copy.deepcopy(compiled)
    removed = []
    if environment_avoidance == 'OFF':
        for row in compiled.get('provenance', []):
            if row.get('category') == 'OBSERVED_ENVIRONMENT':
                object_id = row.get('object_id')
                if object_id in result['cuboids']:
                    removed.append(object_id); result['cuboids'].pop(object_id)
    result['operations_policy'] = {'environment_avoidance': environment_avoidance,
                                   'excluded_observed_object_ids': removed}
    result['digest'] = hashlib.sha256(json.dumps(result, sort_keys=True,
                                               separators=(',', ':')).encode()).hexdigest()
    return result
