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
        "inactive_arm_collision":True,"self_collision":True,"central_exclusion":True,
        "bounded_cartesian_only":True,"automatic_expiry":True}
    if any(policy.get(k)!=v for k,v in required.items()):
        raise ValueError("contact bypass scope widened or altered")
    if not core.get("lift_validation",{}).get("expired_at_end"):
        raise ValueError("contact bypass must expire after initial lift")
    return True
