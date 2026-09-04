import json
from datetime import datetime
import jkrc

robot = jkrc.RC('192.168.99.100')
ret = robot.login()
ret_code = ret[0] if isinstance(ret, (tuple, list)) else ret
print(f"登录返回码: {ret_code}")
if ret_code != 0:
    print("登录失败！")
    exit()
print("登录成功！")

result = {"time": datetime.now().isoformat(), "ip": "192.168.99.100"}

# 1. 关节角度
ret, joints = robot.get_joint_position()
result["joint_degree"] = joints
print("\n" + "="*50)
print("  左臂关节角度 (度)")
print("="*50)
names = ["J1", "J2", "J3", "J4", "J5", "J6"]
for name, val in zip(names, joints):
    print(f"  {name}: {val:>10.3f}")

# 2. TCP位姿
ret, tcp = robot.get_tcp_position()
result["tcp_pose"] = tcp
print("\n" + "="*50)
print("  左臂TCP位姿 (mm, 度)")
print("="*50)
tcp_names = ["X", "Y", "Z", "RX", "RY", "RZ"]
for name, val in zip(tcp_names, tcp):
    print(f"  {name}: {val:>10.3f}")

# 3. 机械臂状态（修正：直接用status_raw，不取[0]）
ret, status_raw = robot.get_robot_status()
result["status_raw"] = str(status_raw)
s = status_raw

status_map = [
    ("错误码",       s[0],  "0=正常"),
    ("是否到位",     s[1],  "1=已到位"),
    ("是否上电",     s[2],  "1=已上电"),
    ("是否使能",     s[3],  "1=已使能"),
    ("速度倍率",     s[4],  "0.7=70%"),
    ("碰撞保护",     s[5],  "0=正常,1=触发"),
    ("拖拽模式",     s[6],  "0=关闭,1=开启"),
    ("软限位触发",   s[7],  "0=正常,1=触发"),
    ("用户坐标系ID", s[8],  ""),
    ("工具ID",       s[9],  ""),
]
result["status_parsed"] = {name: val for name, val, _ in status_map}

print("\n" + "="*50)
print("  左臂硬件状态")
print("="*50)
for name, val, desc in status_map:
    print(f"  {name:<10}: {str(val):<6} {desc}")

# 4. 限位
ret, limit = robot.is_on_limit()
result["is_on_limit"] = limit
print("\n" + "="*50)
print(f"  软限位: {'触发' if limit else '正常'} (code={limit})")

# 5. 碰撞
ret, col = robot.is_in_collision()
result["is_in_collision"] = col
print(f"  碰撞保护: {'触发' if col else '正常'} (code={col})")

robot.logout()
print("\n" + "="*50)
print("  读取完成，已退出登录")
print("="*50)

filename = f"left_arm_baseline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
with open(filename, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(f"\n基线已保存: {filename}")
