#!/usr/bin/env python3
"""Run and plot FREE/AVOID/BLOCK planning-only comparisons."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401; registers old Matplotlib 3D
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ares_r.motion.curobo import CUROBO_COMMIT
from ares_r.motion.curobo_params import planning_profile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pipeline-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--python", default="/home/yikun/ares-r-curobo-venv/bin/python")
    parser.add_argument("--robot-yaml", default="/home/yikun/ares-r-curobo-assets/robot/robot.yml")
    parser.add_argument("--state", type=Path, default=Path("/home/yikun/ARES-R_AUDIT_20260917/afternoon/jaka_readonly_state.json"))
    parser.add_argument("--geometry", type=Path, default=Path("/home/yikun/ARES-R_AUDIT_20260917/body_registration/right_curobo_geometry.json"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    scene = json.loads((args.pipeline_dir / "compiled_scene.json").read_text())
    state = json.loads(args.state.read_text())
    geometry = json.loads(args.geometry.read_text())
    right = state["arms"]["right"]
    start = right["joint_position_rad"]
    # A moderate, previously demonstrated J1-only planning query. No execution.
    goal = list(start)
    goal[0] += 0.28
    request_base = {
        "planning_only": True,
        "execution_allowed": False,
        "planning_scope": "DEMO_OFFLINE_ONLY",
        "compiled_scene": scene,
        "scene_snapshot_id": scene["scene_snapshot_id"],
        "scene_digest": scene["digest"],
        "start_rad": start,
        "goal_rad": goal,
        "T_body_model": geometry["T_body_model"],
        "robot_yaml": args.robot_yaml,
        "tool_translation_m": [value / 1000 for value in right["tool_data"]["pose_mm_rad"][:3]],
        "expected_commit": CUROBO_COMMIT,
        "planning_parameters": planning_profile({}),
    }
    results = {}
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
    for mode in ("FREE", "AVOID", "BLOCK"):
        request = dict(request_base, mode=mode)
        request_path = args.output / (mode.lower() + "_request.json")
        artifact_path = args.output / (mode.lower() + "_planning.json")
        log_path = args.output / (mode.lower() + "_planner.log")
        request_path.write_text(json.dumps(request, indent=2), encoding="utf-8")
        with log_path.open("w") as log:
            completed = subprocess.run(
                [args.python, "-m", "ares_r.motion.pointcloud_demo_worker", str(request_path), str(artifact_path)],
                env=env, stdout=log, stderr=subprocess.STDOUT, timeout=300,
            )
        if completed.returncode or not artifact_path.is_file():
            raise RuntimeError("%s worker failed; inspect %s" % (mode, log_path))
        results[mode] = json.loads(artifact_path.read_text())

    if not all(item["expectation_met"] for item in results.values()):
        raise RuntimeError("one or more demo expectations were not met")
    free = np.asarray(results["FREE"]["tcp_path_body_m"])
    avoid = np.asarray(results["AVOID"]["tcp_path_body_m"])
    if len(free) and len(avoid):
        # Resample by normalized path index for an auditable trajectory delta.
        scale = np.linspace(0, 1, 200)
        a = np.stack([np.interp(scale, np.linspace(0, 1, len(free)), free[:, i]) for i in range(3)], axis=1)
        b = np.stack([np.interp(scale, np.linspace(0, 1, len(avoid)), avoid[:, i]) for i in range(3)], axis=1)
        delta = float(np.max(np.linalg.norm(a - b, axis=1)))
    else:
        delta = None
    summary = {
        "state": "DEMO_OFFLINE_ONLY",
        "execution_allowed": False,
        "same_start_goal": True,
        "scene_snapshot_id": scene["scene_snapshot_id"],
        "scene_digest": scene["digest"],
        "free_avoid_max_tcp_delta_m": delta,
        "results": {mode: {
            "observed_result": item["observed_result"],
            "expectation_met": item["expectation_met"],
            "planning_ms": item["timing_ms"]["planning"],
            "planned_clearance_m": item["clearance_m"]["planned_path"],
        } for mode, item in results.items()},
    }
    (args.output / "planning_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    for mode, item in results.items():
        fig = plt.figure(figsize=(10, 8))
        ax = fig.add_subplot(111, projection="3d")
        path = np.asarray(item["tcp_path_body_m"])
        if len(path):
            ax.plot(path[:, 0], path[:, 1], path[:, 2], linewidth=3, label=mode + " cuRobo TCP")
            ax.scatter(*path[0], s=70, c="green", label="same start")
            ax.scatter(*path[-1], s=70, c="blue", label="same goal")
        ax.set_xlabel("BODY +X forward (m)")
        ax.set_ylabel("BODY +Y left (m)")
        ax.set_zlabel("BODY +Z up (m)")
        ax.set_title("%s planning-only | %s\nDEMO_ONLY / NOT FOR EXECUTION" % (mode, item["observed_result"]), color="crimson")
        ax.legend(loc="best")
        fig.tight_layout()
        fig.savefig(args.output / ("planning_%s.png" % mode.lower()), dpi=180)
        plt.close(fig)

    fig = plt.figure(figsize=(11, 8))
    ax = fig.add_subplot(111, projection="3d")
    for mode, color in (("FREE", "tab:blue"), ("AVOID", "tab:orange")):
        path = np.asarray(results[mode]["tcp_path_body_m"])
        ax.plot(path[:, 0], path[:, 1], path[:, 2], color=color, linewidth=3, label=mode)
    ax.set_xlabel("BODY +X forward (m)")
    ax.set_ylabel("BODY +Y left (m)")
    ax.set_zlabel("BODY +Z up (m)")
    ax.set_title("Same start/goal cuRobo comparison\nDEMO_ONLY / NOT FOR EXECUTION", color="crimson")
    ax.legend()
    fig.tight_layout()
    fig.savefig(args.output / "planning_free_avoid_comparison.png", dpi=180)
    plt.close(fig)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
