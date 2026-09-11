/*
 * 作用：读取相机身份、版本、网络地址、型号和重建器类型。
 * 输入：可选 camera_ip；未指定时阻塞搜索并使用第一台相机。
 * 输出：EpicEyeInfo 主要字段以及 V4 ReconstructorType。
 * 相机影响：只读，不触发拍摄，不修改配置。
 */
#include "epiceye.h"

#include <iostream>
#include <iomanip>
#include <string>
#ifdef _WIN32
#include <Windows.h>
#endif

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
#ifdef _WIN32
    SetConsoleOutputCP(CP_UTF8);
#endif
    std::cout << "SDK Version: " << TFTech::EpicEye::getSDKVersion() << std::endl;
    const std::string ip = resolveIp(argc, argv);
    if (ip.empty()) {
        return 1;
    }

    std::cout << "---------------get " << ip << " EpicEyeInfo---------------" << std::endl;
    TFTech::EpicEyeInfo info;
    if (!TFTech::EpicEye::getInfo(ip, info)) {
        std::cout << "getInfo failed!" << std::endl;
        return 1;
    }
    std::cout << "SN: " << info.SN << std::endl;
    std::cout << "IP: " << info.IP << std::endl;
    std::cout << "Version: " << info.Version << std::endl;
    std::cout << "model: " << info.model << std::endl;
    std::cout << "alias: " << info.alias << std::endl;
    std::cout << "resolution: " << info.width << "x" << info.height << std::endl;

    // 探测重建器类型（V4）
    TFTech::ReconstructorType recType;
    if (TFTech::EpicEye::getReconstructorType(ip, recType)) {
        std::cout << "ReconstructorType: " << static_cast<int>(recType) << std::endl;
    }

    std::cout << std::endl;
    return 0;
}
