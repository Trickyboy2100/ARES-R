#!/usr/bin/env python3
# Author: Jiayuan Sun #

import json
import asyncio
from websockets.sync.client import connect

import websockets

import time
from smtpd import program
import numpy as np

import rospy

class JAKAType():
  LEFT = 0
  RIGHT = 1

class JAKARobot:
    class CoordType():
        BASE = 0
        JOINT = 1
        TOOL = 2
        ABS = 0  # 绝对运动
        INCR = 1  # 增量运动
        cart_x = 0  # x 方向
        cart_y = 1  # y 方向
        cart_z = 2  # z 方向
        cart_rx = 3  # rx 方向
        cart_ry = 4  # ry 方向
        cart_rz = 5  # rz 方向

    def __init__(self, jaka_type):
        if jaka_type == JAKAType.LEFT:
          self.uri = 'ws://192.168.99.30:50091/left/jakactrl'
        else:
          self.uri = 'ws://192.168.99.30:50092/right/jakactrl'

        self.websocket = None

        while not rospy.is_shutdown():
            if self.wsconnect():
                break
            time.sleep(1.0)

        if self.wsconnect() is False:
            exit(0)
        
        self._jog_params = {
            'axis': None,
            'mode': None,
            'coord': None,
            'vel': 0.0,
            'pos': 0.0
        }
        
    
    def wsconnect(self):
        try:
            self.websocket = connect(self.uri)
            res = self.websocket.recv()
            # print(res)
            return True
        except (websockets.ConnectionClosed,OSError) as e:
          print(f'Connection failed: {e}')
          return False

    def get_force_data(self):
        """Get current force sensor data"""
        status = self.get_robot_status()
        y_force = None
        try:
            six_force = status["torq"]["actTorque"]  # 六维力
            print(six_force)
            y_force = six_force[1]  # y轴方向力
            print(f"y方向力:{y_force}")
        except:
            return None
        return y_force

    def init_force_sensor(self):
        cmd = {
          "type":"SetTorsenosrBrand",
          "sensor_brand": 6
          }
        ret1, _ = self.send_cmd(cmd)
        time.sleep(0.5)
        cmd = {
          "type":"SetTorqueSensorMode",
          "sensor_mode": 1
          }
        ret2, _ = self.send_cmd(cmd)
        cmd = {
          "type":"SetCompliantType",
          "sensor_compensation": 1,
          "compliance_type": 0
          }
        ret3, _ = self.send_cmd(cmd)
        return ret1+ret2+ret3

    def jog_wait(self, aj_num=2, move_mode=1, coord_type=2, jog_vel=10, pos_cmd=100):
        self.jog(aj_num,move_mode,coord_type,jog_vel,pos_cmd)
        time.sleep(1)
        in_pos = self.is_in_pos(10)
        # print(in_pos)
        while(not in_pos):
            time.sleep(0.1)
            in_pos = self.is_in_pos(10)
        self.jog_stop(-1)

    def jog(self, axis_num=2, move_mode=1, coord_type=2, jog_vel=10, pos_cmd=100):
        """
        JAKA机器人jog运动控制函数

        参数:
            axis_num: 轴号或坐标分量号(0-5)
                关节坐标系: 0-5表示J1-J6关节
                笛卡尔坐标系: 0-5表示X,Y,Z,Rx,Ry,Rz
            move_mode: 运动方式
                0 代表绝对运动
                1 代表增量运动
                2 代表连续运动
            coord_type: 坐标系类型
                1: 关节坐标系(jkrc.COORD_JOINT)
                0: 基坐标系(jkrc.COORD_BASE)
                2: 工具坐标系(jkrc.COORD_TOOL)
            velocity: mm/s or rad/s
            increment: 增量运动模式下的位移增量
                关节坐标系下单位为度(°)
                笛卡尔坐标系下，位移单位为毫米(mm)，姿态单位为度(°)

        返回值:
            success: 操作是否成功
            err_code: 错误码, 成功时为0
        """
        # 参数检查
        if axis_num < 0 or axis_num > 5:
            print("错误: 轴号必须在0-5之间")
            return False, -1

        if move_mode not in [0, 1, 2]:
            print("错误: 运动方式错误")
            return False, -2

        if coord_type not in [0, 1, 2]:
            print("错误: 坐标系类型无效")
            return False, -3

        if coord_type == 1:
            jog_vel = jog_vel * 3.14159 /180
            pos_cmd = pos_cmd * 3.14159 /180
        else:
            jog_vel = jog_vel
            pos_cmd = pos_cmd

        if move_mode == 0:
            pos_cmd = None
        elif move_mode == 1:
            pos_cmd = pos_cmd
        elif move_mode == 2:
            print("错误: 运动方式错误")
            return False, -3

        # 执行jog运动
        # ret = self.robot.jog(axis_num, move_mode, coord_type, velocity, pos_cmd)
        cmd = {
          "type":"StartJOG",
          "acc": jog_vel,
          "vel": jog_vel,
          "ref": coord_type,
          "nb": axis_num,
          "max_dis": pos_cmd,
          "mode": move_mode
          }
        ret, _ = self.send_cmd(cmd)
        # print(res)
        if ret == 0:
            return True, 0
        else:
            print(f"jog运动失败: 错误码 {ret}")
            return False, ret

    def jog_stop(self, stop_axis=None):
        """
        停止Jog运动
        :param axis: 指定停止的轴（None表示停止所有轴）
        """
        cmd = {
          "type":"StopJOG",
          "nb": stop_axis
          }
        ret, _ = self.send_cmd(cmd)
        # result = self.robot.jog_stop(stop_axis)

        if ret != 0:
            raise RuntimeError(f"停止运动失败，错误码：{ret}")

    def is_in_pos(self, timeout = 5):
        # cmd = {
        #   "type":"IsInPos",
        #   }
        # ret, res = self.send_cmd(cmd)

        # if ret != 0:
        #     raise RuntimeError(f"查询机器人运动是否停止，错误码：{ret}")

        # state = None
        # try:
        #     res = json.loads(res)
        #     state = res["state"]
        # except:
        #     state = None
        stop = 0
        state = 0
        status = None
        for i in range(100):
            time.sleep(0.01)
            if stop > timeout:
                state = 1
                break
            status = self.get_robot_status()
            if status is not None:
                cstate = status["inpos"]
                if cstate == 1:
                    stop += 1
            else:
                stop = 0
                   
        return state

    def joint_move(self, target, mode, is_block, speed):
        # res = self.robot.joint_move(target, 0, is_block, 1)
        target_joint = self.get_joint_position()
        target_joint[0] = target[0]
        target_joint[1] = target[1]
        target_joint[2] = target[2]
        target_joint[3] = target[3]
        target_joint[4] = target[4]
        target_joint[5] = target[5]
        cmd = {
            "type":"MoveJ",
            "speed": 0.5,
            "joint_pos": target_joint,
            "mode": 0
            }
        res, ret = self.send_cmd(cmd)
        print(ret)
        if res != 0:
            raise RuntimeError(f"关节运动失败，错误码：{res}")
        return res
    
    def linear_move(self, target, mode, is_block, speed):
        target_pose = self.get_tcp_position()
        target_pose[0] = target[0]
        target_pose[1] = target[1]
        target_pose[2] = target[2]
        target_pose[3] = target[3]
        target_pose[4] = target[4]
        target_pose[5] = target[5]
        cmd = {
            "type":"MoveL",
            "speed": speed,
            "end_pos": target_pose,
            "mode": 0
        }
        print(cmd)
        res = -100
        for i in range(10):
            res, ret = self.send_cmd(cmd)
            # print(ret)
            if res != 0:
                print(f"直线运动失败，错误码：{res}")
            else:
                return res
        raise RuntimeError(f"关节运动失败，错误码：{res}")

    def safe_move(self, target, move_type="joint",  is_block=True):
        """安全运动接口"""
        if move_type == "joint":
            # res = self.robot.joint_move(target, 0, is_block, 1)
            target_joint = self.get_joint_position()
            target_joint[0] = target[0]
            target_joint[1] = target[1]
            target_joint[2] = target[2]
            target_joint[3] = target[3]
            target_joint[4] = target[4]
            target_joint[5] = target[5]
            cmd = {
              "type":"MoveJ",
              "speed": 0.5,
              "joint_pos": target_joint,
              "mode": 0
              }
            res, ret = self.send_cmd(cmd)
            print(ret)
            if res != 0:
                raise RuntimeError(f"关节运动失败，错误码：{res}")
            return res
        elif move_type == "linear":
            # res = self.robot.linear_move(target, 0, is_block, 25)
            target_pose = self.get_tcp_position()
            target_pose[0] = target[0]
            target_pose[1] = target[1]
            target_pose[2] = target[2]
            target_pose[3] = target[3]
            target_pose[4] = target[4]
            target_pose[5] = target[5]
            cmd = {
              "type":"MoveL",
              "speed": 0.5,
              "end_pos": target_pose,
              "mode": 0
            }
            print(cmd)
            res, ret = self.send_cmd(cmd)
            print(ret)
            if res != 0:
                raise RuntimeError(f"直线运动失败，错误码：{res}")
            return res

    def go_to_home(self, home_name="DEFAULT", timeout=20):
        """移动到指定名称的home位置"""
        return self.run_program_full(home_name)

    def get_tcp_position(self):
        """获取当前TCP位姿"""
        # res = self.robot.get_tcp_position()
        
        cmd = {
          "type":"GetTCPPose"
          }
        ret, res = self.send_cmd(cmd)
        pose = [0,0,0,0,0,0]
        try:
            res = json.loads(res)
            pose[0] = res["x"]
            pose[1] = res["y"]
            pose[2] = res["z"]
            pose[3] = res["rx"]
            pose[4] = res["ry"]
            pose[5] = res["rz"]
        except:
            pose = None
        
        return pose
    
    def kine_inverse(self, tcp):        
        cmd = {
          "type":"GetInverseKin",
          "desc_pose": tcp
          }
        ret, res = self.send_cmd(cmd)
        joints = [0,0,0,0,0,0]
        try:
            res = json.loads(res)
            joints = res["joint_pos"]
        except:
            joints = None
        
        return joints

    def get_joint_position(self):
        cmd = {
          "type":"GetJointPos"
          }
        ret, res = self.send_cmd(cmd)
        pose = [0,0,0,0,0,0]
        try:
            res = json.loads(res)
            pose = res["joint_pos"]
        except:
            pose = None
        
        return pose

    def get_robot_status(self):
        cmd = {
          "type":"GetRobotStatus"
          }
        ret, res = self.send_cmd(cmd)
        status = None
        try:
            status = json.loads(res)
            err = status["err"]
            if err < 0:
                return None
        except:
            status = None
        
        return status

    def set_rapidrate(self, rapidrate):
        cmd = {
          "type":"SetRapidrate",
          "rapidrate": rapidrate
          }
        ret, _ = self.send_cmd(cmd)
        time.sleep(0.5)
        return ret

    def program_start(self, program_name, t):
        """加载预设程序"""
        
        # self.robot.program_load(program_name)
        self.program_load(program_name)
        
        # self.robot.program_run()
        self.program_run()
        time.sleep(t)
        ret = self.program_abort()
        # res = self.robot.program_abort()
        return ret
    
    def run_program_full(self, program):
        self.program_load(program)
        self.program_run()
        time.sleep(0.5)
        in_pos = self.is_in_pos(10)
        # print(in_pos)
        while(not in_pos):
            time.sleep(0.5)
            in_pos = self.is_in_pos(10)
        # time.sleep(1)
        self.program_abort()
    
    def program_load(self, program_name):
        cmd = {
          "type":"ProgramLoad",
          "file": program_name
          }
        ret, _ = self.send_cmd(cmd)
        return ret
    
    def program_run(self):
        cmd = {
          "type":"ProgramRun"
          }
        ret, _ = self.send_cmd(cmd)
        return ret

    def program_abort(self):
        cmd = {
          "type":"ProgramAbort"
          }
        ret, _ = self.send_cmd(cmd)
        return ret

    def shutdown(self):
        # self.robot.logout()
        self.websocket.close()

    def stop(self):
        # self.robot.motion_abort()
        cmd = {
          "type":"StopMotion",
          }
        ret, _ = left.send_cmd(cmd)

    def send_cmd(self,req):
      err = -1
      res = None
      succ = False
      for i in range(100):
        if succ:
            break
        try:
            print(json.dumps(req))
            self.websocket.send(json.dumps(req))
            res = self.websocket.recv()
            print(res)
            resj = json.loads(res)
            err = resj["err"]
            succ = True
            # print("send succ")
        except:
            print("send failed")
            self.websocket.close()
            self.wsconnect()
            time.sleep(0.1)
            continue
      return err, res

if __name__ == '__main__':
    # 机械臂
    try:
        left = JAKARobot(JAKAType.LEFT)
    except Exception as e:
        print(e)

    left.get_tcp_position()

    # jog_control(self, axis_num=2, move_mode=1, coord_type=2, velocity=50, increment=100):
    # left.go_to_home("qingsao_start",19.0)

    # try:
    #     left.linear_move(np.array(tcp_pos[-6:]), 0, True, 5)
    # except Exception as e:
    #     print(e)
    #     camera.close()
    #     left.shutdown()

    time.sleep(10)
    left.shutdown()
  # left.jog_control(2,1,0,-10,10)
  # left.jog_stop(2)
