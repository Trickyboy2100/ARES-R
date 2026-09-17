"""GPU-only Cartesian-to-joint worker. Never imports a hardware adapter.

The pregrasp worker consumes a joint-space goal, because that goal was taught on
site. An Epic detection hands over a Cartesian pose instead, so this worker
bridges exactly that gap and nothing else: it solves IK for the requested tool
poses, ranks the solutions through the same gates the trajectory planner later
applies, and stops. No trajectory is produced here and no motion is ever sent.

The planner is built from the same robot model, scene and parameters as
``pregrasp_worker``, so a joint goal chosen here is directly acceptable to the
already-commissioned ``plan_cspace`` path.
"""

import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time

import numpy

from .curobo import ARM_NAMES, MODEL_NAMES, finite_joints
from .pregrasp_worker import (DEFAULT_MIN_BODY_Z_M, FORBIDDEN_HALF_WIDTH_M, SUPPORTED_ARMS,
                              central_margin, central_wall, chain_kinematics, cuboid_clearance,
                              joint_origins, rigid_transform)
from .scene import scene_cuboids
from .singularity import L_REF_M, evaluate, soft_limit_margin
from .trajectory import load_motion_limits
from ..timing import emit_timing, timestamp

#: The only tool frame the audited robot model exposes.
TOOL_FRAME = "link6"


def pose_vector_to_matrix(values):
    """4x4 transform from ``[x, y, z, roll, pitch, yaw]`` in metres and radians."""
    if len(values) != 6:
        raise ValueError("a pose needs six values, got %d" % len(values))
    if not all(math.isfinite(float(value)) for value in values):
        raise ValueError("a pose needs finite values")
    return rigid_transform([float(value) for value in values[:3]],
                           [float(value) for value in values[3:6]])


def tool_goal_matrix(target_matrix, correction, tool_offset_m):
    """Link6 goal in the planning frame for a TCP target given in the arm base frame.

    Three rigid steps, each of which has silently produced centimetres before:
    the arm base frame is not the model frame, and the model's tool frame is the
    flange, not the TCP.
    """
    inverse_correction = numpy.linalg.inv(numpy.asarray(correction, dtype=float).reshape(4, 4))
    target_model = inverse_correction @ numpy.asarray(target_matrix, dtype=float).reshape(4, 4)
    rotation = target_model[:3, :3]
    position = target_model[:3, 3] - rotation @ numpy.asarray(tool_offset_m, dtype=float)
    goal = numpy.eye(4)
    goal[:3, :3] = rotation
    goal[:3, 3] = position
    return goal


def main():
    process_started = time.monotonic_ns()
    request = json.loads(Path(sys.argv[1]).read_text())
    output_path = Path(sys.argv[2])
    run_id = request.get("run_id", "ik-worker")
    phases = []

    def phase(name, status="completed", started=None, **data):
        record = emit_timing(run_id, name, status, started, **data)
        phases.append(record)
        return record

    phase("worker_process", "started", process_started, pid=os.getpid())
    arm = request.get("arm")
    if arm not in SUPPORTED_ARMS:
        raise RuntimeError("arm must be left or right")
    if request.get("planning_only") is not True:
        raise RuntimeError("the IK worker is planning-only")

    started = time.monotonic_ns()
    import torch
    import yaml
    import curobo
    from curobo.motion_planner import MotionPlanner, MotionPlannerCfg
    from curobo.types import JointState, Pose
    from curobo.types import GoalToolPose
    phase("cuda_python_imports", started=started)

    started = time.monotonic_ns()
    source = Path(curobo.__file__).resolve().parent.parent
    manifest = json.loads((source / "ARES_R_SOURCE_MANIFEST.json").read_text())
    if manifest["commit"] != request["expected_commit"]:
        raise RuntimeError("cuRobo source revision differs from the audited revision")
    for item in manifest["files"]:
        blob = (source / item["path"]).read_bytes()
        if hashlib.sha1(b"blob " + str(len(blob)).encode() + b"\0" + blob).hexdigest() != item["sha"]:
            raise RuntimeError("cuRobo source modified: %s" % item["path"])
    phase("source_manifest_sha1", started=started, file_count=len(manifest["files"]))
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable; CPU/interpolation fallback is forbidden")

    parameters = request["planning_parameters"]
    torch.manual_seed(parameters["random_seed"])
    numpy.random.seed(parameters["random_seed"] % (2 ** 32))

    started = time.monotonic_ns()
    robot_path = Path(request["robot_yaml"])
    robot = yaml.safe_load(robot_path.read_text())
    urdf_path = Path(robot["kinematics"]["urdf_path"])
    origins = joint_origins(urdf_path)
    tool_offset_m = numpy.asarray([float(v) for v in request["tool_translation_m"]], dtype=float)
    correction = numpy.asarray(request["T_controller_model"], dtype=float).reshape(4, 4)
    body = rigid_transform(request["body_base_xyz_m"],
                           [0.0, 0.0, float(request["body_base_yaw_rad"])]) @ correction
    phase("model_urdf_load", started=started, arm=arm)

    start = numpy.asarray(finite_joints(request["start_rad"]), dtype=float)
    targets = request["targets"]
    if not targets:
        raise RuntimeError("no IK targets were requested")

    spheres = robot["kinematics"]["collision_spheres"]["link6"]
    spheres.extend(dict(center=(tool_offset_m * fraction).tolist(),
                        radius=float(request["tool_proxy_radius_m"]))
                   for fraction in numpy.linspace(0.0, 1.0, parameters["tool_proxy_spheres"]))

    model_from_body = numpy.linalg.inv(body)
    scene = {"cuboid": scene_cuboids(request["scene_snapshot"])}
    scene["cuboid"]["body_central_forbidden_halfspace"] = central_wall(model_from_body, arm)
    min_body_z_m = float(request.get("min_body_z_m", DEFAULT_MIN_BODY_Z_M))
    min_clearance_m = float(request.get("min_model_clearance_m", 0.005))

    started = time.monotonic_ns()
    config = MotionPlannerCfg.create(robot=robot, scene_model=scene,
        interpolation_dt=parameters["interpolation_dt"],
        interpolation_buffer_size=parameters["interpolation_buffer_size"],
        num_trajopt_seeds=parameters["num_trajopt_seeds"],
        num_ik_seeds=parameters["num_ik_seeds"],
        use_cuda_graph=parameters["use_cuda_graph"],
        self_collision_check=parameters["self_collision_check"],
        random_seed=parameters["random_seed"],
        optimizer_collision_activation_distance=parameters["optimizer_collision_activation_distance"])
    planner = MotionPlanner(config)
    phase("planner_initialize", started=started)

    names = list(planner.joint_names)
    if len(names) != 6 or set(names) != set(ARM_NAMES):
        raise RuntimeError("unexpected joint mapping: %r" % names)
    order = [ARM_NAMES.index(name) for name in names]
    if list(planner.tool_frames) != [TOOL_FRAME]:
        raise RuntimeError("unexpected tool frames: %r" % (planner.tool_frames,))

    def state(rows):
        rows = numpy.asarray(rows, dtype=float).reshape(-1, 6)
        return JointState.from_position(
            torch.tensor(rows[:, order], device="cuda:0", dtype=torch.float32).contiguous(),
            joint_names=names)

    def clearance(rows):
        """Independent sphere-to-cuboid clearance over the enabled model spheres."""
        rows = numpy.asarray(rows, dtype=float).reshape(-1, 6)
        lowest = float("inf")
        batch = parameters["validation_batch_size"]
        for begin in range(0, len(rows), batch):
            geometry = planner.compute_kinematics(state(rows[begin:begin + batch])).robot_spheres
            current = geometry.detach().cpu().numpy().reshape(-1, 4)
            current = current[current[:, 3] > 0]
            for box in scene["cuboid"].values():
                lowest = min(lowest, float(cuboid_clearance(current[:, :3], current[:, 3], box).min()))
        return lowest

    limits = load_motion_limits(Path(request["motion_limits_file"]))
    lower = [value + limits.soft_limit_margin_rad for value in limits.lower_rad]
    upper = [value - limits.soft_limit_margin_rad for value in limits.upper_rad]

    candidates = []
    for target in targets:
        label = str(target["label"])
        goal_matrix = tool_goal_matrix(pose_vector_to_matrix(target["pose_m_rad"]), correction,
                                       tool_offset_m)
        started = time.monotonic_ns()
        goal = GoalToolPose.from_poses(
            {TOOL_FRAME: Pose(position=torch.tensor(goal_matrix[None, :3, 3], device="cuda:0",
                                                    dtype=torch.float32),
                              rotation=torch.tensor(goal_matrix[None, :3, :3], device="cuda:0",
                                                    dtype=torch.float32))},
            ordered_tool_frames=[TOOL_FRAME], num_goalset=1)
        result = planner.ik_solver.solve_pose(goal, current_state=state(start[None, :]),
                                             return_seeds=int(request["return_seeds"]))
        phase("solve_ik:%s" % label, started=started,
              curobo_total_time_s=float(result.total_time),
              success_count=int(torch.count_nonzero(result.success).item()))
        success = result.success.detach().cpu().numpy().reshape(-1)
        solutions = result.solution.detach().cpu().numpy()
        solutions = numpy.asarray(solutions).reshape(-1, 6)[:, order]
        for index, joints in enumerate(solutions):
            if not bool(success[index]):
                continue
            candidates.append(_measure(label, joints, start, goal_matrix, origins, tool_offset_m,
                                       body, arm, clearance, lower, upper, min_body_z_m,
                                       min_clearance_m))

    if not candidates:
        raise RuntimeError("IK found no solution for any requested target")

    candidates.sort(key=lambda item: (not item["accepted"], item["joint_distance_from_start_rad"],
                                      item["tcp_position_error_m"]))
    accepted = [item for item in candidates if item["accepted"]]
    started = time.monotonic_ns()
    payload = dict(
        schema_version=1, planner="curobo-v2-ik", arm=arm, joint_names=MODEL_NAMES,
        run_id=run_id, source_commit=manifest["commit"], backend_version=str(curobo.__version__),
        torch_version=torch.__version__, gpu=torch.cuda.get_device_name(0),
        planning_only=True, start_rad=start.tolist(),
        return_seeds=int(request["return_seeds"]), target_count=len(targets),
        candidate_count=len(candidates), accepted_count=len(accepted),
        gates=dict(min_model_clearance_m=min_clearance_m, min_body_z_m=min_body_z_m,
                   soft_limit_margin_rad=limits.soft_limit_margin_rad,
                   central_forbidden_half_width_m=FORBIDDEN_HALF_WIDTH_M),
        candidates=candidates,
        recommended=[dict(target=item["target"], joints_rad=item["joints_rad"],
                          joint_distance_from_start_rad=item["joint_distance_from_start_rad"])
                     for item in accepted[:3]],
        timing=dict(worker=phases, parameters=parameters, completed=timestamp(process_started)),
        warning=("IK only. No trajectory was planned and no motion was sent. A chosen goal still "
                 "has to pass motion validate and the commissioned plan_cspace path."))
    phase("ik_worker", started=process_started, candidate_count=len(candidates))
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _measure(label, joints, start, goal_matrix, origins, tool_offset_m, body, arm, clearance,
             lower, upper, min_body_z_m, min_clearance_m):
    """Every gate the trajectory planner will later apply, applied here first."""
    joints = [float(value) for value in joints]
    if not all(math.isfinite(value) for value in joints):
        raise RuntimeError("the IK solver returned a non-finite joint vector")
    tcp, jacobian, links = chain_kinematics(numpy.asarray(joints)[None, :], origins, tool_offset_m)
    world_links = (numpy.concatenate([links, numpy.ones((*links.shape[:2], 1))], axis=2) @ body.T)[:, :, :3]
    margins = central_margin(world_links[:, :, 1], arm)
    singular = evaluate(joints, jacobian[0][:3], jacobian[0][3:], sample_index=0,
                        tcp_m=tcp[0], reference_length=L_REF_M)
    # The solver aims link6 while the camera pose describes the TCP, and both are
    # compared in the planning frame where the FK numbers already live.
    tcp_goal = goal_matrix[:3, 3] + goal_matrix[:3, :3] @ tool_offset_m
    position_error = float(numpy.linalg.norm(tcp[0] - tcp_goal))
    record = dict(
        target=label, joints_rad=joints,
        joint_distance_from_start_rad=float(numpy.max(numpy.abs(numpy.asarray(joints) - start))),
        joint_path_length_rad=float(numpy.abs(numpy.asarray(joints) - start).sum()),
        tcp_position_error_m=position_error,
        min_model_clearance_m=clearance(numpy.asarray(joints)[None, :]),
        min_central_margin_m=float(margins.min()),
        min_link_body_z_m=float(world_links[:, :, 2].min()),
        min_soft_limit_margin_rad=soft_limit_margin(joints, lower, upper),
        min_sigma_min_scaled=float(singular["sigma_min_scaled"]),
        max_condition_number_scaled=float(singular["condition_number_scaled"]),
        singularity_level=singular["level"],
    )
    reasons = []
    if record["min_model_clearance_m"] <= min_clearance_m:
        reasons.append("model clearance %.4f m is below the required margin" % record["min_model_clearance_m"])
    if record["min_central_margin_m"] <= 0.0:
        reasons.append("enters the 14 cm central slab (margin %.4f m)" % record["min_central_margin_m"])
    if record["min_link_body_z_m"] < min_body_z_m:
        reasons.append("drops below the BODY height gate %.3f m" % min_body_z_m)
    if record["min_soft_limit_margin_rad"] <= 0.0:
        reasons.append("has no soft-limit margin")
    record["rejections"] = reasons
    record["accepted"] = not reasons
    return record


if __name__ == "__main__":
    main()
