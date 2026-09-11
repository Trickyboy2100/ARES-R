"""单功能示例：线扫流程。

功能：查询线扫状态 -> 启动线扫 -> 阻塞等待完成；若超时则手动停止；
      最后再查一次最终状态。

用法：
    python examples/line_scan.py [ip]
    ip 可省略；省略时自动搜索并使用第一台相机。

清理规则：正常完成后不主动停止；只有超时或异常才调用 stop_line_scan。
相机影响：会启动真实线扫运动/采集，仅适用于已配置为线扫模式的设备。
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


def main() -> int:
    print(f"SDK Version: {epiceye.get_sdk_version()}")
    ip = _resolve_ip()
    if not ip:
        return 1

    print("---------------getLineScanStatus---------------")
    status = epiceye.get_line_scan_status(ip)
    if status is None:
        print("getLineScanStatus failed!")
        return 1
    print(f"status: {status}")

    print("\n---------------startLineScan---------------")
    started = epiceye.start_line_scan(ip, enable_texture=True, defer_epic_raw_save=True)
    if started is None:
        print("startLineScan failed!")
        return 1
    print(f"startLineScan success! {started}")

    print("\n---------------waitLineScanCompletion---------------")
    if epiceye.wait_line_scan_completion(ip, timeout_ms=60000):
        print("LineScan completed!")
    else:
        print("waitLineScanCompletion timed out!")
        print("\n---------------stopLineScan---------------")
        stop_status = epiceye.stop_line_scan(ip)
        print(f"stopLineScan status: {stop_status}")
        return 1

    print("\n---------------getLineScanStatus (final)---------------")
    final = epiceye.get_line_scan_status(ip)
    if final is not None:
        print(f"status: {final}")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
