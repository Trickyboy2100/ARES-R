import numpy as np
import sys

sys.path.insert(0, '/home/yikun/ws/SDK V2.1.5/Linux/python3/x86_64-linux-gnu')
from jaka_driver import JAKARobot, JAKAType
import time
import rospy
import socket
from std_msgs.msg import Float64MultiArray, Header
import keyboard
import os
import cv2
from jiazhua_control import Jiazhua
from scipy.spatial.transform import Rotation
from utility_function import se3_average, ArucoTracker_Left

ABS = 0
INCR = 1

class MoveController:
    def __init__(self):
        rospy.init_node('MoveController', anonymous=True)

        # 相机到左臂末端的外参矩阵
        self.T_wrist2cam = np.array([[-9.95890521e-01, 8.87416736e-02, 1.80827505e-02, 5.47052404e+00],
                                     [-8.77727052e-02, -9.94947547e-01, 4.87373571e-02, 1.09787753e+02],
                                     [2.23164229e-02, 4.69499000e-02, 9.98647928e-01, -1.51621613e+02],
                                     [0.00000000e+00, 0.00000000e+00, 0.00000000e+00, 1.00000000e+00]])

        # 机器人初始化
        self.robot_left = JAKARobot(JAKAType.LEFT)
        self.robot_right = JAKARobot(JAKAType.RIGHT)
        # print(self.robot_left.login())
        # print(self.robot_left.power_on())
        # print(self.robot_left.enable_robot())
        # print(self.robot_left.set_rapidrate(0.3))
        time.sleep(2)

        # 夹爪初始化
        self.jiazhua = Jiazhua()

    def get_arm_info(self):
        joint = self.robot_left.get_joint_position()
        print(joint)
        tcp_pos = self.robot_left.get_tcp_position()
        print(tcp_pos)

    def jiazhua_release(self):
        self.jiazhua.MOVE_RELEASE(500)

    def jiazhua_control(self, angle):
        self.jiazhua.SEEKPOS(angle)

    def arm_jog(self, aj_num, move_mode, coord_type, jog_vel, pos_cmd, LR):
        arm = self.robot_left if LR == 'left' else self.robot_right

        arm.jog_wait(aj_num=aj_num, move_mode=move_mode, coord_type=coord_type, jog_vel=jog_vel,
                    pos_cmd=pos_cmd)

    def arm_control(self, tcp_pos, LR):
        # joint_pos = [159.588 * np.pi / 180, -425.518 * np.pi / 180, 397.153 * np.pi / 180, 67.807 * np.pi / 180, -59.224 * np.pi / 180, 20.017 * np.pi / 180]
        # joint_pos = [159.588, -425.518, 397.153, 67.807, -59.224, 20.017]
        # self.robot_left.joint_move(joint_pos, ABS, True, 0.1)

        arm = self.robot_left if LR == 'left' else self.robot_right

        print(arm.linear_move(tcp_pos, move_mode = ABS, is_block = True, speed = 45))

    def arm_servo(self, joint_pos, pos_type, LR):
        arm = self.robot_left if LR == 'left' else self.robot_right
        # 关节空间伺服模式运动或笛卡尔空间伺服模式运动
        move = arm.servo_j if pos_type == 'space' else arm.servo_p

        arm.servo_move_enable(True)
        # arm.servo_move_use_none_filter() # 禁用滤波器
        move(joint_pos = joint_pos, move_mode = INCR)

        time.sleep(0.008)
        arm.servo_move_enable(False)

    def close(self):
        self.robot_left.logout()
        self.robot_right.logout()
        self.jiazhua.end_command()

class Camera:

    account = 'admin'
    password = '123456'
    catch = '320,1,1,1,1,0'
    put = '320,1,2,1,1,0'

    def __init__(self, ip='192.168.99.199', port=5700):
        self.ip = ip
        self.port = port
        self.sock = None
        self.connect()

    def connect(self):
        """建立 TCP 连接"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5)  # 设置超时，避免长时间阻塞
            self.sock.connect((self.ip, self.port))
            print(f"Camera connected: {self.ip}:{self.port}")
        except Exception as e:
            print(f"Camera connection failed: {e}")
            self.sock = None

    def send_data(self, data):
        """发送字符串数据，可接收响应"""
        if self.sock is None:
            print("Camera not connected")
            return False
        try:
            # 发送数据
            message = data
            self.sock.sendall(message.encode('utf-8'))
            print(f"Sent to camera: {data}")

            # 尝试接收响应（如果相机有返回数据）
            try:
                response = self.sock.recv(1024)
                if response:
                    print(f"Received from camera: {response.decode('utf-8')}")
                    return response.decode('utf-8')
            except socket.timeout:
                print("No response received (timeout)")
            return True
        except Exception as e:
            print(f"Send failed: {e}")
            self.sock = None
            return False

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None

    def operate(self, order):
        tcp_pos = []
        tcp_pos = self.send_data(self.catch) if order == 'catch' else self.send_data(self.put)
        tcp_pos = tcp_pos.split(',')
        tcp_pos[-6:] = [float(pos) for pos in tcp_pos[-6:]]
        tcp_pos[-3:] = [pos / 180 * np.pi for pos in tcp_pos[-3:]]

        return tcp_pos[-6:]

if __name__ == '__main__':
    # 相机
    try:
        camera = Camera(ip='192.168.99.199', port=5700)
    except Exception as e:
        print(e)

    # 机械臂
    try:
        node = MoveController()

        tcp_pos = camera.operate('put')
        node.arm_control(tcp_pos, 'left')

        # 末端z+前进
        # node.arm_jog(2, 1, 2, 5, -30, 'left')
        # 末端y-抬升
        # node.arm_jog('left', 1, 1, 2, 5, -80)
        node.jiazhua_control(angle=10)
        # seek_pose()
        time.sleep(5)
        # node.jiazhua_release()

    except Exception as e:
        print(e)
        node.robot_left.logout()
        node.jiazhua.end_command()

    node.close()
    # camera.close()

# if __name__ == '__main__':
    # # 输入抓取的编号
    # grasp_num = 2  # 0-2
    # # 输入编码器角度
    # angle = 247.15
    # # 输入底盘误差(mm) x正方向朝前 y正方向朝左
    # x_error = 1.9
    # y_error = -7.9
    # theta = 1.7
    # try:
    #     # 初始化
    #     node = MoveController()
    #     rate = rospy.Rate(5)  # 5Hz
    #     # node.jiazhua.SEEKPOS(300)

    #     node.get_arm_info()
    #     # node.arm_control()

    # except rospy.ROSInterruptException:
    #     rospy.loginfo("程序被中断")

    # except Exception as e:
    #     rospy.logerr(f"程序发生异常: {str(e)}")