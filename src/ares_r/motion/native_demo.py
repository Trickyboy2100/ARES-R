"""Supervised, right-only native SDK demo orchestration; no old SDK connection."""
import json
import math
import os
from pathlib import Path
import subprocess
import time
from contextlib import contextmanager
from dataclasses import replace

from .curobo import CUROBO_COMMIT, run_plan, summarize
from .feedback_audit import status_connections
from .trajectory import load_trajectory, load_motion_limits, validate_trajectory
from .demo_timing import (SPEED_SCALE, SUPPORTED_SPEED_SCALES, SAMPLE_PERIOD_S,
    MAX_JOINT_ACCEL_DEG_S2)
from .demo_envelope import RESET_MAX_EXCURSION_DEG, RESET_MAX_TCP_LENGTH_M, RESET_MAX_DURATION_S

BINARY="/home/yikun/ares-r-curobo-assets/jaka_right_demo"
SDK_LIBRARY="/home/yikun/JAKA/lib"


class NativeExecutionError(RuntimeError):
    def __init__(self,message,code="NATIVE_EXECUTION_FAILED",log=None,recoverable=False):
        super().__init__(message);self.code=code;self.log=Path(log) if log else None;self.recoverable=recoverable


def classify_native_failure(text,events):
    cleanup=(any(e.get("event")=="abort" and e.get("code")==0 for e in events) and
             any(e.get("event")=="servo_disabled" and e.get("code")==0 for e in events) and
             any(e.get("event")=="logout" and e.get("code")==0 for e in events))
    tracking="FAILED tracking error" in text
    return ("TRACKING_ERROR" if tracking else "NATIVE_EXECUTION_FAILED",
            bool(tracking and cleanup),cleanup)


def native_environment():
    """Never inherit the legacy Python SDK's loader configuration."""
    env=dict(os.environ)
    env["LD_LIBRARY_PATH"]=SDK_LIBRARY
    env["LD_BIND_NOW"]="1"  # Resolve every ABI symbol BEFORE login or servo enable.
    env.pop("LD_PRELOAD",None)
    env.pop("LD_AUDIT",None)
    return env


@contextmanager
def exclusive_right(controller):
    if controller.mode!="hardware-enabled":
        raise RuntimeError("native demo requires --enable-hardware")
    from ..adapters.mock import DisabledDevice
    from ..adapters.jaka_sdk import JakaSdkArm
    arm=controller.arms["right"]
    if not isinstance(arm,JakaSdkArm): raise RuntimeError("right arm is not connected")
    close=getattr(arm,"close",None)
    if close: close()
    controller.arms["right"]=DisabledDevice("right released for native SDK; restart Terminal after failure")
    yield
    # Reconnect the dashboard only after native operation/cleanup succeeded.
    cfg=controller.config["jaka"]
    controller.arms["right"]=JakaSdkArm("right",cfg["arms"]["right"],cfg,True)


def snapshot():
    # This process has already released its SDK connection, so its own residual
    # socket must not be mistaken for a competing reader.
    competing = status_connections(exclude_pid=os.getpid())
    if competing: raise RuntimeError("right status port occupied; close other Terminal first")
    result=subprocess.run([BINARY,"snapshot"],env=native_environment(),capture_output=True,text=True,timeout=15)
    if result.returncode: raise RuntimeError("right snapshot failed: "+result.stdout+result.stderr)
    return next(json.loads(line) for line in result.stdout.splitlines()
                if line.startswith("{") and json.loads(line).get("event")=="snapshot")


def plan_micro(config):
    live=snapshot()
    if live["queue"] or live["active_queue"] or not live["inpos"]: raise RuntimeError("right not idle")
    start=live["actual_rad"];goal=list(start);goal[5]+=math.radians(.2)
    diagnostics=dict(joint_position_rad=start,tool_data=dict(tool_id=live["tool_id"],pose_mm_rad=live["tool_mm_rad"]),
                     joint_position_source="sdk222_actual",native_snapshot=live)
    return run_plan(config,start,goal,diagnostics)


#: Hard bounds enforced inside the native sender, read from
#: scripts/jaka_right_demo.cpp. The velocity literal is wrapped in rad(), so
#: rad(3.0) is 3 deg/s and that is 1.9x STRICTER than the 0.10 rad/s site limit.
#: The acceleration literal is the plain ``.2`` of the non-micro branch, already
#: SI, so 0.2 rad/s^2 and identical to the site limit. Getting this backwards
#: invents a 57x phantom gap, so it is pinned by tests against real accepted files.
NATIVE_MAX_JOINT_SPEED_RAD_S = math.radians(3.0)
NATIVE_MAX_JOINT_ACCEL_RAD_S2 = 0.2

#: The sender's third gate is the servo following error (scripts/jaka_right_demo.cpp
#: line 128): it aborts with "tracking error" when the measured joints differ from
#: the PREVIOUS commanded target by more than rad(0.2) = 0.2 deg in legacy
#: modes. The explicit supervised_path mode has a separate 0.5 deg gate. That residual
#: grows with commanded speed, so it is a velocity ceiling far tighter than either
#: the joint limits or the sender's own 3 deg/s gate -- and neither of those can
#: see it. A file can pass every offline gate and still abort mid-motion, which is
#: exactly what happened to right_S1 on 2026-09-14 at 1.73 deg/s.
#:
#: Over the eleven native runs on record the observed ratio (gate value / peak
#: joint speed) spans 0.038 .. 0.114 s. It is a property of the servo loop and of
#: which joints are moving, not a fixed constant, so this uses the conservative end
#: of that range instead of the best-fitting value.
NATIVE_TRACKING_LAG_S = 0.12
#: Legacy mode budget; supervised_path has a separate bounded budget below.
NATIVE_TRACKING_BUDGET_DEG = 0.18
NATIVE_TRACKING_SPEED_CAP_RAD_S = math.radians(
    NATIVE_TRACKING_BUDGET_DEG / NATIVE_TRACKING_LAG_S)

# Right-only supervised A/B trial. Other native modes retain their 0.2-degree
# sender gate and the historical conservative speed ceiling.
SUPERVISED_HARD_TRACKING_GATE_DEG = 1.5
SUPERVISED_TRACKING_BUDGET_DEG = 1.48
SUPERVISED_TRACKING_SPEED_CAP_RAD_S = math.radians(
    SUPERVISED_TRACKING_BUDGET_DEG / NATIVE_TRACKING_LAG_S)
SUPERVISED_MAX_JOINT_SPEED_RAD_S = 0.20
SUPERVISED_MAX_JOINT_ACCEL_RAD_S2 = 0.20

RESAMPLE_MAX_ATTEMPTS = 200
RESAMPLE_STEP = 1.02


def native_move_caps(motion_limits):
    """Per-joint caps accepted by both the site limits and the native sender.

    The tracking ceiling is included here rather than as a separate check because
    the following error is proportional to speed: bounding the speed bounds the
    error, so one velocity cap expresses both gates.
    """
    speed = [min(float(value), NATIVE_MAX_JOINT_SPEED_RAD_S,
                 NATIVE_TRACKING_SPEED_CAP_RAD_S)
             for value in motion_limits.max_velocity_rad_s]
    accel = [min(float(value), NATIVE_MAX_JOINT_ACCEL_RAD_S2)
             for value in motion_limits.max_acceleration_rad_s2]
    return speed, accel


def predicted_tracking_gate_deg(points, dt, lag_s=NATIVE_TRACKING_LAG_S):
    """Predicted worst case of the sender's servo following-error gate, in degrees.

    The sender takes the Chebyshev distance between the measured joints and the
    previous target, and the residual scales with the commanded speed, so
    ``lag_s`` times the fastest joint step predicts the value it will compare
    against the mode-specific sender gate. Reported alongside velocity and acceleration margins so
    the operator can see how much of the tracking allowance a path spends.
    """
    worst = 0.0
    for index in range(1, len(points)):
        step = max(abs(points[index][joint] - points[index - 1][joint])
                   for joint in range(6))
        worst = max(worst, math.degrees(step) / dt * lag_s)
    return worst


def native_move_violations(points, dt, speed_cap, accel_cap):
    """Mirror the sender's per-sample gates exactly.

    The sender records the first sample's velocity as zero, so the first step has
    to satisfy the acceleration gate on its own, and it re-checks the final
    velocity against the acceleration gate once the loop has finished. Both
    details are reproduced here so a file the sender would reject is caught
    before it is written rather than after the operator confirms.
    """
    previous = [0.0] * 6
    violations = []
    for index, row in enumerate(points):
        for joint in range(6):
            speed = (row[joint] - points[index - 1][joint]) / dt if index else 0.0
            if abs(speed) > speed_cap[joint] + 1e-12:
                violations.append((index, joint, "speed"))
            if abs(speed - previous[joint]) / dt > accel_cap[joint] + 1e-12:
                violations.append((index, joint, "acceleration"))
            previous[joint] = speed
    for joint in range(6):
        if abs(previous[joint]) / dt > accel_cap[joint] + 1e-12:
            violations.append((len(points) - 1, joint, "end acceleration"))
    return violations


def native_move_excess(points, dt, speed_cap, accel_cap):
    """Largest factor by which any sender gate is exceeded; <= 1.0 means it passes.

    Same arithmetic as :func:`native_move_violations`, but returning the worst
    ratio instead of every breach lets the resampler aim its next attempt.
    """
    previous = [0.0] * 6
    worst = 0.0
    for index, row in enumerate(points):
        for joint in range(6):
            speed = (row[joint] - points[index - 1][joint]) / dt if index else 0.0
            worst = max(worst, abs(speed) / speed_cap[joint])
            worst = max(worst, abs(speed - previous[joint]) / dt / accel_cap[joint])
            previous[joint] = speed
    for joint in range(6):
        worst = max(worst, abs(previous[joint]) / dt / accel_cap[joint])
    return worst


def resample_for_native(points, source_dt, target_dt, speed_cap, accel_cap,
                        max_duration_s=None):
    """Resample and verify against the sender gates, refining until accepted.

    A single proportional stretch is normally enough for the speed gate, but the
    source is piecewise linear: the velocity is constant inside each segment and
    jumps at every vertex, so the apparent 80 ms acceleration only falls like
    1/stretch instead of the continuum 1/stretch^2. The measured excess is
    therefore used as the next guess, which converges in a couple of attempts
    instead of stepping blindly. Refusing here keeps the failure on the planning
    side rather than after the operator has typed the confirmation phrase.
    """
    stretch = 1.0
    reached = 0.0
    sampled = None
    for _ in range(RESAMPLE_MAX_ATTEMPTS):
        try:
            sampled = resample_uniform(points, source_dt, target_dt, speed_cap, accel_cap,
                                       extra_stretch=stretch,
                                       max_duration_s=max_duration_s)
        except ValueError:
            break
        reached = (len(sampled) - 1) * target_dt
        excess = native_move_excess(sampled, target_dt, speed_cap, accel_cap)
        if excess <= 1.0:
            return sampled
        if max_duration_s is not None and reached >= max_duration_s:
            break
        stretch *= min(1.6, max(RESAMPLE_STEP, excess * 1.03))
    raise RuntimeError(
        "cannot fit this path inside the native sender velocity/acceleration envelope; "
        "resampling reached %.2fx and %.1f s and was still rejected"
        % (stretch, reached))


def resample_uniform(points, source_dt, target_dt, velocity_cap_rad_s, acceleration_cap_rad_s2,
                     extra_stretch=1.0, max_duration_s=None):
    """Time-dilate a piecewise-linear joint path to the native sample period.

    Only the time parameterisation changes. The path is sampled, never extended,
    corrected or replaced by a different planner; the endpoints are preserved
    exactly and the caller revalidates the result against the site limits. The
    output sample count is chosen so the peak joint speed and acceleration stay
    inside those limits.

    ``extra_stretch`` multiplies the computed dilation. The caller uses it to
    refine a result that the native sender would otherwise reject.
    """
    extra_stretch = float(extra_stretch)
    if not (math.isfinite(extra_stretch) and extra_stretch >= 1.0):
        raise ValueError("extra_stretch must be finite and at least one")
    points = [[float(value) for value in point] for point in points]
    if len(points) < 2:
        raise ValueError("at least two points are required")
    dof = len(points[0])
    if any(len(point) != dof for point in points) or dof == 0:
        raise ValueError("every point must share one nonzero joint count")
    if not (math.isfinite(source_dt) and source_dt > 0):
        raise ValueError("source sample period must be positive and finite")
    if not (math.isfinite(target_dt) and target_dt > 0):
        raise ValueError("target sample period must be positive and finite")
    velocity_cap = [float(value) for value in velocity_cap_rad_s]
    acceleration_cap = [float(value) for value in acceleration_cap_rad_s2]
    if len(velocity_cap) != dof or len(acceleration_cap) != dof:
        raise ValueError("limit vectors must match the joint count")
    if any(not math.isfinite(value) or value <= 0 for value in velocity_cap + acceleration_cap):
        raise ValueError("site limits must be positive and finite")

    velocities = [[(end[j] - begin[j]) / source_dt for j in range(dof)]
                  for begin, end in zip(points, points[1:])]
    speed_stretch = max(max(abs(row[j]) for row in velocities) / velocity_cap[j] for j in range(dof))
    acceleration_stretch = 0.0
    for earlier, later in zip(velocities, velocities[1:]):
        for j in range(dof):
            acceleration_stretch = max(acceleration_stretch,
                                       abs(later[j] - earlier[j]) / source_dt / acceleration_cap[j])
    stretch = max(1.0, speed_stretch, math.sqrt(acceleration_stretch)) * extra_stretch
    source_span = (len(points) - 1) * source_dt

    def at_source_time(seconds):
        """Sample the source polyline in its own time base."""
        position = min(max(seconds / source_dt, 0.0), float(len(points) - 1))
        index = min(int(position), len(points) - 2)
        fraction = position - index
        return [begin + (end - begin) * fraction
                for begin, end in zip(points[index], points[index + 1])]

    # Dilate time by ``stretch``, then sample at the native cadence. The index is
    # mapped back into the source time base, so the geometry is never extrapolated.
    count = max(2, int(math.ceil(source_span * stretch / target_dt)) + 1)
    # Refuse before allocating: an extreme stretch would otherwise build millions
    # of samples only for the caller to discard them.
    if max_duration_s is not None and (count - 1) * target_dt > max_duration_s:
        raise ValueError("resampling would need %.1f s, above the %.1f s cap"
                         % ((count - 1) * target_dt, max_duration_s))
    sampled = [at_source_time(source_span * index / (count - 1)) for index in range(count)]
    sampled[0] = list(points[0])
    sampled[-1] = list(points[-1])
    return sampled


def prepare_native_file(config,path,mode):
    path=Path(path);raw=json.loads(path.read_text());req=json.loads((path.parent/"request.json").read_text())
    trajectory=load_trajectory(path)
    if raw.get("source_commit")!=CUROBO_COMMIT or trajectory.arm!="right": raise RuntimeError("unaudited planner output")
    if mode=="micro":
        if trajectory.planner!="curobo-v2-plan_cspace": raise RuntimeError("micro requires cuRobo plan_cspace")
        diagnostics=req.get("diagnostics",{})
        if diagnostics.get("joint_position_source")!="sdk222_actual": raise RuntimeError("fresh SDK222 actual start required")
        live=diagnostics["native_snapshot"]
    elif mode in ("demo20", "reset"):
        if raw.get("speed_scale") not in SUPPORTED_SPEED_SCALES:
            raise RuntimeError("unsupported demo speed profile; replan")
        if trajectory.planner!="curobo-v2-virtual-obstacle-demo" or raw.get("execution_scope")!="supervised_right_empty_workspace" or raw.get("simulation_only"):
            raise RuntimeError("not a supervised 20 cm plan")
        live=req["live_snapshot"]
        if raw.get("intent", "demo20") != mode: raise RuntimeError("trajectory intent mismatch")
        from .demo_reference import load_reference, check_context, at_reference
        reference=load_reference(config)
        if raw.get("reference_id") != reference["id"]: raise RuntimeError("fixed start changed; replan")
        check_context(config,reference,live)
        from .scene import load_scene
        if raw.get("scene_digest")!=load_scene(config)["digest"]: raise RuntimeError("scene changed; replan")
        endpoint=trajectory.points[0] if mode=="demo20" else trajectory.points[-1]
        if mode=="reset" and raw.get("target_kind")=="named_pose":
            from ..named_poses import load_named_poses
            name=raw.get("target_name");pose=load_named_poses(config["named_poses_file"])["poses"].get(name,{})
            target=pose.get("arms",{}).get("right",{})
            goal=target.get("ik_joint_rad",target.get("joint_rad"))
            if not goal or max(abs(a-b) for a,b in zip(goal,endpoint))>1e-4:
                raise RuntimeError("named-pose target changed; replan")
        elif not at_reference(reference,dict(live,actual_rad=endpoint),check_tcp=False):
            raise RuntimeError("plan does not use the fixed reference joints")
        validate_demo20(raw,trajectory,reset=(mode=="reset"))
    elif mode=="pregrasp":
        if trajectory.planner!="curobo-v2-pregrasp":
            raise RuntimeError("pregrasp requires a cuRobo pregrasp plan")
        if raw.get("execution_scope")!="supervised_pregrasp_empty_workspace":
            raise RuntimeError("not a supervised pregrasp plan")
        if raw.get("collision_checked") is not False:
            raise RuntimeError("unexpected collision_checked attestation in a pregrasp plan")
        # The planner keeps its own interpolation cadence. ServoJ needs the native
        # 80 ms cadence, so only the time parameterisation is rewritten here; the
        # geometry is preserved and the result is revalidated just below. The caps
        # are the stricter of the site limits and the sender's own hard bounds.
        live=snapshot()
        site=load_motion_limits(Path(config["motion"]["limits_file"]))
        speed_cap,accel_cap=native_move_caps(site)
        excursion=max(max(abs(point[j]-trajectory.points[0][j]) for point in trajectory.points)
                      for j in range(6))
        if excursion>math.radians(RESET_MAX_EXCURSION_DEG):
            raise RuntimeError("path needs %.1f deg but the sender allows %.0f deg per joint"
                               %(math.degrees(excursion),RESET_MAX_EXCURSION_DEG))
        points=resample_for_native(trajectory.points,trajectory.sample_period_s,SAMPLE_PERIOD_S,
                                  speed_cap,accel_cap,max_duration_s=RESET_MAX_DURATION_S)
        trajectory=replace(trajectory,sample_period_s=SAMPLE_PERIOD_S,points=tuple(points))
    else: raise RuntimeError("unsupported demo mode")
    limits=load_motion_limits(Path(config["motion"]["limits_file"]))
    issues=validate_trajectory(trajectory,limits,live["actual_rad"])
    if any(i.severity=="ERROR" and i.code!="COLLISION" for i in issues): raise RuntimeError("numeric/site gates failed")
    if abs(trajectory.sample_period_s-.08)>1e-9: raise RuntimeError("native demo requires 80 ms samples")
    captured=live["captured_at_unix"]
    if not 0<=time.time()-captured<=300: raise RuntimeError("snapshot expired; replan")
    rows=["ARES_R_RIGHT_V1 %d %.17g %d %d"%(len(trajectory.points),trajectory.sample_period_s,captured,live["tool_id"]),
          " ".join(map(str,live["tool_mm_rad"])),
          " ".join(str(x+limits.soft_limit_margin_rad) for x in limits.lower_rad),
          " ".join(str(x-limits.soft_limit_margin_rad) for x in limits.upper_rad)]
    rows.extend(" ".join(map(str,q)) for q in trajectory.points)
    output=path.parent/("native_%d.txt"%time.time_ns());output.write_text("\n".join(rows)+"\n")
    return output,trajectory


def validate_demo20(raw,trajectory,reset=False):
    demo=raw["demo"];tcp=demo["tcp_path_m"];world=demo["world_link_points_m"]
    if len(tcp)!=len(trajectory.points) or len(world)!=len(tcp): raise RuntimeError("geometry/trajectory count mismatch")
    if any(len(p)!=3 or not all(math.isfinite(v) for v in p) for p in tcp): raise RuntimeError("invalid TCP geometry")
    lengths=[math.sqrt(sum((a[j]-b[j])**2 for j in range(3))) for a,b in zip(tcp,tcp[1:])]
    speed_scale=float(raw["speed_scale"])
    if not (.000001 if reset else .18)<=sum(lengths)<=(RESET_MAX_TCP_LENGTH_M if reset else .22) or max(lengths)/trajectory.sample_period_s>.02*speed_scale: raise RuntimeError("TCP length/speed envelope")
    if demo.get("simulation_collision_checked") is not True or not math.isfinite(demo["min_model_clearance_m"]) or demo["min_model_clearance_m"]<.005:
        raise RuntimeError("virtual model clearance not validated")
    if not reset and demo["baseline_min_clearance_m"]>=0: raise RuntimeError("baseline does not intersect virtual obstacle")
    for links in world:
        if len(links)!=8: raise RuntimeError("missing link geometry")
        for p in links:
            if len(p)!=3 or not all(math.isfinite(v) for v in p) or p[1]>-.07 or p[2]<.8:
                raise RuntimeError("right workspace separation gate")
    summary=summarize(trajectory.points,trajectory.sample_period_s)
    if max(summary["max_excursion_deg"])>(RESET_MAX_EXCURSION_DEG if reset else 20) or max(summary["peak_velocity_deg_s"])>speed_scale or max(summary["peak_acceleration_deg_s2"])>MAX_JOINT_ACCEL_DEG_S2 or summary["duration_s"]>(RESET_MAX_DURATION_S if reset else 115):
        raise RuntimeError("joint envelope")


def execute(config,path,mode,confirmed=False,safety_permit=None):
    if not confirmed: raise RuntimeError("explicit on-site supervised confirmation required")
    competing = status_connections(exclude_pid=os.getpid())
    if competing: raise RuntimeError("right status port occupied")
    native,trajectory=prepare_native_file(config,path,mode)
    from .safety_kernel import require_permit
    require_permit(safety_permit, trajectory.arm, trajectory.points,
                   trajectory.sample_period_s)
    from ..world_geometry import load_world_geometry,base_tcp_to_world
    world=load_world_geometry(Path(config["world_geometry_file"]))
    world_base=world["arms"]["right"]
    base_tcp_to_world(world_base,[0.0]*6)  # validate before starting the sender
    log=Path(path).parent/("native_execution_%d.log"%time.time_ns())
    log.with_suffix(".frame.json").write_text(json.dumps(dict(frame=world["frame"],right_base=world_base,
        position_unit="m",angle_unit="rad",display_angle_unit="deg",rotation="Rz(yaw) Ry(pitch) Rx(roll)"),indent=2))
    from .servo_dashboard import monitor
    # The executed path is the resampled one, so the dashboard total and the
    # watchdog must both use it rather than the saved planner cadence.
    executed=dict(points=trajectory.points,sample_period_s=trajectory.sample_period_s,
                  speed_scale=json.loads(Path(path).read_text()).get("speed_scale",1))
    planned_s=(len(trajectory.points)-1)*trajectory.sample_period_s
    timeout=max(150.0,planned_s*2+60.0,RESET_MAX_DURATION_S+30 if mode=="reset" else 0.0)
    with log.open("x") as stream:
        child=subprocess.Popen([BINARY,mode,str(native),"CONFIRMED_RIGHT_CLEAR"],
                               env=native_environment(),stdout=stream,stderr=subprocess.STDOUT)
        code=monitor(child,log,executed,phase=mode,world_base=world_base,timeout=timeout)
    events=[json.loads(l) for l in log.read_text().splitlines() if l.startswith("{")]
    text=log.read_text()
    if code:
        failure_code,recoverable,cleanup=classify_native_failure(text,events)
        raise NativeExecutionError("native execution failed [%s], cleanup=%s; inspect %s"%(
            failure_code,cleanup,log),code=failure_code,log=log,recoverable=recoverable)
    if not any(e.get("event")=="target_reached" for e in events): raise RuntimeError("no target-reached evidence")
    if not any(e.get("event")=="servo_disabled" and e.get("code")==0 for e in events): raise RuntimeError("servo exit unconfirmed")
    return log
