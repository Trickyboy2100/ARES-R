"""Isolated cuRobo planning and preview. This module never sends robot commands."""

import json
import math
import os
from pathlib import Path
import subprocess
import time
import uuid

CUROBO_COMMIT = "8e734f3ced1df898990bcd92de40abce475907db"
MODEL_NAMES = tuple("joint%d" % i for i in range(1, 7))
ARM_NAMES = MODEL_NAMES  # Existing ARES-R trajectory/limits contract; UI aliases are J1..J6.


def finite_joints(values):
    result = [float(v) for v in values]
    if len(result) != 6 or not all(math.isfinite(v) for v in result):
        raise ValueError("six finite joint angles in radians required")
    return result


def summarize(points, dt):
    if not math.isfinite(dt) or dt <= 0 or len(points) < 2:
        raise ValueError("trajectory requires positive finite timing and at least two points")
    points = [finite_joints(p) for p in points]
    velocities = [[(b[j] - a[j]) / dt for j in range(6)] for a, b in zip(points, points[1:])]
    # Include start from rest and return to rest in the acceleration gate.
    v_rest = [[0.0] * 6] + velocities + [[0.0] * 6]
    accelerations = [[(b[j] - a[j]) / dt for j in range(6)] for a, b in zip(v_rest, v_rest[1:])]
    return {
        "point_count": len(points), "duration_s": (len(points) - 1) * dt,
        "max_excursion_deg": [math.degrees(max(abs(p[j] - points[0][j]) for p in points)) for j in range(6)],
        "peak_velocity_deg_s": [math.degrees(max(abs(v[j]) for v in velocities)) for j in range(6)],
        "peak_acceleration_deg_s2": [math.degrees(max(abs(a[j]) for a in accelerations)) for j in range(6)],
        "start_rad": points[0], "end_rad": points[-1],
    }


def slow_sample_period(points, dt=0.008, max_velocity=0.5, max_acceleration=1.0):
    """Time dilation only: never append, interpolate, or alter planner positions."""
    if not all(math.isfinite(v) and v > 0 for v in (max_velocity, max_acceleration)):
        raise ValueError("positive finite speed/acceleration caps required")
    info = summarize(points, dt)
    scale = max(1.0, max(info["peak_velocity_deg_s"]) / max_velocity,
                math.sqrt(max(info["peak_acceleration_deg_s2"]) / max_acceleration))
    return max(1, math.ceil(dt * scale / 0.008)) * 0.008


def settings(config):
    defaults = {"python": "/home/yikun/ares-r-curobo-venv/bin/python",
                "robot_yaml": "/home/yikun/ares-r-curobo-assets/robot/robot.yml",
                "timeout_s": 240}
    defaults.update(config.get("curobo", {}))
    return defaults


def planner_status(config):
    cfg = settings(config)
    result = {"backend": "cuRobo V2 plan_cspace", "commit": CUROBO_COMMIT,
            "python": cfg["python"], "python_exists": Path(cfg["python"]).is_file(),
            "robot_yaml": cfg["robot_yaml"], "robot_exists": Path(cfg["robot_yaml"]).is_file(),
            "planning_ready": False, "execution": "locked: unstable live actual-feedback channel; model/world commissioning also pending"}
    if result["python_exists"]:
        try:
            probe = subprocess.run([cfg["python"], "-c",
                "import json,torch,curobo; from curobo.motion_planner import MotionPlanner; "
                "print(json.dumps(dict(torch=torch.__version__,curobo=str(curobo.__version__),cuda=torch.cuda.is_available())))"],
                capture_output=True, text=True, timeout=20)
            if probe.returncode:
                result["dependency_error"] = probe.stderr[-1500:]
            else:
                result["environment"] = json.loads(probe.stdout.splitlines()[-1])
                result["planning_ready"] = bool(result["robot_exists"] and result["environment"]["cuda"])
        except (OSError, subprocess.TimeoutExpired, ValueError, IndexError) as exc:
            result["dependency_error"] = str(exc)
    return result


def run_plan(config, start, goal, diagnostics=None):
    start, goal = finite_joints(start), finite_joints(goal)
    if max(abs(a - b) for a, b in zip(start, goal)) > math.radians(0.5) + 1e-12:
        raise ValueError("demo target exceeds 0.5 degree per joint")
    if start == goal:
        raise ValueError("start and goal are identical")
    cfg = settings(config)
    if not Path(cfg["python"]).is_file() or not Path(cfg["robot_yaml"]).is_file():
        raise RuntimeError("cuRobo environment/model unavailable; run curobo status")
    directory = Path(config["logging"]["directory"]) / ("curobo_" + time.strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8])
    directory.mkdir(parents=True, exist_ok=False)
    request = {"start_rad": start, "goal_rad": goal, "robot_yaml": str(Path(cfg["robot_yaml"]).resolve()),
               "arm": "right", "captured_at_unix": time.time(), "diagnostics": diagnostics,
               "expected_commit": CUROBO_COMMIT}
    request_path, output = directory / "request.json", directory / "trajectory.json"
    request_path.write_text(json.dumps(request, indent=2), encoding="utf-8")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
    with (directory / "planner.log").open("w") as log:
        try:
            process = subprocess.run([cfg["python"], "-m", "ares_r.motion.curobo_worker",
                                      str(request_path), str(output)], env=env, stdout=log,
                                     stderr=subprocess.STDOUT, timeout=float(cfg["timeout_s"]))
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("planning timed out; no motion sent; log: %s" % (directory / "planner.log")) from exc
    if process.returncode or not output.is_file():
        raise RuntimeError("planning failed; no fallback/no motion; log: %s" % (directory / "planner.log"))
    return output


def preview(path):
    from .trajectory import load_trajectory
    trajectory = load_trajectory(Path(path))
    info = summarize(trajectory.points, trajectory.sample_period_s)
    info.update({"planner": trajectory.planner, "arm": trajectory.arm,
                 "sample_period_s": trajectory.sample_period_s,
                 "collision_checked": trajectory.collision_checked,
        "execution": "general execution BLOCKED; supervised J6 micro test has separate live/clearance gates"})
    return info
