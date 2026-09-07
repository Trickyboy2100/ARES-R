"""Supervised, right-only native SDK demo orchestration; no old SDK connection."""
import json
import math
from pathlib import Path
import subprocess
import time
from contextlib import contextmanager

from .curobo import CUROBO_COMMIT, run_plan, summarize
from .feedback_audit import status_connections
from .trajectory import load_trajectory, load_motion_limits, validate_trajectory

BINARY="/home/yikun/ares-r-curobo-assets/jaka_right_demo"


@contextmanager
def exclusive_right(controller):
    if controller.mode!="hardware-enabled" or controller.config.get("hardware_devices")!="right-arm":
        raise RuntimeError("native demo requires --enable-hardware --devices right-arm")
    from ..adapters.mock import DisabledDevice
    from ..adapters.jaka_sdk import JakaSdkArm
    arm=controller.arms["right"]
    close=getattr(arm,"close",None)
    if close: close()
    controller.arms["right"]=DisabledDevice("right released for native SDK; restart Terminal after failure")
    yield
    # Reconnect the dashboard only after native operation/cleanup succeeded.
    cfg=controller.config["jaka"]
    controller.arms["right"]=JakaSdkArm("right",cfg["arms"]["right"],cfg,True)


def snapshot():
    if status_connections(): raise RuntimeError("right status port occupied; close other Terminal first")
    result=subprocess.run([BINARY,"snapshot"],capture_output=True,text=True,timeout=15)
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
    elif mode=="demo20":
        if trajectory.planner!="curobo-v2-virtual-obstacle-demo" or raw.get("execution_scope")!="supervised_right_empty_workspace" or raw.get("simulation_only"):
            raise RuntimeError("not a supervised 20 cm plan")
        live=req["live_snapshot"]
        validate_demo20(raw,trajectory)
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


def validate_demo20(raw,trajectory):
    demo=raw["demo"];tcp=demo["tcp_path_m"];world=demo["world_link_points_m"]
    if len(tcp)!=len(trajectory.points) or len(world)!=len(tcp): raise RuntimeError("geometry/trajectory count mismatch")
    if any(len(p)!=3 or not all(math.isfinite(v) for v in p) for p in tcp): raise RuntimeError("invalid TCP geometry")
    lengths=[math.sqrt(sum((a[j]-b[j])**2 for j in range(3))) for a,b in zip(tcp,tcp[1:])]
    if not .18<=sum(lengths)<=.22 or max(lengths)/trajectory.sample_period_s>.02: raise RuntimeError("TCP length/speed envelope")
    if demo.get("simulation_collision_checked") is not True or not math.isfinite(demo["min_model_clearance_m"]) or demo["min_model_clearance_m"]<.005:
        raise RuntimeError("virtual model clearance not validated")
    if demo["baseline_min_clearance_m"]>=0: raise RuntimeError("baseline does not intersect virtual obstacle")
    for links in world:
        if len(links)!=8: raise RuntimeError("missing link geometry")
        for p in links:
            if len(p)!=3 or not all(math.isfinite(v) for v in p) or p[1]>-.07 or p[2]<.8:
                raise RuntimeError("right workspace separation gate")
    summary=summarize(trajectory.points,trajectory.sample_period_s)
    if max(summary["max_excursion_deg"])>20 or max(summary["peak_velocity_deg_s"])>1 or max(summary["peak_acceleration_deg_s2"])>2 or summary["duration_s"]>115:
        raise RuntimeError("joint envelope")


def execute(config,path,mode,confirmed=False):
    if not confirmed: raise RuntimeError("explicit on-site supervised confirmation required")
    if status_connections(): raise RuntimeError("right status port occupied")
    native=prepare_native_file(config,path,mode)
    log=Path(path).parent/("native_execution_%d.log"%time.time_ns())
    with log.open("x") as stream:
        child=subprocess.Popen([BINARY,mode,str(native),"CONFIRMED_RIGHT_CLEAR"],stdout=stream,stderr=subprocess.STDOUT)
        try: code=child.wait(timeout=150)
        except (KeyboardInterrupt,subprocess.TimeoutExpired):
            child.terminate()
            try: child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                raise RuntimeError("native stop unconfirmed; use physical E-stop; log: %s"%log)
            raise RuntimeError("execution interrupted; inspect abort/servo exit in %s"%log)
    if code: raise RuntimeError("native execution failed; inspect %s"%log)
    events=[json.loads(l) for l in log.read_text().splitlines() if l.startswith("{")]
    if not any(e.get("event")=="target_reached" for e in events): raise RuntimeError("no target-reached evidence")
    if not any(e.get("event")=="servo_disabled" and e.get("code")==0 for e in events): raise RuntimeError("servo exit unconfirmed")
    return log
