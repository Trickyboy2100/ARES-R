"""Dependency-free HTTP/WebSocket frontend over the canonical backend."""

from __future__ import annotations

import argparse
import base64
import hashlib
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import struct
import sys
import time
from urllib.parse import urlparse

import numpy as np

from ares_r.cli import load_config
from ares_r.scene_aware_dispatch import SceneAwareDispatcher


ROOT = Path(__file__).resolve().parents[3]
INDEX = Path(__file__).with_name("index.html")


def scene_payload(dispatcher):
    scene = dispatcher.scene_status();motion = dispatcher.motion_status()
    result = {"scene_epoch": scene.get("scene_epoch"),
              "scene_snapshot_id": scene.get("scene_snapshot_id"),
              "base_pose_revision": scene.get("base_pose_revision"),
              "pointcloud_age_s": scene.get("age_s"),
              "calibration_revision": scene.get("calibration_revision"),
              "timings": scene.get("timings_s"), "pointcloud": [],
              "collision_primitives": [], "robot_geometry": [],
              "target_pose": None, "trajectory": [], "trajectory_metrics": None}
    directory = scene.get("scene_dir")
    if directory and Path(directory).exists():
        root = Path(directory);cloud = root / "scene/clean_residual.npz"
        if cloud.exists():
            points = np.load(cloud)["points_body_m"]
            stride = max(1, len(points)//12000)
            result["pointcloud"] = points[::stride].round(4).tolist()
        report = root / "scene/scene_report.json"
        if report.exists():
            result["collision_primitives"] = json.loads(report.read_text()).get("objects", [])
        geometry = root / "whole_robot_geometry.json"
        if geometry.exists():
            result["robot_geometry"] = json.loads(geometry.read_text()).get("boxes", [])
    handle_path = motion.get("plan_handle")
    if handle_path and Path(handle_path).exists():
        handle = json.loads(Path(handle_path).read_text())
        result["target_pose"] = handle["request"].get("goal_pose_body_m_rad")
        planning = Path(handle["plan_artifact"]) / "planning.json"
        if planning.exists():
            plan = json.loads(planning.read_text())
            result["trajectory"] = plan.get("tcp_path_body_m", [])
            result["trajectory_metrics"] = {
                "clearance": plan.get("clearance_m"),
                "limiting_object": plan.get("path_limiting_object_id"),
                "path": plan.get("path_metrics"),
                "hard_validity": handle.get("hard_validity")}
    return result


def system_status(dispatcher):
    scene=dispatcher.scene_status();motion=dispatcher.motion_status()
    return {"BASE": "MOVING" if scene.get("reason")=="BASE_MOVING" else "SETTLED",
            "SCENE": scene.get("state", "INVALID"),
            "PLANNER": motion.get("state", "IDLE"),
            "EXECUTION": motion.get("execution_state", "IDLE"),
            "base_pose_revision": scene.get("base_pose_revision"),
            "scene_epoch": scene.get("scene_epoch"),
            "scene_snapshot_id": scene.get("scene_snapshot_id"),
            "pointcloud_age_s": scene.get("age_s"),
            "scan_timing_s": scene.get("timings_s"),
            "planner_timing_s": motion.get("planner_timing_s")}


def _ws_frame(payload):
    data=json.dumps(payload,separators=(",",":")).encode()
    header=bytearray([0x81])
    if len(data)<126:header.append(len(data))
    elif len(data)<65536:header.extend([126]);header.extend(struct.pack("!H",len(data)))
    else:header.extend([127]);header.extend(struct.pack("!Q",len(data)))
    return bytes(header)+data


class Handler(BaseHTTPRequestHandler):
    dispatcher = None

    def _json(self, value, status=200):
        data=json.dumps(value,indent=2).encode()
        self.send_response(status);self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data)

    def _body(self):
        length=int(self.headers.get("Content-Length","0"))
        return json.loads(self.rfile.read(length) or b"{}")

    def _websocket(self, payload_fn):
        key=self.headers.get("Sec-WebSocket-Key")
        if not key:return self._json({"error":"websocket upgrade required"},426)
        accept=base64.b64encode(hashlib.sha1((key+"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        self.send_response(101);self.send_header("Upgrade","websocket")
        self.send_header("Connection","Upgrade");self.send_header("Sec-WebSocket-Accept",accept);self.end_headers()
        try:
            while True:
                self.wfile.write(_ws_frame(payload_fn()));self.wfile.flush();time.sleep(1)
        except (BrokenPipeError,ConnectionResetError):pass

    def do_GET(self):
        path=urlparse(self.path).path
        if path=="/":
            data=INDEX.read_bytes();self.send_response(200);self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data)
        elif path=="/api/system/status":self._json(system_status(self.dispatcher))
        elif path=="/api/scene/status":self._json(self.dispatcher.scene_status())
        elif path=="/api/motion/status":self._json(self.dispatcher.motion_status())
        elif path=="/api/scene/data":self._json(scene_payload(self.dispatcher))
        elif path=="/api/events":self._websocket(lambda:system_status(self.dispatcher))
        elif path=="/api/scene/stream":self._websocket(lambda:scene_payload(self.dispatcher))
        elif path.startswith("/api/motion/"):
            try:self._json(self.dispatcher.motion_preview(path.rsplit("/",1)[-1]))
            except Exception as exc:self._json({"error":str(exc)},409)
        else:self._json({"error":"not found"},404)

    def do_POST(self):
        path=urlparse(self.path).path
        try:
            body=self._body()
            if path=="/api/scene/scan":value=self.dispatcher.scene_scan(True,body.get("arm","right"))
            elif path=="/api/scene/invalidate":value=self.dispatcher.scene_invalidate(body.get("reason","WEBUI"))
            elif path=="/api/motion/plan":value=self.dispatcher.motion_plan(body)
            elif path=="/api/motion/stop":value=self.dispatcher.motion_stop()
            elif path=="/api/task/ab/run-next":value=self.dispatcher.ab_plan_next(body["destination"])
            elif path=="/api/art/command":value=self.dispatcher.dispatch(body["command"])
            elif path.endswith("/execute"):
                raise RuntimeError("supervised execution requires ART/TTY confirmation")
            else:return self._json({"error":"not found"},404)
            self._json(value)
        except Exception as exc:self._json({"error":"%s: %s"%(type(exc).__name__,exc)},409)

    def log_message(self, pattern, *args):
        sys.stderr.write("WEBUI "+pattern%args+"\n")


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--host",default="127.0.0.1");parser.add_argument("--port",type=int,default=8765)
    parser.add_argument("--config",default="config/system.json");args=parser.parse_args()
    Handler.dispatcher=SceneAwareDispatcher(load_config(args.config))
    server=ThreadingHTTPServer((args.host,args.port),Handler)
    print("ARES-R scene-aware UI: http://%s:%d"%(args.host,args.port),flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()


if __name__=="__main__":main()
