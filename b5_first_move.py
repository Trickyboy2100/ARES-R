import time
import math
import jkrc

DEG2RAD = math.pi / 180.0  # 角度转弧度

robot = jkrc.RC('192.168.99.100')
ret = robot.login()
ret_code = ret[0] if isinstance(ret, (tuple, list)) else ret
print(f"登录: {'成功' if ret_code == 0 else f'失败 code={ret_code}'}")
if ret_code != 0:
    exit()

# 读当前关节（弧度）
ret, current_rad = robot.get_joint_position()
current_deg = [x / DEG2RAD for x in current_rad]
print(f"\n当前关节:")
print(f"  弧度: {[round(x,4) for x in current_rad]}")
print(f"  角度: {[round(x,2) for x in current_deg]}")

# 目标：J4增加5度（先转成弧度）
target_deg = list(current_deg)
target_deg[3] = current_deg[3] + 20.0  # J4微动5度
target_rad = [x * DEG2RAD for x in target_deg]

print(f"\n目标关节:")
print(f"  弧度: {[round(x,4) for x in target_rad]}")
print(f"  角度: {[round(x,2) for x in target_deg]}")
print(f"  J4变化: +5.00度")

print(f"\n⚠️  即将运动：J4从 {current_deg[3]:.2f}° 动到 {target_deg[3]:.2f}°（+5度）")
print(f"⚠️  其他关节不动")
print(f"⚠️  速度倍率请保持在低位")
ans = input("\n确认运动？输入 yes 继续，其他取消: ")
if ans.strip().lower() != "yes":
    print("已取消")
    robot.logout()
    exit()

# 运动（传入弧度！速度0.1）
print("\n开始运动...")
ret = robot.joint_move(target_rad, 0, 1, 0.1)  # 目标(弧度), 绝对, 阻塞, 速度
print(f"运动返回码: {ret}")

# 读运动后关节
ret, after_rad = robot.get_joint_position()
after_deg = [x / DEG2RAD for x in after_rad]
print(f"\n运动后关节:")
print(f"  弧度: {[round(x,4) for x in after_rad]}")
print(f"  角度: {[round(x,2) for x in after_deg]}")
print(f"  J4实际变化: {after_deg[3] - current_deg[3]:.2f}度")

time.sleep(2)

# 回到原位置（传入弧度）
print("\n回到原位置...")
ret = robot.joint_move(list(current_rad), 0, 1, 0.1)
print(f"回位返回码: {ret}")

ret, final_rad = robot.get_joint_position()
final_deg = [x / DEG2RAD for x in final_rad]
print(f"\n最终关节(角度): {[round(x,2) for x in final_deg]}")

robot.logout()
print("\n✅ 首次微动完成，已退出登录")
