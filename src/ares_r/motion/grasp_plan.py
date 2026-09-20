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
from .scene import scene_identity, scene_snapshot_id
from ..timing import timestamp
from ..world_geometry import base_tcp_to_world
from .se3 import pose_mm_rad_to_matrix, transform_revision

SCHEMA_VERSION = 1


def _require_separation(declared):
    """The operator must state that the other arm is out of the swept volume."""
    if declared is not True:
        raise RuntimeError(
            "the other arm's physical separation has not been declared. This is an operator "
            "statement about the real cell, not something this code can observe; pass it "
            "explicitly once you have confirmed the other arm is out of the swept volume")


def prepare(config, arm, case_id, reader, profile, other_arm_separated,
            detection=None, scene_snapshot=None, perception=None, stop="pregrasp",
            acknowledge_standoff_skipped=False):
    """Build a scene-bound IK case from an already committed observation.

    Capturing from Epic inside this function is intentionally forbidden: the
    detection and pointcloud must first become one ObservationEpoch and frozen
    SceneSnapshot, otherwise a trajectory could be planned against a different
    physical scene than the target pose.

    ``stop`` selects which of the two solved Cartesian stops becomes the case
    goal. It defaults to the standoff, because the audited execution sequence
    approaches first and inserts along a straight line second. Planning straight
    to the grasp is allowed only as an explicit, acknowledged choice so that
    skipping the standoff can never happen by omission.
    """
    if arm not in SUPPORTED_ARMS:
        raise ValueError("arm must be left or right, got %r" % (arm,))
    if stop not in ("pregrasp", "grasp"):
        raise ValueError("stop must be pregrasp or grasp, got %r" % (stop,))
    if stop == "grasp" and not acknowledge_standoff_skipped:
        raise RuntimeError(
            "planning straight to the grasp skips the audited approach standoff. "
            "Pass acknowledge_standoff_skipped=True once you have decided this is a "
            "reachability or inspection run rather than a staged pick")
    _require_separation(other_arm_separated)
    if perception is not None:
        raise RuntimeError("Epic-to-cuRobo direct planning is forbidden; commit detection and cloud to WorldModel first")
    if detection is None or scene_snapshot is None:
        raise RuntimeError("detection plus frozen SceneSnapshot are required")
    if not isinstance(scene_snapshot, dict):
        raise RuntimeError("invalid SceneSnapshot")
    snapshot_id = scene_snapshot_id(scene_snapshot)
    scene_provenance = scene_identity(scene_snapshot)

    started = time.time()
    start_path, start = capture(config, "start", case_id, arm, reader)

    if not detection.success:
        raise RuntimeError("the camera returned no grasp point: %s" % (detection.error,))
    plan = build_grasp_plan(config, detection, arm)

    diagnostics = dict(joint_position_rad=start["joint_position_rad"],
                       tcp_pose_mm_rad=start["tcp_pose_mm_rad"])
    tool_revision = transform_revision(pose_mm_rad_to_matrix(start["tcp_pose_mm_rad"]))
    expected_tool_revision = detection.meta.get("tool_revision")
    if expected_tool_revision != tool_revision:
        raise RuntimeError("live tool/TCP revision differs from the Epic task profile")
    ik_directory, payload = solve_ik(config, arm, build_targets(plan), diagnostics, profile,
                                     scene_snapshot=scene_snapshot)
    # The staged pick approaches the standoff first; anything else is deliberate.
    candidate = best_candidate(payload, target=stop)

    geometry = _arm_geometry(config, arm)
    target_id = "%s_%s" % (case_id, candidate["target"])
    pose_m_rad = list((plan.pregrasp if stop == "pregrasp" else plan.grasp).values())
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
            scene_snapshot_id=snapshot_id,
            scene_provenance=scene_provenance,
            tool_revision=tool_revision,
            stop=stop,
            standoff_skipped=(stop == "grasp"),
        ),
        warning=("Goal joints come from IK against a camera pose, not from a teach capture. "
                 "Re-read the live arm before planning: this is a target, not an observation."),
    )
    path = target_path(config, target_id)
    # The target tree is not tracked, so the first run after a branch change has
    # nowhere to write. Create the directory rather than failing on a fresh tree.
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError("%s already exists; move it aside instead of overwriting a target"
                           % path)
    path.write_text(json.dumps(target, indent=2), encoding="utf-8")

    manifest = dict(
        schema_version=SCHEMA_VERSION, case_id=case_id, arm=arm, goal_target_id=target_id,
        other_arm_physically_separated=True, tool_id=start["tool_id"],
        tcp_revision=tool_revision, scene_snapshot_id=snapshot_id,
        scene_note="camera goal from Epic space %s" % detection.meta.get("space_id"),
        operator_note="start captured live; goal solved by %s" % Path(ik_directory).name,
    )
    manifest_path = case_dir(config, case_id) / "manifest.json"
    if manifest_path.exists():
        raise RuntimeError("%s already exists; move it aside instead of overwriting a manifest"
                           % manifest_path)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return dict(case_id=case_id, arm=arm, start=str(start_path), target=str(path),
                manifest=str(manifest_path), ik_run=str(ik_directory), stop=stop,
                candidates=payload["candidate_count"], accepted=payload["accepted_count"],
                joint_travel_rad=candidate["joint_distance_from_start_rad"],
                elapsed_s=round(time.time() - started, 2))


def plan(config, case_id, profile):
    """Run the existing audited planner over the case that :func:`prepare` wrote."""
    return plan_case(config, case_id, profile)
