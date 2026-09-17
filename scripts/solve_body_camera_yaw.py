#!/usr/bin/env python3
"""Solve a quality-gated BODY<-CAMERA rotation while leaving tx/ty blocked."""

import argparse
import json
import math
from pathlib import Path

import numpy as np

from ares_r.perception.body_registration import robust_translation_yaw


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("prior", type=Path)
    parser.add_argument("observations", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    prior = json.loads(args.prior.read_text())
    observations = json.loads(args.observations.read_text())
    selected_prior = float(observations.get("yaw_prior_selected_deg",
                                            math.degrees(float(prior["yaw_prior_rad"]))))
    fit = robust_translation_yaw(observations["observations"], math.radians(selected_prior))
    original_yaw = float(prior["yaw_prior_rad"])
    c, s = math.cos(-original_yaw), math.sin(-original_yaw)
    level_from_prior = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=float)
    r_level_camera = level_from_prior @ np.asarray(prior["R_body_camera_prior"], dtype=float)
    c, s = math.cos(fit["yaw_rad"]), math.sin(fit["yaw_rad"])
    r_body_camera = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=float) @ r_level_camera
    result = {
        "schema_version": 1,
        "state": "UNCOMMISSIONED",
        "rotation_and_z_validated": True,
        "xy_translation_commissioned": False,
        "BODY_SCENE_ALLOWED": False,
        "R_body_camera": r_body_camera.tolist(),
        "camera_height_body_m": prior["camera_height_body_m"],
        "tx_body_camera_m": None,
        "ty_body_camera_m": None,
        "yaw_fit": fit,
        "sources": {"roll_pitch": "TABLE_SUPPORT_PLANE",
                    "z": "TABLE_HEIGHT_0.750",
                    "yaw": "TABLE_EDGE_PLUS_QUALITY_GATED_TRANSLATIONS",
                    "xy": "MISSING_MEASURED_PRIOR"},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"state": result["state"], "yaw_deg": fit["yaw_deg"],
                      "accepted": len(fit["accepted"]), "rejected": len(fit["rejected"])}))


if __name__ == "__main__":
    main()
