#!/usr/bin/env python3
"""Persistent Pixel Pro capture service for latency-sensitive scene scans."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import time

import epiceye
import numpy as np


def capture(endpoint: str, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    captured_at_unix=time.time()
    total_at = time.perf_counter()
    at = time.perf_counter()
    frame_id = epiceye.trigger_frame(endpoint, pointcloud=True)
    trigger_s = time.perf_counter() - at
    if frame_id is None:
        raise RuntimeError("Epic trigger_frame failed")
    at = time.perf_counter()
    raw = epiceye.get_frame_in_epicraw(endpoint, frame_id)
    download_s = time.perf_counter() - at
    if raw is None:
        raise RuntimeError("Epic get_frame_in_epicraw failed")
    at = time.perf_counter()
    document = epiceye.try_load_epic_raw_document_from_bytes(raw)
    points, width, height = epiceye.decode_point_cloud_from_epicraw(document)
    decode_s = time.perf_counter() - at
    if points is None:
        raise RuntimeError("Epic point-cloud decode failed")
    points = np.asarray(points, dtype=np.float32).reshape(-1, 3)
    at = time.perf_counter()
    artifact = output / "pointcloud_camera_mm.npy"
    np.save(artifact, points, allow_pickle=False)
    write_s = time.perf_counter() - at
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    valid = np.isfinite(points).all(axis=1) & np.any(points != 0.0, axis=1)
    result = {
        "schema_version": 1, "kind": "epic_fast_pointcloud_capture",
        "frame_id": str(frame_id), "endpoint": endpoint,
        "captured_at_unix":captured_at_unix,
        "coordinate_frame": "Epic depth/pointcloud camera",
        "source_coordinate_unit": "mm", "width": int(width),
        "height": int(height), "vertex_count": int(len(points)),
        "valid_point_count": int(valid.sum()), "valid_ratio": float(valid.mean()),
        "artifact": str(artifact.resolve()), "sha256": digest,
        "timing_s": {"trigger": trigger_s, "download": download_s,
                     "decode": decode_s, "npy_write": write_s,
                     "total": time.perf_counter() - total_at},
    }
    (output / "manifest.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def serve(path: Path) -> None:
    if path.exists():
        path.unlink()
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(path)); os.chmod(path, 0o600); server.listen(4)
    try:
        while True:
            connection, _ = server.accept()
            with connection:
                request = json.loads(connection.recv(65536).decode())
                try:
                    if request.get("command") == "stop":
                        connection.sendall(b'{"ok":true}\n'); return
                    result = capture(request["endpoint"], Path(request["output"]))
                    response = {"ok": True, "result": result}
                except Exception as exc:
                    response = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
                connection.sendall((json.dumps(response) + "\n").encode())
    finally:
        server.close()
        if path.exists():
            path.unlink()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", type=Path, required=True)
    serve(parser.parse_args().socket)
