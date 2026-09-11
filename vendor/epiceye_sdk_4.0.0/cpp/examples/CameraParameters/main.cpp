/*
 * 作用：读取相机保存的完整内外参，并读取当前深度输出的相机矩阵与畸变参数。
 * 输入：可选 camera_ip；未指定时阻塞搜索并使用第一台相机。
 * 说明：V3 为扁平参数，V4 为多路图像源的详细 CameraParametersConfig。
 * 相机影响：只读，不计算、不写入内参。
 */
#include "epiceye.h"

#include <iomanip>
#include <iostream>
#include <string>

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

int main(int argc, char** argv) {
    std::cout << "SDK Version: " << TFTech::EpicEye::getSDKVersion() << std::endl;
    const std::string ip = resolveIp(argc, argv);
    if (ip.empty()) {
        return 1;
    }

    std::cout << "---------------get " << ip << " CameraParameters---------------" << std::endl;
    nlohmann::json cameraParameters;
    if (!TFTech::EpicEye::getCameraParameters(ip, cameraParameters)) {
        std::cout << "getCameraParameters failed!" << std::endl;
        return 1;
    }
    std::cout << cameraParameters.dump(2) << std::endl;

    std::vector<double> cameraMatrix;
    if (!TFTech::EpicEye::getCameraMatrix(ip, cameraMatrix)) {
        std::cout << "getCameraMatrix failed!" << std::endl;
        return 1;
    }
    std::cout << "Current depth cameraMatrix (3x3 row-major): ";
    std::cout << std::setprecision(17);
    for (const double value : cameraMatrix) std::cout << value << " ";
    std::cout << std::endl;

    std::vector<double> distortion;
    if (!TFTech::EpicEye::getDistortion(ip, distortion)) {
        std::cout << "getDistortion failed!" << std::endl;
        return 1;
    }
    std::cout << "Current depth distortion (k1,k2,p1,p2,k3): ";
    for (const double value : distortion) std::cout << value << " ";
    std::cout << std::endl;

    return 0;
}
