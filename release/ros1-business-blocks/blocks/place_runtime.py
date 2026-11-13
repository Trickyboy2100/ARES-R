"""Invoke the pinned Place implementation with persistent payload ownership."""
import copy
import json
import math
from pathlib import Path
from .canonical import verify_place_result


def execute_with_payload(existing, params, output, sessions, session_id, *,
                         validate_payload, return_center=True):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    proof = validate_payload()
    if proof.get('validated') is not True:
        raise ValueError('PAYLOAD_NOT_VALIDATED')
    (output / 'payload-before.json').write_text(json.dumps(proof, indent=2) + '\n')
    geometry = proof['geometry']
    original_plan, original_save = existing.plan_leg, existing.save
    released = False
    original_demo = existing.DEMO_ID
    existing.DEMO_ID = params['demo_id']
    def plan(payload, *args, **kwargs):
        request = dict(payload)
        if not released:
            request.update(attached_object_geometry=copy.deepcopy(geometry),
                           attached_object_revision=geometry['revision'])
        return original_plan(request, *args, **kwargs)
    def save(path, value):
        nonlocal released
        original_save(path, value)
        if Path(path) == output / 'place/release.json':
            raw = value.get('readback_raw')
            stage = params['stages']['dmp_place']
            if (type(raw) in (int, float) and math.isfinite(raw)
                    and abs(raw - stage['release_raw']) <= stage['release_readback_tolerance_raw']):
                sessions.transition(session_id, 'HELD_CONFIRMED', 'RELEASED_CONFIRMED')
                released = True
    existing.plan_leg, existing.save = plan, save
    try:
        result = existing.stage_place(params, output / 'place', True, stop_after='release')
        checked = verify_place_result(output / 'place', params, result)
        if not released:
            raise ValueError('RELEASE_SESSION_NOT_COMMITTED')
        if return_center:
            center = existing.stage_center(params, output / 'center', True)
            if center.get('state') != 'AT_CENTER':
                raise ValueError('CENTER_NOT_CONFIRMED')
            checked['center'] = center
            checked['terminal_state'] = 'RELEASED_RETREATED_CENTER'
        return dict(checked, success=True, payload_session_id=session_id)
    except BaseException:
        if not released and sessions.get(session_id)['state'] == 'HELD_CONFIRMED':
            sessions.transition(session_id, 'HELD_CONFIRMED', 'UNCERTAIN')
        raise
    finally:
        existing.plan_leg, existing.save = original_plan, original_save
        existing.DEMO_ID = original_demo
