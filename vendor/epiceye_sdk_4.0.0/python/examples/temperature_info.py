"""单功能示例：读取相机内部温度信息（V4）。

用法：
    python examples/temperature_info.py [ip]

输出键由具体相机型号决定，业务代码不应写死传感器名称。
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


def main() -> int:
    ip = _resolve_ip()
    if not ip:
        return 1

    print(f"Camera: {ip}")
    temperature_info = epiceye.get_temperature_info(ip)
    if temperature_info is None:
        print("get_temperature_info failed")
        return 1

    for key, value in temperature_info.items():
        display_value = "N/A" if value is None else value
        unit = " °C" if key.endswith("_celsius") and value is not None else ""
        print(f"{key}: {display_value}{unit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
