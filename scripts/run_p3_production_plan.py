#!/usr/bin/env python3
"""Launch one execution-impossible P3 cuRobo planning worker."""

import argparse,json,os,subprocess
from pathlib import Path
import sys

REPOSITORY=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPOSITORY/"src"))
from ares_r.cli import load_config
from ares_r.motion.curobo import CUROBO_COMMIT
from ares_r.motion.curobo_params import planning_profile
from ares_r.motion.se3 import pose_mm_rad_to_matrix


def load(path):return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    p=argparse.ArgumentParser();p.add_argument("scene_dir",type=Path);p.add_argument("--audit",required=True)
    p.add_argument("--output",required=True);p.add_argument("--benchmark-runs",type=int,default=3);a=p.parse_args()
    config=load_config(str(REPOSITORY/"config/system.json"));scene=load(a.scene_dir/"compiled_scene.json")
    report=load(a.scene_dir/"scene_report.json");targets=load(a.scene_dir/"targets.json");audit=load(a.audit)
    tool=audit["diagnostics"]["tool_data"]["pose_mm_rad"]
    request={"schema_version":1,"planning_only":True,"execution_allowed":False,"mode":report["mode"],
        "compiled_scene":scene,"scene_snapshot_id":scene["scene_snapshot_id"],"scene_digest":scene["digest"],
        "start_rad":targets["start_rad"],"goal_rad":targets["goal_rad"],"active_arm":targets["active_arm"],
        "T_body_model":report["T_body_model"],
        "T_link6_tcp":pose_mm_rad_to_matrix(tool),"geometry_revision":report["geometry_revision"],
        "inactive_arm_revision":report["inactive_arm_revision"],"collision_model":load(config["robot_collision"]["model"]),
        "robot_yaml":config["curobo"]["robot_yaml"],"expected_commit":CUROBO_COMMIT,
        "planning_parameters":planning_profile(config),"benchmark_runs":a.benchmark_runs}
    output=Path(a.output);output.parent.mkdir(parents=True,exist_ok=True);request_path=output.with_name("planner_request.json")
    request_path.write_text(json.dumps(request,indent=2)+"\n");log=output.with_name("planner.log")
    env=dict(os.environ,PYTHONPATH=str(REPOSITORY/"src"))
    with log.open("w") as stream:
        result=subprocess.run([config["curobo"]["python"],"-m","ares_r.motion.production_scene_worker",
                               str(request_path),str(output)],cwd=str(REPOSITORY),env=env,
                              stdout=stream,stderr=subprocess.STDOUT,timeout=float(config["curobo"]["timeout_s"]))
    if result.returncode or not output.is_file():
        raise RuntimeError("P3 planning failed contract; inspect %s"%log)
    print(output.read_text())


if __name__=="__main__":main()
