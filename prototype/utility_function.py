import numpy as np
import sys
sys.path.insert(0, '/home/yikun/ws/SDK V2.1.5/Linux/python3/x86_64-linux-gnu')
import jkrc
import time
import rospy
from std_msgs.msg import Float64MultiArray, Header
from scipy.spatial.transform import Rotation


def se3_average(pose_list):
    """
    计算SE(3)流形上的位姿平均

    参数:
        pose_list: 包含4x4齐次变换矩阵的列表

    返回:
        avg_pose: 平均后的4x4齐次变换矩阵
    """
    if not pose_list:
        rospy.logwarn("位姿列表为空！")
        return np.eye(4)

    # 分离旋转和平移分量
    rotations = []
    translations = []

    for pose in pose_list:
        # 确保是4x4矩阵
        if pose.shape != (4, 4):
            rospy.logerr(f"无效的位姿矩阵形状: {pose.shape}，应为(4, 4)")
            continue

        # 提取旋转部分 (3x3)
        R = pose[:3, :3]
        # 提取平移部分 (3,)
        t = pose[:3, 3]

        rotations.append(R)
        translations.append(t)

    # 1. 计算旋转平均 (在SO(3)流形上)
    # 转换为Rotation对象
    rot_objects = [Rotation.from_matrix(R) for R in rotations]

    # 转换为四元数表示 (N x 4)
    quats = np.array([r.as_quat() for r in rot_objects])

    # 计算平均四元数
    avg_quat = np.mean(quats, axis=0)

    # 归一化平均四元数
    avg_quat /= np.linalg.norm(avg_quat)

    # 转换为旋转矩阵
    avg_rotation = Rotation.from_quat(avg_quat).as_matrix()

    # 2. 计算平移平均
    # 更精确的方法：将平移转换到平均旋转的坐标系下
    translations_arr = np.array(translations)

    # 方法1：直接算术平均 (当旋转变化不大时效果良好)
    # avg_translation = np.mean(translations_arr, axis=0)

    # 方法2：在平均旋转坐标系下计算平移 (更精确)
    aligned_translations = []
    for R, t in zip(rotations, translations):
        # 计算当前旋转到平均旋转的变换
        R_diff = avg_rotation @ R.T
        # 将平移转换到平均旋转坐标系
        t_aligned = R_diff @ t
        aligned_translations.append(t_aligned)

    avg_translation = np.mean(aligned_translations, axis=0)

    # 3. 构建平均位姿矩阵
    avg_pose = np.eye(4)
    avg_pose[:3, :3] = avg_rotation
    avg_pose[:3, 3] = avg_translation

    return avg_pose


class ArucoTracker_Left:
    """
    Aruco码跟踪器类，用于控制机械臂跟随Aruco码

    功能:
    - 根据Aruco码位置调整机械臂位置
    - 支持X/Y/Z轴移动
    - 可配置移动速度和阈值

    参数:
        robot: 机械臂控制对象
        max_xy_error: X/Y轴最大允许误差(mm)
        max_z: Z轴最大允许距离(mm)
    """

    def __init__(self, robot, max_xy_error=2.0, max_z=90, fast_vel=100, medium_vel=100, slow_vel=100,
                 fast_duration=1.5, medium_duration=1.0, slow_duration=0.5):
        self.robot = robot
        self.max_xy_error = max_xy_error
        self.max_z = max_z

        # 移动速度配置
        self.fast_vel = fast_vel
        self.medium_vel = medium_vel
        self.slow_vel = slow_vel

        # 移动时间配置
        self.fast_duration = fast_duration
        self.medium_duration = medium_duration
        self.slow_duration = slow_duration

        rospy.loginfo("Aruco跟踪器初始化完成")

    def center_aruco(self, pose, z_final):
        """
        根据Aruco码位姿调整机械臂位置，使其居中

        参数:
            pose: Aruco码位姿矩阵(4x4)

        返回:
            bool: 是否成功居中
        """
        # 提取位姿分量
        x = pose[0, 3]
        y = pose[1, 3]
        z = pose[2, 3]

        rospy.loginfo(f"Aruco码当前位置: x={x:.3f}, y={y:.3f}, z={z:.3f}")

        if abs(x) <= self.max_xy_error and abs(y) <= self.max_xy_error and z <= self.max_z:
            return True

        # 处理X轴偏移
        if abs(x) > self.max_xy_error:
            self._adjust_axis('x', x)

        # 处理Y轴偏移
        if abs(y) > self.max_xy_error:
            self._adjust_axis('y', y)

        # 处理Z轴偏移
        if z > self.max_z:
            self._adjust_z(z, z_final)


        return False

    def _adjust_axis(self, axis, error):
        """
        调整单轴位置

        参数:
            axis: 调整轴 ('x' 或 'y')
            error: 当前误差值
        """
        axis_num = 0 if axis == 'x' else 1
        abs_error = abs(error)

        # 根据误差大小选择速度和移动时间
        if abs_error > 10:
            vel = self.fast_vel
            duration = self.fast_duration
            move_cmd = -abs_error if error > 0 else abs_error
        elif abs_error > 5:
            vel = self.medium_vel
            duration = self.medium_duration
            move_cmd = -abs_error if error > 0 else abs_error
        else:
            vel = self.slow_vel
            duration = self.slow_duration
            move_cmd = -abs_error if error > 0 else abs_error

        rospy.loginfo(f"调整{axis}轴: 误差={error:.3f}, 速度={vel}, 时间={duration:.1f}s")

        # 执行移动
        self.robot.jog(aj_num=axis_num, move_mode=1, coord_type=2,
                       jog_vel=vel, pos_cmd=move_cmd)
        in_pos = self.robot.is_in_pos()[1]
        while(not in_pos):
            time.sleep(0.1)
            in_pos = self.robot.is_in_pos()[1]
            print(in_pos)
        time.sleep(0.5)  # 等待稳定

    def _adjust_z(self, z, z_final):
        """
        调整Z轴位置

        参数:
            z: 当前Z值
        """
        if z > self.max_z + 10:
            move_cmd = z - (self.max_z + 8)
            vel = self.fast_vel
            duration = self.fast_duration
                    # 执行移动
            self.robot.jog(aj_num=2, move_mode=1, coord_type=2,
                       jog_vel=vel, pos_cmd=move_cmd)
            in_pos = self.robot.is_in_pos()[1]
            while(not in_pos):
                time.sleep(0.1)
                in_pos = self.robot.is_in_pos()[1]
                print(in_pos)
            self.robot.jog_stop(-1)
            time.sleep(0.5)  # 等待稳定
        else:
            # move_cmd = 3
            # vel = self.medium_vel
            # duration = self.medium_duration
            #print("zding")
            tcp = self.robot.get_tcp_position()[1]
            tcp[2] = z_final
            ret = self.robot.linear_move(tcp, 0, True, 100)

        rospy.loginfo(f"调整Z轴: z={z:.3f}")

        # 执行移动
        # self.robot.jog(aj_num=2, move_mode=1, coord_type=2,
        #                jog_vel=vel, pos_cmd=move_cmd)
        # time.sleep(duration)
        # self.robot.jog_stop(-1)
        # time.sleep(0.5)  # 等待稳定



class ArucoTracker_Right:
    """
    Aruco码跟踪器类，用于控制机械臂跟随Aruco码

    功能:
    - 根据Aruco码位置调整机械臂位置
    - 支持X/Y/Z轴移动
    - 可配置移动速度和阈值

    参数:
        robot: 机械臂控制对象
        max_xy_error: X/Y轴最大允许误差(mm)
        max_z: Z轴最大允许距离(mm)
    """

    def __init__(self, robot, max_xy_error=1.0, max_z=90, fast_vel=200, medium_vel=200, slow_vel=200,
                 fast_duration=1.5, medium_duration=1.0, slow_duration=0.5):
        self.robot = robot
        self.max_xy_error = max_xy_error
        self.max_z = max_z

        # 移动速度配置
        self.fast_vel = fast_vel
        self.medium_vel = medium_vel
        self.slow_vel = slow_vel

        # 移动时间配置
        self.fast_duration = fast_duration
        self.medium_duration = medium_duration
        self.slow_duration = slow_duration

        rospy.loginfo("Aruco跟踪器初始化完成")

    def center_aruco(self, pose, z_final):
        """
        根据Aruco码位姿调整机械臂位置，使其居中

        参数:
            pose: Aruco码位姿矩阵(4x4)

        返回:
            bool: 是否成功居中
        """
        # 提取位姿分量
        x = pose[0, 3]
        y = pose[1, 3]
        z = pose[2, 3]

        rospy.loginfo(f"Aruco码当前位置: x={x:.3f}, y={y:.3f}, z={z:.3f}")

        if abs(x) <= self.max_xy_error and abs(y) <= self.max_xy_error and z <= self.max_z:
            return True

        # 处理X轴偏移
        if abs(x) > self.max_xy_error:
            self._adjust_axis('x', x)

        # 处理Y轴偏移
        if abs(y) > self.max_xy_error:
            self._adjust_axis('y', y)

        # 处理Z轴偏移
        if z > self.max_z:
            self._adjust_z(z, z_final)


        return False

    def _adjust_axis(self, axis, error):
        """
        调整单轴位置

        参数:
            axis: 调整轴 ('x' 或 'y')
            error: 当前误差值
        """
        axis_num = 0 if axis == 'x' else 2
        abs_error = abs(error)

        # 根据误差大小选择速度和移动时间
        if abs_error > 10:
            vel = self.fast_vel
            duration = self.fast_duration
            move_cmd = -abs_error if error > 0 else abs_error
        elif abs_error > 5:
            vel = self.medium_vel
            duration = self.medium_duration
            move_cmd = -abs_error if error > 0 else abs_error
        else:
            vel = self.slow_vel
            duration = self.slow_duration
            move_cmd = -abs_error if error > 0 else abs_error

        rospy.loginfo(f"调整{axis}轴: 误差={error:.3f}, {axis_num},速度={vel}, 时间={duration:.1f}s")

        # 执行移动
        self.robot.jog(aj_num=axis_num, move_mode=1, coord_type=2,
                       jog_vel=vel, pos_cmd=move_cmd)
        in_pos = self.robot.is_in_pos()[1]
        while(not in_pos):
            time.sleep(0.1)
            in_pos = self.robot.is_in_pos()[1]
        time.sleep(0.5)  # 等待稳定

        rospy.loginfo("wancheng")

    def _adjust_z(self, z, z_final):
        """
        调整Z轴位置

        参数:
            z: 当前Z值
        """
        if z > self.max_z + 10:
            move_cmd = z - (self.max_z + 8)
            rospy.loginfo(f"调整Z轴: z={z:.3f}, move_cmd = {move_cmd} ")
            vel = self.fast_vel
            duration = self.fast_duration
            # 执行移动
            self.robot.jog(aj_num=1, move_mode=1, coord_type=2,
                       jog_vel=vel, pos_cmd=-move_cmd)
            in_pos = self.robot.is_in_pos()[1]
            while(not in_pos):
                time.sleep(0.1)
                in_pos = self.robot.is_in_pos()[1]
            self.robot.jog_stop(-1)
            time.sleep(0.5)  # 等待稳定
            rospy.loginfo("wancheng")
        else:
            # move_cmd = 3
            # vel = self.medium_vel
            # duration = self.medium_duration
            rospy.loginfo(f"调整Z轴: z={z:.3f}")
            tcp = self.robot.get_tcp_position()[1]
            tcp[2] = z_final #-367  #-358
            ret = self.robot.linear_move(tcp, 0, True, 100)
            rospy.loginfo("wancheng")



