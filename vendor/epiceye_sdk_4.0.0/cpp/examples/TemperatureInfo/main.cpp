/*
 * 作用：读取 V4 相机内部温度传感器的当前值。
 * 输入：可选 camera_ip；未指定时阻塞搜索并使用第一台相机。
 * 输出：温度键由具体型号决定，业务代码不应写死键集合。
 * 相机影响：只读，不触发拍摄，不修改配置。
 */
#include "epiceye.h"

#include <iostream>
#include <string>
#include <vector>
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

int main(int argc, char **argv) {
#ifdef _WIN32
    SetConsoleOutputCP(CP_UTF8);
#endif
    const std::string ip = resolveIp(argc, argv);
    if (ip.empty()) {
        return 1;
    }

    std::cout << "Camera: " << ip << std::endl;
    nlohmann::json temperatureInfo;
    if (!TFTech::EpicEye::getTemperatureInfo(ip, temperatureInfo)) {
        std::cerr << "getTemperatureInfo failed" << std::endl;
        return 1;
    }

    for (auto item = temperatureInfo.cbegin(); item != temperatureInfo.cend(); ++item) {
        std::cout << item.key() << ": ";
        if (item.value().is_null()) {
            std::cout << "N/A";
        } else if (item.value().is_string()) {
            std::cout << item.value().get<std::string>();
        } else {
            std::cout << item.value().dump();
        }
        if (item.key().size() >= 8 && item.key().compare(item.key().size() - 8, 8, "_celsius") == 0 && !item.value().is_null()) {
            std::cout << " °C";
        }
        std::cout << std::endl;
    }
    return 0;
}
