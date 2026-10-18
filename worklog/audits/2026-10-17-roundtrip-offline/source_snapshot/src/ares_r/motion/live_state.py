"""Read-only live state checks shared by every motion client."""

from __future__ import annotations

import json
import math
import time
from urllib.request import urlopen


def base_stationarity(config, *, count=3, interval_s=1.0):
    url = config["base"]["base_url"].rstrip("/") + "/robot/status"
    samples = []
    for index in range(count):
        if index:
            time.sleep(interval_s)
        with urlopen(url, timeout=5) as response:
            item = json.load(response)
        info = item["info"]
        log = item.get("log") or {}
        samples.append({"at_unix": time.time(), "x_m": float(info["x"]),
                        "y_m": float(info["y"]), "yaw_deg": float(info["yawNumber"]),
                        "map_id": info["mapId"],
                        "state": item["state"]["current"]["state"],
                        "motion_log_id": log.get("id"),
                        "motion_queue_id": log.get("queueId")})
    drift_m = max(math.hypot(row["x_m"]-samples[0]["x_m"],
                             row["y_m"]-samples[0]["y_m"]) for row in samples)
    yaw_drift_deg = max(abs(row["yaw_deg"]-samples[0]["yaw_deg"]) for row in samples)
    idle = all(row["state"] == "IDLE" and row["map_id"] == samples[0]["map_id"]
               for row in samples)
    marker = (samples[0]["motion_log_id"], samples[0]["motion_queue_id"])
    controller_idle_stable = (None not in marker and all(
        (row["motion_log_id"], row["motion_queue_id"]) == marker for row in samples))
    return {"stationary": bool(idle and controller_idle_stable), "amr_idle": idle,
            "controller_idle_marker_stable": controller_idle_stable,
            "map_pose_stable": drift_m <= .005 and yaw_drift_deg <= .1,
            "translation_drift_m": drift_m, "yaw_drift_deg": yaw_drift_deg,
            "samples": samples,
            "method": "fresh AMR IDLE plus stable motion log/queue marker"}

