/*
 * 作用：演示线扫完整生命周期：查询状态 -> 启动 -> 等待 EOT -> 查询最终状态。
 * 输入：可选 camera_ip；仅适用于摆动线扫或固定线扫相机。
 * 清理规则：正常完成后不主动 Stop；超时或异常时才 Stop。
 * 相机影响：会启动真实线扫运动/采集，运行前必须确认设备周围安全。
 */
#include "epiceye.h"

#include <iostream>
#include <iomanip>
#include <string>
#include <thread>
#include <chrono>
#include <vector>

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

    std::cout << std::endl << "Using IP: " << ip << std::endl;

    // 查询线扫状态
    std::cout << "---------------getLineScanStatus---------------" << std::endl;
    TFTech::LineScanStatus status;
    if (TFTech::EpicEye::getLineScanStatus(ip, status)) {
        std::cout << "status: " << TFTech::EpicEye::lineScanStatusToString(status) << std::endl;
    } else {
        std::cout << "getLineScanStatus failed!" << std::endl;
        return 1;
    }

    // 启用线扫
    std::cout << std::endl << "---------------startLineScan---------------" << std::endl;
    bool enableTexture = true;
    bool deferEpicRawSave = false;
    std::string frameId;
    if (TFTech::EpicEye::startLineScan(ip, frameId, enableTexture, deferEpicRawSave)) {
        std::cout << "startLineScan success! frameId: " << frameId << std::endl;
    } else {
        std::cout << "startLineScan failed!" << std::endl;
        return 1;
    }

    // 通过 WebSocket 持续消费线扫数据并阻塞等待 EOT
    std::cout << std::endl << "---------------waitLineScanCompletion---------------" << std::endl;
    int timeoutMs = 60000;
    if (TFTech::EpicEye::waitLineScanCompletion(ip, timeoutMs)) {
        std::cout << "LineScan completed!" << std::endl;
        std::vector<uint8_t> epicRawBytes;
        if (!TFTech::EpicEye::getFrameInEpicRaw(ip, frameId, epicRawBytes)) {
            std::cerr << "getFrameInEpicRaw failed after LineScan completion!" << std::endl;
            return 1;
        }
        std::cout << "EpicRaw bytes: " << epicRawBytes.size() << std::endl;
    } else {
        std::cout << "waitLineScanCompletion timed out!" << std::endl;

        // 超时则手动停止
        std::cout << std::endl << "---------------stopLineScan---------------" << std::endl;
        std::string statusHex;
        if (TFTech::EpicEye::stopLineScan(ip, statusHex)) {
            std::cout << "stopLineScan success! statusHex: " << statusHex << std::endl;
        } else {
            std::cout << "stopLineScan failed!" << std::endl;
        }
        return 1;
    }

    // 最终状态
    std::cout << std::endl << "---------------getLineScanStatus (final)---------------" << std::endl;
    TFTech::LineScanStatus finalStatus;
    if (TFTech::EpicEye::getLineScanStatus(ip, finalStatus)) {
        std::cout << "status: " << TFTech::EpicEye::lineScanStatusToString(finalStatus) << std::endl;
    }

    std::cout << std::endl << "Done." << std::endl;
    return 0;
}
