"""单功能示例：相机配置读写。

功能：依次演示 get_config / get_parameter_list / get_config_style（仅前 500 字符）/
      set_config（原样回写验证）/ set_parameter（切换到参数列表首个预设）。

用法：
    python examples/camera_config.py [ip]
    ip 可省略；省略时自动搜索并使用第一台相机。

相机影响：会原样回写当前配置，并切换到参数列表中的首个预设；运行前应确认允许切换参数。
"""

import json
import sys
from dataclasses import asdict
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

    print(f"---------------getConfig ({ip})---------------")
    config = epiceye.get_config(ip)
    if config is None:
        print("getConfig failed!")
        return 1
    print(json.dumps(config, indent=2, ensure_ascii=False))

    print(f"---------------getParameterList ({ip})---------------")
    parameter_list = epiceye.get_parameter_list(ip)
    if parameter_list is None:
        print("getParameterList failed!")
        return 1
    print(json.dumps([asdict(preset) for preset in parameter_list], indent=2, ensure_ascii=False))

    print(f"---------------getConfigStyle ({ip})---------------")
    style = epiceye.get_config_style(ip)
    if style is None:
        print("getConfigStyle failed!")
        return 1
    else:
        # 样式数据较长，仅展示前 500 个字符
        print(json.dumps(style, indent=2, ensure_ascii=False)[:500])

    print(f"---------------setConfig ({ip})---------------")
    if epiceye.set_config(ip, config):
        print("setConfig success!")
    else:
        print("setConfig failed!")
        return 1

    print(f"---------------setParameter ({ip})---------------")
    if not parameter_list:
        print("setParameter failed: parameter list is empty")
        return 1
    first_preset = parameter_list[0]
    print(f"selecting param: {first_preset.Name} ({first_preset.Id})")
    if epiceye.set_parameter(ip, first_preset.Id):
        print("setParameter success!")
    else:
        print("setParameter failed!")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
