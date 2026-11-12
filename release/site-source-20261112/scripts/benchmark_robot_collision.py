#!/usr/bin/env python3
"""Repeatable CPU latency benchmark for the P2 geometry backend."""

import argparse,json
from pathlib import Path
import sys,time
import numpy as np

REPOSITORY=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPOSITORY/"src"))
from ares_r.perception.body_pointcloud import load_artifact
from ares_r.perception.robot_collision import (build_geometry_snapshot,inactive_arm_obstacles,
    mutual_arm_collisions,self_filter_body_cloud)


def load(path): return json.loads(Path(path).read_text(encoding="utf-8"))
def stats(values): return {"runs":len(values),"p50_s":float(np.percentile(values,50)),
                           "p95_s":float(np.percentile(values,95)),"max_s":float(max(values))}
def timed(function,runs):
    values=[]
    for _ in range(runs):
        started=time.perf_counter();function();values.append(time.perf_counter()-started)
    return stats(values)


def main():
    p=argparse.ArgumentParser();p.add_argument("--model",required=True);p.add_argument("--world",required=True)
    p.add_argument("--left-audit",required=True);p.add_argument("--right-audit",required=True)
    p.add_argument("--cloud",required=True);p.add_argument("--output",required=True);a=p.parse_args()
    model,world=load(a.model),load(a.world);audits={"left":load(a.left_audit),"right":load(a.right_audit)}
    snap=build_geometry_snapshot(model,world,audits);cloud,_=load_artifact(Path(a.cloud));points=cloud.points_body_m
    result={"geometry_export":timed(lambda:build_geometry_snapshot(model,world,audits),100),
            "inactive_arm_world_both_directions":timed(lambda:(inactive_arm_obstacles(snap,"left"),inactive_arm_obstacles(snap,"right")),100),
            "mutual_collision_query_both_directions":timed(lambda:(mutual_arm_collisions(snap,"left"),mutual_arm_collisions(snap,"right")),100),
            "self_filter_20mm":timed(lambda:self_filter_body_cloud(points,snap,.02),5),
            "point_count":int(len(points)),"execution":"NONE"}
    output=Path(a.output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8");print(json.dumps(result,indent=2))


if __name__=="__main__":main()
