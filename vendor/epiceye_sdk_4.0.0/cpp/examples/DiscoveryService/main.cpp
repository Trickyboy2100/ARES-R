/*
 * 作用：启动常驻发现服务，通过回调持续输出在线相机列表变化。
 * 区别：searchCamera 是阻塞式一次性测试；本示例适合应用程序长期维护设备列表。
 * 生命周期：注册回调 -> startDiscovery -> 用户结束 -> stopDiscovery -> 清理回调。
 * 相机影响：只监听广播，不修改设备。
 */
#include "epiceye.h"

#include <iostream>
#include <iomanip>
#include <string>
#include <vector>

int main(int argc, char** argv) {
    std::cout << "SDK Version: " << TFTech::EpicEye::getSDKVersion() << std::endl;
    std::cout << "---------------EpicEye Continuous Discovery---------------" << std::endl;

    TFTech::EpicEye::setDiscoveryCallback([]() {
        std::vector<TFTech::EpicEyeInfo> list;
        TFTech::EpicEye::getDiscoveredCameras(list);
        std::cout << "\n[Updated] Camera count: " << list.size() << std::endl;
        for (size_t i = 0; i < list.size(); i++) {
            std::cout << std::right << std::setw(3) << i << ": "
                      << std::left << std::setw(20) << std::setfill(' ') << list[i].IP
                      << std::left << std::setw(30) << list[i].SN << std::endl;
        }
    });

    TFTech::EpicEye::startDiscovery();
    std::cout << "Continuous discovery started. Listening for cameras..." << std::endl;
    std::cout << "Press Enter to stop." << std::endl << std::endl;

    std::cin.get();

    TFTech::EpicEye::stopDiscovery();
    std::cout << "Continuous discovery stopped." << std::endl;

    return 0;
}
