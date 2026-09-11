/*
 * 作用：通过 UDP 广播执行一次阻塞式搜索，并打印局域网相机列表。
 * 输入：无。
 * 限制：仅用于测试和临时诊断；正式应用应使用 startDiscovery/stopDiscovery 与回调。
 * 相机影响：只发送/接收发现报文，不修改设备。
 */
#include "epiceye.h"

#include <iostream>
#include <iomanip>
#include <string>

int main(int argc, char** argv) {
    std::cout << "SDK Version: " << TFTech::EpicEye::getSDKVersion() << std::endl;
    std::cout << "---------------search EpicEye camera---------------" << std::endl;

    std::vector<TFTech::EpicEyeInfo> cameraList;
    if (TFTech::EpicEye::searchCamera(cameraList)) {
        std::cout << "Camera found: " << cameraList.size() << std::endl;
        for (size_t i = 0; i < cameraList.size(); i++) {
            std::cout << std::right << std::setw(3) << i << ": "
                      << std::left << std::setw(20) << std::setfill(' ') << cameraList[i].IP
                      << std::left << std::setw(30) << cameraList[i].SN << std::endl;
        }
    } else {
        std::cout << "Camera not found!" << std::endl;
        return 1;
    }

    return 0;
}
