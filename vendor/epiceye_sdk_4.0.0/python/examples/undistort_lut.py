"""单功能示例：去畸变查找表 LUT。

功能：
    - 搜到相机：读 info 尺寸 + get_camera_matrix / get_distortion，然后
      get_undistort_lut（在线，从相机取）与 compute_undistort_lut（离线本地算），
      最后 clear_undistort_lut_cache 清缓存。
    - 搜不到相机：用一组演示内参走 compute_undistort_lut 离线演示。

    注意：畸变全 0 时 get_undistort_lut 直接返回 None（无需 LUT）。

用法：
    python examples/undistort_lut.py [ip]
    ip 可省略；省略时自动搜索，搜不到则走离线演示。

数据格式：每个像素对应两个 float 映射坐标；清理操作只影响当前 SDK 进程缓存。
相机影响：在线路径只读，离线路径不连接相机。
"""

import sys
from typing import Optional

import numpy as np

import epiceye


def _resolve_ip() -> Optional[str]:
    if len(sys.argv) > 1 and sys.argv[1]:
        return sys.argv[1]

    cameras = epiceye.search_camera()
    if not cameras:
        print("Camera not found!")
        return None
    return cameras[0].get("ip")


def _lut_info(lut):
    if lut is None:
        return "None"
    arr = np.asarray(lut)
    flat = arr.reshape(-1)
    head = ", ".join(f"{v:.3f}" for v in flat[:4])
    return f"shape={arr.shape}, size={flat.size}, [0..3]={head}"


def _offline_demo():
    print("\n--- computeUndistortLut (offline, no camera) ---")
    camera_matrix = [1420.0, 0.0, 710.0, 0.0, 1420.0, 710.0, 0.0, 0.0, 1.0]
    distortion = [-0.05, 0.01, 0.0, 0.0, 0.0]
    lut = epiceye.compute_undistort_lut(1420, 1420, camera_matrix, distortion)
    print(f"computeUndistortLut: {_lut_info(lut)}")


def _normalize_info(info):
    if isinstance(info, dict) and isinstance(info.get("data"), dict):
        return info["data"]
    return info


def main() -> int:
    print(f"SDK Version: {epiceye.get_sdk_version()}")
    print("---------------Undistort LUT---------------")

    ip = _resolve_ip()
    if ip is None:
        _offline_demo()
        return 0
    print(f"Using camera: {ip}\n")

    info = _normalize_info(epiceye.get_info(ip))
    if info is None:
        print("getInfo failed!")
        return 1
    width, height = info.get("width"), info.get("height")
    print(f"Camera resolution: {width}x{height}")

    camera_matrix = epiceye.get_camera_matrix(ip)
    if camera_matrix is None:
        print("getCameraMatrix failed!")
        return 1
    distortion = epiceye.get_distortion(ip)
    print(f"cameraMatrix: {list(camera_matrix)}")
    print(f"distortion: {None if distortion is None else list(distortion)}\n")

    print("--- getUndistortLut (online, from camera) ---")
    lut = epiceye.get_undistort_lut(ip, width, height, camera_matrix, distortion)
    if lut is None:
        print("getUndistortLut returned None (distortion all zero or failed)")
    else:
        print(f"getUndistortLut: {_lut_info(lut)}")

    print("\n--- computeUndistortLut (offline) ---")
    lut2 = epiceye.compute_undistort_lut(width, height, camera_matrix, distortion)
    print(f"computeUndistortLut: {_lut_info(lut2)}")

    print("\n--- clearUndistortLutCache ---")
    epiceye.clear_undistort_lut_cache(ip)
    print(f"Cache cleared for: {ip}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
