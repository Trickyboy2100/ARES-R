"""Fresh hold validation using the existing grasp verification implementation."""
import math
from ares_r.manipulation.grasp_verification import verify_grasp_phase


def validate_payload_session(session, *, object_type, tool_revision,
                             geometry_revision, readbacks, parameters, now):
    if session.get('state') != 'HELD_CONFIRMED':
        raise ValueError('PAYLOAD_NOT_HELD')
    expected = {'object_type': object_type, 'tool_revision': tool_revision,
                'geometry_revision': geometry_revision}
    for name, value in expected.items():
        if not value or session.get(name) != value:
            raise ValueError('PAYLOAD_BINDING_CHANGED:' + name)
    evidence = session.get('evidence') or {}
    if evidence.get('verification', {}).get('result') != 'PASS':
        raise ValueError('ORIGINAL_GRASP_PROOF_MISSING')
    delta = evidence.get('local_scene_delta')
    if not delta:
        raise ValueError('SOURCE_OBSERVATION_MISSING')
    # Keep the original verifier's five-second freshness window and configured
    # spread/hold thresholds. Every sample must belong to this fresh window.
    if not readbacks or any(
        not isinstance(row.get('captured_at_unix'), (int, float))
        or not math.isfinite(row['captured_at_unix'])
        or not 0 <= now - row['captured_at_unix'] <= 5
        for row in readbacks
    ):
        raise ValueError('FRESH_GRIPPER_WINDOW_REQUIRED')
    previous = evidence['verification'].get('readbacks', [])
    positions = [row.get('position_raw') for row in previous]
    if len(positions) < 2 or any(type(value) is not int for value in positions):
        raise ValueError('ORIGINAL_GRIPPER_FEEDBACK_MISSING')
    tolerance = parameters['grasp_verification']['maximum_readback_spread_raw']
    if any(type(row.get('position_raw')) is not int
           or not min(positions)-tolerance <= row['position_raw'] <= max(positions)+tolerance
           for row in readbacks):
        raise ValueError('HELD_GRIPPER_POSITION_CHANGED')
    result = verify_grasp_phase(delta, readbacks, parameters,
                                phase='HOLD_CANDIDATE', now=now)
    if result['result'] != 'PASS':
        raise ValueError('CURRENT_HOLD_NOT_CONFIRMED')
    return {'validated': True, 'binding': expected, 'verification': result,
            'transport_handoff_ready': False}
