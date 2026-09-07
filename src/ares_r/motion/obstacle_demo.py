"""Isolated virtual right-arm demo. No SDK, live-state read or execution path."""

import json
import os
from pathlib import Path
import subprocess
import time
import uuid

from .curobo import CUROBO_COMMIT, settings


def run_demo(config):
    from .native_demo import snapshot
    live=snapshot()
    if live["queue"] or live["active_queue"] or not live["inpos"]: raise RuntimeError("right not idle")
    cfg = settings(config)
    if not Path(cfg["python"]).is_file() or not Path(cfg["robot_yaml"]).is_file():
        raise RuntimeError("GPU environment/model unavailable; run on .32, or preview saved evidence")
    directory = Path(config["logging"]["directory"]) / (
        "curobo_obstacle_" + time.strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8])
    directory.mkdir(parents=True, exist_ok=False)
    request = dict(robot_yaml=str(Path(cfg["robot_yaml"]).resolve()),
                   expected_commit=CUROBO_COMMIT, arm="right", planning_only=True,
                   start_rad=live["actual_rad"],live_snapshot=live,
                   tool_translation_m=[v/1000 for v in live["tool_mm_rad"][:3]],
                   tool_source="SDK222 live tool snapshot",
                   obstacle_dims_m=[0.025, 0.025, 0.025],
                   tool_proxy_radius_m=0.025,
                   tcp_length_range_m=[0.18, 0.22])
    audit=Path(__file__).resolve().parents[3]/"worklog/evidence/2026-09-07-curobo/right_fk_audit.json"
    request["T_controller_model"]=json.loads(audit.read_text())["T_controller_model"]
    world=json.loads(Path(config["world_geometry_file"]).read_text())["arms"]["right"]
    request.update(body_right_yaw_rad=world["base_rpy_rad"][2],body_right_xyz_m=world["base_xyz_m"])
    req, output = directory / "request.json", directory / "trajectory.json"
    req.write_text(json.dumps(request, indent=2), encoding="utf-8")
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[2]))
    with (directory / "planner.log").open("w") as log:
        try:
            process = subprocess.run([cfg["python"], "-m", "ares_r.motion.obstacle_demo_worker",
                                      str(req), str(output)], env=env, stdout=log,
                                     stderr=subprocess.STDOUT, timeout=max(240, float(cfg["timeout_s"])))
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("virtual demo timed out; no motion; inspect %s" % directory) from exc
    if process.returncode or not output.is_file():
        raise RuntimeError("virtual demo failed; no fallback/no motion; inspect %s" % directory)
    return output
