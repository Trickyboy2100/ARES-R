"""GPU-only virtual obstacle planning. Never imports a hardware adapter."""

import hashlib
import json
import math
from pathlib import Path
import sys
import time
import xml.etree.ElementTree as ET

from .curobo import ARM_NAMES, finite_joints, slow_sample_period, summarize
from .scene import scene_cuboids
from .demo_envelope import RESET_MAX_EXCURSION_DEG, RESET_MAX_DURATION_S
from .demo_timing import (SPEED_SCALE, SAMPLE_PERIOD_S, MAX_JOINT_SPEED_DEG_S,
                         MAX_JOINT_ACCEL_DEG_S2, MAX_TCP_SPEED_M_S,
                         SUPPORTED_SPEED_SCALES, sample_count_at_scale)


def main():
    import numpy as np
    import torch
    import yaml
    import curobo
    from curobo.motion_planner import MotionPlanner, MotionPlannerCfg
    from curobo.types import JointState

    request = json.loads(Path(sys.argv[1]).read_text())
    if request.get("planning_only") is not True or request["arm"] != "right":
        raise RuntimeError("virtual right-arm request required")
    speed_scale=float(request.get("speed_scale",SPEED_SCALE))
    if speed_scale not in SUPPORTED_SPEED_SCALES: raise RuntimeError("unsupported speed scale")
    source = Path(curobo.__file__).resolve().parent.parent
    manifest = json.loads((source / "ARES_R_SOURCE_MANIFEST.json").read_text())
    if manifest["commit"] != request["expected_commit"]:
        raise RuntimeError("cuRobo source revision mismatch")
    for item in manifest["files"]:
        blob = (source / item["path"]).read_bytes()
        if hashlib.sha1(b"blob " + str(len(blob)).encode() + b"\0" + blob).hexdigest() != item["sha"]:
            raise RuntimeError("modified cuRobo source: " + item["path"])
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA required; no fallback")
    torch.manual_seed(123)
    robot_path = Path(request["robot_yaml"])
    robot = yaml.safe_load(robot_path.read_text())
    urdf_path = Path(robot["kinematics"]["urdf_path"])
    root = ET.parse(urdf_path).getroot()
    offset = np.asarray(request["tool_translation_m"])

    def transform(xyz, rpy):
        r, p, y = rpy
        cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
        t = np.eye(4)
        t[:3,:3] = [[cy*cp, cy*sp*sr-sy*cr, cy*sp*cr+sy*sr],
                     [sy*cp, sy*sp*sr+cy*cr, sy*sp*cr-cy*sr], [-sp, cp*sr, cp*cr]]
        t[:3,3] = xyz
        return t

    origins = []
    for name in ARM_NAMES:
        joint = root.find("joint[@name='%s']" % name)
        if joint.find("axis").get("xyz") != "0 0 1":
            raise RuntimeError("unexpected URDF joint axis")
        origin = joint.find("origin")
        origins.append(transform([float(v) for v in origin.get("xyz").split()],
                                 [float(v) for v in origin.get("rpy").split()]))

    def fk(q):
        t = np.eye(4)
        links = [t[:3,3].tolist()]
        for origin, value in zip(origins, q):
            t = t @ origin @ transform([0,0,0], [0,0,value])
            links.append(t[:3,3].tolist())
        tcp = t[:3,:3] @ offset + t[:3,3]
        return tcp, links + [tcp.tolist()]

    # Virtual tube from flange to live TCP. This is not a
    # measured gripper/attachment model and cannot certify the real robot.
    spheres = robot["kinematics"]["collision_spheres"]["link6"]
    spheres.extend(dict(center=(offset*f).tolist(), radius=request["tool_proxy_radius_m"])
                   for f in np.linspace(0, 1, 12))
    start = np.asarray(finite_joints(request["start_rad"]))
    started = time.monotonic()
    attempts = []
    probe=start.copy();probe[0]+=.01
    radius=float(np.linalg.norm(fk(probe)[0]-fk(start)[0]))/.01
    reset=request.get("intent")=="reset"
    if not reset and radius<.1: raise RuntimeError("unsuitable starting lever arm")
    correction=np.asarray(request["T_controller_model"])
    yaw=float(request["body_right_yaw_rad"])
    body=transform(request["body_right_xyz_m"],[0,0,yaw]) @ correction
    predicted=correction @ np.r_[fk(start)[0],1]
    if np.linalg.norm(predicted[:3]-np.asarray(request["live_snapshot"]["tcp_mm_rad"][:3])/1000)>.003:
        raise RuntimeError("live TCP and planning FK differ by more than 3 mm")
    goals=[np.asarray(finite_joints(request["goal_rad"]))] if reset else [start+np.array([length/radius,0,0,0,0,0]) for length in (.16,.14,.18)]
    for goal in goals:
        delta_deg=math.degrees(goal[0]-start[0])
        midpoint = fk((start+goal)/2)[0]
        dims = np.asarray(request["obstacle_dims_m"])
        scene = {"cuboid": scene_cuboids(request["scene_snapshot"])}
        # A reset uses an empty/manual scene, not a newly invented obstacle
        # between nearby endpoints. The remote sentinel keeps the collision
        # backend initialized; it is not a claimed physical obstacle.
        if reset: midpoint=np.array([10.,10.,10.])
        scene["cuboid"]["virtual_block"]=dict(dims=dims.tolist(),pose=midpoint.tolist()+[1,0,0,0])
        cfg = MotionPlannerCfg.create(robot=robot, scene_model=scene,
            interpolation_dt=0.008, interpolation_buffer_size=5000,
            num_trajopt_seeds=8, num_ik_seeds=8, use_cuda_graph=False,
            self_collision_check=True, random_seed=123)
        planner = MotionPlanner(cfg)
        names = list(planner.joint_names)
        if len(names) != 6 or set(names) != set(ARM_NAMES):
            raise RuntimeError("unexpected joint mapping")
        def state(rows):
            rows = np.asarray(rows).reshape(-1,6)
            return JointState.from_position(torch.tensor(rows[:,[ARM_NAMES.index(n) for n in names]],
                device="cuda:0", dtype=torch.float32).contiguous(), joint_names=names)
        def clearance(rows):
            # Independent sphere-to-AABB distances, all enabled model spheres.
            lowest = float("inf")
            for begin in range(0, len(rows), 128):
                geometry = planner.compute_kinematics(state(rows[begin:begin+128])).robot_spheres
                s = geometry.detach().cpu().numpy().reshape(-1,4)
                s = s[s[:,3] > 0]
                for box in scene["cuboid"].values():
                    d = np.abs(s[:,:3]-np.asarray(box["pose"][:3]))-np.asarray(box["dims"])/2
                    signed = np.linalg.norm(np.maximum(d,0),axis=1)+np.minimum(np.max(d,axis=1),0)-s[:,3]
                    lowest = min(lowest, float(signed.min()))
            return lowest
        baseline = np.linspace(start,goal,101)
        baseline_clearance = clearance(baseline)
        if min(clearance([start]),clearance([goal])) <= 0 or (not reset and baseline_clearance >= 0):
            attempts.append(dict(delta_deg=delta_deg, reason="invalid demonstration endpoints/baseline"))
            continue
        result = planner.plan_cspace(state(goal),state(start),max_attempts=5)
        if result is None or not bool(torch.all(result.success).item()):
            attempts.append(dict(delta_deg=delta_deg,reason="cuRobo failed"))
            print(attempts[-1],flush=True)
            continue
        plan = result.get_interpolated_plan()
        raw = plan.position.detach().cpu().numpy().reshape(-1,6)
        output_names = list(plan.joint_names)
        if len(output_names) != 6 or set(output_names) != set(ARM_NAMES):
            raise RuntimeError("invalid output joint mapping")
        points = raw[:,[output_names.index(n) for n in ARM_NAMES]]
        if not np.isfinite(points).all() or max(np.max(np.abs(points[0]-start)),np.max(np.abs(points[-1]-goal))) > 1e-4:
            raise RuntimeError("planner endpoint mismatch; no correction appended")
        tcp = np.asarray([fk(q)[0] for q in points])
        length = float(np.linalg.norm(np.diff(tcp,axis=0),axis=1).sum())
        # Oversample ONLY for validation, never replace planner positions.
        dense = np.concatenate([a+(b-a)*np.arange(4)[:,None]/4 for a,b in zip(points,points[1:])] + [points[-1:]])
        gap = clearance(dense)
        attempt = dict(delta_deg=delta_deg,tcp_length_m=length,min_clearance_m=gap)
        attempts.append(attempt); print(attempt,flush=True)
        lo,hi = request["tcp_length_range_m"]
        if not lo <= length <= hi or gap < 0.002:
            continue
        # Native servo consumes 80 ms samples. Preserve cuRobo geometry and
        # resample its piecewise-linear path in time at a slow uniform period.
        # This is NOT a fallback planner; revalidate the resampled path below.
        desired_dt=slow_sample_period(points.tolist(),max_velocity=.8,max_acceleration=1.5)
        times=np.arange(len(points))*desired_dt
        sample_count,legacy_duration=sample_count_at_scale(len(points),desired_dt,speed_scale)
        native_times=np.linspace(0,times[-1],sample_count)
        points=np.stack([np.interp(native_times,times,points[:,j]) for j in range(6)],axis=1)
        dt=SAMPLE_PERIOD_S
        summary = summarize(points.tolist(),dt)
        if max(summary["max_excursion_deg"])>(RESET_MAX_EXCURSION_DEG if reset else 20) or max(summary["peak_velocity_deg_s"])>speed_scale or max(summary["peak_acceleration_deg_s2"])>MAX_JOINT_ACCEL_DEG_S2 or summary["duration_s"]>(RESET_MAX_DURATION_S if reset else 115):
            attempts[-1].update(rejected="native motion envelope",summary=summary)
            continue
        dense=np.concatenate([a+(b-a)*np.arange(4)[:,None]/4 for a,b in zip(points,points[1:])] + [points[-1:]])
        gap=clearance(dense)
        if gap<.005: continue
        tcp=np.asarray([fk(q)[0] for q in points])
        if np.linalg.norm(np.diff(tcp,axis=0),axis=1).max()/dt>.02*speed_scale:
            attempts[-1]["rejected"]="TCP speed envelope"
            continue
        links=np.asarray([fk(q)[1] for q in points])
        world_links=(np.concatenate([links,np.ones((*links.shape[:2],1))],axis=2) @ body.T)[:,:,:3]
        obstacle_corners=np.asarray([midpoint+dims/2*np.array([1 if i&(1<<j) else -1 for j in range(3)]) for i in range(8)])
        world_obstacle=(np.c_[obstacle_corners,np.ones(8)] @ body.T)[:,:3]
        # Keep all modeled joint/TCP points on the right side and well above
        # the AGV, with a radius allowance. Left pose is not queried.
        workspace_bad=bool(world_links[:,:,1].max()>-.07 or world_links[:,:,2].min()<.8)
        if workspace_bad:
            attempts[-1].update(rejected="right workspace separation",max_world_y_m=float(world_links[:,:,1].max()),min_world_z_m=float(world_links[:,:,2].min()))
            continue
        length=float(np.linalg.norm(np.diff(tcp,axis=0),axis=1).sum())
        if not lo<=length<=hi: continue
        data = dict(schema_version=1,planner="curobo-v2-virtual-obstacle-demo",arm="right",
            joint_names=ARM_NAMES,sample_period_s=dt,points=points.tolist(),
            collision_checked=False,execution_scope="supervised_right_empty_workspace",
            robot_model_revision=hashlib.sha256(robot_path.read_bytes()+urdf_path.read_bytes()).hexdigest(),
            world_revision=request["scene_snapshot"]["digest"],tool_revision="LIVE_TOOL_PLUS_VIRTUAL_TUBE",
            attached_object_revision="none",source_commit=manifest["commit"],
            intent=request.get("intent","demo20"),reference_id=request["reference_id"],scene_digest=request["scene_snapshot"]["digest"],
            simulation_only=bool(request.get("simulation_only",False)),
            speed_scale=speed_scale,legacy_duration_s=legacy_duration,
            summary=summary,planning_time_s=time.monotonic()-started,
            backend_version=str(curobo.__version__),gpu=torch.cuda.get_device_name(0),
            demo=dict(tcp_path_m=tcp.tolist(),link_points_m=links.tolist(),world_link_points_m=world_links.tolist(),world_obstacle_corners_m=[] if reset else world_obstacle.tolist(),
                baseline_tcp_m=[fk(q)[0].tolist() for q in baseline],
                obstacle=scene["cuboid"]["virtual_block"],frame="URDF base_link (not body/world)",
                tcp_length_m=length,tcp_chord_m=float(np.linalg.norm(tcp[-1]-tcp[0])),
                min_model_clearance_m=gap,baseline_min_clearance_m=baseline_clearance,
                validation_sample_count=len(dense),tool_proxy_radius_m=request["tool_proxy_radius_m"],
                simulation_collision_checked=True,attempts=attempts),
            warning="Virtual obstacle/model checks only; physical execution requires separately confirmed empty right workspace and native gates")
        Path(sys.argv[2]).write_text(json.dumps(data,indent=2),encoding="utf-8")
        print(json.dumps(data["demo"]["attempts"]),flush=True)
        return
    raise RuntimeError("no cuRobo path passed requested length and clearance gates: %r" % attempts)


if __name__ == "__main__":
    main()
