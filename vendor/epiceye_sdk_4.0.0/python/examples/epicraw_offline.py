"""单功能示例：EpicRaw 离线解析。

功能：从 .epicraw 文件（命令行首参为文件路径）或相机取一帧 EpicRaw 字节，
      然后纯离线（不再连相机）解析：
      - try_load_epic_raw_document_from_bytes  一次解析多次复用
      - decode_camera_config_from_epicraw      拍摄时相机配置
      - get_depth_intrinsics_from_epicraw      深度内参 / 畸变 / 尺寸
      - decode_image / decode_depth / decode_point_cloud_from_epicraw
      - compute_undistort_lut                  离线计算去畸变查找表
      - get_metadata_str_from_epicraw          取指定元素 MetaDataStr

用法：
    python examples/epicraw_offline.py <file.epicraw>   # 离线解析文件
    python examples/epicraw_offline.py <ip>             # 从指定相机取一帧再解析
    python examples/epicraw_offline.py                  # 搜索相机取一帧再解析

相机影响：文件模式完全不连接相机；在线模式触发一次拍摄，但不修改配置。
"""

import os
import sys
from typing import Optional

import epiceye
from epiceye import EpicRaw3DataType


def _resolve_ip() -> Optional[str]:
    if len(sys.argv) > 1 and sys.argv[1]:
        return sys.argv[1]

    cameras = epiceye.search_camera()
    if not cameras:
        print("Camera not found!")
        return None
    return cameras[0].get("ip")


def _load_bytes() -> bytes:
    """首参为文件则读文件，否则搜索相机触发取一帧。"""
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        path = sys.argv[1]
        print(f"Loading EpicRaw from file: {path}")
        with open(path, "rb") as f:
            data = f.read()
        print(f"Loaded {len(data)} bytes")
        return data

    ip = _resolve_ip()
    if not ip:
        raise SystemExit("Pass an EpicRaw file path or camera IP as the first argument.")

    print(f"Using camera: {ip}")
    frame_id = epiceye.trigger_frame(ip, pointcloud=True)
    if frame_id is None:
        raise SystemExit("triggerFrame failed!")
    print(f"frameID: {frame_id}")
    raw = epiceye.get_frame_in_epicraw(ip, frame_id)
    if raw is None:
        raise SystemExit("getFrameInEpicRaw failed!")
    print(f"Got {len(raw)} bytes from camera")
    return raw


def main() -> int:
    print(f"SDK Version: {epiceye.get_sdk_version()}")
    print("---------------EpicRaw Offline Parse---------------")
    raw = _load_bytes()

    print("\n--- tryLoadEpicRawDocumentFromBytes ---")
    doc = epiceye.try_load_epic_raw_document_from_bytes(raw)
    if doc is None:
        print("Failed to load EpicRaw document!")
        return 1
    print(f"EpicRaw loaded: file_type={getattr(doc, 'file_type', '?')}")

    print("\n--- decodeCameraConfigFromEpicRaw ---")
    camera_config = epiceye.decode_camera_config_from_epicraw(doc)
    print(f"Camera config: {camera_config}")

    # 深度内参：返回 (distortion, camera_matrix, depth_width, depth_height)
    print("\n--- getDepthIntrinsicsFromEpicRaw ---")
    distortion, camera_matrix, depth_w, depth_h = epiceye.get_depth_intrinsics_from_epicraw(doc)
    print(f"Depth size: {depth_w}x{depth_h}")
    print(f"CameraMatrix: {None if camera_matrix is None else list(camera_matrix)}")
    print(f"Distortion: {None if distortion is None else list(distortion)}")

    print("\n--- decodeImageFromEpicRaw ---")
    image = epiceye.decode_image_from_epicraw(doc)
    if image is not None:
        print(f"decodeImage success! shape={image.shape} dtype={image.dtype}")
    else:
        print("decodeImage: no texture element in this EpicRaw.")

    print("\n--- decodeImageFromEpicRaw by type ---")
    raw_image = epiceye.decode_image_from_epicraw(
        doc, EpicRaw3DataType.TextureBGR
    )
    if raw_image is not None:
        print(
            "raw image: "
            f"type={raw_image.data_type.name} "
            f"size={raw_image.width}x{raw_image.height} "
            f"matType={raw_image.mat_type} "
            f"bytes={len(raw_image.data)}"
        )
    else:
        print("raw image: requested element not found or invalid.")

    print("\n--- decodeDepthFromEpicRaw ---")
    depth, dw, dh = epiceye.decode_depth_from_epicraw(doc)
    if depth is not None:
        print(f"decodeDepth success! size: {dw}x{dh}")
    else:
        print("decodeDepth: no depth element in this EpicRaw.")

    print("\n--- decodePointCloudFromEpicRaw ---")
    # 离线计算 LUT（可为 None，此处演示带内参计算）
    lut = None
    if camera_matrix is not None and depth_w and depth_h:
        lut = epiceye.compute_undistort_lut(depth_w, depth_h, camera_matrix, distortion)
    points, pw, ph = epiceye.decode_point_cloud_from_epicraw(doc, lut)
    if points is not None:
        print(f"decodePointCloud success! size: {pw}x{ph}")
    else:
        print("decodePointCloud: no pointcloud/depth element in this EpicRaw.")

    print("\n--- getMetaDataStr ---")
    meta = epiceye.get_metadata_str_from_epicraw(doc, EpicRaw3DataType.TextureBGR)
    if meta:
        print(f"TextureBGR MetaData: {meta}")
    else:
        meta = epiceye.get_metadata_str_from_epicraw(doc, EpicRaw3DataType.DepthSrcImg2)
        print(f"DepthSrcImg2 MetaData: {meta}" if meta else "(no matching element metadata found)")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
