"""CUDA planning-only worker for the pointcloud collision demo.

This module deliberately has no hardware imports and never exposes an
execution function.  Every request must be bound to a frozen SceneSnapshot.
"""

import hashlib
import json
import math
from pathlib import Path
import sys
import time
import xml.etree.ElementTree as ET


ARM_NAMES = ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6"]


def _transform(xyz, rpy):
    import numpy as np
    r, p, y = rpy
    cr, sr = math.cos(r), math.sin(r)
    cp, sp = math.cos(p), math.sin(p)
    cy, sy = math.cos(y), math.sin(y)
    out = np.eye(4)
    out[:3, :3] = [
        [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
        [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
        [-sp, cp * sr, cp * cr],
    ]
    out[:3, 3] = xyz
    return out


def main():
    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    output_path = Path(sys.argv[2])
    if request.get("planning_only") is not True or request.get("execution_allowed") is not False:
        raise RuntimeError("planning-only/execution-blocked request required")
    if request.get("planning_scope") != "DEMO_OFFLINE_ONLY":
        raise RuntimeError("DEMO_OFFLINE_ONLY scope required")
    scene = request["compiled_scene"]
    if scene.get("execution_allowed") is not False:
        raise RuntimeError("compiled scene must block execution")
    if scene["scene_snapshot_id"] != request["scene_snapshot_id"]:
        raise RuntimeError("snapshot binding mismatch")
    if scene["digest"] != request["scene_digest"]:
        raise RuntimeError("scene digest mismatch")

    imports_at = time.perf_counter()
    import numpy as np
    import torch
    import yaml
    import curobo
    from curobo.motion_planner import MotionPlanner, MotionPlannerCfg
    from curobo.types import JointState
    from curobo._src.geom.types import SceneCfg
    import_ms = (time.perf_counter() - imports_at) * 1000
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA required; CPU fallback forbidden")

    source = Path(curobo.__file__).resolve().parent.parent
    manifest = json.loads((source / "ARES_R_SOURCE_MANIFEST.json").read_text())
    if manifest["commit"] != request["expected_commit"]:
        raise RuntimeError("cuRobo revision mismatch")
    for item in manifest["files"]:
        blob = (source / item["path"]).read_bytes()
        git_sha = hashlib.sha1(b"blob " + str(len(blob)).encode() + b"\0" + blob).hexdigest()
        if git_sha != item["sha"]:
            raise RuntimeError("modified cuRobo source: " + item["path"])

    robot_path = Path(request["robot_yaml"])
    robot = yaml.safe_load(robot_path.read_text())
    urdf = ET.parse(robot["kinematics"]["urdf_path"]).getroot()
    origins = []
    for name in ARM_NAMES:
        joint = urdf.find("joint[@name='%s']" % name)
        origin = joint.find("origin")
        origins.append(_transform(
            [float(v) for v in origin.get("xyz").split()],
            [float(v) for v in origin.get("rpy").split()],
        ))
    tool_offset = np.asarray(request["tool_translation_m"], dtype=float)
    robot["kinematics"]["collision_spheres"]["link6"].extend(
        {"center": (tool_offset * fraction).tolist(), "radius": 0.025}
        for fraction in np.linspace(0, 1, 12)
    )

    def fk(q):
        transform = np.eye(4)
        for origin, value in zip(origins, q):
            transform = transform @ origin @ _transform([0, 0, 0], [0, 0, value])
        return transform[:3, :3] @ tool_offset + transform[:3, 3]

    start = np.asarray(request["start_rad"], dtype=float)
    goal = np.asarray(request["goal_rad"], dtype=float)
    midpoint = fk((start + goal) / 2)
    goal_tcp = fk(goal)
    mode = request["mode"]
    known = {
        key: value for key, value in scene["cuboids"].items()
        if key.startswith("known_support")
    }
    cuboids = dict(known)
    augmentation = None
    if mode == "AVOID":
        augmentation = {
            "id": "DEMO_OBSTACLE_AUGMENTATION",
            "role": "DEMO_OBSTACLE_AUGMENTATION",
            "source": "FREE joint-line TCP midpoint; layered over real Pixel Pro scene",
            "dims": request.get("avoid_dims_m", [0.025, 0.025, 0.025]),
            "pose": midpoint.tolist() + [1, 0, 0, 0],
        }
        cuboids[augmentation["id"]] = {"dims": augmentation["dims"], "pose": augmentation["pose"]}
    elif mode == "BLOCK":
        augmentation = {
            "id": "DEMO_BLOCK_GOAL",
            "role": "DEMO_OBSTACLE_AUGMENTATION",
            "source": "goal enclosure for expected planning failure",
            "dims": [0.10, 0.10, 0.10],
            "pose": goal_tcp.tolist() + [1, 0, 0, 0],
        }
        cuboids[augmentation["id"]] = {"dims": augmentation["dims"], "pose": augmentation["pose"]}
    elif mode != "FREE":
        raise RuntimeError("unknown mode")

    params = request["planning_parameters"]
    torch.manual_seed(params["random_seed"])
    world_at = time.perf_counter()
    cfg = MotionPlannerCfg.create(
        robot=robot,
        scene_model={"cuboid": cuboids},
        interpolation_dt=params["interpolation_dt"],
        interpolation_buffer_size=params["interpolation_buffer_size"],
        num_trajopt_seeds=params["num_trajopt_seeds"],
        num_ik_seeds=params["num_ik_seeds"],
        use_cuda_graph=params["use_cuda_graph"],
        self_collision_check=True,
        random_seed=params["random_seed"],
        optimizer_collision_activation_distance=params["optimizer_collision_activation_distance"],
    )
    planner = MotionPlanner(cfg)
    world_update_ms = (time.perf_counter() - world_at) * 1000
    names = list(planner.joint_names)

    def state(rows):
        rows = np.asarray(rows, dtype=float).reshape(-1, 6)
        ordered = rows[:, [ARM_NAMES.index(name) for name in names]]
        return JointState.from_position(
            torch.tensor(ordered, device="cuda:0", dtype=torch.float32).contiguous(),
            joint_names=names,
        )

    def clearance(rows):
        geometry = planner.compute_kinematics(state(rows)).robot_spheres.detach().cpu().numpy().reshape(-1, 4)
        geometry = geometry[geometry[:, 3] > 0]
        minimum = float("inf")
        for box in cuboids.values():
            delta = np.abs(geometry[:, :3] - np.asarray(box["pose"][:3])) - np.asarray(box["dims"]) / 2
            signed = np.linalg.norm(np.maximum(delta, 0), axis=1) + np.minimum(np.max(delta, axis=1), 0) - geometry[:, 3]
            minimum = min(minimum, float(signed.min()))
        return minimum

    benchmark_runs = int(request.get("benchmark_runs", 1))
    world_update_samples = []
    if benchmark_runs > 1:
        typed_scene = SceneCfg.create({"cuboid": cuboids})
        planner.update_world(typed_scene)  # warm-up
        for _ in range(benchmark_runs):
            updated_at = time.perf_counter()
            planner.update_world(typed_scene)
            torch.cuda.synchronize()
            world_update_samples.append((time.perf_counter() - updated_at) * 1000)

    baseline = np.linspace(start, goal, 101)
    collision_samples = []
    if benchmark_runs > 1:
        clearance([start]); clearance([goal]); clearance(baseline)
        torch.cuda.synchronize()
    for _ in range(benchmark_runs):
        collision_at = time.perf_counter()
        start_clearance = clearance([start])
        goal_clearance = clearance([goal])
        baseline_clearance = clearance(baseline)
        torch.cuda.synchronize()
        collision_samples.append((time.perf_counter() - collision_at) * 1000)
    collision_query_ms = collision_samples[-1]

    def solve_once():
        solved_at = time.perf_counter()
        value = planner.plan_cspace(
            state(goal), state(start), max_attempts=params["max_attempts"],
            enable_graph_attempt=params["enable_graph_attempt"],
        )
        torch.cuda.synchronize()
        return value, (time.perf_counter() - solved_at) * 1000

    if benchmark_runs > 1:
        solve_once()  # warm-up is intentionally excluded
    planning_samples = []
    result = None
    for _ in range(benchmark_runs):
        result, elapsed = solve_once()
        planning_samples.append(elapsed)
    planning_ms = planning_samples[-1]
    success = result is not None and bool(torch.all(result.success).item())
    points = []
    tcp_model = []
    tcp_body = []
    path_clearance = None
    if success:
        plan = result.get_interpolated_plan()
        raw = plan.position.detach().cpu().numpy().reshape(-1, 6)
        output_names = list(plan.joint_names)
        points_np = raw[:, [output_names.index(name) for name in ARM_NAMES]]
        points = points_np.tolist()
        tcp_model_np = np.asarray([fk(q) for q in points_np])
        tcp_model = tcp_model_np.tolist()
        t_body_model = np.asarray(request["T_body_model"], dtype=float)
        tcp_body = ((np.c_[tcp_model_np, np.ones(len(tcp_model_np))] @ t_body_model.T)[:, :3]).tolist()
        dense = np.concatenate([
            a + (b - a) * np.arange(4)[:, None] / 4 for a, b in zip(points_np, points_np[1:])
        ] + [points_np[-1:]])
        path_clearance = clearance(dense)

    expected = "SUCCESS" if mode in ("FREE", "AVOID") else "FAILURE"
    observed = "SUCCESS" if success else "FAILURE"
    if mode == "AVOID" and min(start_clearance, goal_clearance) <= 0:
        raise RuntimeError("AVOID augmentation intersects an endpoint")
    artifact = {
        "schema_version": 2,
        "planner": "cuRobo",
        "mode": mode,
        "planning_only": True,
        "execution_allowed": False,
        "planning_scope": "DEMO_OFFLINE_ONLY",
        "expected_result": expected,
        "observed_result": observed,
        "expectation_met": expected == observed,
        "scene_snapshot_id": scene["scene_snapshot_id"],
        "scene_digest": scene["digest"],
        "planning_context_digest": scene["planning_context_digest"],
        "calibration_candidate_revision": scene["calibration_revision"],
        "robot_model_revision": hashlib.sha256(robot_path.read_bytes()).hexdigest(),
        "tool_revision": "SDK222_SAVED_READ_ONLY_PLUS_25MM_PROXY",
        "start_rad": start.tolist(),
        "goal_rad": goal.tolist(),
        "augmentation": augmentation,
        "world_cuboid_ids": list(cuboids),
        "trajectory_points_rad": points,
        "tcp_path_model_m": tcp_model,
        "tcp_path_body_m": tcp_body,
        "clearance_m": {
            "start": start_clearance,
            "goal": goal_clearance,
            "joint_linear_baseline": baseline_clearance,
            "planned_path": path_clearance,
        },
        "timing_ms": {
            "cuda_import": import_ms,
            "curobo_world_and_planner_init": world_update_ms,
            "collision_query": collision_query_ms,
            "planning": planning_ms,
            "curobo_reported_total": float(result.total_time) * 1000 if result is not None else None,
            "curobo_reported_solve": float(result.solve_time) * 1000 if result is not None else None,
        },
        "benchmark": {
            "warmup_runs": 1 if benchmark_runs > 1 else 0,
            "measured_runs": benchmark_runs,
            "curobo_world_update_ms": world_update_samples,
            "collision_query_ms": collision_samples,
            "planning_ms": planning_samples,
        },
        "gpu": torch.cuda.get_device_name(0),
        "curobo_version": str(curobo.__version__),
        "source_commit": manifest["commit"],
    }
    output_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps({
        "mode": mode, "success": success, "expectation_met": artifact["expectation_met"],
        "planning_ms": planning_ms, "path_clearance_m": path_clearance,
        "start_clearance_m": start_clearance, "goal_clearance_m": goal_clearance,
    }))


if __name__ == "__main__":
    main()
