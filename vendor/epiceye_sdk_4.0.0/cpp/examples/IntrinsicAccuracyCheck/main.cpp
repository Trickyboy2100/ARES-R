/*
 * 作用：执行一次内参精度检查，输出标定板位姿、尺寸误差、立体/彩色对齐误差和倾角提示。
 * 输入：可选 camera_ip；未指定时阻塞搜索并使用第一台相机。
 * 前提：标定板完整位于视野中，并满足返回的距离、尺寸和倾角要求。
 * 相机影响：触发拍摄和检查计算，但不会写入或覆盖内参。
 */
#include "epiceye.h"

#include <cmath>
#include <iomanip>
#include <iostream>
#include <string>
#include <vector>

namespace {

std::string resolveIp(int argc, char** argv) {
    if (argc > 1 && argv[1][0] != '\0') {
        return argv[1];
    }

    std::vector<TFTech::EpicEyeInfo> cameras;
    if (!TFTech::EpicEye::searchCamera(cameras) || cameras.empty()) {
        std::cerr << "Camera not found!" << std::endl;
        return {};
    }
    return cameras[0].IP;
}

void printResult(const TFTech::IntrinsicAccuracyCheckResult &result) {
    std::cout << std::fixed << std::setprecision(6);
    std::cout << "Board type: " << result.value("boardTypeDetected", -1) << std::endl;
    std::cout << "Board hint: " << result.value("boardHint", std::string()) << std::endl;
    std::cout << "Depth camera accuracy: " << result.value("calibrationBoardSizeRatio", 0.0)
              << ", pass: " << std::boolalpha << result.value("cameraAccuracyPass", false) << std::endl;
    std::cout << "Depth average alignment error: " << result.value("stereoAveragePixelError", 0.0)
              << ", pass: " << result.value("stereoAveragePass", false) << std::endl;
    std::cout << "Depth max alignment error: " << result.value("stereoMaxPixelError", 0.0)
              << ", pass: " << result.value("stereoMaxPass", false) << std::endl;
    std::cout << "Color camera accuracy: " << result.value("colorCalibrationBoardSizeRatio", 0.0)
              << ", pass: " << result.value("colorCameraAccuracyPass", false) << std::endl;
    std::cout << "Color average alignment error: " << result.value("colorStereoAveragePixelError", 0.0)
              << ", pass: " << result.value("colorStereoAveragePass", false) << std::endl;
    std::cout << "Color max alignment error: " << result.value("colorStereoMaxPixelError", 0.0)
              << ", pass: " << result.value("colorStereoMaxPass", false) << std::endl;
    std::cout << "Stereo metrics valid: " << result.value("stereoMetricsValid", false) << std::endl;
    std::cout << "Board tilt angle: " << result.value("boardTiltAngle", 0.0)
              << ", warning: " << result.value("boardTiltWarning", false) << std::endl;

    auto previews = result.find("previewImages");
    std::size_t previewCount = previews != result.end() && previews->is_array() ? previews->size() : 0;
    std::cout << "Preview image count: " << previewCount << std::endl;

    bool boardPositionValid = result.value("boardPositionValid", false);
    auto pose = result.find("boardPose");
    if (boardPositionValid && pose != result.end() && pose->is_array() && pose->size() >= 3) {
        double x = (*pose)[0].get<double>();
        double y = (*pose)[1].get<double>();
        double z = (*pose)[2].get<double>();
        std::cout << std::setprecision(1);
        std::cout << "Board position (mm): X=" << x << ", Y=" << y << ", Z=" << z << std::endl;
        std::cout << "Board distance (mm): " << std::sqrt(x * x + y * y + z * z) << std::endl;
    } else {
        std::cout << "Board position: invalid" << std::endl;
    }

    bool colorMetricsPresent = result.value("colorCalibrationBoardSizeRatio", 0.0) > 0
        || result.value("colorStereoAveragePixelError", 0.0) > 0
        || result.value("colorStereoMaxPixelError", 0.0) > 0;
    bool stereoMetricsValid = result.value("stereoMetricsValid", false);
    bool checkPassed = result.value("cameraAccuracyPass", false)
        && (!stereoMetricsValid
            || result.value("stereoAveragePass", false) && result.value("stereoMaxPass", false))
        && (!colorMetricsPresent
            || result.value("colorCameraAccuracyPass", false)
                && result.value("colorStereoAveragePass", false)
                && result.value("colorStereoMaxPass", false));
    std::cout << "Intrinsic accuracy check passed: " << checkPassed << std::endl;
}

}  // namespace

int main(int argc, char **argv) {
    std::string ip = resolveIp(argc, argv);
    if (ip.empty()) {
        return 1;
    }

    std::cout << "Camera: " << ip << std::endl;
    TFTech::IntrinsicAccuracyCheckResult result;
    if (!TFTech::EpicEye::checkIntrinsicAccuracy(ip, result)) {
        std::cerr << "checkIntrinsicAccuracy failed." << std::endl;
        return 1;
    }

    printResult(result);
    return 0;
}
