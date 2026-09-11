import sys
import time
import math
import threading
import termios
import tty
import jkrc

DEG2RAD = math.pi / 180.0
joint_names = ["J1", "J2", "J3", "J4", "J5", "J6"]
ARMS = {"left": "192.168.99.100", "right": "192.168.99.101"}

# ========== 急停相关 ==========
emergency_stop = False
stop_lock = threading.Lock()

def get_key():
    """读取单个按键，不需要回车"""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

def keyboard_watcher(robot):
    """后台线程：监听空格键，按下就急停"""
    global emergency_stop
    while True:
        try:
            key = get_key()
        except:
            break
        if key == ' ':  # 空格键
            with stop_lock:
                if not emergency_stop:
                    emergency_stop = True
                    print("\n\n" + "="*50)
                    print("  ⚠️  空格键触发急停！")
                    print("="*50 + "\n")
                    try:
                        robot.motion_abort()
                    except Exception as e:
                        print(f"motion_abort调用: {e}")
            break
        time.sleep(0.01)

# ========== 解析参数 ==========
if len(sys.argv) >= 4:
    arm_name = sys.argv[1].lower()
    MOVE_JOINT = int(sys.argv[2])
    MOVE_DEGREE = float(sys.argv[3])
else:
    arm_name = input("选择手臂 (left/right): ").strip().lower()
    print("关节: 0=J1, 1=J2, 2=J3, 3=J4, 4=J5, 5=J6")
    MOVE_JOINT = int(input("关节号: "))
    MOVE_DEGREE = float(input("角度: "))

if arm_name not in ARMS:
    print(f"错误: 手臂名必须是 left 或 right")
    exit()

ip = ARMS[arm_name]
SPEED = 0.1

# ========== 连接 ==========
print(f"\n连接 {arm_name.upper()} 臂 (IP: {ip})...")
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
    marker = " ← 动这个" if i == MOVE_JOINT else ""
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
print(f"\n  🚨 运动过程中按【空格键】可立刻急停！")

ans = input("\n确认运动？输入 yes 继续: ")
if ans.strip().lower() != "yes":
    print("已取消")
    robot.logout()
    exit()

# ========== 启动键盘监听线程 ==========
watcher = threading.Thread(target=keyboard_watcher, args=(robot,), daemon=True)
watcher.start()

# ========== 非阻塞运动 ==========
print(f"\n开始运动 {joint_names[MOVE_JOINT]}... (按空格急停)")
ret = robot.joint_move(target_rad, 0, 0, SPEED)  # 非阻塞
print(f"运动指令返回码: {ret}")

# 轮询等待到位或急停
move_success = False
for _ in range(500):  # 最多等50秒
    with stop_lock:
        if emergency_stop:
            break
    ret, in_pos = robot.is_in_pos()
    if in_pos == 1:
        move_success = True
        break
    time.sleep(0.1)

# ========== 运动结果 ==========
with stop_lock:
    stopped = emergency_stop

if stopped:
    print(f"\n⚠️  运动被空格键急停！")
    ret, after_rad = robot.get_joint_position()
    after_deg = [x / DEG2RAD for x in after_rad]
    print(f"停止时 {joint_names[MOVE_JOINT]}: {after_deg[MOVE_JOINT]:.2f}°")
    print(f"目标位置: {target_deg[MOVE_JOINT]:.2f}°")
    print(f"\n⚠️  急停后不会自动回位，请手动确认机械臂状态")
    print("⚠️  确认安全后，可以重新运行脚本回位")
else:
    if move_success:
        print(f"\n✅ 运动完成！")
    else:
        print(f"\n⚠️  运动超时（50秒未到位）")
    
    ret, after_rad = robot.get_joint_position()
    after_deg = [x / DEG2RAD for x in after_rad]
    print(f"运动后 {joint_names[MOVE_JOINT]}: {after_deg[MOVE_JOINT]:.2f}°")
    print(f"实际变化: {after_deg[MOVE_JOINT] - current_deg[MOVE_JOINT]:+.2f}°")
    
    time.sleep(2)
    
    # 自动回位
    print(f"\n回到原位置...")
    ret = robot.joint_move(list(current_rad), 0, 1, SPEED)
    print(f"回位返回码: {ret}")
    
    ret, final_rad = robot.get_joint_position()
    final_deg = [x / DEG2RAD for x in final_rad]
    print(f"回位后 {joint_names[MOVE_JOINT]}: {final_deg[MOVE_JOINT]:.2f}°")

robot.logout()
print(f"\n✅ {arm_name.upper()} 臂完成，已退出登录")
