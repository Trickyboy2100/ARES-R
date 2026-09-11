"""持续发现服务示例。

作用：注册发现事件，启动常驻监听，实时输出在线相机列表；按 Enter 后停止并清理回调。
区别：search_camera 是阻塞式一次性测试，本示例适合应用程序长期维护设备列表。
相机影响：只监听发现广播，不修改相机。
"""

import epiceye


def on_updated() -> None:
    camera_list = epiceye.get_discovered_cameras()
    print(f"\n[Updated] Camera count: {len(camera_list)}")
    for i, camera in enumerate(camera_list):
        ip = camera.get("ip", "")
        sn = camera.get("sn", "")
        model = camera.get("model", "")
        print(f"{i:>3}: {ip:<22}{sn:<30} {model}")


def main() -> int:
    print(f"SDK Version: {epiceye.get_sdk_version()}")
    print("---------------EpicEye Continuous Discovery---------------")

    epiceye.set_discovery_callback(on_updated)
    epiceye.start_discovery()
    print("Continuous discovery started. Listening for cameras...")
    print("Press Enter to stop.\n")

    try:
        input()
    except (EOFError, KeyboardInterrupt):
        pass

    epiceye.stop_discovery()
    print("Continuous discovery stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
