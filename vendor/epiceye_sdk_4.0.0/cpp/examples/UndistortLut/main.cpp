/*
 * 作用：演示在线获取、离线计算和清理去畸变 LUT 缓存。
 * 数据格式：LUT 每像素包含两个 float 映射坐标 (u',v')；全零畸变不需要 LUT。
 * 缓存范围：清理操作只影响当前 SDK 进程，不修改相机。
 * 相机影响：在线路径只读；离线路径不连接相机。
 */
#include "epiceye.h"

#include <iostream>
#include <iomanip>
#include <string>
#include <sstream>

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
    std::cout << "---------------Undistort LUT---------------" << std::endl;

    const std::string ip = resolveIp(argc, argv);
    if (ip.empty()) {
        // Demo: 离线计算模式不需要在线相机
        std::cout << std::endl;
        std::cout << "--- computeUndistortLut (offline, no camera) ---" << std::endl;
        std::vector<double> demoCameraMatrix = {
            1420.0, 0.0, 710.0,
            0.0, 1420.0, 710.0,
            0.0, 0.0, 1.0
        };
        std::vector<double> demoDistortion = {-0.05, 0.01, 0.0, 0.0, 0.0};
        std::vector<float> lut;
        if (TFTech::EpicEye::computeUndistortLut(1420, 1420, demoCameraMatrix, demoDistortion, lut)) {
            std::cout << "computeUndistortLut success! lut size: " << lut.size() << std::endl;
            std::cout << "lut[0..3]: " << lut[0] << ", " << lut[1] << ", " << lut[2] << ", " << lut[3] << std::endl;
        } else {
            std::cout << "computeUndistortLut failed." << std::endl;
            return 1;
        }
        return 0;
    }

    std::cout << "Using camera: " << ip << std::endl << std::endl;

    // 获取相机信息
    TFTech::EpicEyeInfo info;
    if (!TFTech::EpicEye::getInfo(ip, info)) {
        std::cout << "getInfo failed!" << std::endl;
        return 1;
    }
    std::cout << "Camera resolution: " << info.width << "x" << info.height << std::endl;

    // 获取内参
    std::vector<double> cameraMatrix;
    std::vector<double> distortion;
    if (!TFTech::EpicEye::getCameraMatrix(ip, cameraMatrix)) {
        std::cout << "getCameraMatrix failed!" << std::endl;
        return 1;
    }
    if (!TFTech::EpicEye::getDistortion(ip, distortion)) {
        std::cout << "getDistortion failed!" << std::endl;
        return 1;
    }

    std::cout << std::setprecision(17);
    std::cout << "cameraMatrix: ";
    for (auto v : cameraMatrix) std::cout << v << " ";
    std::cout << std::endl;
    std::cout << "distortion: ";
    for (auto v : distortion) std::cout << v << " ";
    std::cout << std::endl << std::endl;

    // 在线获取去畸变查找表
    std::cout << "--- getUndistortLut (online, from camera) ---" << std::endl;
    std::vector<float> lut;
    if (TFTech::EpicEye::getUndistortLut(ip, info.width, info.height, cameraMatrix, distortion, lut)) {
        std::cout << "getUndistortLut success! lut size: " << lut.size() << std::endl;
        std::cout << "lut[0..3]: " << lut[0] << ", " << lut[1] << ", " << lut[2] << ", " << lut[3] << std::endl;
    } else {
        std::cout << "getUndistortLut returned empty (distortion all zero or failed)" << std::endl;
    }

    // 离线计算
    std::cout << std::endl << "--- computeUndistortLut (offline) ---" << std::endl;
    std::vector<float> lut2;
    if (TFTech::EpicEye::computeUndistortLut(info.width, info.height, cameraMatrix, distortion, lut2)) {
        std::cout << "computeUndistortLut success! lut size: " << lut2.size() << std::endl;
    } else {
        std::cout << "computeUndistortLut failed." << std::endl;
    }

    // 清除缓存
    std::cout << std::endl << "--- clearUndistortLutCache ---" << std::endl;
    TFTech::EpicEye::clearUndistortLutCache(ip);
    std::cout << "Cache cleared for: " << ip << std::endl;

    return 0;
}
