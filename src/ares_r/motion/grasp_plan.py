"""Epic detection -> IK -> an audited pregrasp case that plan_cspace can consume.

Three links in this chain are already audited and must not be short-circuited:

* the live arm is read twice before it is trusted as a start, through
  ``pregrasp.capture``, so a creeping arm cannot be recorded as settled;
* the goal is produced by IK against the camera pose, and the target record says
  so -- it is not a taught point and must never be mistaken for one;
* planning still goes through ``pregrasp.plan_case`` unchanged, which keeps the
  clearance, central-slab, height, limit and singularity gates in one place.

Nothing here commands hardware. The only motion that follows is
``pregrasp.run_case``, with its own confirmation phrase and start-distance check.
"""

import json
import math
from pathlib import Path
import time

from .grasp import build_grasp_plan
from .ik import best_candidate, build_targets, solve_ik
from .pregrasp import (SUPPORTED_ARMS, _arm_geometry, capture, case_dir, plan_case, target_path)
from ..timing import timestamp
from ..world_geometry import base_tcp_to_world

SCHEMA_VERSION = 1


def _require_separation(declared):
    """The operator must state that the other arm is out of the swept volume."""
    if declared is not True:
        raise RuntimeError(
            "the other arm's physical separation has not been declared. This is an operator "
            "statement about the real cell, not something this code can observe; pass it "
            "explicitly once you have confirmed the other arm is out of the swept volume")


def prepare(config, arm, case_id, reader, profile, other_arm_separated, perception=None):
    """Capture the start, solve IK for the camera pose, and write the case files."""
    if arm not in SUPPORTED_ARMS:
        raise ValueError("arm must be left or right, got %r" % (arm,))
    _require_separation(other_arm_separated)

    started = time.time()
    start_path, start = capture(config, "start", case_id, arm, reader)

    close_perception = False
    if perception is None:
        from ..adapters.epic import EpicClient
        perception = EpicClient(config["epic"])
        close_perception = True
    try:
        detection = perception.detect_pick()
    finally:
        if close_perception:
            perception.close()
    if not detection.success:
        raise RuntimeError("the camera returned no grasp point: %s" % (detection.error,))
    plan = build_grasp_plan(config, detection, arm)

    diagnostics = dict(joint_position_rad=start["joint_position_rad"],
                       tcp_pose_mm_rad=start["tcp_pose_mm_rad"])
    ik_directory, payload = solve_ik(config, arm, build_targets(plan), diagnostics, profile)
    # The first planned motion is to the standoff, never straight to the grasp.
    candidate = best_candidate(payload, target="pregrasp")

    geometry = _arm_geometry(config, arm)
    target_id = "%s_%s" % (case_id, candidate["target"])
    pose_m_rad = list(plan.pregrasp.values())
    body_tcp = base_tcp_to_world(geometry, [value * 1000.0 for value in pose_m_rad[:3]]
                                 + list(pose_m_rad[3:]))
    target = dict(
        schema_version=SCHEMA_VERSION, kind="goal", identifier=target_id, arm=arm,
        captured_at_unix=time.time(), captured_at=timestamp(),
        joint_position_rad=candidate["joints_rad"],
        joint_position_deg=[math.degrees(value) for value in candidate["joints_rad"]],
        tcp_position_mm_rad=[value * 1000.0 for value in pose_m_rad[:3]] + list(pose_m_rad[3:]),
        body_tcp_m_rad=body_tcp,
        tool_id=start["tool_id"], tcp_pose_mm_rad=start["tcp_pose_mm_rad"],
        body_frame=dict(name="body", translation_unit="m", rotation_unit="rad",
                        order="[x, y, z, roll, pitch, yaw]"),
        source=dict(
            kind="epic_ik", ik_run=str(ik_directory), planned_target=candidate["target"],
            camera_frame=plan.frame_id, camera_pose_m_rad=list(plan.grasp.values()),
            insertion_mode=plan.insertion_mode, approach_m=plan.approach_m,
            approach_direction=plan.approach_direction, tilt_deg=plan.tilt_deg,
            tcp_position_error_m=candidate["tcp_position_error_m"],
            min_model_clearance_m=candidate["min_model_clearance_m"],
            min_central_margin_m=candidate["min_central_margin_m"],
            min_soft_limit_margin_rad=candidate["min_soft_limit_margin_rad"],
            raw_response=detection.raw_response,
        ),
        warning=("Goal joints come from IK against a camera pose, not from a teach capture. "
                 "Re-read the live arm before planning: this is a target, not an observation."),
    )
    path = target_path(config, target_id)
    if path.exists():
        raise RuntimeError("%s already exists; move it aside instead of overwriting a target"
                           % path)
    path.write_text(json.dumps(target, indent=2), encoding="utf-8")

    manifest = dict(
        schema_version=SCHEMA_VERSION, case_id=case_id, arm=arm, goal_target_id=target_id,
        other_arm_physically_separated=True, tool_id=start["tool_id"],
        tcp_revision="tool_id_%s" % start["tool_id"],
        scene_note="camera goal from Epic space %s" % detection.meta.get("space_id"),
        operator_note="start captured live; goal solved by %s" % Path(ik_directory).name,
    )
    manifest_path = case_dir(config, case_id) / "manifest.json"
    if manifest_path.exists():
        raise RuntimeError("%s already exists; move it aside instead of overwriting a manifest"
                           % manifest_path)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return dict(case_id=case_id, arm=arm, start=str(start_path), target=str(path),
                manifest=str(manifest_path), ik_run=str(ik_directory),
                candidates=payload["candidate_count"], accepted=payload["accepted_count"],
                joint_travel_rad=candidate["joint_distance_from_start_rad"],
                elapsed_s=round(time.time() - started, 2))


def plan(config, case_id, profile):
    """Run the existing audited planner over the case that :func:`prepare` wrote."""
    return plan_case(config, case_id, profile)
