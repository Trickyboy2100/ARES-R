import sys
import time
import math
import jkrc

DEG2RAD = math.pi / 180.0
joint_names = ["J1", "J2", "J3", "J4", "J5", "J6"]

ARMS = {
    "left":  "192.168.99.100",
    "right": "192.168.99.101",
}

# ========== 解析参数 ==========
if len(sys.argv) >= 4:
    # 命令行: python3 b5_move.py left/right 关节号 角度
    arm_name = sys.argv[1].lower()
    MOVE_JOINT = int(sys.argv[2])
    MOVE_DEGREE = float(sys.argv[3])
else:
    # 交互式
    arm_name = input("选择手臂 (left/right): ").strip().lower()
    print("可用关节: 0=J1, 1=J2, 2=J3, 3=J4, 4=J5, 5=J6")
    MOVE_JOINT = int(input("输入关节号 (0-5): "))
    MOVE_DEGREE = float(input("输入转动角度 (度): "))

if arm_name not in ARMS:
    print(f"错误: 手臂名必须是 left 或 right，你输入的是 {arm_name}")
    exit()

ip = ARMS[arm_name]
SPEED = 0.1

# ========== 连接机械臂 ==========
print(f"\n连接 {arm_name} 臂 (IP: {ip})...")
robot = jkrc.RC(ip)
ret = robot.login()
ret_code = ret[0] if isinstance(ret, (tuple, list)) else ret
print(f"登录: {'成功' if ret_code == 0 else f'失败 code={ret_code}'}")
if ret_code != 0:
    exit()

# ========== 读当前关节 ==========
ret, current_rad = robot.get_joint_position()
current_deg = [x / DEG2RAD for x in current_rad]

print(f"\n{arm_name.upper()} 臂当前关节(角度):")
for i, name in enumerate(joint_names):
    marker = " ← 要动这个" if i == MOVE_JOINT else ""
    print(f"  {name}: {current_deg[i]:>8.2f}°{marker}")

# ========== 计算目标 ==========
target_deg = list(current_deg)
target_deg[MOVE_JOINT] = current_deg[MOVE_JOINT] + MOVE_DEGREE
target_rad = [x * DEG2RAD for x in target_deg]

print(f"\n{'='*55}")
print(f"  手臂: {arm_name.upper()} 臂")
print(f"  关节: {joint_names[MOVE_JOINT]}")
print(f"  从:   {current_deg[MOVE_JOINT]:.2f}° → {target_deg[MOVE_JOINT]:.2f}°")
print(f"  变化: {MOVE_DEGREE:+.2f}°")
print(f"  速度: {SPEED}")
print(f"{'='*55}")

ans = input("\n确认运动？输入 yes 继续: ")
if ans.strip().lower() != "yes":
    print("已取消")
    robot.logout()
    exit()

# ========== 运动 ==========
print(f"\n开始运动 {joint_names[MOVE_JOINT]}...")
ret = robot.joint_move(target_rad, 0, 1, SPEED)
print(f"运动返回码: {ret}")

ret, after_rad = robot.get_joint_position()
after_deg = [x / DEG2RAD for x in after_rad]
print(f"运动后 {joint_names[MOVE_JOINT]}: {after_deg[MOVE_JOINT]:.2f}°")
print(f"实际变化: {after_deg[MOVE_JOINT] - current_deg[MOVE_JOINT]:+.2f}°")

time.sleep(2)

# ========== 回位 ==========
print(f"\n回到原位置...")
ret = robot.joint_move(list(current_rad), 0, 1, SPEED)
print(f"回位返回码: {ret}")

ret, final_rad = robot.get_joint_position()
final_deg = [x / DEG2RAD for x in final_rad]
print(f"回位后 {joint_names[MOVE_JOINT]}: {final_deg[MOVE_JOINT]:.2f}°")

robot.logout()
print(f"\n✅ {arm_name.upper()} 臂完成，已退出登录")
