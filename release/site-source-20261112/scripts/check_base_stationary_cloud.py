#!/usr/bin/env python3
"""Read-only static-camera check from two robot-self-filtered CLEAR clouds.

ICP is used only to measure relative movement, never to change T_body_camera
or the SceneSnapshot. A nonzero ICP correction is a FAIL, not a new extrinsic.
"""

import argparse
import json
import math
from pathlib import Path

import numpy as np
import open3d as o3d


def check(previous, current):
    previous, current = Path(previous), Path(current)
    a = np.load(previous)["points_body_m"]
    b = np.load(current)["points_body_m"]
    if len(a) < 1000 or len(b) < 1000:
        raise ValueError("insufficient residual environment points")
    source = o3d.geometry.PointCloud()
    target = o3d.geometry.PointCloud()
    source.points = o3d.utility.Vector3dVector(a)
    target.points = o3d.utility.Vector3dVector(b)
    result = o3d.pipelines.registration.registration_icp(
        source, target, 0.05, np.eye(4),
        o3d.pipelines.registration.TransformationEstimationPointToPoint(),
        o3d.pipelines.registration.ICPConvergenceCriteria(max_iteration=50))
    transform = result.transformation
    translation = float(np.linalg.norm(transform[:3, 3]))
    rotation = math.degrees(math.acos(float(np.clip((np.trace(transform[:3, :3])-1)/2,
                                                   -1, 1))))
    stable = bool(result.fitness >= 0.95 and result.inlier_rmse <= 0.005
                  and translation <= 0.003 and rotation <= 0.15)
    return {"stationary": stable, "method": "CLEAR residual cloud motion check only",
            "changes_calibration": False, "previous": str(previous), "current": str(current),
            "previous_points": len(a), "current_points": len(b),
            "fitness": float(result.fitness), "rmse_m": float(result.inlier_rmse),
            "translation_m": translation, "rotation_deg": rotation,
            "T_current_previous_measurement_only": transform.tolist(),
            "thresholds": {"min_fitness": 0.95, "max_rmse_m": 0.005,
                           "max_translation_m": 0.003, "max_rotation_deg": 0.15}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("previous", type=Path)
    parser.add_argument("current", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("refusing to overwrite stationarity evidence")
    report = check(args.previous, args.current)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("stationary", "fitness", "rmse_m",
                                               "translation_m", "rotation_deg")}))


if __name__ == "__main__":
    main()
