/*
 * 作用：识别目标相机，并通过 UDP 下发 DHCP 或静态 IP 配置。
 * 输入：<targetIP> [newIP] [netMask] [DHCP|Manual]；未给 newIP 时默认 DHCP。
 * 相机影响：会修改网络配置，旧 IP 可能立即失效。
 * 重要：发送成功不等于相机确认，结束后应重新搜索验证实际 IP。
 */
#include "epiceye.h"

#include <iostream>
#include <iomanip>
#include <string>

int main(int argc, char** argv) {
    std::cout << "SDK Version: " << TFTech::EpicEye::getSDKVersion() << std::endl;
    std::cout << "---------------Camera IP Config---------------" << std::endl;

    const bool hasSpecifiedTarget = argc > 1 && argv[1][0] != '\0';
    // 搜索相机
    std::vector<TFTech::EpicEyeInfo> cameraList;
    if (!TFTech::EpicEye::searchCamera(cameraList)) {
        std::cout << "Camera not found!" << std::endl;
    } else {
        std::cout << "Camera found: " << cameraList.size() << std::endl;
        for (size_t i = 0; i < cameraList.size(); i++) {
            std::cout << std::right << std::setw(3) << i << ": "
                      << std::left << std::setw(20) << std::setfill(' ') << cameraList[i].IP
                      << std::left << std::setw(30) << cameraList[i].SN << std::endl;
        }
    }

    if (!hasSpecifiedTarget) {
        std::cout << std::endl;
        std::cout << "Usage: " << argv[0] << " <targetIP> [newIP] [netMask] [DHCP|Manual]" << std::endl;
        std::cout << "Example (DHCP):  " << argv[0] << " 192.168.1.100" << std::endl;
        std::cout << "Example (Manual): " << argv[0] << " 192.168.1.100 192.168.1.200 255.255.255.0 Manual" << std::endl;
        std::cout << std::endl;
        std::cout << "No target IP given; showing current cameras only." << std::endl;
        return 0;
    }

    TFTech::EpicEyeIPConfig config;

    std::string targetIP = argv[1];
    const size_t portSeparator = targetIP.find(':');
    if (portSeparator != std::string::npos) {
        targetIP = targetIP.substr(0, portSeparator);
    }
    std::cout << "DestinationIP: " << targetIP << std::endl;

    TFTech::EpicEyeInfo targetCamera;
    bool targetFound = false;
    for (const auto& camera : cameraList) {
        std::string cameraIP = camera.IP;
        const size_t cameraPortSeparator = cameraIP.find(':');
        if (cameraPortSeparator != std::string::npos) {
            cameraIP = cameraIP.substr(0, cameraPortSeparator);
        }
        if (cameraIP == targetIP) {
            targetCamera = camera;
            targetFound = true;
            break;
        }
    }
    if (!targetFound) {
        targetFound = TFTech::EpicEye::getInfo(targetIP + ":5000", targetCamera);
    }
    if (!targetFound || targetCamera.SN.empty() || targetCamera.SN.find("EpicEyeSN") != std::string::npos) {
        std::cout << "Cannot identify the target camera. Confirm that the target IP is reachable or discoverable, then retry." << std::endl;
        return 1;
    }

    config.sn = targetCamera.SN;
    std::cout << "Target camera SN: " << targetCamera.SN << std::endl;

    if (argc >= 3) {
        config.ip = argv[2];
    }
    if (argc >= 4) {
        config.netMask = argv[3];
    }
    if (argc >= 5) {
        config.type = argv[4];
    }

    std::cout << "Config: type=" << config.type
              << " ip=" << config.ip
              << " netMask=" << config.netMask << std::endl;

    if (TFTech::EpicEye::setEpicEyeIPConfig(targetIP, config)) {
        std::cout << "setEpicEyeIPConfig request sent (UDP has no ack; verify the new address by rediscovery)." << std::endl;
    } else {
        std::cout << "setEpicEyeIPConfig request could not be sent." << std::endl;
        return 1;
    }

    return 0;
}
