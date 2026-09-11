"""读取相机保存的完整内外参 JSON，并读取当前深度输出的内参与畸变。

用法：python examples/camera_parameters.py [ip]
ip 可省略；省略时自动搜索并查询第一台相机。

读取相机当前内参。本示例只读，不写入内参。
"""

import json
import sys
from typing import Optional

import epiceye


def _resolve_ip() -> Optional[str]:
    if len(sys.argv) > 1 and sys.argv[1]:
        return sys.argv[1]

    cameras = epiceye.search_camera()
    if not cameras:
        print("Camera not found!")
        return None
    return cameras[0].get("ip")


def _query_one(ip: str) -> bool:
    print(f"---------------get {ip} CameraParameters---------------")
    parameters = epiceye.get_camera_parameters(ip)
    if parameters is None:
        print("get_camera_parameters failed!")
        return False
    print(json.dumps(parameters, indent=2, ensure_ascii=False))

    camera_matrix = epiceye.get_camera_matrix(ip)
    if camera_matrix is None:
        print("get_camera_matrix failed!")
        return False
    print(f"Current depth camera_matrix (3x3 row-major): {list(camera_matrix)}")

    distortion = epiceye.get_distortion(ip)
    if distortion is None:
        print("get_distortion failed!")
        return False
    print(f"Current depth distortion (k1,k2,p1,p2,k3): {list(distortion)}")
    return True


def main() -> int:
    print(f"SDK Version: {epiceye.get_sdk_version()}")
    ip = _resolve_ip()
    if not ip:
        return 1

    return 0 if _query_one(ip) else 1


if __name__ == "__main__":
    raise SystemExit(main())
