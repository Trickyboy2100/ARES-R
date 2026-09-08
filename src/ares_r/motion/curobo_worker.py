"""GPU worker: no SDK import, sockets, or hardware execution API."""

import hashlib
import json
from pathlib import Path
import sys
import time

from .curobo import ARM_NAMES, MODEL_NAMES, finite_joints, slow_sample_period, summarize
from ..timing import emit_timing, timestamp


def main():
    process_started = time.monotonic_ns()
    request = json.loads(Path(sys.argv[1]).read_text())
    run_id = request.get("run_id", "curobo-worker")
    parameters = request["planning_parameters"]
    phases = []
    def phase(name, status="completed", started=None, **data):
        event = emit_timing(run_id, name, status, started, **data)
        phases.append(event)
        return event
    phase("worker_process", "started", process_started)
    started = time.monotonic_ns()
    import torch
    import curobo
    from curobo.motion_planner import MotionPlanner, MotionPlannerCfg
    from curobo.types import JointState
    phase("cuda_python_imports", started=started)
    started = time.monotonic_ns()
    source = Path(curobo.__file__).resolve().parent.parent
    manifest = json.loads((source / "ARES_R_SOURCE_MANIFEST.json").read_text())
    if manifest["commit"] != request["expected_commit"]:
        raise RuntimeError("cuRobo source revision differs from audited revision")
    for item in manifest["files"]:
        data = (source / item["path"]).read_bytes()
        if hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest() != item["sha"]:
            raise RuntimeError("cuRobo source modified: %s" % item["path"])
    phase("source_manifest_sha1", started=started, file_count=len(manifest["files"]))
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable; CPU/interpolation fallback is forbidden")
    robot_path = Path(request["robot_yaml"])
    started = time.monotonic_ns()
    config = MotionPlannerCfg.create(
        robot=str(robot_path), interpolation_dt=parameters["interpolation_dt"],
        interpolation_buffer_size=parameters["interpolation_buffer_size"],
        num_trajopt_seeds=parameters["num_trajopt_seeds"],
        num_ik_seeds=parameters["num_ik_seeds"],
        use_cuda_graph=parameters["use_cuda_graph"],
        self_collision_check=parameters["self_collision_check"],
        random_seed=parameters["random_seed"],
        optimizer_collision_activation_distance=parameters["optimizer_collision_activation_distance"])
    phase("planner_config_create", started=started)
    started = time.monotonic_ns()
    planner = MotionPlanner(config)
    phase("planner_initialize", started=started)
    names = list(planner.joint_names)
    if set(names) != set(MODEL_NAMES) or len(names) != 6:
        raise RuntimeError("model must have exactly six explicitly mapped arm joints: %r" % names)
    def state(values):
        values = finite_joints(values)
        row = [values[MODEL_NAMES.index(n)] for n in names]
        return JointState.from_position(torch.tensor([row], device="cuda:0", dtype=torch.float32), joint_names=names)
    planning_started = time.monotonic_ns()
    phase("plan_cspace", "started", planning_started)
    result = planner.plan_cspace(
        state(request["goal_rad"]), state(request["start_rad"]),
        max_attempts=parameters["max_attempts"],
        enable_graph_attempt=parameters["enable_graph_attempt"])
    phase("plan_cspace", started=planning_started,
          result_total_time_s=float(getattr(result, "total_time", 0.0)),
          result_solve_time_s=float(getattr(result, "solve_time", 0.0)))
    if result is None or not bool(torch.all(result.success).item()):
        raise RuntimeError("cuRobo plan_cspace failed; no fallback allowed")
    plan = result.get_interpolated_plan()
    raw = plan.position.detach().cpu()
    while raw.ndim > 2 and raw.shape[0] == 1:
        raw = raw[0]
    if raw.ndim != 2 or raw.shape[1] != 6:
        raise RuntimeError("ambiguous plan dimensions: %r" % (tuple(raw.shape),))
    output_names = list(plan.joint_names)
    if len(output_names) != 6 or set(output_names) != set(MODEL_NAMES):
        raise RuntimeError("interpolated joint order unavailable")
    points = [[row[output_names.index(n)] for n in MODEL_NAMES] for row in raw.tolist()]
    for label, actual in (("start_rad", points[0]), ("goal_rad", points[-1])):
        if max(abs(a - b) for a, b in zip(actual, request[label])) > 1e-4:
            raise RuntimeError("planner endpoint mismatch: %s; no appended correction allowed" % label)
    started = time.monotonic_ns()
    dt = max(0.08, slow_sample_period(points, parameters["interpolation_dt"]))
    summary = summarize(points, dt)
    if max(summary["max_excursion_deg"]) > 0.5 + 1e-3 or summary["duration_s"] > 60:
        raise RuntimeError("planned path leaves micro-demo envelope or exceeds 60 seconds")
    import yaml
    robot_config = yaml.safe_load(robot_path.read_text())
    urdf_path = Path(robot_config["kinematics"]["urdf_path"])
    revision = hashlib.sha256(robot_path.read_bytes() + urdf_path.read_bytes()).hexdigest()
    phase("trajectory_validate_resample", started=started, point_count=len(points), sample_period_s=dt)
    output = {"schema_version": 1, "planner": "curobo-v2-plan_cspace", "arm": "right",
              "joint_names": ARM_NAMES, "sample_period_s": dt, "points": points,
              "collision_checked": False, "robot_model_revision": revision,
              "world_revision": "UNCOMMISSIONED_EMPTY_WORLD",
              "tool_revision": "UNCOMMISSIONED", "attached_object_revision": "none",
              "summary": summary, "planning_time_s": (time.monotonic_ns() - planning_started) / 1e9,
              "backend_version": str(getattr(curobo, "__version__", "unknown")),
              "source_commit": manifest["commit"],
              "torch_version": torch.__version__, "gpu": torch.cuda.get_device_name(0),
              "warning": "Planner model checks are not site collision certification. Preview only.",
              "timing": {"worker": phases, "parameters": parameters,
                         "completed": timestamp(process_started)}}
    started = time.monotonic_ns()
    Path(sys.argv[2]).write_text(json.dumps(output, indent=2), encoding="utf-8")
    phase("trajectory_write", started=started, bytes=Path(sys.argv[2]).stat().st_size)
    phase("worker_process", "completed", process_started)
    output["timing"]["worker"] = phases
    output["timing"]["completed"] = timestamp(process_started)
    Path(sys.argv[2]).write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        try:
            failed_request = json.loads(Path(sys.argv[1]).read_text())
            emit_timing(failed_request.get("run_id", "curobo-worker"), "worker_process", "failed",
                        error=type(exc).__name__, message=str(exc))
        finally:
            raise
