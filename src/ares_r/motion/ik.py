"""Cartesian grasp pose -> ranked joint goals, through the audited cuRobo model.

This is the orchestration half of the IK bridge. It assembles the same request
the trajectory planner already trusts (robot model, audited controller transform,
scene, limits) and hands the worker a list of Cartesian targets. The worker
returns joint candidates plus every gate the planner will later re-apply; nothing
here plans a trajectory and nothing here can move an arm.
"""

import json
import os
from pathlib import Path
import subprocess
import time
import uuid

from .curobo import CUROBO_COMMIT, settings
from .curobo_params import PROFILES, planning_profile, profiled_config
from .pregrasp import _arm_correction, _arm_geometry
from .pregrasp_worker import SUPPORTED_ARMS
from .scene import load_scene
from ..timing import run_logged_process, timestamp
from .se3 import pose_mm_rad_to_matrix, transform_revision

WORKER_MODULE = "ares_r.motion.ik_worker"
SCHEMA_VERSION = 1


def build_targets(plan):
    """The two Cartesian stops a grasp needs, in the frame the camera reported."""
    return [
        dict(label="pregrasp", pose_m_rad=list(plan.pregrasp.values())),
        dict(label="grasp", pose_m_rad=list(plan.grasp.values())),
    ]


def solve_ik(config, arm, targets, diagnostics, profile, scene_snapshot=None):
    """Solve IK for each target. Planning only: this function never sends motion."""
    if arm not in SUPPORTED_ARMS:
        raise ValueError("arm must be left or right, got %r" % (arm,))
    if profile not in PROFILES:
        raise ValueError("unknown planning profile %r; reviewed profiles are %s"
                         % (profile, ", ".join(sorted(PROFILES))))
    if not targets:
        raise ValueError("at least one IK target is required")
    if not isinstance(scene_snapshot, dict) or not scene_snapshot.get("snapshot_id"):
        raise ValueError("IK requires a frozen SceneSnapshot; Epic-to-cuRobo direct planning is forbidden")
    geometry = _arm_geometry(config, arm)
    correction, audit_path = _arm_correction(config, arm)
    settings_ = settings(config)
    for path, label in ((settings_["python"], "cuRobo python"),
                        (settings_["robot_yaml"], "robot model")):
        if not Path(path).is_file():
            raise RuntimeError("%s not found: %s; run curobo status" % (label, path))

    joints = [float(value) for value in diagnostics["joint_position_rad"]]
    tool_mm = [float(value) for value in diagnostics["tcp_pose_mm_rad"]]
    tool_transform = pose_mm_rad_to_matrix(tool_mm)
    tool_revision = transform_revision(tool_transform)
    parameters = planning_profile(profiled_config(config, profile))
    scene = scene_snapshot
    pragmatic = config.get("pregrasp", {})

    run_id = time.strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8]
    directory = (Path(config["logging"]["directory"])
                 / ("ik_%s_%s_%s" % (time.strftime("%Y%m%d"), arm, run_id)))
    directory.mkdir(parents=True, exist_ok=False)
    request = dict(
        schema_version=SCHEMA_VERSION, run_id=directory.name, arm=arm, planning_only=True,
        planning_profile_name=profile,
        robot_yaml=str(Path(settings_["robot_yaml"]).resolve()),
        expected_commit=CUROBO_COMMIT,
        start_rad=joints,
        targets=targets,
        goal_frame="arm base (the frame the camera reported); converted in the worker",
        T_link6_tcp=tool_transform,
        tool_revision=tool_revision,
        tool_proxy_radius_m=float(pragmatic.get("tool_proxy_radius_m", 0.025)),
        body_base_xyz_m=list(geometry["base_xyz_m"]),
        body_base_yaw_rad=float(geometry["base_rpy_rad"][2]),
        T_controller_model=correction,
        fk_audit=str(audit_path),
        scene_snapshot=scene,
        motion_limits_file=str(Path(config["motion"]["limits_file"]).resolve()),
        min_body_z_m=float(pragmatic.get("min_body_z_m", 0.8)),
        min_model_clearance_m=float(pragmatic.get("min_model_clearance_m", 0.005)),
        return_seeds=int(parameters["num_ik_seeds"]),
        planning_parameters=parameters,
        request_timestamp=timestamp(),
    )
    request_path = directory / "request.json"
    request_path.write_text(json.dumps(request, indent=2), encoding="utf-8")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
    output = directory / "candidates.json"
    try:
        returncode, wall_s = run_logged_process(
            [settings_["python"], "-m", WORKER_MODULE, str(request_path), str(output)],
            env, directory / "worker.log", float(settings_["timeout_s"]), "cuRobo")
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("IK timed out; no motion was sent; inspect %s" % directory) from exc
    if returncode or not output.is_file():
        raise RuntimeError("IK failed; no motion was sent; inspect %s" % (directory / "worker.log"))
    payload = json.loads(output.read_text(encoding="utf-8"))
    payload["orchestration_wall_s"] = wall_s
    payload["directory"] = str(directory)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return directory, payload


def best_candidate(payload, target=None):
    """Highest-ranked accepted candidate, or a refusal that says why.

    ``target`` restricts the choice to one labelled stop, which is how the
    standoff is planned first instead of jumping straight to the grasp.
    """
    candidates = payload.get("candidates", [])
    if target is not None:
        candidates = [item for item in candidates if item.get("target") == target]
    accepted = [item for item in candidates if item.get("accepted")]
    if not accepted:
        reasons = sorted({reason for item in candidates
                          for reason in item.get("rejections", [])})
        detail = "; ".join(reasons) if reasons else "no candidate was returned"
        if target is not None:
            detail = "no accepted candidate for target %r (%s)" % (target, detail)
        raise RuntimeError("no IK candidate passed the gates: %s" % detail)
    return accepted[0]
