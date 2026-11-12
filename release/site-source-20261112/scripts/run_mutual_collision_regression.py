#!/usr/bin/env python3
"""Offline, non-executing bidirectional inactive-arm collision regression."""

import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys
import time

REPOSITORY=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPOSITORY/"src"))
from ares_r.perception.robot_collision import (CollisionBox, RobotGeometrySnapshot,
    inactive_arm_obstacles, load_geometry_snapshot, mutual_arm_collisions)


def snapshot_with(snapshot, boxes=None, joints=None):
    return RobotGeometrySnapshot(tuple(boxes or snapshot.boxes),joints or snapshot.joints_rad,
        snapshot.geometry_revision,snapshot.joint_snapshot_revision,snapshot.tool_revision,
        snapshot.scene_revision,snapshot.timings_s,snapshot.provenance)


def main():
    parser=argparse.ArgumentParser();parser.add_argument("geometry");parser.add_argument("--output",required=True)
    args=parser.parse_args();started=time.perf_counter();snap=load_geometry_snapshot(Path(args.geometry))
    current={side:mutual_arm_collisions(snap,side) for side in ("left","right")}
    # Deliberate overlap: move one left arm box onto a right arm box without touching hardware.
    boxes=list(snap.boxes); left=next(i for i,b in enumerate(boxes) if b.owner=="left_arm")
    right=next(b for b in boxes if b.owner=="right_arm")
    boxes[left]=replace(boxes[left],center_body_m=right.center_body_m,rotation_body=right.rotation_body)
    overlap=snapshot_with(snap,boxes=boxes)
    forced={side:mutual_arm_collisions(overlap,side) for side in ("left","right")}
    # Explicit gripper participation: overlap left/right gripper envelopes.
    boxes=list(snap.boxes); li=next(i for i,b in enumerate(boxes) if b.geometry_id=="left/gripper")
    rb=next(b for b in boxes if b.geometry_id=="right/gripper")
    boxes[li]=replace(boxes[li],center_body_m=rb.center_body_m,rotation_body=rb.rotation_body)
    grip=snapshot_with(snap,boxes=boxes)
    gripper={side:mutual_arm_collisions(grip,side) for side in ("left","right")}
    base_obs={side:inactive_arm_obstacles(snap,side) for side in ("left","right")}
    changed_joints={k:list(v) for k,v in snap.joints_rad.items()};changed_joints["left"][0]+=0.1
    changed=snapshot_with(snap,joints=changed_joints)
    changed_obs=inactive_arm_obstacles(changed,"right")
    result={"schema_version":1,"execution":"NONE","current_clear":not current["left"] and not current["right"],
            "current_collisions":current,
            "forced_overlap_detected_both_directions":bool(forced["left"] and forced["right"]),
            "forced_overlap":forced,
            "gripper_detected_both_directions":bool(any(x["gripper_involved"] for x in gripper["left"]) and any(x["gripper_involved"] for x in gripper["right"])),
            "gripper_overlap":gripper,
            "inactive_obstacle_counts":{s:len(v["boxes"]) for s,v in base_obs.items()},
            "inactive_revision_changes_with_joint_revision":base_obs["right"]["revision"]!=changed_obs["revision"],
            "active_right_inactive_left_revision":base_obs["right"]["revision"],
            "active_left_inactive_right_revision":base_obs["left"]["revision"],
            "elapsed_s":time.perf_counter()-started}
    result["pass"]=(result["current_clear"] and result["forced_overlap_detected_both_directions"] and
                    result["gripper_detected_both_directions"] and result["inactive_revision_changes_with_joint_revision"])
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2))
    if not result["pass"]: raise SystemExit(2)


if __name__=="__main__": main()
