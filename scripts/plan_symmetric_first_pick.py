#!/usr/bin/env python3
"""Plan every whole-chain-valid two-finger grasp branch and select one.

No hardware calls occur here.  Selection requires both the downstream
kinematic-chain audit and a fully validated cuRobo pregrasp path in the same
fresh SceneSnapshot.  A branch that is attractive kinematically but collides
in the live world cannot win.
"""

import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT=Path(__file__).resolve().parents[1]


def load(path):return json.loads(Path(path).read_text())
def write(path,value):Path(path).write_text(json.dumps(value,indent=2)+"\n")


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--plan-dir",type=Path,required=True)
    parser.add_argument("--chain-audit",type=Path,required=True)
    args=parser.parse_args()
    request=load(args.plan_dir/"planner_request.json")
    chain=load(args.chain_audit)
    scores={row["grasp_symmetry_id"]:row for row in chain["candidates"]
            if row["kinematic_chain_valid"]}
    env=dict(os.environ,PYTHONPATH=str(ROOT/"src"))
    outcomes=[]
    for goal,meta in zip(request["goal_candidates_rad"],
                         request["goal_candidate_metadata"]):
        symmetry=meta["grasp_symmetry_id"]
        if symmetry not in scores:continue
        branch=args.plan_dir/("symmetry_"+symmetry.lower())
        branch.mkdir(exist_ok=True)
        value=copy.deepcopy(request);value["goal_rad"]=goal
        value["goal_candidates_rad"]=[goal];value["goal_candidate_metadata"]=[meta]
        value["whole_chain_symmetry_binding"]={"policy":chain["policy"],
            "selected_grasp_symmetry_id":symmetry,
            "roll_branch":scores[symmetry]["roll_branch"]}
        success=False;profile=None
        for name,updates in (("FAST",{}),("FALLBACK",{
                "num_ik_seeds":8,"num_trajopt_seeds":8,"max_attempts":10,
                "enable_graph_attempt":1})):
            candidate=copy.deepcopy(value);candidate["planning_parameters"].update(updates)
            candidate["planner_profile_revision"]=(
                "FAST_4_2_WHOLE_CHAIN_SYMMETRY" if name=="FAST" else
                "FALLBACK_8_8_GRAPH_WHOLE_CHAIN_SYMMETRY")
            request_path=branch/("request_"+name.lower()+".json")
            planning_path=branch/("planning_"+name.lower()+".json")
            write(request_path,candidate)
            result=subprocess.run([sys.executable,"-m","ares_r.motion.production_scene_worker",
                str(request_path),str(planning_path)],cwd=ROOT,env=env,text=True,
                capture_output=True,timeout=900)
            (branch/("planner_"+name.lower()+".log")).write_text(
                (result.stdout or "")+(result.stderr or ""))
            planning=load(planning_path) if planning_path.exists() else {}
            if result.returncode==0 and planning.get("observed_result")=="SUCCESS":
                success=True;profile=name
                shutil.copy2(request_path,branch/"selected_request.json")
                shutil.copy2(planning_path,branch/"selected_planning.json")
                break
        outcomes.append({"grasp_symmetry_id":symmetry,"curobo_pregrasp_valid":success,
            "planner_profile":profile,"joint_path_cost":scores[symmetry]["joint_path_cost"],
            "max_stage_joint_distance_rad":scores[symmetry]["max_stage_joint_distance_rad"],
            "artifact_dir":str(branch)})
    valid=[row for row in outcomes if row["curobo_pregrasp_valid"]]
    selected=min(valid,key=lambda row:(row["max_stage_joint_distance_rad"],
                                       row["joint_path_cost"])) if valid else None
    report={"schema_version":1,"policy":"CUROBO_PLUS_WHOLE_CHAIN_GRASP_SELECTION_V1",
        "scene_snapshot_id":request["scene_snapshot_id"],"outcomes":outcomes,
        "selected_grasp_symmetry_id":selected["grasp_symmetry_id"] if selected else None,
        "planning_only":True,"execution_allowed":False}
    write(args.plan_dir/"grasp_symmetry_selection.json",report)
    if selected is None:raise SystemExit("no grasp symmetry passed fresh-scene cuRobo validation")
    source=Path(selected["artifact_dir"])
    shutil.copy2(source/"selected_request.json",args.plan_dir/"planner_request.json")
    shutil.copy2(source/"selected_planning.json",args.plan_dir/"planning.json")
    print(json.dumps(report,indent=2))


if __name__=="__main__":main()
