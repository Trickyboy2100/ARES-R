#!/bin/bash
PYTHONPATH="/home/yikun/ws/JAKA/SDK V2.1.5/Linux/python3/x86_64-linux-gnu" python3 << 'PYEOF'
import sys
from datetime import datetime
import jkrc

C_RESET  = "\033[0m"
C_BOLD   = "\033[1m"
C_GREEN  = "\033[92m"
C_RED    = "\033[91m"
C_CYAN   = "\033[96m"
C_GRAY   = "\033[90m"

ARMS = {"left": "192.168.99.100", "right": "192.168.99.101"}

def ok_text(val):
    return f"{C_GREEN}正常{C_RESET}" if val == 0 else f"{C_RED}异常{C_RESET}"

def read_arm(name, ip):
    print(f"\n{C_BOLD}{C_CYAN}===== {name.upper()} 臂  (IP: {ip}) ====={C_RESET}")

    robot = jkrc.RC(ip)
    ret = robot.login()
    ret_code = ret[0] if isinstance(ret, (tuple, list)) else ret
    if ret_code != 0:
        print(f"  {C_RED}登录失败 code={ret_code}{C_RESET}")
        return

    # 关节角度
    ret, j = robot.get_joint_position()
    print(f"\n  关节角度(度):")
    print(f"    {'J1':>8} {'J2':>8} {'J3':>8} {'J4':>8} {'J5':>8} {'J6':>8}")
    print(f"    {j[0]:>8.3f} {j[1]:>8.3f} {j[2]:>8.3f} {j[3]:>8.3f} {j[4]:>8.3f} {j[5]:>8.3f}")

    # TCP位姿
    ret, t = robot.get_tcp_position()
    print(f"\n  TCP位姿(mm,度):")
    print(f"    {'X':>8} {'Y':>8} {'Z':>8} {'RX':>8} {'RY':>8} {'RZ':>8}")
    print(f"    {t[0]:>8.2f} {t[1]:>8.2f} {t[2]:>8.2f} {t[3]:>8.2f} {t[4]:>8.2f} {t[5]:>8.2f}")

    # 硬件状态
    ret, s = robot.get_robot_status()
    print(f"\n  硬件状态:")
    print(f"    上电:    {'已上电' if s[2] else '未上电'}")
    print(f"    使能:    {'已使能' if s[3] else '未使能'}")
    print(f"    速度:    {s[4]*100:.0f}%")
    print(f"    碰撞:    {ok_text(s[5])}")
    print(f"    软限位:  {ok_text(s[7])}")
    print(f"    拖拽:    {'开启' if s[6] else '关闭'}")
    print(f"    工具ID:  {s[9]}")

    # 安全状态
    ret, limit = robot.is_on_limit()
    ret, col = robot.is_in_collision()
    print(f"\n  安全状态:")
    print(f"    软限位:  {ok_text(limit)}")
    print(f"    碰撞:    {ok_text(col)}")

    robot.logout()
    print(f"\n  {C_GREEN}已退出登录{C_RESET}")

# 主流程
target = sys.argv[1] if len(sys.argv) > 1 else "all"
print(f"\n{C_BOLD}JAKA双臂状态查看  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{C_RESET}")
print(f"{C_GRAY}只读模式，不会下发运动指令{C_RESET}")

if target in ("all", "left"):
    read_arm("left", ARMS["left"])
if target in ("all", "right"):
    read_arm("right", ARMS["right"])

print(f"\n{C_GREEN}完成{C_RESET}\n")
PYEOF
