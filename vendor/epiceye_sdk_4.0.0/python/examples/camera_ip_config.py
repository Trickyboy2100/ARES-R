"""单功能示例：相机 IP 配置下发。

功能：识别目标相机，然后通过 UDP 目标单播和组播兼容路径下发 IP 配置。
      不传参数时仅列出当前相机并打印用法。

用法：
    python examples/camera_ip_config.py <targetIP> [newIP] [netMask] [DHCP|Manual]

示例：
    切 DHCP :  python examples/camera_ip_config.py 192.168.1.100
    手动 IP :  python examples/camera_ip_config.py 192.168.1.100 192.168.1.200 255.255.255.0 Manual

相机影响：会修改网络配置，旧 IP 可能立即失效。接口只表示报文已发送，需重新搜索验证结果。
"""

import sys

import epiceye


def _host(endpoint: str) -> str:
    return endpoint.split(":", maxsplit=1)[0]


def main() -> int:
    print(f"SDK Version: {epiceye.get_sdk_version()}")
    print("---------------Camera IP Config---------------")

    specified_target_ip = _host(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] else None
    camera_list = epiceye.search_camera()
    if not camera_list:
        print("Camera not found!")
        # 即使搜不到也允许继续（目标 IP 已知时可直接下发）
    else:
        print(f"Camera found: {len(camera_list)}")
        for i, cam in enumerate(camera_list):
            print(f"{i:>3}: {cam.get('ip', ''):<22}{cam.get('sn', ''):<30}")

    if specified_target_ip is None:
        prog = "examples/camera_ip_config.py"
        print()
        print(f"Usage: python {prog} <targetIP> [newIP] [netMask] [DHCP|Manual]")
        print(f"Example (DHCP):   python {prog} 192.168.1.100")
        print(f"Example (Manual): python {prog} 192.168.1.100 192.168.1.200 255.255.255.0 Manual")
        print()
        print("No target IP given; showing current cameras only.")
        return 0

    target_ip = specified_target_ip
    new_ip = sys.argv[2] if len(sys.argv) >= 3 else None
    netmask = sys.argv[3] if len(sys.argv) >= 4 else "255.255.255.0"
    ip_type = sys.argv[4] if len(sys.argv) >= 5 else "DHCP"

    print(f"DestinationIP: {target_ip}")
    target_camera = next(
        (camera for camera in camera_list or [] if _host(camera.get("ip", "")) == target_ip),
        None,
    )
    if target_camera is None:
        target_camera = epiceye.get_info(f"{target_ip}:5000")

    target_sn = target_camera.get("sn", "") if target_camera else ""
    if not target_sn or "EpicEyeSN" in target_sn:
        print(
            "Cannot identify the target camera. "
            "Confirm that the target IP is reachable or discoverable, then retry."
        )
        return 1

    print(f"Target camera SN: {target_sn}")
    print(f"Config: type={ip_type} ip={new_ip} netMask={netmask}")

    ok = epiceye.set_epiceye_ip_config(
        ip=target_ip, new_ip=new_ip, netmask=netmask, ip_type=ip_type, sn=target_sn
    )
    if not ok:
        print("setEpicEyeIPConfig request could not be sent.")
        return 1

    print("setEpicEyeIPConfig request sent (UDP has no ack; verify the new address by rediscovery).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
