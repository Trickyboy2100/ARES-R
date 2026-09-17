"""Supervised dual-arm pregrasp planning and execution orchestration.

This module is the only entry point the terminal uses. It keeps the two phases
strictly separate:

* ``plan_case`` is planning-only. It never imports a hardware adapter and it can
  run with the arms powered down.
* ``run_case`` re-reads the real joints, refuses to move when the arm has moved
  away from the planned start, and requires the operator to type an exact
  confirmation phrase before the native sender is started.

Execution is commissioned for the right arm only. The left arm is planned and
previewed, but ``run_case`` refuses it: there is no audited left native sender, so
pretending otherwise would be worse than refusing.
"""

import json
import math
import os
from pathlib import Path
import re
import subprocess
import time
import uuid

from .curobo import CUROBO_COMMIT, settings
from .curobo_params import PROFILES, planning_profile, profiled_config
from .pregrasp_worker import SUPPORTED_ARMS
from ..timing import run_logged_process, timestamp

WORKER_MODULE = "ares_r.motion.pregrasp_worker"
SCHEMA_VERSION = 1
EXECUTION_COMMISSIONED_ARMS = ("right",)
PLACEHOLDER = re.compile(r"REPLACE_")
MAX_CAPTURE_JOINT_SPREAD_RAD = math.radians(0.02)
MAX_CAPTURE_TCP_SPREAD_MM = 1.0


def repository_root(config):
    return Path(config["logging"]["directory"]).resolve().parent


def case_root(config):
    return repository_root(config) / "worklog" / "pregrasp"


def case_dir(config, case_id):
    if not case_id or "/" in case_id or "\\" in case_id or case_id.startswith("."):
        raise ValueError("case id must be a plain name")
    return case_root(config) / "cases" / case_id


def target_path(config, target_id):
    if not target_id or "/" in target_id or "\\" in target_id or target_id.startswith("."):
        raise ValueError("target id must be a plain name")
    return case_root(config) / "targets" / ("%s.json" % target_id)


def _reject_placeholders(value, where="manifest"):
    """A half-filled manifest must never reach the planner."""
    if isinstance(value, str):
        if PLACEHOLDER.search(value):
            raise ValueError("%s still contains a REPLACE_ placeholder: %r" % (where, value))
    elif isinstance(value, list):
        for item in value:
            _reject_placeholders(item, where)
    elif isinstance(value, dict):
        for key, item in value.items():
            _reject_placeholders(item, "%s.%s" % (where, key))


def _six_finite(values, label):
    if not isinstance(values, (list, tuple)) or len(values) != 6:
        raise ValueError("%s must be a list of six numbers" % label)
    converted = [float(value) for value in values]
    if not all(math.isfinite(value) for value in converted):
        raise ValueError("%s must be finite" % label)
    return converted


def load_json(path, label):
    path = Path(path)
    if not path.is_file():
        raise RuntimeError("%s not found: %s" % (label, path))
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise RuntimeError("%s is not valid JSON: %s" % (label, path)) from exc


def load_manifest(config, case_id):
    """Case manifest from ``worklog/pregrasp/cases/<case_id>/manifest.json``."""
    manifest = load_json(case_dir(config, case_id) / "manifest.json", "case manifest")
    _reject_placeholders(manifest, "manifest")
    if int(manifest.get("schema_version", 0)) != SCHEMA_VERSION:
        raise ValueError("manifest schema_version must be %d" % SCHEMA_VERSION)
    if manifest.get("case_id") != case_id:
        raise ValueError("manifest case_id %r does not match %r" % (manifest.get("case_id"), case_id))
    if manifest.get("arm") not in SUPPORTED_ARMS:
        raise ValueError("manifest arm must be left or right")
    if not manifest.get("goal_target_id"):
        raise ValueError("manifest needs a goal_target_id naming a captured target")
    if manifest.get("other_arm_physically_separated") is not True:
        raise ValueError("manifest must declare other_arm_physically_separated=true before planning")
    return manifest


def resolve_case(config, case_id):
    """Merge manifest, captured start, captured goal and the live arm identity."""
    manifest = load_manifest(config, case_id)
    arm = manifest["arm"]
    start_record = load_json(case_dir(config, case_id) / "start.json", "captured start")
    target_record = load_json(target_path(config, manifest["goal_target_id"]), "captured goal")
    if start_record.get("arm") != arm or target_record.get("arm") != arm:
        raise ValueError("captured start and goal must belong to arm %s" % arm)
    if start_record.get("tool_id") != target_record.get("tool_id"):
        raise ValueError("captured start and goal were taken with different controller tools")
    declared = manifest.get("tool_id")
    if declared is not None and declared != start_record.get("tool_id"):
        raise ValueError("manifest tool_id %r does not match the captured tool_id %r"
                         % (declared, start_record.get("tool_id")))
    return dict(
        case_id=case_id, arm=arm,
        start_joint_rad=_six_finite(start_record["joint_position_rad"], "start joints"),
        start_body_tcp_m_rad=_six_finite(start_record["body_tcp_m_rad"], "start BODY TCP"),
        # Kept in the controller millimetre frame: the worker compares its own
        # model FK against this raw capture, so the units must not be converted.
        start_controller_tcp_mm_rad=_six_finite(start_record["tcp_position_mm_rad"],
                                                "start controller TCP"),
        goal_joint_rad=_six_finite(target_record["joint_position_rad"], "goal joints"),
        goal_body_tcp_m_rad=_six_finite(target_record["body_tcp_m_rad"], "goal BODY TCP"),
        goal_ik_branch_id=manifest.get("goal_ik_branch_id"),
        other_arm_joint_rad=manifest.get("other_arm_joint_rad"),
        other_arm_physically_separated=bool(manifest.get("other_arm_physically_separated")),
        tool_id=start_record.get("tool_id"),
        tcp_revision=manifest.get("tcp_revision"),
        scene_note=manifest.get("scene_note"),
        operator_note=manifest.get("operator_note"),
        start_captured_at_unix=start_record.get("captured_at_unix"),
        goal_captured_at_unix=target_record.get("captured_at_unix"),
        sources={"manifest": manifest, "start": start_record, "goal": target_record},
    )


def _arm_geometry(config, arm):
    """BODY frame of one arm, validated for the level-base projection only."""
    world = load_json(Path(config["world_geometry_file"]), "world geometry")
    geometry = world["arms"][arm]
    if abs(float(geometry["base_rpy_rad"][0])) > 1e-12 or abs(float(geometry["base_rpy_rad"][1])) > 1e-12:
        raise RuntimeError("the BODY projection only supports level arm bases")
    return geometry


def _arm_correction(config, arm):
    """Audited ``T_controller_model`` for one arm, produced by audit_curobo_fk.py."""
    evidence = repository_root(config) / "worklog" / "evidence"
    candidates = sorted(evidence.glob("*/%s_fk_audit.json" % arm))
    if not candidates:
        raise RuntimeError("no %s FK audit found under %s; run scripts/audit_curobo_fk.py --side %s"
                           % (arm, evidence, arm))
    audit = load_json(candidates[-1], "%s FK audit" % arm)
    if audit.get("arm") != arm:
        raise RuntimeError("%s FK audit reports arm %r" % (arm, audit.get("arm")))
    matrix = audit.get("T_controller_model")
    if not isinstance(matrix, list) or len(matrix) != 4 or any(len(row) != 4 for row in matrix):
        raise RuntimeError("%s FK audit has no usable T_controller_model" % arm)
    return matrix, candidates[-1]


def capture(config, kind, identifier, arm, arm_reader):
    """Read one arm twice and persist ``start.json`` or the named goal target.

    Two consecutive reads must agree before the values are stored: a single
    sample cannot tell a settled arm from one still creeping.
    """
    if arm not in SUPPORTED_ARMS:
        raise ValueError("arm must be left or right")
    if kind not in ("start", "goal"):
        raise ValueError("kind must be start or goal, got %r" % (kind,))
    if not identifier:
        raise ValueError("a %s capture needs an identifier" % kind)
    geometry = _arm_geometry(config, arm)
    samples = []
    for _ in range(2):
        diagnostics = arm_reader.diagnostics()
        samples.append(dict(
            joint_position_rad=_six_finite(diagnostics["joint_position_rad"], "joints"),
            tcp_position_mm_rad=_six_finite(diagnostics["tcp_position_mm_rad"], "TCP"),
            tool_id=diagnostics.get("tool_id"),
            tcp_pose_mm_rad=_six_finite(diagnostics["tool_data"]["pose_mm_rad"], "tool TCP"),
        ))
    first, second = samples
    joint_spread = max(abs(a - b) for a, b in zip(first["joint_position_rad"], second["joint_position_rad"]))
    if joint_spread > MAX_CAPTURE_JOINT_SPREAD_RAD:
        raise RuntimeError("arm is still moving: joint readings differ by %.4f rad; stop it and retry"
                           % joint_spread)
    tcp_spread = max(abs(a - b) for a, b in zip(first["tcp_position_mm_rad"][:3], second["tcp_position_mm_rad"][:3]))
    if tcp_spread > MAX_CAPTURE_TCP_SPREAD_MM:
        raise RuntimeError("arm is still moving: TCP readings differ by %.3f mm; stop it and retry"
                           % tcp_spread)
    from ..world_geometry import base_tcp_to_world
    body_tcp = base_tcp_to_world(geometry, first["tcp_position_mm_rad"])
    record = dict(
        schema_version=SCHEMA_VERSION, kind=kind, identifier=identifier, arm=arm,
        captured_at_unix=time.time(), captured_at=timestamp(),
        joint_position_rad=first["joint_position_rad"],
        joint_position_deg=[math.degrees(value) for value in first["joint_position_rad"]],
        tcp_position_mm_rad=first["tcp_position_mm_rad"],
        body_tcp_m_rad=body_tcp,
        tool_id=first["tool_id"], tcp_pose_mm_rad=first["tcp_pose_mm_rad"],
        body_frame=dict(name="body", translation_unit="m", rotation_unit="rad",
                        order="[x, y, z, roll, pitch, yaw]"),
        repeatability=dict(joint_spread_rad=joint_spread, tcp_spread_mm=tcp_spread,
                           reads=2, rule="two consecutive reads must agree"),
        warning="Captured geometry only. Nothing was commanded and no motion was sent.",
    )
    if kind == "start":
        output = case_dir(config, identifier) / "start.json"
    else:
        output = target_path(config, identifier)
    if output.exists():
        raise RuntimeError("%s already exists; move it aside instead of overwriting a capture" % output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return output, record


def plan_case(config, case_id, profile, arm_reader=None):
    """Plan one case. Planning only: this function never sends a motion command."""
    if profile not in PROFILES:
        raise ValueError("unknown planning profile %r; reviewed profiles are %s"
                         % (profile, ", ".join(sorted(PROFILES))))
    case = resolve_case(config, case_id)
    arm = case["arm"]
    geometry = _arm_geometry(config, arm)
    correction, audit_path = _arm_correction(config, arm)
    # The worker compares its own model FK against this raw controller TCP, so the
    # value deliberately stays in the controller millimetre frame.
    live = dict(joint_position_rad=case["start_joint_rad"],
                tcp_position_mm_rad=case["start_controller_tcp_mm_rad"],
                tool_id=case["tool_id"])

    settings_ = settings(config)
    if not Path(settings_["python"]).is_file():
        raise RuntimeError("cuRobo python not found: %s; run curobo status" % settings_["python"])
    if not Path(settings_["robot_yaml"]).is_file():
        raise RuntimeError("robot model not found: %s; run curobo status" % settings_["robot_yaml"])

    profiled = profiled_config(config, profile)
    parameters = planning_profile(profiled)
    from .scene import load_scene
    scene = load_scene(config)
    pragrasp = config.get("pregrasp", {})

    run_id = time.strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8]
    directory = (Path(config["logging"]["directory"])
                 / ("pregrasp_%s_%s_%s" % (time.strftime("%Y%m%d"), case_id, run_id)))
    directory.mkdir(parents=True, exist_ok=False)
    request = dict(
        schema_version=SCHEMA_VERSION, run_id=directory.name, case_id=case_id, arm=arm,
        planning_only=True, planning_profile_name=profile,
        robot_yaml=str(Path(settings_["robot_yaml"]).resolve()),
        expected_commit=CUROBO_COMMIT,
        start_rad=case["start_joint_rad"], goal_rad=case["goal_joint_rad"],
        start_body_tcp_m_rad=case["start_body_tcp_m_rad"],
        goal_body_tcp_m_rad=case["goal_body_tcp_m_rad"],
        live_snapshot=live,
        tool_id=case["tool_id"],
        tool_translation_m=[value / 1000.0 for value in case["sources"]["start"]["tcp_pose_mm_rad"][:3]],
        tool_proxy_radius_m=float(pragrasp.get("tool_proxy_radius_m", 0.025)),
        body_base_xyz_m=list(geometry["base_xyz_m"]),
        body_base_yaw_rad=float(geometry["base_rpy_rad"][2]),
        T_controller_model=correction,
        scene_snapshot=scene,
        motion_limits_file=str(Path(config["motion"]["limits_file"]).resolve()),
        min_body_z_m=float(pragrasp.get("min_body_z_m", 0.8)),
        min_model_clearance_m=float(pragrasp.get("min_model_clearance_m", 0.005)),
        tcp_frame_check_tolerance_m=float(pragrasp.get("tcp_frame_check_tolerance_m", 0.003)),
        planning_parameters=parameters,
        request_timestamp=timestamp(),
        other_arm_modeled=False,
        other_arm_note=("the other arm is excluded by physical separation, not by this model"
                        if case["other_arm_physically_separated"]
                        else "the manifest did not declare the other arm physically separated"),
    )
    request_path = directory / "request.json"
    request_path.write_text(json.dumps(request, indent=2), encoding="utf-8")
    (directory / "case.json").write_text(json.dumps(
        dict(schema_version=SCHEMA_VERSION, case_id=case_id, arm=arm, profile=profile,
             run_id=directory.name, resolved=case, fk_audit=str(audit_path),
             planning_parameters=parameters, scene_digest=scene.get("digest"),
             started_at=timestamp()), indent=2), encoding="utf-8")

    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
    trajectory_path = directory / "trajectory.json"
    singularity_path = directory / "singularity.json"
    try:
        returncode, wall_s = run_logged_process(
            [settings_["python"], "-m", WORKER_MODULE, str(request_path),
             str(trajectory_path), str(singularity_path)],
            env, directory / "planner.log", float(settings_["timeout_s"]), "cuRobo")
    except subprocess.TimeoutExpired as exc:
        _write_result(directory, dict(profile=profile, success=False, stage="timeout",
                                      error="planning timed out; no motion sent"))
        raise RuntimeError("planning timed out; no motion was sent; inspect %s" % directory) from exc
    if returncode or not trajectory_path.is_file() or not singularity_path.is_file():
        _write_result(directory, dict(profile=profile, success=False, stage="worker",
                                      returncode=returncode,
                                      error=_last_log_error(directory / "planner.log")))
        raise RuntimeError("planning failed for profile %s; no fallback and no motion; inspect %s"
                           % (profile, directory))

    payload = json.loads(trajectory_path.read_text(encoding="utf-8"))
    payload["orchestration_wall_s"] = wall_s
    payload["case_id"] = case_id
    trajectory_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    from .preview import write_preview
    preview_path = write_preview(trajectory_path)
    singularity = json.loads(singularity_path.read_text(encoding="utf-8"))
    result = dict(
        profile=profile, success=True, stage="completed", case_id=case_id, arm=arm,
        directory=str(directory), orchestration_wall_s=wall_s,
        plan_cspace_wall_ms=phase_elapsed_ms(payload, "plan_cspace"),
        curobo_total_time_s=phase_field(payload, "plan_cspace", "curobo_total_time_s"),
        curobo_solve_time_s=phase_field(payload, "plan_cspace", "curobo_solve_time_s"),
        points=len(payload["points"]), duration_s=payload["summary"]["duration_s"],
        singularity=singularity["summary"], preview=str(preview_path),
    )
    _write_result(directory, result)
    return directory, result


def phase_elapsed_ms(payload, phase):
    for event in payload.get("timing", {}).get("worker", []):
        if event.get("phase") == phase and event.get("status") == "completed":
            return event.get("elapsed_ms")
    return None


def phase_field(payload, phase, key):
    for event in payload.get("timing", {}).get("worker", []):
        if event.get("phase") == phase and event.get("status") == "completed":
            return event.get(key)
    return None


def _last_log_error(path):
    if not Path(path).is_file():
        return "planner log missing"
    lines = [line.strip() for line in Path(path).read_text(errors="replace").splitlines() if line.strip()]
    return lines[-1] if lines else "planner log empty"


def _write_result(directory, result):
    Path(directory, "result.json").write_text(
        json.dumps(dict(result, finished_at=timestamp()), indent=2), encoding="utf-8")


def latest_plan(config, arm=None):
    """Most recent planning-only run directory, optionally restricted to one arm."""
    root = Path(config["logging"]["directory"])
    candidates = [path for path in root.glob("pregrasp_*") if (path / "trajectory.json").is_file()]
    if arm:
        candidates = [path for path in candidates if json.loads(
            (path / "trajectory.json").read_text(encoding="utf-8")).get("arm") == arm]
    if not candidates:
        raise RuntimeError("no pregrasp plan found; run pregrasp plan CASE PROFILE first")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def preview_plan(config, target="last"):
    """Report the singularity and geometry review for a saved plan. Never moves."""
    from .curobo import preview as curobo_preview
    from .preview import write_preview
    directory = latest_plan(config) if target == "last" else Path(target)
    trajectory = Path(directory) / "trajectory.json"
    if not trajectory.is_file():
        raise RuntimeError("no trajectory in %s" % directory)
    payload = json.loads(trajectory.read_text(encoding="utf-8"))
    report = curobo_preview(trajectory)
    geometry = payload.get("pregrasp", {})
    report.update(case_id=payload.get("case_id"), arm=payload.get("arm"),
                  profile=payload.get("planning_profile"),
                  directory=str(directory),
                  singularity=payload.get("singularity_summary"),
                  geometry=dict((key, geometry.get(key)) for key in (
                      "min_model_clearance_m", "min_central_margin_m", "min_link_body_z_m",
                      "min_soft_limit_margin_rad", "tcp_frame_check_deviation_m",
                      "endpoint_error_rad", "other_arm_modeled", "planner_points",
                      "sampled_points", "subsamples_per_segment")))
    return report, write_preview(trajectory)


def run_case(controller, target="last"):
    """Execute the most recent plan once, after an explicit confirmation phrase.

    Takes the live ``TaskController`` rather than a config mapping: releasing the
    SDK connection so the native sender can own the controller is a controller
    level operation, and passing a plain dict here would fail only after the
    operator had already typed the confirmation phrase.
    """
    config = controller.config
    directory = latest_plan(config) if target == "last" else Path(target)
    trajectory_path = Path(directory) / "trajectory.json"
    payload = json.loads(trajectory_path.read_text(encoding="utf-8"))
    arm = payload["arm"]
    if arm not in EXECUTION_COMMISSIONED_ARMS:
        raise RuntimeError(
            "execution is commissioned for %s only. The %s arm has no audited native sender, so this "
            "plan stays planning-only; do not drive it with a MoveJ or an old demo script."
            % ("/".join(EXECUTION_COMMISSIONED_ARMS), arm))
    case_record = load_json(Path(directory) / "case.json", "case record")
    if case_record.get("case_id") != payload.get("case_id"):
        raise RuntimeError("case.json and trajectory.json disagree; replan")

    from ..adapters.jaka_sdk import JakaSdkArm
    from .trajectory import load_motion_limits
    reader = controller.arms.get(arm)
    if not isinstance(reader, JakaSdkArm):
        raise RuntimeError("the %s arm is not connected, so its live start cannot be verified" % arm)
    limits = load_motion_limits(Path(config["motion"]["limits_file"]))
    live = reader.diagnostics()
    actual = _six_finite(live["joint_position_rad"], "live joints")
    worst = max(abs(a - b) for a, b in zip(actual, payload["points"][0]))
    if worst > limits.max_start_error_rad:
        raise RuntimeError(
            "start mismatch: the arm is %.4f rad away from the planned first point (limit %.4f rad). "
            "Discard this execution approval and replan from the fresh state."
            % (worst, limits.max_start_error_rad))

    from .native_demo import exclusive_right, execute
    phrase = "RUN PREGRASP %s" % payload["case_id"]
    print("RIGHT ONLY: empty gripper, clear the whole swept workspace, on-site observation, "
          "physical E-stop within reach. No automatic return after the move.")
    if input("Type %s: " % phrase).strip() != phrase:
        print("Cancelled; no motion.")
        return None
    with exclusive_right(controller):
        log = execute(config, trajectory_path, "pregrasp", confirmed=True)
    return log


def planned_arm(config, target="last"):
    """Arm of a saved plan, so the terminal can hand over the right reader."""
    directory = latest_plan(config) if target == "last" else Path(target)
    payload = json.loads((Path(directory) / "trajectory.json").read_text(encoding="utf-8"))
    arm = payload.get("arm")
    if arm not in SUPPORTED_ARMS:
        raise RuntimeError("plan %s has no usable arm field" % directory)
    return arm


def read_live(config, arm):
    """One read-only SDK sample used by the terminal for captures and preflight."""
    from ..adapters.jaka_sdk import JakaSdkArm
    arm_object = JakaSdkArm(arm, config["jaka"]["arms"][arm], config["jaka"])
    try:
        return arm_object.diagnostics()
    finally:
        close = getattr(arm_object, "close", None)
        if close:
            close()
