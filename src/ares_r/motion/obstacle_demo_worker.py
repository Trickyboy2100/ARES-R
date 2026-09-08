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
from ..timing import emit_timing,timestamp


def main():
    process_started=time.monotonic_ns()
    request = json.loads(Path(sys.argv[1]).read_text())
    run_id=request.get("run_id","unknown")
    phases=[]
    def phase(name,status="instant",started=None,**data):
        record=emit_timing(run_id,name,status,started,**data);phases.append(record);return record
    phase("worker_process","started",process_started,pid=__import__("os").getpid())
    imports_started=time.monotonic_ns()
    import numpy as np
    import torch
    import yaml
    import curobo
    from curobo.motion_planner import MotionPlanner, MotionPlannerCfg
    from curobo.types import JointState
    phase("cuda_python_imports","completed",imports_started)
    if request.get("planning_only") is not True or request["arm"] != "right":
        raise RuntimeError("virtual right-arm request required")
    speed_scale=float(request.get("speed_scale",SPEED_SCALE))
    if speed_scale not in SUPPORTED_SPEED_SCALES: raise RuntimeError("unsupported speed scale")
    parameters=request["planning_parameters"]
    phase("request_validation","completed",process_started,parameters=parameters)
    manifest_started=time.monotonic_ns();source = Path(curobo.__file__).resolve().parent.parent
    manifest = json.loads((source / "ARES_R_SOURCE_MANIFEST.json").read_text())
    if manifest["commit"] != request["expected_commit"]:
        raise RuntimeError("cuRobo source revision mismatch")
    for item in manifest["files"]:
        blob = (source / item["path"]).read_bytes()
        if hashlib.sha1(b"blob " + str(len(blob)).encode() + b"\0" + blob).hexdigest() != item["sha"]:
            raise RuntimeError("modified cuRobo source: " + item["path"])
    phase("source_manifest_sha1","completed",manifest_started,file_count=len(manifest["files"]))
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA required; no fallback")
    torch.manual_seed(parameters["random_seed"])
    model_started=time.monotonic_ns()
    robot_path = Path(request["robot_yaml"])
    robot = yaml.safe_load(robot_path.read_text())
    urdf_path = Path(robot["kinematics"]["urdf_path"])
    root = ET.parse(urdf_path).getroot()
    offset = np.asarray(request["tool_translation_m"])
    phase("model_urdf_load","completed",model_started)

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
                   for f in np.linspace(0,1,parameters["tool_proxy_spheres"]))
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

    def matrix_quaternion_wxyz(r):
        # Stable branch form; cuRobo cuboids use [w,x,y,z].
        w=math.sqrt(max(0,1+r[0,0]+r[1,1]+r[2,2]))/2
        x=math.copysign(math.sqrt(max(0,1+r[0,0]-r[1,1]-r[2,2]))/2,r[2,1]-r[1,2])
        yq=math.copysign(math.sqrt(max(0,1-r[0,0]+r[1,1]-r[2,2]))/2,r[0,2]-r[2,0])
        z=math.copysign(math.sqrt(max(0,1-r[0,0]-r[1,1]+r[2,2]))/2,r[1,0]-r[0,1])
        return [w,x,yq,z]

    # Model the forbidden BODY half-space as a large cuboid. Its near face is
    # exactly Y=-70 mm; the far faces sit outside the robot workspace.
    model_from_body=np.linalg.inv(body)
    # The planner collides link spheres, while the independent hard gate below
    # checks link-center Y<=-70 mm. Offset the face to -20 mm so typical 50 mm
    # model spheres drive their centers to the hard boundary without making the
    # current, already-clear endpoint invalid.
    center_body=np.array([0.,2.49,2.5,1.])
    center_model=(model_from_body@center_body)[:3]
    central_wall=dict(dims=[5.,5.02,5.],pose=center_model.tolist()+matrix_quaternion_wxyz(model_from_body[:3,:3]))
    predicted=correction @ np.r_[fk(start)[0],1]
    if np.linalg.norm(predicted[:3]-np.asarray(request["live_snapshot"]["tcp_mm_rad"][:3])/1000)>.003:
        raise RuntimeError("live TCP and planning FK differ by more than 3 mm")
    goals=[np.asarray(finite_joints(request["goal_rad"]))] if reset else [start+np.array([length/radius,0,0,0,0,0]) for length in parameters["demo_candidate_tcp_m"]]
    phase("planning_setup","completed",process_started,candidate_count=len(goals),reset=reset)
    for candidate_index,goal in enumerate(goals):
        candidate_started=time.monotonic_ns();phase("candidate","started",candidate_started,candidate_index=candidate_index)
        delta_deg=math.degrees(goal[0]-start[0])
        midpoint = fk((start+goal)/2)[0]
        dims = np.asarray(request["obstacle_dims_m"])
        scene = {"cuboid": scene_cuboids(request["scene_snapshot"])}
        if request.get("plan_central_wall",False):
            scene["cuboid"]["body_central_forbidden_halfspace"]=central_wall
        # A reset uses an empty/manual scene, not a newly invented obstacle
        # between nearby endpoints. The remote sentinel keeps the collision
        # backend initialized; it is not a claimed physical obstacle.
        if reset: midpoint=np.array([10.,10.,10.])
        scene["cuboid"]["virtual_block"]=dict(dims=dims.tolist(),pose=midpoint.tolist()+[1,0,0,0])
        config_started=time.monotonic_ns()
        cfg = MotionPlannerCfg.create(robot=robot,scene_model=scene,
            interpolation_dt=parameters["interpolation_dt"],interpolation_buffer_size=parameters["interpolation_buffer_size"],
            num_trajopt_seeds=parameters["num_trajopt_seeds"],num_ik_seeds=parameters["num_ik_seeds"],
            use_cuda_graph=parameters["use_cuda_graph"],self_collision_check=parameters["self_collision_check"],
            random_seed=parameters["random_seed"],optimizer_collision_activation_distance=parameters["optimizer_collision_activation_distance"])
        phase("planner_config_create","completed",config_started,candidate_index=candidate_index)
        planner_started=time.monotonic_ns()
        planner = MotionPlanner(cfg)
        phase("planner_initialize","completed",planner_started,candidate_index=candidate_index)
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
            batch=parameters["validation_batch_size"]
            for begin in range(0,len(rows),batch):
                geometry = planner.compute_kinematics(state(rows[begin:begin+batch])).robot_spheres
                s = geometry.detach().cpu().numpy().reshape(-1,4)
                s = s[s[:,3] > 0]
                for box in scene["cuboid"].values():
                    d = np.abs(s[:,:3]-np.asarray(box["pose"][:3]))-np.asarray(box["dims"])/2
                    signed = np.linalg.norm(np.maximum(d,0),axis=1)+np.minimum(np.max(d,axis=1),0)-s[:,3]
                    lowest = min(lowest, float(signed.min()))
            return lowest
        baseline_started=time.monotonic_ns();baseline = np.linspace(start,goal,101)
        baseline_clearance = clearance(baseline);start_clearance=clearance([start]);goal_clearance=clearance([goal])
        if min(start_clearance,goal_clearance) <= 0 or (not reset and baseline_clearance >= 0):
            attempts.append(dict(delta_deg=delta_deg, reason="invalid demonstration endpoints/baseline",
                start_clearance_m=start_clearance,goal_clearance_m=goal_clearance,baseline_clearance_m=baseline_clearance))
            phase("baseline_collision_validation","rejected",baseline_started,candidate_index=candidate_index)
            continue
        phase("baseline_collision_validation","completed",baseline_started,candidate_index=candidate_index)
        solve_started=time.monotonic_ns();phase("plan_cspace","started",solve_started,candidate_index=candidate_index)
        result = planner.plan_cspace(state(goal),state(start),max_attempts=parameters["max_attempts"],
                                     enable_graph_attempt=parameters["enable_graph_attempt"])
        phase("plan_cspace","completed",solve_started,candidate_index=candidate_index,
              curobo_total_time_s=float(result.total_time) if result is not None else None,
              curobo_solve_time_s=float(result.solve_time) if result is not None else None)
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
        validation_started=time.monotonic_ns();subsamples=parameters["validation_subsamples"]
        dense = np.concatenate([a+(b-a)*np.arange(subsamples)[:,None]/subsamples for a,b in zip(points,points[1:])] + [points[-1:]])
        gap = clearance(dense)
        attempt = dict(delta_deg=delta_deg,tcp_length_m=length,min_clearance_m=gap)
        attempts.append(attempt); print(attempt,flush=True)
        phase("raw_path_validation","completed",validation_started,candidate_index=candidate_index,dense_samples=len(dense))
        lo,hi = request["tcp_length_range_m"]
        if not lo <= length <= hi or gap < 0.002:
            continue
        # Native servo consumes 80 ms samples. Preserve cuRobo geometry and
        # resample its piecewise-linear path in time at a slow uniform period.
        # This is NOT a fallback planner; revalidate the resampled path below.
        resample_started=time.monotonic_ns();desired_dt=slow_sample_period(points.tolist(),max_velocity=.8,max_acceleration=1.5)
        times=np.arange(len(points))*desired_dt
        sample_count,legacy_duration=sample_count_at_scale(len(points),desired_dt,speed_scale)
        native_times=np.linspace(0,times[-1],sample_count)
        points=np.stack([np.interp(native_times,times,points[:,j]) for j in range(6)],axis=1)
        dt=SAMPLE_PERIOD_S
        summary = summarize(points.tolist(),dt)
        phase("servo_time_resample","completed",resample_started,candidate_index=candidate_index,output_points=len(points))
        if max(summary["max_excursion_deg"])>(RESET_MAX_EXCURSION_DEG if reset else 20) or max(summary["peak_velocity_deg_s"])>speed_scale or max(summary["peak_acceleration_deg_s2"])>MAX_JOINT_ACCEL_DEG_S2 or summary["duration_s"]>(RESET_MAX_DURATION_S if reset else 115):
            attempts[-1].update(rejected="native motion envelope",summary=summary)
            continue
        final_validation_started=time.monotonic_ns()
        dense=np.concatenate([a+(b-a)*np.arange(subsamples)[:,None]/subsamples for a,b in zip(points,points[1:])] + [points[-1:]])
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
            per_sample=world_links[:,:,1].max(axis=1);worst=int(np.argmax(per_sample))
            attempts[-1].update(rejected="right workspace separation",max_world_y_m=float(per_sample[worst]),
                worst_sample=worst,sample_count=len(points),start_max_world_y_m=float(per_sample[0]),
                end_max_world_y_m=float(per_sample[-1]),min_world_z_m=float(world_links[:,:,2].min()))
            continue
        length=float(np.linalg.norm(np.diff(tcp,axis=0),axis=1).sum())
        if not lo<=length<=hi: continue
        phase("final_geometry_validation","completed",final_validation_started,candidate_index=candidate_index,dense_samples=len(dense))
        data = dict(schema_version=1,planner="curobo-v2-virtual-obstacle-demo",arm="right",
            joint_names=ARM_NAMES,sample_period_s=dt,points=points.tolist(),
            collision_checked=False,execution_scope="supervised_right_empty_workspace",
            robot_model_revision=hashlib.sha256(robot_path.read_bytes()+urdf_path.read_bytes()).hexdigest(),
            world_revision=request["scene_snapshot"]["digest"],tool_revision="LIVE_TOOL_PLUS_VIRTUAL_TUBE",
            attached_object_revision="none",source_commit=manifest["commit"],
            intent=request.get("intent","demo20"),reference_id=request["reference_id"],scene_digest=request["scene_snapshot"]["digest"],
            target_kind=request.get("target_kind"),target_name=request.get("target_name"),
            simulation_only=bool(request.get("simulation_only",False)),
            speed_scale=speed_scale,legacy_duration_s=legacy_duration,
            summary=summary,planning_time_s=time.monotonic()-started,
            timing=dict(worker=phases,parameters=parameters,completed=timestamp(process_started)),
            backend_version=str(curobo.__version__),gpu=torch.cuda.get_device_name(0),
            demo=dict(tcp_path_m=tcp.tolist(),link_points_m=links.tolist(),world_link_points_m=world_links.tolist(),world_obstacle_corners_m=[] if reset else world_obstacle.tolist(),
                baseline_tcp_m=[fk(q)[0].tolist() for q in baseline],
                obstacle=scene["cuboid"]["virtual_block"],frame="URDF base_link (not body/world)",
                tcp_length_m=length,tcp_chord_m=float(np.linalg.norm(tcp[-1]-tcp[0])),
                min_model_clearance_m=gap,baseline_min_clearance_m=baseline_clearance,
                validation_sample_count=len(dense),tool_proxy_radius_m=request["tool_proxy_radius_m"],
                simulation_collision_checked=True,attempts=attempts),
            warning="Virtual obstacle/model checks only; physical execution requires separately confirmed empty right workspace and native gates")
        output_started=time.monotonic_ns();Path(sys.argv[2]).write_text(json.dumps(data,indent=2),encoding="utf-8")
        phase("trajectory_write","completed",output_started,candidate_index=candidate_index,bytes=Path(sys.argv[2]).stat().st_size)
        # Rewrite once to include the trajectory-write timing record itself.
        data["timing"]["worker"]=phases;data["timing"]["completed"]=timestamp(process_started)
        Path(sys.argv[2]).write_text(json.dumps(data,indent=2),encoding="utf-8")
        phase("worker_process","completed",process_started,candidate_index=candidate_index)
        data["timing"]["worker"]=phases;data["timing"]["completed"]=timestamp(process_started)
        Path(sys.argv[2]).write_text(json.dumps(data,indent=2),encoding="utf-8")
        print(json.dumps(data["demo"]["attempts"]),flush=True)
        return
    raise RuntimeError("no cuRobo path passed requested length and clearance gates: %r" % attempts)


if __name__ == "__main__":
    try: main()
    except Exception as exc:
        try:
            request=json.loads(Path(sys.argv[1]).read_text())
            emit_timing(request.get("run_id","unknown"),"worker_process","failed",error=type(exc).__name__,message=str(exc))
        finally: raise
