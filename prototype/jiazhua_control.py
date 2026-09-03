import math
import time
import sys
import serial
import struct


class Jiazhua:
    def __init__(self):
        # 配置串口
        self.ser = serial.Serial(
            port='/dev/ttyUSB0',  # 根据实际情况替换为你的串口端口
            baudrate=115200,
            timeout=1
        )
        self.id = 1  # 目标ID

    def calculate_checksum(self, data):
        """计算给定数据的校验和。"""
        return sum(data) & 0xFF

    def create_command_frame(self, id, cmd, data):
        """创建指令帧。"""
        frame = [0xEB, 0x90]  # 帧头
        frame.append(id)
        frame.append(len(data) + 1)
        frame.append(cmd)
        frame.extend(data)
        frame.append(self.calculate_checksum(frame[2:]))  # 校验和
        return bytearray(frame)

    def create_null_command_frame(self, id, cmd):
        """创建空数据指令帧。"""
        frame = [0xEB, 0x90]  # 帧头
        frame.append(id)
        frame.append(0x01)
        frame.append(cmd)
        frame.append(self.calculate_checksum(frame[2:]))  # 校验和
        return bytearray(frame)

    def send_command(self, frame):
        """通过串口发送指令帧。"""
        self.ser.write(frame)

    def read_response(self):
        """读取串口的响应帧。"""
        response = self.ser.read(self.ser.in_waiting or 1)
        return response
    
    def read_fixed_length(self, length, timeout=1.0):
        self.ser.timeout = timeout
        data = self.ser.read(length)
        if len(data) != length:
            raise TimeoutError(f"Expected {length} bytes, got {len(data)}")
        return data

    def end_command(self):
        # 关闭串口
        self.ser.close()

    def PARA_SAVE(self):  # 主控单元将当前夹爪使用的开口最大最小值参数保存到内部闪存，掉电不丢失。
        # 示例：参数固化
        # data  参数
        cmd_id = 0x01  # 设置ID的指令号
        frame_set_id = self.create_null_command_frame(self.id, cmd_id)
        self.send_command(frame_set_id)
        response = self.read_response()
        print("设置ID的响应:", response)

    def PARA_ID_SET(self, new_id):  # 主控单元设置夹爪的 ID 号
        # 示例：设置夹爪的ID
        # new_id  新ID
        cmd_id = 0x04  # 设置ID的指令号
        data_set_id = [new_id]
        frame_set_id = self.create_command_frame(self.id, cmd_id, data_set_id)
        self.send_command(frame_set_id)
        response = self.read_response()
        print("设置ID的响应:", response)

    def MOVE_CATCH_XG(self, speed, force):  # 主控单元设置夹爪以输入的速度和力控阈值去夹取，主控单元设置夹爪以输入的速度和力控阈值去夹取，当夹持力超过设定的力控阈值后，夹爪停止运动
        # 示例：力控夹取
        # speed 速度
        # force 力控阈值，单位：克
        cmd_id = 0x10  # 力控夹取的指令号
        data_force_grasp = list(struct.pack('<H', speed)) + list(struct.pack('<H', force))
        frame_force_grasp = self.create_command_frame(self.id, cmd_id, data_force_grasp)
        self.send_command(frame_force_grasp)
        response = self.read_response()
        print("力控夹取的响应:", response)

    def MOVE_CATCH2_XG(self, speed, force):  # 主控单元设置夹爪以输入的速度和力控阈值去夹取，当夹持力超过设定的力控阈值后，夹爪停止运动；
        # 当夹爪停止运动后，如果检测到夹持力小于力控阈值时，夹爪会继续夹取直到夹持力超过设定的力控阈值
        # 示例：力控持续夹取
        # speed 速度 0-1000
        # force 力控阈值，单位：克 0-2000
        cmd_id = 0x18  # 力控持续夹取的指令号
        data_force_grasp = list(struct.pack('<H', speed)) + list(struct.pack('<H', force))
        frame_force_grasp = self.create_command_frame(self.id, cmd_id, data_force_grasp)
        self.send_command(frame_force_grasp)
        response = self.read_fixed_length(7)
        print("力控夹取的响应:", response)

    def MOVE_RELEASE(self, speed):  # 主控单元设置夹爪以输入的速度参数将夹爪松开到最大开口位置
        # 示例：松开夹爪
        # speed 速度 0-1000
        cmd_id = 0x11  # 松开夹爪的指令号
        data_speed_grasp = list(struct.pack('<H', speed))
        frame_force_grasp = self.create_command_frame(self.id, cmd_id, data_speed_grasp)
        self.send_command(frame_force_grasp)
        response = self.read_fixed_length(7)
        print("力控夹取的响应:", response)

    def SEEKPOS(self, position):  # 主控单元指定夹爪的目标开口度，夹爪接受到这条指令后，如果当前开口度小于设定开口度，以设定速度松开直到开口度达到目标开口度后停止运动；
        # 如果当前开口度大于设定开口度，以设定速度和力控阈值去夹取，当夹持力超过设定的力控阈值后，或者开口度达到目标开口度后停止运动
        # 示例：指定开口度
        # position 目标位置
        cmd_id = 0x54  # 指定位置的指令号
        data_seek_pos = list(struct.pack('<H', position))
        frame_seek_pos = self.create_command_frame(self.id, cmd_id, data_seek_pos)
        self.send_command(frame_seek_pos)
        response = self.read_fixed_length(7)
        print("移动到指定位置的响应:", response)

    def MOVE_STOPHERE(self):  # 主控单元通过该指令让运动中的夹爪停止运动，保持在该位置不动
        # 示例：主控单元通过该指令让运动中的夹爪停止运动，保持在该位置不动
        cmd_id = 0x16  # 指定位置的指令号
        frame_seek_pos = self.create_null_command_frame(self.id, cmd_id)
        self.send_command(frame_seek_pos)
        response = self.read_response()
        print("移动到指定位置的响应:", response)

    def SET_EG_PARA(self, open_max, open_min):  # 主控单元设置夹爪的最大和最小开口参数
        # 示例：主控单元设置夹爪的最大和最小开口参数
        # open_max 夹爪最大值
        # open_min 夹爪最小值
        cmd_id = 0x12  # 指定位置的指令号
        data_seek_pos = list(struct.pack('<H', open_max)) + list(struct.pack('<H', open_min))
        frame_seek_pos = self.create_command_frame(self.id, cmd_id, data_seek_pos)
        self.send_command(frame_seek_pos)
        response = self.read_response()
        print("移动到指定位置的响应:", response)

    def READ_EG_PARA(self):  # 主控单元读取夹爪的开口参数
        # 示例：读取开口参数
        cmd_id = 0x13  # 指定位置的指令号
        frame_seek_pos = self.create_null_command_frame(self.id, cmd_id)
        self.send_command(frame_seek_pos)
        response = self.read_response()
        print("移动到指定位置的响应:", response)

    def READ_ACTPOS(self):  # 主控单元读取夹爪的当前开口
        # 示例：读取当前开口度
        cmd_id = 0xD9  # 指定位置的指令号
        frame_seek_pos = self.create_null_command_frame(self.id, cmd_id)
        self.send_command(frame_seek_pos)
        response = self.read_fixed_length(8)
        print("移动到指定位置的响应:", response)
        return parse_response_combined(response)

    def READ_EG_RUNSTATE(self):  # 主控单元读取夹爪运行状态，可得到当前开口大小，夹持力设定值，运行状态，故障码、驱动器温度值，
        # 该指令可以周期性的获取到夹爪的运行状态信息，帮助用户快速定位夹爪的状态
        # 示例：读取夹爪运行状态
        cmd_id = 0x41  # 指定位置的指令号
        frame_seek_pos = self.create_null_command_frame(self.id, cmd_id)
        self.send_command(frame_seek_pos)
        response = self.read_response()
        print("移动到指定位置的响应:", response)

    def ERROR_CLR(self):  # 对夹爪的故障码中的 bit0、bit2、bit3 和 bit4 产生的故障，可通过故障清除指令来恢复夹爪的正常工作，
        # 而 bit1 的过温故障（温度高于 80 摄氏度）只能等待温度降低到（低于 60 摄氏度）后自己恢复正常工作。
        # 对于经过故障清除指令后仍然又出现的故障，说明该产品的故障不可被清除，该故障一直存在，需要进行工程师维修处理
        # 示例：故障清除
        cmd_id = 0x17  # 指定位置的指令号
        frame_seek_pos = self.create_null_command_frame(self.id, cmd_id)
        self.send_command(frame_seek_pos)
        response = self.read_response()
        print("移动到指定位置的响应:", response)

def parse_response_combined(response_bytes):
    """
    解析响应数据，将倒数第二和第三个字节拼接为16位整数
    
    参数:
    response_bytes -- 字节串，例如 b'\x16\x01\x02T\x01X'
    
    返回:
    一个整数，由倒数第三和第二个字节拼接而成（高位在前，即大端序）
    """
    if len(response_bytes) < 3:
        raise ValueError("响应数据长度不足，至少需要3个字节")
    
    # 获取倒数第三和第二个字节
    third_last = response_bytes[-3]  # 高位字节
    second_last = response_bytes[-2]  # 低位字节
    
    # 拼接为16位整数（小端序）
    combined = (second_last << 8) | third_last 
        
    return combined


if __name__ == '__main__':
    jiazhua = Jiazhua()
    #time.sleep(3)
    jiazhua.SEEKPOS(600)
    #jiazhua.MOVE_CATCH2_XG(500, 500)
    time.sleep(8)
    # jiazhua.MOVE_RELEASE(400)
    #response = jiazhua.READ_ACTPOS()
    #print(response)
    #time.sleep(5)
    jiazhua.MOVE_CATCH2_XG(100, 300)
   # time.sleep(6)
    #jiazhua.SEEKPOS(550)
