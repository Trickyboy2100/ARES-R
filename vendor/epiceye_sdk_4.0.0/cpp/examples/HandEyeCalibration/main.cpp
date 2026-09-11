/*
 * 作用：提供一套不依赖相机网页的完整手眼标定控制台流程。
 * 流程：读取机器人库 -> 默认首品牌首型号 -> 配置安装方式/姿态规则 -> 成对采集位姿 -> 计算 -> 精度检查。
 * 数据规则：每个 boardPoseArray 必须与同一静止时刻的 robotPose 配对，机器人移动后不能复用旧数据。
 * 相机影响：会保存安装方式和机器人参数；计算成功后服务端会保存手眼结果。不会写入内参。
 */
#include "epiceye.h"

#include <algorithm>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

std::string resolveIp(int argc, char **argv) {
    if (argc > 1 && argv[1][0] != '\0') return argv[1];
    std::vector<TFTech::EpicEyeInfo> cameras;
    if (!TFTech::EpicEye::searchCamera(cameras) || cameras.empty()) return {};
    return cameras.front().IP;
}

int readChoice(const std::string &prompt, const std::vector<int> &allowed) {
    while (true) {
        std::cout << prompt << ": ";
        int value = -1;
        if (std::cin >> value && std::find(allowed.begin(), allowed.end(), value) != allowed.end()) {
            std::cin.ignore(std::numeric_limits<std::streamsize>::max(), '\n');
            return value;
        }
        std::cin.clear();
        std::cin.ignore(std::numeric_limits<std::streamsize>::max(), '\n');
        std::cout << "Invalid choice." << std::endl;
    }
}

std::vector<float> readValues(const std::string &label, size_t count) {
    while (true) {
        std::cout << label << "; enter " << count << " values separated by spaces: ";
        std::string line;
        std::getline(std::cin, line);
        std::istringstream input(line);
        std::vector<float> values;
        float value = 0.0f;
        while (input >> value) values.push_back(value);
        if (values.size() == count) return values;
        std::cout << "Invalid input." << std::endl;
    }
}

std::string rotationTypeName(TFTech::RobotRotationType value) {
    switch (value) {
    case TFTech::RobotRotationType::FixedPose: return "FixedPose";
    case TFTech::RobotRotationType::Quaternion: return "Quaternion";
    case TFTech::RobotRotationType::RotationVector: return "RotationVector";
    default: return "EulerPose";
    }
}

std::string eulerTypeName(TFTech::RobotEulerType value) {
    static const std::array<const char *, 12> names{{"XYZ", "XZY", "YXZ", "YZX", "ZXY", "ZYX", "XYX", "YXY", "XZX", "ZXZ", "YZY", "ZYZ"}};
    const size_t index = static_cast<size_t>(value);
    return index < names.size() ? names[index] : "XYZ";
}

std::string poseMarks(const TFTech::RobotParameters &robot) {
    if (!robot.marks.empty()) return robot.marks;
    return robot.rotationType == TFTech::RobotRotationType::Quaternion ? "X,Y,Z,Qx,Qy,Qz,Qw" : "X,Y,Z,Rx,Ry,Rz";
}

std::vector<float> readRobotPose(const TFTech::RobotParameters &robot) {
    // 四元数需要 7 个值，其他旋转表达需要 6 个值；顺序和单位由机器人库决定。
    const size_t count = robot.rotationType == TFTech::RobotRotationType::Quaternion ? 7 : 6;
    return readValues("Robot pose (" + poseMarks(robot) + ")", count);
}

template <size_t N>
void printArray(const std::array<float, N> &values) {
    for (size_t index = 0; index < values.size(); ++index) {
        if (index > 0) std::cout << ", ";
        std::cout << values[index];
    }
}

bool captureBoard(const std::string &ip, const std::string &prompt, TFTech::CalibrationBoardPose &board) {
    std::cout << prompt;
    std::string line;
    std::getline(std::cin, line);
    if (!TFTech::EpicEye::getCalibrationBoardPose(ip, board)) {
        std::cout << "Calibration board capture failed." << std::endl;
        return false;
    }
    return true;
}

void capturePoint(const std::string &ip, const TFTech::RobotParameters &robot, std::vector<TFTech::HandEyePoint> &points) {
    // 先移动并等待机械结构稳定，再检测标定板；随后立即输入同一时刻的机器人位姿。
    TFTech::CalibrationBoardPose board;
    if (!captureBoard(ip, "Move the calibration board/robot to a new pose, then press Enter to capture.", board)) return;
    TFTech::HandEyePoint point;
    point.id = points.empty() ? 1 : points.back().id + 1;
    point.boardPoseArray = board.boardPoseArray;
    point.robotPose = readRobotPose(robot);
    points.push_back(point);
    std::cout << "Point #" << point.id << " captured. boardPose=[";
    printArray(point.boardPoseArray);
    std::cout << "], intrinsicAccuracy=" << board.cameraInternalAccuracy << std::endl;
}

bool calculate(const std::string &ip, TFTech::HandEyeInstallationType installationType, const TFTech::RobotParameters &robot, const std::vector<TFTech::HandEyePoint> &points) {
    if (points.empty()) {
        std::cout << "No calibration points have been collected." << std::endl;
        return false;
    }
    TFTech::HandEyeCalculationRequest request;
    request.installationType = installationType;
    request.handEyePoints = points;
    if (robot.axisNumber == 3 || robot.axisNumber == 4) {
        // 3/4 轴机器人自由度不足，需要工具偏移和标定板参考位置；6 轴无需补充。
        TFTech::HandEyeSpecialParams special;
        const std::vector<float> offset = readValues("Offset", 3);
        const std::vector<float> boardPosition = readValues("Board position", 3);
        std::copy(offset.begin(), offset.end(), special.offset.begin());
        std::copy(boardPosition.begin(), boardPosition.end(), special.boardPosition.begin());
        request.specialParams = special;
    }

    // 计算成功后，相机服务端会把手眼结果保存到当前标定上下文中。
    TFTech::HandEyeCalibrationResult result;
    if (!TFTech::EpicEye::calculateHandEyeCalibrationResult(ip, request, result)) {
        std::cout << "Hand-eye calculation failed." << std::endl;
        return false;
    }
    std::cout << "Calibration success: " << std::boolalpha << result.success << std::endl;
    std::cout << "Pose [x,y,z,rx,ry,rz]: ";
    for (float value : result.pose) std::cout << value << " ";
    std::cout << std::endl;
    std::cout << "Error: rotation mean/max=" << result.hecError.rotMean << "/" << result.hecError.rotMax
              << " deg, translation mean/max=" << result.hecError.transMean << "/" << result.hecError.transMax << " mm" << std::endl;
    std::cout << "Warning type: " << result.hecWarnData.warnType << std::endl;
    for (const auto &pair : result.hecWarnData.warnPairs) std::cout << "Warning pair: " << pair[0] << ", " << pair[1] << std::endl;
    std::cout << "The camera stores the calculation result as part of its hand-eye calibration data." << std::endl;
    return result.success;
}

bool captureAccuracyPoint(const std::string &ip, const TFTech::RobotParameters &robot, const std::string &name, TFTech::RobotAccuracyPoint &point) {
    TFTech::CalibrationBoardPose board;
    if (!captureBoard(ip, "Move to the " + name + " pose, then press Enter to capture.", board)) return false;
    point.boardPoseArray = board.boardPoseArray;
    point.robotPose = readRobotPose(robot);
    point.cameraInternalAccuracy = board.cameraInternalAccuracy;
    return true;
}

void runRobotAccuracy(const std::string &ip, const TFTech::RobotParameters &robot) {
    // 起点和终点都重新采集配对位姿，再比较机器人报告移动量与视觉检测移动量。
    static const std::array<const char *, 3> directions{{"x", "y", "z"}};
    TFTech::RobotAccuracyRequest request;
    request.direction = directions[static_cast<size_t>(readChoice("Direction: 0=X, 1=Y, 2=Z", {0, 1, 2}))];
    if (!captureAccuracyPoint(ip, robot, "start", request.directionPoseData.startPoint)) return;
    if (!captureAccuracyPoint(ip, robot, "end", request.directionPoseData.endPoint)) return;
    TFTech::RobotAccuracyResult result;
    if (!TFTech::EpicEye::calculateRobotAccuracy(ip, request, result)) {
        std::cout << "Robot accuracy calculation failed." << std::endl;
        return;
    }
    std::cout << "Robot accuracy: boardDistance=" << result.boardDistance << ", robotDistance=" << result.robotDistance
              << ", difference=" << result.moveDistance << ", positionPrecision=" << result.positionPrecision << ", orientation=[";
    printArray(result.orientationPrecision);
    std::cout << "]" << std::endl;
}

void runHandEyeAccuracy(const std::string &ip, TFTech::HandEyeInstallationType installationType, const TFTech::RobotParameters &robot) {
    // 使用已保存的手眼结果将新标定板位姿转换到机器人基坐标系。
    // Eye-in-Hand 需要当前机器人位姿；Eye-to-Hand 的相机固定，robotPose 为空。
    TFTech::CalibrationBoardPose board;
    if (!captureBoard(ip, "Place the board in the view, then press Enter to capture for result verification.", board)) return;
    TFTech::HandEyeAccuracyRequest request;
    request.boardPoseArray = board.boardPoseArray;
    request.gridSize = board.gridSize;
    request.directionZ = readChoice("Board Z direction: 0=Up, 1=Down", {0, 1}) == 0 ? "up" : "down";
    if (installationType == TFTech::HandEyeInstallationType::EyeInHand) request.robotPose = readRobotPose(robot);
    TFTech::HandEyeAccuracyResult result;
    if (!TFTech::EpicEye::calculateHandEyeAccuracy(ip, request, result)) {
        std::cout << "Hand-eye accuracy check failed." << std::endl;
        return;
    }
    std::cout << "Board pose in robot base coordinates: [";
    printArray(result.boardPoseArray);
    std::cout << "]" << std::endl;
}

}  // namespace

int main(int argc, char **argv) {
    std::cout << "SDK Version: " << TFTech::EpicEye::getSDKVersion() << std::endl;
    std::cout << "Hand-eye calibration console workflow." << std::endl;
    std::cout << "Usage: HandEyeCalibration [camera_ip]" << std::endl;
    const std::string ip = resolveIp(argc, argv);
    if (ip.empty()) {
        std::cout << "Camera not found." << std::endl;
        return 1;
    }

    // Example 自行读取机器人库并配置相机，不能依赖网页中的历史选择。
    TFTech::RobotLibrary library;
    if (!TFTech::EpicEye::getRobotLibrary(ip, library) || library.empty() || library.begin()->second.empty()) {
        std::cout << "Failed to read robot library." << std::endl;
        return 1;
    }
    const TFTech::RobotInfo &firstRobot = library.begin()->second.front();
    TFTech::RobotParameters robot = firstRobot;
    std::cout << "Robot library loaded: " << library.size() << " brands. Default robot: [" << robot.brand << "] " << robot.model << std::endl;
    const TFTech::HandEyeInstallationType installationType = readChoice("Installation type: 0=Eye-To-Hand, 1=Eye-In-Hand", {0, 1}) == 0
        ? TFTech::HandEyeInstallationType::EyeToHand
        : TFTech::HandEyeInstallationType::EyeInHand;
    // 相机端将根据这里保存的规则解释后续 robotPose。
    if (!TFTech::EpicEye::configureHandEyeCalibration(ip, installationType, robot)) {
        std::cout << "Failed to save robot parameters." << std::endl;
        return 1;
    }
    std::cout << "Configured: robot=[" << robot.brand << "] " << robot.model << ", axis=" << robot.axisNumber
              << ", rotation=" << rotationTypeName(robot.rotationType) << ", euler=" << eulerTypeName(robot.eulerType)
              << ", unit=" << (robot.angleUnit == TFTech::RobotAngleUnit::Radian ? "Radian" : "Degree") << std::endl;
    std::cout << "Pose fields: " << poseMarks(robot) << std::endl;

    std::vector<TFTech::HandEyePoint> points;
    while (true) {
        const int action = readChoice("1=Capture point  2=Calculate  3=Robot accuracy check  4=List points  5=Clear points  0=Exit", {0, 1, 2, 3, 4, 5});
        if (action == 0) return 0;
        if (action == 1) capturePoint(ip, robot, points);
        else if (action == 2) {
            if (calculate(ip, installationType, robot, points) && readChoice("Run hand-eye result accuracy check now? 0=No, 1=Yes", {0, 1}) == 1) {
                runHandEyeAccuracy(ip, installationType, robot);
            }
        } else if (action == 3) runRobotAccuracy(ip, robot);
        else if (action == 4) {
            if (points.empty()) std::cout << "No points collected." << std::endl;
            for (const auto &point : points) {
                std::cout << "#" << point.id << ": board=[";
                printArray(point.boardPoseArray);
                std::cout << "], robot=[";
                for (size_t index = 0; index < point.robotPose.size(); ++index) {
                    if (index > 0) std::cout << ", ";
                    std::cout << point.robotPose[index];
                }
                std::cout << "]" << std::endl;
            }
        } else {
            points.clear();
            std::cout << "All collected points were cleared." << std::endl;
        }
    }
}
