#!/usr/bin/env python3
"""Create the immutable V1 grasp-verification result from live evidence."""

import argparse
import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ares_r.manipulation.grasp_verification import local_tcp_scene_delta, verify_grasp_v1, verify_grasp_phase


def main():
    p = argparse.ArgumentParser(); p.add_argument("--epoch", type=Path, required=True)
    p.add_argument("--post-scene", type=Path, required=True)
    p.add_argument("--readbacks", type=Path, required=True); p.add_argument("--output", type=Path, required=True)
    p.add_argument('--phase',choices=('LEGACY','HOLD_CANDIDATE','POST_LIFT'),default='LEGACY')
    p.add_argument('--lift-arrived',action='store_true');p.add_argument('--lift-displacement-m',type=float,default=0.)
    a = p.parse_args()
    observation = json.loads((a.epoch / "manipulation_observation.json").read_text())
    before = np.load(a.epoch / "live_scene/scene/clean_residual.npz")["points_body_m"]
    after = np.load(a.post_scene / "scene/clean_residual.npz")["points_body_m"]
    params = json.loads((ROOT / "config/tray_to_groove_v2.json").read_text())
    cfg=params["grasp_verification"]
    delta = local_tcp_scene_delta(before, after, observation["target"]["pose_m_rad"][:3],
                                  radius_m=cfg["local_tcp_radius_m"], voxel_m=cfg["voxel_m"])
    readbacks=[]
    for line in a.readbacks.read_text().splitlines():
        try:row=json.loads(line)
        except json.JSONDecodeError:continue
        if row.get('action')=='read':readbacks.append(row)
    readbacks=readbacks[-len(cfg['delayed_readback_s']):]
    if not readbacks or any('captured_at_unix' not in row for row in readbacks):
        raise RuntimeError('GENUINE_GRIPPER_TIMESTAMPS_REQUIRED')
    if a.phase=='LEGACY':result=verify_grasp_v1(delta,readbacks,params)
    else:result=verify_grasp_phase(delta,readbacks,params,phase=a.phase,
        initial_lift_arrived=a.lift_arrived,lift_displacement_m=a.lift_displacement_m)
    payload = {"schema_version": 1, "observation_id": observation["observation_id"],
               "pre_pointcloud_sha256": observation["pointcloud_sha256"],
               "post_scene_snapshot_id": json.loads((a.post_scene / "scene/snapshot.json").read_text())["snapshot_id"],
               "local_scene_delta": delta, "verification": result}
    a.output.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))
    if result["result"] != "PASS": raise SystemExit(2)


if __name__ == "__main__": main()
