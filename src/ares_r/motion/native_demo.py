"""Supervised, right-only native SDK demo orchestration; no old SDK connection."""
import json
import math
import os
from pathlib import Path
import subprocess
import time
from contextlib import contextmanager

from .curobo import CUROBO_COMMIT, run_plan, summarize
from .feedback_audit import status_connections
from .trajectory import load_trajectory, load_motion_limits, validate_trajectory
from .demo_timing import (SPEED_SCALE, SUPPORTED_SPEED_SCALES,
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
    if status_connections(): raise RuntimeError("right status port occupied; close other Terminal first")
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
            goal=pose.get("arms",{}).get("right",{}).get("ik_joint_rad")
            if not goal or max(abs(a-b) for a,b in zip(goal,endpoint))>1e-4:
                raise RuntimeError("named-pose target changed; replan")
        elif not at_reference(reference,dict(live,actual_rad=endpoint),check_tcp=False):
            raise RuntimeError("plan does not use the fixed reference joints")
        validate_demo20(raw,trajectory,reset=(mode=="reset"))
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
    return output


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


def execute(config,path,mode,confirmed=False):
    if not confirmed: raise RuntimeError("explicit on-site supervised confirmation required")
    if status_connections(): raise RuntimeError("right status port occupied")
    native=prepare_native_file(config,path,mode)
    from ..world_geometry import load_world_geometry,base_tcp_to_world
    world=load_world_geometry(Path(config["world_geometry_file"]))
    world_base=world["arms"]["right"]
    base_tcp_to_world(world_base,[0.0]*6)  # validate before starting the sender
    log=Path(path).parent/("native_execution_%d.log"%time.time_ns())
    log.with_suffix(".frame.json").write_text(json.dumps(dict(frame=world["frame"],right_base=world_base,
        position_unit="m",angle_unit="rad",display_angle_unit="deg",rotation="Rz(yaw) Ry(pitch) Rx(roll)"),indent=2))
    from .servo_dashboard import monitor
    with log.open("x") as stream:
        child=subprocess.Popen([BINARY,mode,str(native),"CONFIRMED_RIGHT_CLEAR"],
                               env=native_environment(),stdout=stream,stderr=subprocess.STDOUT)
        code=monitor(child,log,json.loads(Path(path).read_text()),phase=mode,world_base=world_base,
                     timeout=RESET_MAX_DURATION_S+30 if mode=="reset" else 150)
    events=[json.loads(l) for l in log.read_text().splitlines() if l.startswith("{")]
    text=log.read_text()
    if code:
        failure_code,recoverable,cleanup=classify_native_failure(text,events)
        raise NativeExecutionError("native execution failed [%s], cleanup=%s; inspect %s"%(
            failure_code,cleanup,log),code=failure_code,log=log,recoverable=recoverable)
    if not any(e.get("event")=="target_reached" for e in events): raise RuntimeError("no target-reached evidence")
    if not any(e.get("event")=="servo_disabled" and e.get("code")==0 for e in events): raise RuntimeError("servo exit unconfirmed")
    return log
