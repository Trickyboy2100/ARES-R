"""单功能示例：搜索相机。

功能：打印 SDK 版本，通过 UDP 广播搜索局域网内的 EpicEye 相机，并逐台打印
      序号 / IP / SN / 型号 / 分辨率。

用法：
    python examples/search_camera.py

限制：这是阻塞式一次性搜索，仅用于测试和临时诊断；正式应用应使用持续发现服务。
相机影响：只发送/接收发现报文，不修改设备。
"""

import epiceye


def main() -> int:
    print(f"SDK Version: {epiceye.get_sdk_version()}")
    print("---------------search EpicEye camera---------------")

    camera_list = epiceye.search_camera()
    if not camera_list:
        print("Camera not found!")
        return 1

    print(f"Camera found: {len(camera_list)}")
    for i, cam in enumerate(camera_list):
        # search_camera 返回的 dict 键：ip / sn / model / alias / width / height
        ip = cam.get("ip", "")
        sn = cam.get("sn", "")
        model = cam.get("model", "")
        w = cam.get("width", "?")
        h = cam.get("height", "?")
        print(f"{i:>3}: {ip:<22}{sn:<30} {model} {w}x{h}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
