#!/usr/bin/env python3
"""Camera-only Pixel Pro capture with immutable EpicRaw and provenance."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import time

import cv2
import epiceye


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default="192.168.99.199:5000")
    parser.add_argument("--output", required=True)
    parser.add_argument("--vendor-example", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location("epic_capture_example", args.vendor_example)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)

    started = time.time()
    frame_id = epiceye.trigger_frame(args.endpoint, pointcloud=True)
    if not frame_id:
        raise RuntimeError("Pixel Pro trigger_frame failed")
    raw = epiceye.get_frame_in_epicraw(args.endpoint, frame_id)
    if raw is None:
        raise RuntimeError("Pixel Pro get_frame_in_epicraw failed")
    raw_path = output / "frame.epicraw"
    raw_path.write_bytes(raw)
    document = epiceye.try_load_epic_raw_document_from_bytes(raw)
    if document is None:
        raise RuntimeError("saved EpicRaw cannot be decoded")

    image = epiceye.decode_image_from_epicraw(document)
    if image is not None:
        cv2.imwrite(str(output / "image8bit.png"), helper._to_8bit(image))
    depth, width, height = epiceye.decode_depth_from_epicraw(document)
    if depth is not None:
        helper._save_depth_grey(depth, str(output / "depthGrey.png"))
    points, point_width, point_height = epiceye.decode_point_cloud_from_epicraw(document)
    if points is None:
        raise RuntimeError("saved EpicRaw has no pointcloud")
    helper._write_ply(points, str(output / "pointcloud.ply"))

    cameras = epiceye.search_camera() or []
    camera = next((value for value in cameras if value.get("ip") == args.endpoint),
                  cameras[0] if cameras else {})
    files = {}
    for path in sorted(output.iterdir()):
        if path.is_file():
            files[path.name] = {"bytes": path.stat().st_size, "sha256": sha(path)}
    manifest = {
        "schema_version": 1, "capture_kind": "STATIC_CAMERA_ONLY_NO_ROBOT_MOTION",
        "frame_id": frame_id, "captured_at_unix": started,
        "captured_at_local": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(started)),
        "endpoint": args.endpoint, "sdk_version": epiceye.get_sdk_version(),
        "camera": camera, "epicraw_bytes": len(raw),
        "pointcloud_width": point_width, "pointcloud_height": point_height,
        "depth_width": width, "depth_height": height, "source_unit": "mm",
        "files": files,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
