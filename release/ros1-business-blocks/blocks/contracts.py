"""Versioned stage boundaries shared by preparation and replay.

No production runner imports this module. A future canonical adapter must provide
fresh physical evidence for each stage, and share the canonical global owner.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PICK = ('CAPTURE_SCENE', 'DETECT_TARGET', 'PREGRASP', 'CONTACT', 'CLOSE',
        'VERIFY_BEFORE_LIFT', 'LIFT230', 'VERIFY_AFTER_LIFT', 'HOLD_CONFIRMED')
PLACE = ('VERIFY_PAYLOAD', 'CAPTURE_SCENE', 'DETECT_TARGET', 'PREPLACE',
         'CONTROLLED_DESCEND', 'RELEASE_CONFIRMED', 'RETREAT_CLEAR')

def registry():
    return json.loads((ROOT / 'block_registry.json').read_text())['blocks']

def resolve(block_id):
    for row in registry():
        if row['block_id'] == block_id:
            return row
    raise ValueError('UNKNOWN_BLOCK')

def prepare(block_id, revision, repository, *, return_center=False):
    row = resolve(block_id)
    if row['kind'] == 'utility':
        raise ValueError('USE_EXISTING_CENTER_RESTORE_ACTION')
    if row['profile_revision'] != revision:
        raise ValueError('PROFILE_REVISION_MISMATCH')
    if not row.get('profile_source'):
        raise ValueError('PROFILE_NOT_BOUND')
    source = Path(repository) / row['profile_source']
    if hashlib.sha256(source.read_bytes()).hexdigest() != row['profile_sha256']:
        raise ValueError('PROFILE_SHA_MISMATCH')
    stages = PICK if row['kind'] == 'pick' else PLACE + (('CENTER',) if return_center else ())
    return dict(block_id=block_id, profile_revision=revision,
                profile_sha256=row['profile_sha256'], stages=list(stages),
                physical_motion=False, physical_start_enabled=False,
                canonical_adapter_ready=False, acceptance=row['acceptance'])

def replay(plan, evidence, *, cancelled_at=None):
    """Validate ordered synthetic/frozen records, never dispatch any command.

    Input rows are adapter reports, not proof of physical commissioning.
    Missing/ambiguous release and stop never become successful terminal states.
    """
    results = []
    for index, stage in enumerate(plan['stages']):
        if cancelled_at == stage:
            return dict(success=False, code='STOP_REQUESTED', terminal_state='UNCERTAIN',
                        stop_confirmed=False, events=results, physical_motion=False)
        if index >= len(evidence) or evidence[index].get('stage') != stage:
            return dict(success=False, code='MISSING_OR_OUT_OF_ORDER_EVIDENCE', events=results)
        row = evidence[index]
        results.append(row)
        if row.get('verified') is not True:
            return dict(success=False, code='POSTCONDITION_NOT_VERIFIED', events=results)
    if len(evidence) != len(plan['stages']):
        return dict(success=False, code='UNEXPECTED_EXTRA_STAGE', events=results)
    pick = plan['stages'][-1] == 'HOLD_CONFIRMED'
    if pick and not evidence[-1].get('payload_session_id'):
        return dict(success=False, code='PAYLOAD_SESSION_REQUIRED', events=results)
    return dict(success=True, code='OFFLINE_REPLAY_PASS',
                terminal_state='HELD_CONFIRMED' if pick else 'RELEASED_RETREATED',
                payload_state='HELD_CONFIRMED' if pick else 'RELEASED_CONFIRMED',
                payload_session_id=evidence[-1].get('payload_session_id', ''),
                transport_handoff_ready=False, physical_motion=False, events=results)
