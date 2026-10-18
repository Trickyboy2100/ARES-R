"""Integrity checks for the immutable first-pick execution package."""

import hashlib
import json


STAGE_ACTIONS=("FRESH_ATOMIC_RIGHT_PICK_OBSERVATION","CUROBO_MOVE_TO_50MM_PREGRASP",
 "GRIPPER_TO_40_PERCENT","CONTACT_BYPASS_STRAIGHT_APPROACH","CLOSE_GRIPPER",
 "DELAYED_READBACK_AND_LOCAL_SCENE_DELTA","IF_VERIFIED_BODY_Z_LIFT_100MM",
 "EXPIRE_CONTACT_BYPASS_V1","ACTIVATE_COARSE_ATTACHED_OBJECT","HOLD_STOP")


def _sha(value):return hashlib.sha256(json.dumps(
    value,sort_keys=True,separators=(",",":")).encode()).hexdigest()


def verify_first_pick_package(value):
    core=dict(value);observed=core.pop("package_sha256",None)
    if observed!=_sha(core):raise ValueError("first-pick package digest mismatch")
    if (core.get("package_type")!="FIRST_PICK_EXECUTION_PACKAGE" or
            core.get("immutable") is not True or core.get("execution_allowed") is not False or
            core.get("FIRST_PICK_EXECUTION_PACKAGE_READY") is not True):
        raise ValueError("invalid first-pick package state")
    actions=tuple(row.get("action") for row in core.get("stages",()))
    if actions!=STAGE_ACTIONS:raise ValueError("first-pick stage order mismatch")
    policy=core.get("contact_bypass_policy",{})
    required={"policy_id":"CONTACT_BYPASS_V1","active_arm":"right",
        "active_tool_world_collision":False,"arm_link_world_collision":True,
        "inactive_arm_collision":True,"self_collision":True,
        "bounded_cartesian_only":True,"automatic_expiry":True}
    if any(policy.get(k)!=v for k,v in required.items()):
        raise ValueError("contact bypass scope widened or altered")
    # Central exclusion follows the versioned site switch (P3.9B keeps it OFF).
    # The value must still be an explicit boolean, never missing or coerced.
    if type(policy.get("central_exclusion")) is not bool:
        raise ValueError("contact bypass central exclusion must be boolean")
    if not core.get("lift_validation",{}).get("expired_at_end"):
        raise ValueError("contact bypass must expire after initial lift")
    if core.get('prechecked_branch'):
        contact,lift,_=bound_contact_lift({'selected_goal_candidate_metadata':core['prechecked_branch'],
            'trajectory_points_rad':core['trajectories']['pregrasp']},{},core['observation_id'])
        if contact!=core['trajectories']['contact'] or lift!=core['trajectories']['lift']:
            raise ValueError('prechecked contact/lift changed during packaging')
    return True


def bound_contact_lift(planning,request,observation_id):
    """Use the selected prechecked branch without another numerical IK solve."""
    import numpy as np
    selected=dict(planning.get('selected_goal_candidate_metadata') or {})
    branch_hash=selected.pop('branch_sha256',None)
    if not branch_hash or branch_hash!=_sha(selected):raise ValueError('PRECHECK_BRANCH_DIGEST_MISMATCH')
    if selected.get('observation_id')!=observation_id:raise ValueError('PRECHECK_OBSERVATION_MISMATCH')
    paths=selected['prechecked_paths'];pregrasp=np.asarray(planning['trajectory_points_rad'][-1])
    contact=np.asarray(paths['contact']);lift=np.asarray(paths['lift'])
    if contact.shape!=(26,6) or lift.shape!=(51,6):raise ValueError('PRECHECK_PATH_SHAPE')
    if not np.isfinite(contact).all() or not np.isfinite(lift).all():raise ValueError('PRECHECK_NONFINITE')
    if np.max(np.abs(contact[0]-pregrasp))>1e-4:raise ValueError('CUROBO_PRECHECK_BRANCH_SEAM')
    if np.max(np.abs(contact[-1]-lift[0]))>1e-4:raise ValueError('CONTACT_LIFT_BRANCH_SEAM')
    return contact.tolist(),lift.tolist(),dict(selected,branch_sha256=branch_hash)
