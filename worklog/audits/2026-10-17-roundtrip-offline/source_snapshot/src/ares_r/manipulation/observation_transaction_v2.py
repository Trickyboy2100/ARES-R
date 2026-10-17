"""Parallel 5700 + 5000 transaction behind one stationary-state bracket."""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
from pathlib import Path
import time
import uuid


class ObservationTransactionV2:
    SCHEMA_VERSION=2
    def __init__(self,*,read_robot_state,detect_resource,capture_pointcloud,commit_scene,
                 clock=time.time,joint_stability_rad=math.radians(.25),max_capture_skew_s=3.0):
        self.read_robot_state=read_robot_state;self.detect_resource=detect_resource
        self.capture_pointcloud=capture_pointcloud;self.commit_scene=commit_scene
        self.clock=clock;self.joint_stability_rad=joint_stability_rad
        self.max_capture_skew_s=max_capture_skew_s
    @staticmethod
    def _joints(state,side):
        value=state[side].get("diagnostics",state[side]);return tuple(value["joint_position_rad"])
    def capture(self,destination,*,profile,purpose="pick"):
        destination=Path(destination)
        if destination.exists():raise FileExistsError("refusing to overwrite observation V2")
        destination.mkdir(parents=True)
        started=self.clock();before=self.read_robot_state("before")
        with ThreadPoolExecutor(max_workers=2,thread_name_prefix="obs-v2") as pool:
            detection_future=pool.submit(self.detect_resource,profile)
            cloud_future=pool.submit(self.capture_pointcloud,destination/"capture_5000")
            detection=detection_future.result();cloud=cloud_future.result()
        sensor_done=self.clock();after=self.read_robot_state("after")
        maximum_delta=max(abs(a-b) for side in ("left","right")
                          for a,b in zip(self._joints(before,side),self._joints(after,side)))
        if maximum_delta>self.joint_stability_rad:raise RuntimeError("ROBOT_MOVED_DURING_OBSERVATION")
        detection_at=float(detection.get("captured_at_unix",detection.get("timestamp",started)))
        cloud_at=float(cloud.get("captured_at_unix",started))
        if abs(detection_at-cloud_at)>self.max_capture_skew_s:raise RuntimeError("CAPTURE_WINDOW_SKEW")
        scene=self.commit_scene(cloud,detection,destination/"scene")
        pointcloud_sha=cloud.get("sha256") or hashlib.sha256(
            json.dumps(cloud,sort_keys=True).encode()).hexdigest()
        artifact={"schema_version":self.SCHEMA_VERSION,"transaction_state":"COMMITTED",
            "observation_id":"OBS2_"+uuid.uuid4().hex,"profile":profile,"purpose":purpose,
            "detection_id":detection["request_id"],"pointcloud_sha256":pointcloud_sha,
            "scene_snapshot_id":scene["scene_snapshot_id"],"scene_digest":scene["scene_digest"],
            "calibration_revision":scene.get("calibration_revision"),
            "tool_revision":scene.get("tool_revision"),"robot_state_before":before,
            "robot_state_after":after,"maximum_joint_delta_rad":maximum_delta,
            "capture_skew_s":abs(detection_at-cloud_at),"captured_at_unix":started,
            "completed_at_unix":self.clock(),"timing_s":{"parallel_sensors":sensor_done-started,
            "total":self.clock()-started},"provenance":{"5700":detection,"5000":cloud}}
        tmp=destination/"observation_v2.json.tmp";final=destination/"observation_v2.json"
        tmp.write_text(json.dumps(artifact,indent=2)+"\n");tmp.replace(final)
        return artifact
