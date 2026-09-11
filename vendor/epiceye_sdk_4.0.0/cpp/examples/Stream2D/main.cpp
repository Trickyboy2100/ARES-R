/*
 * 作用：查询 Stream2D 状态，并启动一个由 SDK 托管的 WebRTC 会话接收 H264 数据。
 * 输入：可选 camera_ip 和接收帧数；fps 只透传给相机，SDK 不做节流。
 * 输出：回调直接获得相机输出的 Annex-B H264 编码帧，不解码、不重新编码。
 * 生命周期：达到 Example 目标帧数后主动停止当前 RTC 会话。
 */
#include "epiceye.h"

#include <iostream>
#include <string>
#include <chrono>
#include <condition_variable>
#include <memory>
#include <mutex>
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

    // 查询 2D 流状态
    std::cout << "---------------getStream2DStatus---------------" << std::endl;
    TFTech::Stream2DStatus status;
    if (TFTech::EpicEye::getStream2DStatus(ip, status)) {
        std::cout << "isStreaming: " << (status.isStreaming ? "true" : "false") << std::endl;
        std::cout << "peerCount: " << status.peerCount << std::endl;
        std::cout << "cameraCount: " << status.cameraCount << std::endl;
    } else {
        std::cout << "getStream2DStatus failed!" << std::endl;
    }

    // 启动一个 Stream2D RTC 会话并接收帧
    std::cout << std::endl << "---------------startStream2DRtcSession---------------" << std::endl;
    TFTech::Stream2DRtcSessionOptions options;
    options.fps = 60;
    options.cameraIndex = 0;

    constexpr int targetFrameCount = 5;
    std::mutex frameMutex;
    std::condition_variable frameCondition;
    bool targetReached = false;
    auto onFrame = [&](const TFTech::Stream2DRtcFrame& frame) {
        std::cout << "Frame #" << frame.frameIndex
                  << " timestamp: " << frame.timestamp
                  << " codec: " << frame.codec
                  << " size: " << frame.sample.size() << " bytes" << std::endl;
        if (frame.frameIndex >= targetFrameCount) {
            std::lock_guard<std::mutex> lock(frameMutex);
            targetReached = true;
            frameCondition.notify_one();
        }
    };

    std::unique_ptr<TFTech::Stream2DRtcSession> session;
    bool sessionSucceeded = TFTech::EpicEye::startStream2DRtcSession(ip, options, onFrame, session);
    if (sessionSucceeded) {
        std::unique_lock<std::mutex> lock(frameMutex);
        sessionSucceeded = frameCondition.wait_for(lock, std::chrono::seconds(15), [&] { return targetReached; });
        lock.unlock();
        TFTech::EpicEye::stopStream2DRtcSession(session);
        std::cout << "Session stopped. Total frames: " << session->frameCount() << std::endl;
        if (!sessionSucceeded) {
            std::cout << "No 5 frames were received within 15 seconds." << std::endl;
        }
    } else {
        std::cout << "startStream2DRtcSession failed!" << std::endl;
    }

    // 查看关闭后的状态
    std::cout << std::endl << "---------------getStream2DStatus (after session)---------------" << std::endl;
    TFTech::Stream2DStatus statusAfter;
    if (TFTech::EpicEye::getStream2DStatus(ip, statusAfter)) {
        std::cout << "isStreaming: " << (statusAfter.isStreaming ? "true" : "false") << std::endl;
    }
    std::cout << std::endl << "Done." << std::endl;
    return sessionSucceeded ? 0 : 1;
}
