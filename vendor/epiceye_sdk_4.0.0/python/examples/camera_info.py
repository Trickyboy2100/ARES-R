"""单功能示例：相机信息查询。

功能：对指定相机调用 get_info 打印基础信息，并调用
      get_reconstructor_type 探测重建器类型（V4 相机）。

用法：
    python examples/camera_info.py [ip]
    ip 可省略；省略时自动搜索并查询第一台相机。

相机影响：只读，不触发拍摄，不修改配置。
"""

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


def _normalize_info(info):
    """V4 相机返回 {"status":0,"data":{...}}，取内层 data；V3 直接是裸 dict。"""
    if isinstance(info, dict) and isinstance(info.get("data"), dict):
        return info["data"]
    return info


def _query_one(ip: str) -> bool:
    print(f"---------------get {ip} EpicEyeInfo---------------")
    info = _normalize_info(epiceye.get_info(ip))
    if info is None:
        print("getInfo failed!")
        return False
    print(f"SN        : {info.get('sn')}")
    print(f"IP        : {info.get('ip')}")
    print(f"Version   : {info.get('version')}")
    print(f"model     : {info.get('model')}")
    print(f"alias     : {info.get('alias')}")
    print(f"resolution: {info.get('width')}x{info.get('height')}")

    rec_type = epiceye.get_reconstructor_type(ip)
    if rec_type is not None:
        # 0=Mono 1=BinoWithoutColor 2=BinoWithColor 999=Unknown
        print(f"ReconstructorType: {rec_type}")
    return True


def main() -> int:
    print(f"SDK Version: {epiceye.get_sdk_version()}")
    ip = _resolve_ip()
    if not ip:
        return 1

    return 0 if _query_one(ip) else 1


if __name__ == "__main__":
    raise SystemExit(main())
