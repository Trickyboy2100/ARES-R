"""Supervised right J6 micro-demo, NOT a general collision-certified executor."""

import json
import math
from pathlib import Path
import time
from contextlib import ExitStack

from .jaka_sdk import _value, parse_robot_status
from .jaka_actual import JakaActualReader
from ..motion.curobo import ARM_NAMES, CUROBO_COMMIT, summarize
from ..motion import load_trajectory, load_motion_limits, validate_trajectory

MICRO_BLOCK_REASON = (
    "live cuRobo execution suspended: SDK/10004 actual-feedback connection "
    "closed during the 2026-09-07 test; stable feedback must be commissioned first"
)


def healthy(robot):
    status = parse_robot_status(_value(robot.get_robot_status(), "robot status"))
    if (status["errcode"] or status["emergency_stop"] or status["protective_stop"]
            or status["on_soft_limit"] or status["drag_mode"]
            or not all(status[k] for k in ("powered_on", "enabled", "sdk_socket_connected"))):
        raise RuntimeError("micro-demo blocked by controller state")
    return status


def check_micro(trajectory, request, raw, limits, diagnostics):
    if trajectory.arm != "right" or trajectory.planner != "curobo-v2-plan_cspace" or raw.get("source_commit") != CUROBO_COMMIT:
        raise RuntimeError("only audited right-arm cuRobo output accepted")
    if tuple(trajectory.joint_names) != ARM_NAMES:
        raise RuntimeError("unexpected joint ordering")
    if not 0.04 <= trajectory.sample_period_s <= 0.08:
        raise RuntimeError("micro-demo requires 40..80 ms sampling")
    if not request.get("diagnostics") or request.get("arm") != "right":
        raise RuntimeError("live right-arm planning snapshot required")
    age = time.time() - float(request.get("captured_at_unix", 0))
    if not math.isfinite(age) or not 0 <= age <= 300:
        raise RuntimeError("planning snapshot expired; replan")
    if diagnostics["tool_data"] != request["diagnostics"]["tool_data"]:
        raise RuntimeError("active tool changed since planning")
    if diagnostics["is_on_limit"] or diagnostics["is_in_collision"]:
        raise RuntimeError("controller limit/collision query blocks execution")
    current = diagnostics["joint_position_rad"]
    if len(current) != 6 or not all(math.isfinite(v) for v in current):
        raise RuntimeError("invalid live joint feedback")
    issues = validate_trajectory(trajectory, limits, current)
    # Only this supervised J6 <=0.5 degree test permits an operator-cleared
    # local workspace in place of full-world collision commissioning. Keep
    # collision_checked=False in the original artifact; never rewrite it.
    if any(issue.severity == "ERROR" and issue.code != "COLLISION" for issue in issues):
        raise RuntimeError("trajectory numeric/site-limit gates failed")
    summary = summarize(trajectory.points, trajectory.sample_period_s)
    if (max(summary["max_excursion_deg"][:5]) > 0.005
            or summary["max_excursion_deg"][5] > 0.5 + 1e-4
            or max(summary["peak_velocity_deg_s"]) > 0.5 + 1e-8
            or max(summary["peak_acceleration_deg_s2"]) > 1.0 + 1e-8
            or summary["duration_s"] > 60):
        raise RuntimeError("trajectory exceeds supervised J6 micro-demo envelope")
    if max(abs(a-b) for a, b in zip(current, trajectory.points[0])) > math.radians(0.02):
        raise RuntimeError("start moved since planning; replan")
    if any(abs(a-b) > 1e-4 for a,b in zip(trajectory.points[-1], request["goal_rad"])):
        raise RuntimeError("goal does not match planning request")
    return summary


def execute_micro(arm, path, limits_path, confirmed=False, clock=time.monotonic, sleeper=time.sleep,
                  telemetry_factory=JakaActualReader):
    if not confirmed:
        raise RuntimeError("explicit supervised micro-demo confirmation required")
    if arm.name != "right" or arm.ip != "192.168.99.101" or not arm.motion_enabled:
        raise RuntimeError("executor is restricted to enabled right controller .101")
    if telemetry_factory is JakaActualReader:
        # A real test lost feedback after sample 16. Keep offline dependency-
        # injected tests available, but do not expose another live retry.
        raise RuntimeError(MICRO_BLOCK_REASON)
    import fcntl
    path = Path(path)
    trajectory = load_trajectory(path)
    request = json.loads((path.parent / "request.json").read_text())
    raw = json.loads(path.read_text())
    with open("/tmp/ares-r-right-servo.lock", "a") as lock, ExitStack() as stack:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        robot = arm.robot
        # Finish legacy SDK status queries before the dedicated 10004 reader
        # owns feedback. Mixing the two readers can invalidate SDK data RPCs.
        diagnostics = arm.diagnostics()
        if not healthy(robot)["in_position"]:
            raise RuntimeError("right arm must be stationary before servo enable")
        reader = stack.enter_context(telemetry_factory(arm.ip))
        reader.read()  # Warm the telemetry connection before enabling servo.
        first_actual = reader.read()
        diagnostics["joint_position_rad"] = first_actual["joint_actual_position_rad"]
        summary = check_micro(trajectory, request, raw, load_motion_limits(Path(limits_path)), diagnostics)
        step = round(trajectory.sample_period_s / 0.008)
        log_path = path.parent / ("execution_%d.jsonl" % time.time_ns())
        enabled = False
        with log_path.open("x") as log:
            def record(event, **values):
                log.write(json.dumps(dict(event=event, monotonic=clock(), **values)) + "\n")
                log.flush()
            def cleanup_record(event, **values):
                try:
                    record(event, **values)
                except OSError:
                    pass  # A full disk must never prevent abort or servo disable.
            try:
                record("supervised_micro_begin", summary=summary, api="servo_j_extend", absolute_mode=0)
                _value(robot.servo_move_enable(True), "servo enable")
                enabled = True
                deadline = clock()
                previous = trajectory.points[0]
                for index, point in enumerate(trajectory.points):
                    wait = deadline - clock()
                    if wait > 0: sleeper(wait)
                    if clock() - deadline > trajectory.sample_period_s * 0.5:
                        raise RuntimeError("send loop late; no catch-up burst permitted")
                    feedback = reader.read()
                    if feedback["tool_id"] != diagnostics["tool_data"]["tool_id"]:
                        raise RuntimeError("tool ID changed during servo")
                    actual = feedback["joint_actual_position_rad"]
                    if len(actual) != 6 or not all(math.isfinite(v) for v in actual):
                        raise RuntimeError("invalid feedback")
                    if max(abs(a-b) for a,b in zip(actual, previous)) > math.radians(0.1):
                        raise RuntimeError("tracking error exceeded 0.1 degree")
                    if clock() - deadline > trajectory.sample_period_s * 0.5:
                        raise RuntimeError("status query exceeded send budget")
                    _value(robot.servo_j_extend(list(point), 0, step), "servo_j_extend absolute")
                    record("sample", index=index, target_rad=point, actual_rad=actual, deadline=deadline,
                           controller_reported_rad=feedback["joint_position_rad"],
                           feedback_roundtrip_s=feedback.get("roundtrip_s"))
                    previous = point
                    deadline += trajectory.sample_period_s
                sleeper(max(0, deadline-clock()))
                actual = reader.read()["joint_actual_position_rad"]
                if len(actual) != 6 or not all(math.isfinite(v) for v in actual) or max(
                        abs(a-b) for a,b in zip(actual, trajectory.points[-1])) > math.radians(0.05):
                    raise RuntimeError("final feedback outside 0.05 degree tolerance")
                record("target_reached", actual_rad=actual)
            except BaseException as error:
                cleanup_record("execution_failed", error=repr(error))
                if enabled:
                    try:
                        _value(robot.motion_abort(), "right motion abort")
                        cleanup_record("abort_accepted")
                    except BaseException as cleanup_error:
                        cleanup_record("abort_failed", error=str(cleanup_error))
                raise
            finally:
                if enabled:
                    _value(robot.servo_move_enable(False), "servo disable")
                    cleanup_record("servo_disabled")
        return log_path
