"""GPU-only P3 planner for one frozen production SceneSnapshot.

There is intentionally no execution entry point in this module.  CLEAR, AVOID
and BLOCK all consume the complete compiled world; BLOCK differs only because
its SceneSnapshot contains an explicitly labelled goal enclosure.
"""

import hashlib,json,math
from pathlib import Path
import sys,time,xml.etree.ElementTree as ET

ARM_NAMES=["joint%d"%i for i in range(1,7)]
_RUNTIME_CACHE={}
from ares_r.perception.robot_owned_filter import grid_spheres_local as grid_spheres
from ares_r.motion.ab_demo_state import classify_reference_corridor,validate_curobo_only_policy
from ares_r.motion.execution_tool_envelope import verify_execution_tool_envelope
from ares_r.motion.independent_path_validation import validate_dense_world
from ares_r.motion.tcp_orientation import (HORIZONTAL_FORWARD_R_BODY,validate_level_path,
                                           validate_path)


def transform(xyz,rpy):
    import numpy as np
    r,p,y=[float(x) for x in rpy];cr,sr=math.cos(r),math.sin(r);cp,sp=math.cos(p),math.sin(p);cy,sy=math.cos(y),math.sin(y)
    value=np.eye(4);value[:3,:3]=[[cy*cp,cy*sp*sr-sy*cr,cy*sp*cr+sy*sr],
        [sy*cp,sy*sp*sr+cy*cr,sy*sp*cr-cy*sr],[-sp,cp*sr,cp*cr]];value[:3,3]=xyz
    return value


def path_metrics(points):
    import numpy as np
    p=np.asarray(points,dtype=float)
    if len(p)<2:return {"path_length_m":0.,"endpoint_distance_m":0.,"length_ratio":None,"max_straight_line_deviation_m":None}
    length=float(np.linalg.norm(np.diff(p,axis=0),axis=1).sum());direct=float(np.linalg.norm(p[-1]-p[0]))
    t=np.linspace(0,1,len(p))[:,None];line=p[0]+t*(p[-1]-p[0]);deviation=float(np.linalg.norm(p-line,axis=1).max())
    return {"path_length_m":length,"endpoint_distance_m":direct,
            "length_ratio":length/direct if direct>1e-9 else None,"max_straight_line_deviation_m":deviation}


def bounded_validation_knots(points,max_joint_step_rad=.002):
    import numpy as np
    q=np.asarray(points,dtype=float);selected=[q[0]];last=q[0]
    for row in q[1:-1]:
        if float(np.max(np.abs(row-last)))>=max_joint_step_rad:
            selected.append(row);last=row
    if len(selected)==1 or not np.array_equal(selected[-1],q[-1]):selected.append(q[-1])
    return np.asarray(selected)


def main():
    request_at=time.perf_counter()
    request=json.loads(Path(sys.argv[1]).read_text());output=Path(sys.argv[2])
    if request.get("planning_only") is not True or request.get("execution_allowed") is not False:
        raise RuntimeError("P3 request must be planning-only and execution-blocked")
    if request.get("point_to_point_policy") is not None:
        validate_curobo_only_policy(request["point_to_point_policy"])
    scene=request["compiled_scene"]
    if scene.get("planning_scope")!="P3_PRODUCTION_PLANNING_ONLY" or scene.get("execution_allowed") is not False:
        raise RuntimeError("compiled P3 planning-only scene required")
    if scene["scene_snapshot_id"]!=request["scene_snapshot_id"] or scene["digest"]!=request["scene_digest"]:
        raise RuntimeError("stale/mismatched SceneSnapshot binding")
    imported=time.perf_counter()
    import numpy as np
    import torch,yaml,curobo
    from curobo.motion_planner import MotionPlanner,MotionPlannerCfg
    from curobo._src.cost.tool_pose_criteria import ToolPoseCriteria
    from curobo.types import GoalToolPose,JointState,Pose
    from curobo._src.geom.types import SceneCfg
    import_s=time.perf_counter()-imported
    if not torch.cuda.is_available():raise RuntimeError("CUDA required; no fallback")
    source=Path(curobo.__file__).resolve().parent.parent;manifest=json.loads((source/"ARES_R_SOURCE_MANIFEST.json").read_text())
    if manifest["commit"]!=request["expected_commit"]:raise RuntimeError("cuRobo revision mismatch")
    for item in manifest["files"]:
        blob=(source/item["path"]).read_bytes();sha=hashlib.sha1(b"blob "+str(len(blob)).encode()+b"\0"+blob).hexdigest()
        if sha!=item["sha"]:raise RuntimeError("modified cuRobo source: "+item["path"])
    robot_path=Path(request["robot_yaml"]);robot=yaml.safe_load(robot_path.read_text())
    collision_model=request["collision_model"]
    params=request["planning_parameters"]
    sphere_cell_m=float(params.get("active_sphere_cell_m",.035))
    if not .015 <= sphere_cell_m <= .060:
        raise ValueError("active sphere cell must be between 15 and 60 mm")
    spheres={link:grid_spheres(box,sphere_cell_m) for link,box in collision_model["arm_link_boxes"].items()}
    envelope=request.get("execution_tool_envelope")
    if envelope is not None:
        verify_execution_tool_envelope(envelope,collision_model,request["controller_tool_pose_mm_rad"])
        spheres["link6"].extend(grid_spheres(envelope["box"],sphere_cell_m))
    else:
        spheres["link6"].extend(grid_spheres(collision_model["gripper_max_envelope_link6"],sphere_cell_m))
    for link in robot["kinematics"]["collision_spheres"]:robot["kinematics"]["collision_spheres"][link]=spheres.get(link,[])
    active_revision="sha256:"+hashlib.sha256(json.dumps(spheres,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    urdf=ET.parse(robot["kinematics"]["urdf_path"]).getroot();origins=[]
    for name in ARM_NAMES:
        node=urdf.find("joint[@name='%s']"%name);origin=node.find("origin")
        origins.append(transform([float(x) for x in origin.get("xyz").split()],[float(x) for x in origin.get("rpy").split()]))
    tool=np.asarray(request["T_link6_tcp"],dtype=float)
    def fk(q):
        value=np.eye(4)
        for origin,angle in zip(origins,q):value=value@origin@transform([0,0,0],[0,0,float(angle)])
        return value@tool
    torch.manual_seed(params["random_seed"])
    orientation_lock=request.get("orientation_lock")
    signature_orientation=orientation_lock
    if orientation_lock is not None and orientation_lock.get("policy") in (
            "LEVEL_YAW_FREE_V1","LEVEL_YAW_TARGET_V1"):
        signature_orientation={key:value for key,value in orientation_lock.items()
            if key not in ("candidate_target_rotations","candidate_yaws_rad",
                           "final_yaw_target_rad")}
    static_signature=hashlib.sha256(json.dumps({"robot":robot,"spheres":spheres,
        "parameters":params,"orientation_lock":signature_orientation},sort_keys=True,
        separators=(",",":")).encode()).hexdigest()
    cuboids=dict(scene["cuboids"]);world_at=time.perf_counter()
    cached=_RUNTIME_CACHE.get(static_signature)
    if cached is None:
        cfg=MotionPlannerCfg.create(robot=robot,scene_model={"cuboid":cuboids},
            collision_cache={"cuboid":max(512,len(cuboids)+32)},interpolation_dt=params["interpolation_dt"],
            interpolation_buffer_size=params["interpolation_buffer_size"],num_trajopt_seeds=params["num_trajopt_seeds"],
            num_ik_seeds=params["num_ik_seeds"],use_cuda_graph=params["use_cuda_graph"],
            self_collision_check=True,random_seed=params["random_seed"],
            optimizer_collision_activation_distance=params["optimizer_collision_activation_distance"])
        planner=MotionPlanner(cfg);names=list(planner.joint_names)
        if orientation_lock is not None:
            policy=orientation_lock.get("policy")
            target_rotation=np.asarray(orientation_lock.get("target_R_body_tcp",
                orientation_lock.get("candidate_target_rotations",[np.eye(3)])[0]),dtype=float)
            if (policy not in ("BODY_FORWARD_HORIZONTAL_V1", "FIXED_ROTATION_V1",
                               "LEVEL_YAW_FREE_V1", "LEVEL_YAW_TARGET_V1") or
                    target_rotation.shape!=(3,3) or
                    not np.allclose(target_rotation.T@target_rotation,np.eye(3),atol=1e-5) or
                    not np.isclose(np.linalg.det(target_rotation),1.0,atol=1e-5)):
                raise ValueError("unknown or invalid BODY TCP orientation contract")
            planner.update_tool_pose_criteria({"link6":ToolPoseCriteria.track_orientation(
                rpy=orientation_lock.get("criteria_rpy",[1.0,1.0,1.0]),non_terminal_scale=1.0)})
        cached={"planner":planner,"names":names,"warmup_done":False}
        _RUNTIME_CACHE[static_signature]=cached
        runtime_reused=False
    else:
        planner=cached["planner"];names=cached["names"];runtime_reused=True
    world_init_s=time.perf_counter()-world_at
    def state(rows):
        rows=np.asarray(rows,dtype=float).reshape(-1,6);ordered=rows[:,[ARM_NAMES.index(x) for x in names]]
        return JointState.from_position(torch.tensor(ordered,device="cuda:0",dtype=torch.float32).contiguous(),joint_names=names)
    def runtime_goal_candidates(start):
        runtime_goal=request.get("runtime_motion_goal")
        if runtime_goal is None:
            return [np.asarray(row,dtype=float) for row in
                    (request.get("goal_candidates_rad") or [request["goal_rad"]])],[]
        target_position=np.asarray(runtime_goal["position_m"],dtype=float)
        body_from_model=np.asarray(request["T_body_model"],dtype=float)
        model_from_body=np.linalg.inv(body_from_model)
        tcp_from_link6=np.asarray(request["T_link6_tcp"],dtype=float)
        candidates=[];metadata=[]
        for pose_index,item in enumerate(request.get("goal_candidate_metadata") or []):
            body_tcp=np.eye(4);body_tcp[:3,:3]=np.asarray(item["rotation"],dtype=float)
            body_tcp[:3,3]=target_position
            model_link6=model_from_body@body_tcp@np.linalg.inv(tcp_from_link6)
            goal_pose=GoalToolPose.from_poses({"link6":Pose(
                position=torch.tensor(model_link6[None,:3,3],device="cuda:0",dtype=torch.float32),
                rotation=torch.tensor(model_link6[None,:3,:3],device="cuda:0",dtype=torch.float32))},
                ordered_tool_frames=["link6"],num_goalset=1)
            solved=planner.ik_solver.solve_pose(goal_pose,current_state=state(start[None,:]),
                                                return_seeds=int(params["num_ik_seeds"]))
            mask=solved.success.detach().cpu().numpy().reshape(-1)
            rows=solved.solution.detach().cpu().numpy().reshape(-1,6)
            rows=rows[:,[names.index(name) for name in ARM_NAMES]]
            for solution_index,row in enumerate(rows):
                if not bool(mask[solution_index]):continue
                candidates.append(np.asarray(row,dtype=float))
                metadata.append(dict(item,pose_candidate_index=pose_index,
                    ik_solution_index=solution_index,
                    joint_distance_rad=float(np.linalg.norm(row-start)),
                    curobo_ik_total_time_s=float(solved.total_time)))
        if not candidates:
            raise RuntimeError("runtime BODY target is unreachable; no A/B fallback")
        order=sorted(range(len(candidates)),key=lambda index:metadata[index]["joint_distance_rad"])
        return [candidates[index] for index in order],[metadata[index] for index in order]
    def quaternion_rotation(q):
        w,x,y,z=[float(v) for v in q]
        return np.asarray([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                           [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                           [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
    def clearance_by_sample(rows):
        rows=np.asarray(rows,dtype=float).reshape(-1,6)
        current=planner.compute_kinematics(state(rows)).robot_spheres.detach().cpu().numpy()
        current=current.reshape(len(rows),-1,4)
        valid=current[0,:,3]>0
        current=current[:,valid,:];values={}
        for name,box in cuboids.items():
            rotation=quaternion_rotation(box["pose"][3:])
            local=(current[:,:,:3]-np.asarray(box["pose"][:3]))@rotation
            delta=np.abs(local)-np.asarray(box["dims"])/2
            signed=(np.linalg.norm(np.maximum(delta,0),axis=2)+
                    np.minimum(np.max(delta,axis=2),0)-current[:,:,3])
            values[name]=signed.min(axis=1)
        return values
    def clearance_details(rows):
        return {name:float(values.min()) for name,values in clearance_by_sample(rows).items()}
    def clearance_trace(rows):
        values=clearance_by_sample(rows)
        if not values:return [float("inf")]*len(rows)
        return np.min(np.stack(list(values.values()),axis=1),axis=1).tolist()
    def clearance(rows):
        values=clearance_details(rows)
        return min(values.values()) if values else float("inf")
    ab_demo=request.get("ab_demo")
    corridor=None
    if ab_demo is not None:
        validate_curobo_only_policy(ab_demo)
        if (ab_demo.get("motion_policy")!="CUROBO_ONLY_FOR_EVERY_POINT_TO_POINT_LEG"
                or ab_demo.get("TOOL_TCP_PHYSICAL_SEMANTICS_UNRESOLVED")!="YES"
                or request.get("execution_allowed") is not False):
            raise RuntimeError("P3.2 cuRobo-only planning and tool/TCP gate required")
        reference=np.asarray(ab_demo["reference_chord_joints_rad"],dtype=float)
        if reference.ndim!=2 or reference.shape[1]!=6 or len(reference)<21:
            raise ValueError("dense whole-arm reference corridor required")
        reference_dense=np.concatenate([a+(b-a)*np.arange(4)[:,None]/4
            for a,b in zip(reference,reference[1:])]+[reference[-1:]])
        gaps=clearance_details(reference_dense)
        classification,hit_ids=classify_reference_corridor(
            gaps,clearance([reference[0],reference[-1]]))
        corridor={"classification":classification,"whole_arm_gripper_checked":True,
                  "reference_only_never_executed":True,"min_gap_by_object_m":gaps,
                  "blocking_object_ids":hit_ids,
                  "observed_blocking_object_ids":[name for name in hit_ids if name.startswith("observed_")]}
        if classification=="SCENE_INVALID":
            print(json.dumps({"corridor_diagnostic":corridor,
                "start_min_gap_m":clearance([reference[0]]),
                "goal_min_gap_m":clearance([reference[-1]]),
                "start_nearest":sorted(clearance_details([reference[0]]).items(),key=lambda x:x[1])[:6],
                "goal_nearest":sorted(clearance_details([reference[-1]]).items(),key=lambda x:x[1])[:6]}),flush=True)
            raise RuntimeError("A/B endpoint or scene invalid; no planning fallback")
    # Explicit world update is separately timed from planner initialization.
    typed=SceneCfg.create({"cuboid":cuboids});planner.update_world(typed);torch.cuda.synchronize()
    updates=[]
    for _ in range(int(request.get("benchmark_runs",3))):
        at=time.perf_counter();planner.update_world(typed);torch.cuda.synchronize();updates.append(time.perf_counter()-at)
    start=np.asarray(request["start_rad"],dtype=float)
    goal_candidates,resolved_goal_metadata=runtime_goal_candidates(start)
    def solve_segment(begin,end):
        return planner.plan_cspace(state(end),state(begin),max_attempts=params["max_attempts"],
                                   enable_graph_attempt=params["enable_graph_attempt"])
    def solve(goal_value):
        at=time.perf_counter()
        try:
            value=solve_segment(start,goal_value)
            torch.cuda.synchronize();return [value],time.perf_counter()-at,None
        except Exception as exc:  # BLOCK may be rejected before an ordinary result is allocated.
            return None,time.perf_counter()-at,"%s: %s"%(type(exc).__name__,exc)
    warmup_s=0.0
    warmup_policy=request.get("warmup_policy","ONCE_PER_RUNTIME")
    if warmup_policy not in ("ONCE_PER_RUNTIME","NONE"):
        raise ValueError("unknown planner warmup policy")
    if warmup_policy=="NONE":
        cached["warmup_done"]=True
    if not cached["warmup_done"]:
        _,warmup_s,_=solve(goal_candidates[0])
        cached["warmup_done"]=True
    samples=[];errors=[];result=None;selected_goal_index=None
    for candidate_index,candidate_goal in enumerate(goal_candidates):
        for _ in range(int(request.get("benchmark_runs",3))):
            result,elapsed,error=solve(candidate_goal);samples.append(elapsed)
            if error:errors.append(error)
        if result is not None and all(bool(torch.all(part.success).item()) for part in result):
            selected_goal_index=candidate_index;break
    goal=goal_candidates[selected_goal_index if selected_goal_index is not None else 0]
    baseline=np.linspace(start,goal,101);start_details=clearance_details([start]);goal_details=clearance_details([goal])
    start_gap=min(start_details.values());goal_gap=min(goal_details.values());baseline_gap=clearance(baseline)
    success=result is not None and all(bool(torch.all(part.success).item()) for part in result);points=[];tcp_body=[];path_gap=None
    path_details={}
    central_margin=None
    smoothness=None
    independent=None
    planner_clearance_trace=[]
    independent_validation_s=0.0
    orientation_validation=None
    goal_position_error_m=None
    postprocess_at=time.perf_counter()
    if success:
        segments=[]
        for segment_index,part in enumerate(result):
            plan=part.get_interpolated_plan();raw=plan.position.detach().cpu().numpy().reshape(-1,6)
            order=list(plan.joint_names);row=raw[:,[order.index(x) for x in ARM_NAMES]]
            segments.append(row if segment_index==0 else row[1:])
        q=np.concatenate(segments);points=q.tolist();T=np.asarray(request["T_body_model"])
        tcp=np.asarray([(T@fk(row))[:3,3] for row in q]);tcp_body=tcp.tolist()
        runtime_goal=request.get("runtime_motion_goal")
        if runtime_goal is not None:
            goal_position_error_m=float(np.linalg.norm(
                tcp[-1]-np.asarray(runtime_goal["position_m"],dtype=float)))
        central_margin=float((-tcp[:,1]-.07).min() if request["active_arm"]=="right"
                             else (tcp[:,1]-.07).min())
        dt=float(params["interpolation_dt"])
        v=np.diff(q,axis=0)/dt;a=np.diff(v,axis=0)/dt;j=np.diff(a,axis=0)/dt
        max_step=float(np.max(np.abs(np.diff(q,axis=0))))
        max_v=float(np.max(np.abs(v)))
        max_a=float(np.max(np.abs(a))) if len(a) else 0.0
        max_j=float(np.max(np.abs(j))) if len(j) else 0.0
        slow_scale=max(1.0,max_v/.35,math.sqrt(max_a/1.0),(max_j/10.0)**(1.0/3.0))
        smoothness={"sample_period_s":dt,"max_joint_step_rad":max_step,
            "max_joint_speed_rad_s":max_v,"max_joint_accel_rad_s2":max_a,
            "max_joint_jerk_rad_s3":max_j,
            "recommended_offline_time_scale_for_smooth_preview":slow_scale,
            "time_scaled_speed_bound_rad_s":max_v/slow_scale,
            "time_scaled_accel_bound_rad_s2":max_a/slow_scale**2,
            "time_scaled_jerk_bound_rad_s3":max_j/slow_scale**3,
            "physical_execution_commissioned":False}
        validation_knots=bounded_validation_knots(q)
        dense=np.concatenate([a+(b-a)*np.arange(2)[:,None]/2
                              for a,b in zip(validation_knots,validation_knots[1:])]+[validation_knots[-1:]])
        path_details=clearance_details(dense)
        planner_clearance_trace=clearance_trace(dense)
        path_gap=min(path_details.values()) if path_details else float("inf")
        if (central_margin<=0 or path_gap<=0 or not np.isfinite(q).all() or max_step>.15 or
                (runtime_goal is not None and goal_position_error_m>
                 float(runtime_goal["position_tolerance_m"]))):
            success=False;points=[];tcp_body=[];path_gap=None;path_details={}
        elif envelope is not None:
            validation_at=time.perf_counter()
            independent=validate_dense_world(points,request,subdivisions=2)
            independent_validation_s=time.perf_counter()-validation_at
            if not independent["collision_free"]:
                success=False
        if success and orientation_lock is not None:
            if orientation_lock["policy"] in ("LEVEL_YAW_FREE_V1","LEVEL_YAW_TARGET_V1"):
                orientation_validation=validate_level_path(
                    lambda row:T@fk(row),q,subdivisions=4,
                    tolerance_deg=float(orientation_lock["max_error_deg"]),
                    final_yaw_rad=orientation_lock.get("final_yaw_target_rad"))
            else:
                orientation_validation=validate_path(
                    lambda row:T@fk(row),q,subdivisions=4,
                    tolerance_deg=float(orientation_lock["max_error_deg"]),
                    target_rotation=orientation_lock["target_R_body_tcp"])
            if not orientation_validation["passed"]:
                success=False
    mode=request["mode"];expected="FAILURE" if mode=="BLOCK" else "SUCCESS";observed="SUCCESS" if success else "FAILURE"
    payload={"schema_version":3,"planner":"cuRobo","mode":mode,"planning_only":True,"execution_allowed":False,
        "expected_result":expected,"observed_result":observed,"expectation_met":expected==observed,
        "scene_snapshot_id":scene["scene_snapshot_id"],"scene_digest":scene["digest"],
        "planning_context_digest":scene["planning_context_digest"],"calibration_revision":scene["calibration_revision"],
        "geometry_revision":request["geometry_revision"],"inactive_arm_revision":request["inactive_arm_revision"],
        "active_collision_revision":active_revision,"active_collision_sphere_count":sum(map(len,spheres.values())),
        "execution_tool_envelope_revision":envelope["revision"] if envelope else None,
        "active_collision_sphere_cell_m":sphere_cell_m,
        "world_cuboid_ids":list(cuboids),"start_rad":start.tolist(),"goal_rad":goal.tolist(),
        "selected_goal_candidate_index":selected_goal_index,
        "selected_goal_candidate_metadata":(
            resolved_goal_metadata[selected_goal_index]
            if selected_goal_index is not None and resolved_goal_metadata else None),
        "runtime_motion_goal":request.get("runtime_motion_goal"),
        "goal_position_error_m":goal_position_error_m,
        "trajectory_points_rad":points,"tcp_path_body_m":tcp_body,"path_metrics":path_metrics(tcp_body),
        "clearance_m":{"start":start_gap,"goal":goal_gap,"joint_linear_baseline":baseline_gap,"planned_path":path_gap},
        "path_clearance_by_object_m":path_details,
        "planner_clearance_trace_m":planner_clearance_trace,
        "path_limiting_object_id":min(path_details,key=path_details.get) if path_details else None,
        "central_tcp_margin_m":central_margin,
        "dense_post_validation_samples":len(dense) if success else None,
        "orientation_validation":orientation_validation,
        "smoothness":smoothness,
        "independent_dense_validation":independent,
        "endpoint_clearance_by_object_m":{"start":start_details,"goal":goal_details},
        "timing_s":{"cuda_import":import_s,"curobo_world_and_planner_init":world_init_s,
                    "persistent_runtime_reused":runtime_reused,
                    "one_time_warmup_s":warmup_s,
                    "world_update_samples":updates,"planning_samples":samples,
                    "planning_errors":errors,
                    "independent_dense_validation":independent_validation_s,
                    "planning_reported_total":sum(float(x.total_time) for x in result) if result else None,
                    "planning_reported_solve":sum(float(x.solve_time) for x in result) if result else None},
        "gpu":torch.cuda.get_device_name(0),"curobo_version":str(curobo.__version__),"source_commit":manifest["commit"]}
    if request.get("motion_contract"):
        payload["motion_contract"]=request["motion_contract"]
        payload["planner_clearance_policy"]=request.get("planner_clearance_policy")
        payload["motion_constraints"]=request.get("motion_constraints")
    if request.get("point_to_point_policy") is not None:
        payload["point_to_point_policy"]=request["point_to_point_policy"]
    if request.get("TOOL_TCP_PHYSICAL_SEMANTICS_UNRESOLVED"):
        payload["TOOL_TCP_PHYSICAL_SEMANTICS_UNRESOLVED"]=request["TOOL_TCP_PHYSICAL_SEMANTICS_UNRESOLVED"]
        payload["READY_FOR_FIRST_SUPERVISED_CLEAR_EXECUTION"]="NO"
    if ab_demo is not None:
        payload["ab_demo"]={"motion_policy":ab_demo["motion_policy"],
            "TOOL_TCP_PHYSICAL_SEMANTICS_UNRESOLVED":"YES",
            "READY_FOR_FIRST_SUPERVISED_CLEAR_EXECUTION":"NO",
            "planner_mode":ab_demo["planner_mode"],"corridor":corridor,
            "explicit_waypoints":[],"smoothness":smoothness,
            "max_tcp_z_m":(float(np.max(np.asarray(tcp_body)[:,2])) if tcp_body else None),
            "arc_height_above_endpoints_m":(float(np.max(np.asarray(tcp_body)[:,2])-
                max(tcp_body[0][2],tcp_body[-1][2])) if tcp_body else None)}
    payload["timing_s"]["postprocess_and_validation"]=time.perf_counter()-postprocess_at
    payload["timing_s"]["request_wall_before_serialization"]=time.perf_counter()-request_at
    serialization_at=time.perf_counter();encoded=json.dumps(payload,indent=2)+"\n"
    payload["timing_s"]["serialization"]=time.perf_counter()-serialization_at
    payload["timing_s"]["request_to_result_wall"]=time.perf_counter()-request_at
    output.write_text(json.dumps(payload,indent=2)+"\n")
    print(json.dumps({"mode":mode,"observed":observed,"expectation_met":payload["expectation_met"],
                      "minimum_clearance_m":path_gap,"planning_samples_s":samples}))
    if not payload["expectation_met"]:raise SystemExit(2)


if __name__=="__main__":main()
