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
SERVO_PERIOD = 0.008

G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; C = "\033[96m"; B = "\033[1m"; N = "\033[0m"

emergency_stop = False
stop_lock = threading.Lock()

def get_key():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return ch

def keyboard_watcher(robot):
    global emergency_stop
    while True:
        try:
            key = get_key()
        except:
            break
        if key == ' ':
            with stop_lock:
                if not emergency_stop:
                    emergency_stop = True
                    print(f"\n\n{Y}{B}  ⚠️  空格键触发急停！{N}\n")
                    try:
                        robot.motion_abort()
                    except:
                        pass
            break
        time.sleep(0.005)

def interactive_input():
    print(f"\n{B}{C}=== JAKA servo_j 连续伺服 ==={N}")
    while True:
        arm_name = input("\n选择手臂 (left/right): ").strip().lower()
        if arm_name in ARMS:
            break
        print("  请输入 left 或 right")
    print("\n关节: 0=J1  1=J2  2=J3  3=J4  4=J5  5=J6")
    while True:
        c = input("关节号: ").strip()
        if c.isdigit() and 0 <= int(c) <= 5:
            joint = int(c)
            break
    while True:
        c = input("转动角度(度): ").strip()
        try:
            deg = float(c)
            if deg != 0:
                break
        except:
            pass
    print("\n速度: 1=5°/s  2=10°/s  3=20°/s")
    c = input("选择(默认2): ").strip()
    speed = {1:5.0, 2:10.0, 3:20.0}.get(int(c) if c.isdigit() else 2, 10.0)
    return arm_name, joint, deg, speed

if len(sys.argv) >= 4:
    arm_name = sys.argv[1].lower()
    MOVE_JOINT = int(sys.argv[2])
    MOVE_DEGREE = float(sys.argv[3])
    MOVE_SPEED = 10.0
else:
    arm_name, MOVE_JOINT, MOVE_DEGREE, MOVE_SPEED = interactive_input()

if arm_name not in ARMS:
    print("错误: 手臂名必须是 left 或 right")
    exit()

ip = ARMS[arm_name]

# ========== 连接 + 自动使能 ==========
print(f"\n连接 {B}{arm_name.upper()}{N} 臂 (IP: {ip})...")
robot = jkrc.RC(ip)
ret = robot.login()
rc = ret[0] if isinstance(ret, (tuple, list)) else ret
print(f"登录: {G+'成功' if rc==0 else R+f'失败 code={rc}'}{N}")
if rc != 0:
    exit()

# ★ 自动使能机械臂
print("使能机械臂...")
ret = robot.enable_robot()
print(f"使能返回: {ret}")
time.sleep(1.5)  # 等使能完成

# 确认使能状态
ret, status = robot.get_robot_status()
print(f"状态: 上电={status[2]} 使能={status[3]}")
if status[3] != 1:
    print(f"{R}错误: 机械臂未使能，无法运动{N}")
    robot.logout()
    exit()

# ========== 读当前关节 ==========
ret, current_rad = robot.get_joint_position()
current_deg = [x / DEG2RAD for x in current_rad]

print(f"\n{B}当前关节(角度):{N}")
print(f"  {'J1':>8} {'J2':>8} {'J3':>8} {'J4':>8} {'J5':>8} {'J6':>8}")
print(f"  {current_deg[0]:>8.2f} {current_deg[1]:>8.2f} {current_deg[2]:>8.2f} {current_deg[3]:>8.2f} {current_deg[4]:>8.2f} {current_deg[5]:>8.2f}")

# ========== 计算目标 ==========
target_deg = list(current_deg)
target_deg[MOVE_JOINT] += MOVE_DEGREE
target_rad = [x * DEG2RAD for x in target_deg]

duration = abs(MOVE_DEGREE) / MOVE_SPEED
steps = max(10, int(duration / SERVO_PERIOD))

print(f"\n{B}{C}{'='*50}{N}")
print(f"  手臂:   {arm_name.upper()} 臂")
print(f"  关节:   {joint_names[MOVE_JOINT]}")
print(f"  从:     {current_deg[MOVE_JOINT]:.2f}° → {target_deg[MOVE_JOINT]:.2f}°")
print(f"  变化:   {MOVE_DEGREE:+.2f}°")
print(f"  速度:   {MOVE_SPEED}°/秒")
print(f"  时间:   {duration:.2f}秒")
print(f"  帧数:   {steps} 帧 ({SERVO_PERIOD*1000:.0f}ms/帧)")
print(f"{B}{C}{'='*50}{N}")
print(f"\n  {Y}🚨 运动中按【空格键】立刻急停！{N}")

ans = input("\n确认运动？输入 yes: ")
if ans.strip().lower() != "yes":
    print("已取消")
    robot.logout()
    exit()

# ========== 伺服运动函数 ==========
def servo_move(robot, start, end, n, label):
    global emergency_stop

    print(f"\n[{label}] 进入伺服模式...")
    robot.servo_move_enable(True)
    time.sleep(0.3)  # 等伺服模式就绪

    ok = False
    sent = 0
    t0 = time.time()

    try:
        delta = [(end[i] - start[i]) / n for i in range(6)]
        deadline = time.time() + SERVO_PERIOD

        for i in range(n):
            with stop_lock:
                if emergency_stop:
                    print(f"\n[{label}] {Y}急停，第{i}/{n}帧停止{N}")
                    break

            ret, lim = robot.is_on_limit()
            if lim:
                print(f"\n[{label}] {R}限位触发，停止！{N}")
                break
            ret, col = robot.is_in_collision()
            if col:
                print(f"\n[{label}] {R}碰撞触发，停止！{N}")
                break

            tgt = [start[j] + delta[j] * (i + 1) for j in range(6)]
            ret = robot.servo_j(tgt, 1)  # 2个参数
            rc = ret[0] if isinstance(ret, (tuple, list)) else ret
            if rc != 0:
                print(f"\n[{label}] {R}servo_j失败 第{i}帧: {ret}{N}")
                break

            sent += 1

            rem = deadline - time.time()
            if rem > 0:
                time.sleep(rem)
            elif rem < -SERVO_PERIOD:
                print(f"\n[{label}] {Y}周期超时 第{i}帧: {-rem*1000:.1f}ms{N}")
            deadline += SERVO_PERIOD
        else:
            ok = True

    finally:
        print(f"[{label}] 退出伺服模式...")
        try:
            robot.servo_move_enable(False)
        except:
            pass

    elapsed = time.time() - t0
    if sent > 0:
        fps = sent / elapsed
        print(f"\n[{label}] {B}📊 帧率:{N}")
        print(f"  发送: {sent}/{n} 帧")
        print(f"  耗时: {elapsed*1000:.1f} ms")
        print(f"  每帧: {elapsed/sent*1000:.2f} ms")
        print(f"  帧率: {fps:.1f} 帧/秒 (理论125)")

    if ok:
        print(f"[{label}] {G}✅ 完成{N}")
    return ok

# ========== 启动键盘监听 ==========
watcher = threading.Thread(target=keyboard_watcher, args=(robot,), daemon=True)
watcher.start()

# ========== 去程 ==========
move_ok = servo_move(robot, current_rad, target_rad, steps, "去程")

ret, after_rad = robot.get_joint_position()
after_deg = [x / DEG2RAD for x in after_rad]
print(f"\n运动后 {joint_names[MOVE_JOINT]}: {after_deg[MOVE_JOINT]:.2f}° (变化 {after_deg[MOVE_JOINT]-current_deg[MOVE_JOINT]:+.2f}°)")

# ========== 回位 ==========
with stop_lock:
    stopped = emergency_stop

if stopped:
    print(f"\n{Y}⚠️  急停后不自动回位，请手动确认{N}")
elif move_ok:
    time.sleep(1)
    print(f"\n开始回位...")
    servo_move(robot, target_rad, current_rad, steps, "回程")
    ret, final_rad = robot.get_joint_position()
    final_deg = [x / DEG2RAD for x in final_rad]
    print(f"\n回位后 {joint_names[MOVE_JOINT]}: {final_deg[MOVE_JOINT]:.2f}°")
else:
    print(f"\n{Y}⚠️  运动未完成，不自动回位{N}")

robot.logout()
print(f"\n{G}✅ {arm_name.upper()} 臂完成，已退出登录{N}\n")
