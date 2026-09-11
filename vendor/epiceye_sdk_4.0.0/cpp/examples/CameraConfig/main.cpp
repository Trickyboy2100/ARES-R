/*
 * 作用：演示相机配置、参数预设列表和配置样式的完整读写链路。
 * 输入：可选 camera_ip；未指定时阻塞搜索并使用第一台相机。
 * 流程：读取配置/预设/样式 -> 原样回写配置 -> 切换到首个参数预设。
 * 相机影响：最后两步会写相机，当前参数预设可能发生切换。
 */
#include "epiceye.h"
#include "nlohmann_json.hpp"

#include <iostream>
#include <iomanip>
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

void printConfigJson(const nlohmann::json& configJson, const std::string& printOffset = "") {
    for (const auto& item : configJson.items()) {
        std::cout << printOffset << item.key() << ": ";
        if (!item.key().empty() && configJson[item.key()].is_object()) {
            std::cout << "{" << std::endl;
            printConfigJson(configJson[item.key()], printOffset + "  ");
            std::cout << printOffset << "}" << std::endl;
        } else if (!item.key().empty() && configJson[item.key()].is_array()) {
            std::cout << "[" << std::endl;
            for (size_t i = 0; i < configJson[item.key()].size(); i++) {
                if (configJson[item.key()][i].is_object()) {
                    std::cout << printOffset << "  {" << std::endl;
                    printConfigJson(configJson[item.key()][i], printOffset + "    ");
                    std::cout << printOffset << "  }" << std::endl;
                    continue;
                }
                std::cout << printOffset << "  " << configJson[item.key()][i] << std::endl;
            }
            std::cout << printOffset << "]" << std::endl;
        } else if (!item.key().empty()) {
            std::cout << item.value() << std::endl;
        }
    }
}

int main(int argc, char** argv) {
    std::cout << "SDK Version: " << TFTech::EpicEye::getSDKVersion() << std::endl;
    const std::string ip = resolveIp(argc, argv);
    if (ip.empty()) {
        return 1;
    }

    std::cout << "---------------getConfig (" << ip << ")---------------" << std::endl;

    nlohmann::json configJson;
    if (!TFTech::EpicEye::getConfig(ip, configJson)) {
        std::cout << "getConfig failed!" << std::endl;
        return 1;
    }
    printConfigJson(configJson);

    // SDK 按相机版本严格校验协议字段，对外统一提供 Id/Name。
    std::cout << "---------------getParameterList (" << ip << ")---------------" << std::endl;
    std::vector<TFTech::SimpleCameraParameter> parameterPresets;
    if (!TFTech::EpicEye::getParameterList(ip, parameterPresets)) {
        std::cout << "getParameterList failed!" << std::endl;
        return 1;
    }
    for (const auto &preset : parameterPresets) {
        std::cout << preset.Name << " (" << preset.Id << ")" << std::endl;
    }

    std::cout << "---------------getConfigStyle (" << ip << ")---------------" << std::endl;
    nlohmann::json styleJson;
    if (TFTech::EpicEye::getConfigStyle(ip, styleJson)) {
        std::string styleStr = styleJson.dump(2);
        std::cout << styleStr.substr(0, 500) << std::endl;
    } else {
        std::cout << "getConfigStyle failed!" << std::endl;
        return 1;
    }

    std::cout << "---------------setConfig (" << ip << ")---------------" << std::endl;
    if (!TFTech::EpicEye::setConfig(ip, configJson)) {
        std::cout << "setConfig failed!" << std::endl;
        return 1;
    }
    std::cout << "setConfig success!" << std::endl;

    std::cout << "---------------setParameter (" << ip << ")---------------" << std::endl;
    if (parameterPresets.empty()) {
        std::cerr << "setParameter failed: parameter list is empty" << std::endl;
        return 1;
    }
    const TFTech::SimpleCameraParameter &firstPreset = parameterPresets.front();
    std::cout << "selecting param: " << firstPreset.Name << " (" << firstPreset.Id << ")" << std::endl;
    if (!TFTech::EpicEye::setParameter(ip, firstPreset.Id)) {
        std::cout << "setParameter failed!" << std::endl;
        return 1;
    }
    std::cout << "setParameter success!" << std::endl;

    std::cout << std::endl;
    return 0;
}
