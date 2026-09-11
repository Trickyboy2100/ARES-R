#!/usr/bin/env python3
# B1 只读状态基线采集脚本（严禁写入/使能/移动）

import json
import sys
from pathlib import Path
from datetime import datetime

# 将 src 目录加入 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# ------------------------------------------------------------
# 【重要】请根据 src/ares_r/adapters/jaka_servo.py 中的实际类名修改
# 如果类名是 JakaArm，请把下面的 JakaServo 改为 JakaArm
# ------------------------------------------------------------
from ares_r.adapters.jaka_servo import JakaServo  

# 读取系统配置，获取左右臂 IP
config_path = Path("/home/yikun/ARES-R/config/system.json")
with open(config_path) as f:
    config = json.load(f)

# 假设配置文件结构中有 arms.left.ip 和 arms.right.ip
# （如果路径不同，请根据实际 system.json 调整）
left_ip = config.get("arms", {}).get("left", {}).get("ip", "192.168.1.1")
right_ip = config.get("arms", {}).get("right", {}).get("ip", "192.168.1.2")

print(f"[INFO] 左臂 IP: {left_ip}")
print(f"[INFO] 右臂 IP: {right_ip}")

# 初始化左右臂适配器（仅建立只读连接，绝不调用 enable 或 move）
left_arm = JakaServo(left_ip)
right_arm = JakaServo(right_ip)

# ------------------------------------------------------------
# 采集左臂数据（只调用 B1 规定的只读函数）
# ------------------------------------------------------------
left_data = {
    "arm": "left",
    "ip": left_ip,
    "sdk_version": left_arm.get_sdk_version(),
    "robot_status": left_arm.get_robot_status(),
    "joint_position": left_arm.get_joint_position(),
    "tcp_position": left_arm.get_tcp_position(),
    "is_on_limit": left_arm.is_on_limit(),
    "is_in_collision": left_arm.is_in_collision(),
}

# ------------------------------------------------------------
# 采集右臂数据
# ------------------------------------------------------------
right_data = {
    "arm": "right",
    "ip": right_ip,
    "sdk_version": right_arm.get_sdk_version(),
    "robot_status": right_arm.get_robot_status(),
    "joint_position": right_arm.get_joint_position(),
    "tcp_position": right_arm.get_tcp_position(),
    "is_on_limit": right_arm.is_on_limit(),
    "is_in_collision": right_arm.is_in_collision(),
}

# ------------------------------------------------------------
# 组装完整基线快照（含时间戳和额外元信息）
# ------------------------------------------------------------
baseline = {
    "timestamp": datetime.now().isoformat(),
    "left": left_data,
    "right": right_data,
}

# 打印到屏幕（方便肉眼确认）
print("\n" + "=" * 60)
print("BASELINE SNAPSHOT")
print(json.dumps(baseline, indent=2, default=str))
print("=" * 60)

# ------------------------------------------------------------
# 保存到 worklog 目录（留痕、可追溯）
# ------------------------------------------------------------
output_dir = Path("/home/yikun/ARES-R/worklog")
output_dir.mkdir(parents=True, exist_ok=True)
output_file = output_dir / f"baseline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
with open(output_file, "w") as f:
    json.dump(baseline, f, indent=2, default=str)

print(f"\n[SUCCESS] 基线已保存至: {output_file}")
