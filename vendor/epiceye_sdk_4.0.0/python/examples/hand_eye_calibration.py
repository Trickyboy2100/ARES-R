"""不依赖相机网页的完整手眼标定控制台流程。

流程：读取完整机器人库 -> 默认选择首品牌首型号 -> 配置安装方式和机器人姿态规则 ->
      成对采集标定板/机器人位姿 -> 计算手眼结果 -> 可选执行机器人精度和手眼结果精度检查。

数据规则：每个 boardPoseArray 必须与同一静止时刻的 robotPose 配对；机器人移动后不能复用旧数据。
相机影响：会保存 installationType 和 robotParams；手眼计算成功后服务端会保存结果。不会写入内参。
"""

from __future__ import annotations

import sys
from typing import Any, Dict, List, Optional

import epiceye
from epiceye._core import (
    CalculateHandEyeAccuracyParams,
    CalculateHandEyeCalibrationResultParams,
    CalculateRobotAccuracyParams,
    ConfigureHandEyeCalibrationParams,
    HandEyePointData,
    RobotAccuracyDirectionData,
    RobotAccuracyPoint,
    RobotParameters,
    SpecialParams,
)


def resolve_ip() -> Optional[str]:
    if len(sys.argv) > 1 and sys.argv[1]:
        return sys.argv[1]
    cameras = epiceye.search_camera()
    if not cameras:
        print("Camera not found.")
        return None
    return cameras[0].get("ip")


def read_choice(prompt: str, allowed: List[int]) -> int:
    while True:
        try:
            value = int(input(f"{prompt}: "))
        except ValueError:
            value = -1
        if value in allowed:
            return value
        print("Invalid choice.")


def read_values(label: str, count: int) -> List[float]:
    while True:
        try:
            values = [float(value) for value in input(f"{label}; enter {count} values separated by spaces: ").replace(",", " ").split()]
        except ValueError:
            values = []
        if len(values) == count:
            return values
        print("Invalid input.")


def robot_from_dict(value: Dict[str, Any]) -> RobotParameters:
    return RobotParameters(
        brand=str(value.get("brand", "")),
        model=str(value.get("model", "")),
        rotationType=str(value.get("rotationType", "EulerPose")),
        eulerType=str(value.get("eulerType", "XYZ")),
        angleUnit=str(value.get("angleUnit", "Degree")),
        isCustomRobot=bool(value.get("isCustomRobot", False)),
        axisNumber=int(value.get("axisNumber", 6)),
        marks=str(value.get("marks", "X,Y,Z,Rx,Ry,Rz")),
    )


def pose_marks(robot: RobotParameters) -> str:
    return robot.marks or ("X,Y,Z,Qx,Qy,Qz,Qw" if robot.rotationType == "Quaternion" else "X,Y,Z,Rx,Ry,Rz")


def read_robot_pose(robot: RobotParameters) -> List[float]:
    # 四元数需要 7 个值，其他旋转表达需要 6 个值；字段顺序和单位必须服从机器人库。
    count = 7 if robot.rotationType == "Quaternion" else 6
    return read_values(f"Robot pose ({pose_marks(robot)})", count)


def capture_board(ip: str, prompt: str) -> Optional[Dict[str, Any]]:
    input(prompt)
    board = epiceye.get_calibration_board_pose(ip)
    if not board or not isinstance(board.get("boardPoseArray"), list) or len(board["boardPoseArray"]) != 7:
        print("Calibration board capture failed.")
        return None
    return board


def capture_point(ip: str, robot: RobotParameters, points: List[HandEyePointData]) -> None:
    # 先完成机械移动并稳定，再拍摄标定板；检测成功后立即输入同一时刻的机器人位姿。
    board = capture_board(ip, "Move the calibration board/robot to a new pose, then press Enter to capture.")
    if board is None:
        return
    point = HandEyePointData(read_robot_pose(robot), board["boardPoseArray"], max([value.id for value in points], default=0) + 1)
    points.append(point)
    print(f"Point #{point.id} captured. boardPose={point.boardPoseArray}, intrinsicAccuracy={board.get('cameraInternalAccuracy', 0)}")


def calculate(ip: str, installation_type: str, robot: RobotParameters, points: List[HandEyePointData]) -> Optional[Dict[str, Any]]:
    if not points:
        print("No calibration points have been collected.")
        return None
    special_params = None
    if robot.axisNumber in (3, 4):
        # 3/4 轴自由度不足，需要额外提供工具偏移和标定板参考位置；6 轴无需填写。
        special_params = SpecialParams(read_values("Offset", 3), read_values("Board position", 3))
    # 计算成功后相机服务端会把手眼结果保存到当前标定上下文中。
    result = epiceye.calculate_handeye_calibration_result(ip, CalculateHandEyeCalibrationResultParams(installation_type, points, special_params))
    if result is None:
        print("Hand-eye calculation failed.")
        return None
    error = result.get("hecError") or {}
    print(f"Calibration success: {result.get('success', False)}")
    print(f"Pose [x,y,z,rx,ry,rz]: {result.get('pose', [])}")
    print(f"Error: rotation mean/max={error.get('rotMean', 0)}/{error.get('rotMax', 0)} deg, translation mean/max={error.get('transMean', 0)}/{error.get('transMax', 0)} mm")
    print(f"Warning: {result.get('hecWarnData', {})}")
    print("The camera stores the calculation result as part of its hand-eye calibration data.")
    return result


def capture_accuracy_point(ip: str, robot: RobotParameters, name: str) -> Optional[RobotAccuracyPoint]:
    board = capture_board(ip, f"Move to the {name} pose, then press Enter to capture.")
    if board is None:
        return None
    return RobotAccuracyPoint(board["boardPoseArray"], read_robot_pose(robot), float(board.get("cameraInternalAccuracy", 0)))


def run_robot_accuracy(ip: str, robot: RobotParameters) -> None:
    # 起点、终点都必须重新检测标定板并输入各自机器人位姿，随后比较两套移动量。
    direction = ["x", "y", "z"][read_choice("Direction: 0=X, 1=Y, 2=Z", [0, 1, 2])]
    start = capture_accuracy_point(ip, robot, "start")
    if start is None:
        return
    end = capture_accuracy_point(ip, robot, "end")
    if end is None:
        return
    result = epiceye.calculate_robot_accuracy(ip, CalculateRobotAccuracyParams(RobotAccuracyDirectionData(start, end), direction))
    print("Robot accuracy result: " + (str(result) if result is not None else "failed"))


def run_handeye_accuracy(ip: str, installation_type: str, robot: RobotParameters) -> None:
    # 使用已保存的手眼结果把新标定板位姿转换到机器人基坐标系。
    # Eye-in-Hand 需要当前机器人位姿；Eye-to-Hand 相机固定，robotPose 为空。
    board = capture_board(ip, "Place the board in the view, then press Enter to capture for result verification.")
    if board is None:
        return
    robot_pose = read_robot_pose(robot) if installation_type == "EIH" else []
    direction = "up" if read_choice("Board Z direction: 0=Up, 1=Down", [0, 1]) == 0 else "down"
    result = epiceye.calculate_handeye_accuracy(ip, CalculateHandEyeAccuracyParams(board["boardPoseArray"], robot_pose, int(board.get("gridSize", 0)), direction))
    if result is None:
        print("Hand-eye accuracy check failed.")
        return
    print(f"Board pose in robot base coordinates: {result.get('boardPoseArray', [])}")


def main() -> int:
    print(f"SDK Version: {epiceye.get_sdk_version()}")
    ip = resolve_ip()
    if not ip:
        return 1
    # Example 自行读取机器人库和设置机器人，不能依赖相机网页中可能存在的历史选择。
    robot_library = epiceye.get_robot_library(ip)
    if not robot_library:
        print("Failed to read robot library.")
        return 1
    first_brand, first_models = next(iter(robot_library.items()))
    if not first_models:
        print(f"Robot brand {first_brand} has no models.")
        return 1
    robot = robot_from_dict(first_models[0])
    print(f"Robot library loaded: {len(robot_library)} brands. Default robot: [{robot.brand}] {robot.model}")
    installation_type = "ETH" if read_choice("Installation type: 0=Eye-To-Hand, 1=Eye-In-Hand", [0, 1]) == 0 else "EIH"
    # 相机端计算服务将根据这里保存的规则解释后续 robotPose。
    if not epiceye.configure_handeye_calibration(ip, ConfigureHandEyeCalibrationParams(installation_type, robot)):
        print("Failed to save robot parameters.")
        return 1
    print(f"Configured: installation={installation_type}, robot=[{robot.brand}] {robot.model}, axis={robot.axisNumber}, rotation={robot.rotationType}, euler={robot.eulerType}, unit={robot.angleUnit}")
    print(f"Pose fields: {pose_marks(robot)}")

    points: List[HandEyePointData] = []
    while True:
        action = read_choice("1=Capture point  2=Calculate  3=Robot accuracy check  4=List points  5=Clear points  0=Exit", [0, 1, 2, 3, 4, 5])
        if action == 0:
            return 0
        if action == 1:
            capture_point(ip, robot, points)
        elif action == 2:
            result = calculate(ip, installation_type, robot, points)
            if result and result.get("success") and read_choice("Run hand-eye result accuracy check now? 0=No, 1=Yes", [0, 1]) == 1:
                run_handeye_accuracy(ip, installation_type, robot)
        elif action == 3:
            run_robot_accuracy(ip, robot)
        elif action == 4:
            for point in points:
                print(f"#{point.id}: board={point.boardPoseArray}, robot={point.robotPose}")
            if not points:
                print("No points collected.")
        else:
            points.clear()
            print("All collected points were cleared.")


if __name__ == "__main__":
    raise SystemExit(main())
