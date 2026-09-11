/*
 * 作用：触发一次拍摄，按 frameId 下载 EpicRaw，并从同一文档解码图像、深度和点云。
 * 输入：可选 camera_ip；未指定时阻塞搜索并使用第一台相机。
 * 关键点：frameId 把触发与取帧绑定，避免读到其他拍摄产生的帧。
 * 相机影响：触发一次拍摄，不修改配置。
 */
#include "epiceye.h"

#include <iomanip>
#include <iostream>
#include <string>
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

int main(int argc, char **argv) {
    const std::string ip = resolveIp(argc, argv);
    if (ip.empty()) {
        return 1;
    }

    std::string frameId;
    if (!TFTech::EpicEye::triggerFrame(ip, frameId, true)) {
        std::cerr << "triggerFrame failed!" << std::endl;
        return 1;
    }

    std::vector<uint8_t> rawBytes;
    if (!TFTech::EpicEye::getFrameInEpicRaw(ip, frameId, rawBytes)) {
        std::cerr << "getFrameInEpicRaw failed!" << std::endl;
        return 1;
    }

    TFTech::EpicRawDocument document;
    if (!TFTech::EpicEye::tryLoadEpicRawDocumentFromBytes(rawBytes, document)) {
        std::cerr << "tryLoadEpicRawDocumentFromBytes failed!" << std::endl;
        return 1;
    }
    std::cout << "EpicRaw bytes: " << rawBytes.size() << std::endl;

    std::vector<uint8_t> image;
    int imageWidth = 0;
    int imageHeight = 0;
    int pixelByteSize = 0;
    if (TFTech::EpicEye::decodeImageFromEpicRaw(
            document, image, imageWidth, imageHeight, pixelByteSize)) {
        std::cout << "Image: " << imageWidth << "x" << imageHeight
                  << ", bytes=" << image.size()
                  << ", channelBytes=" << pixelByteSize << std::endl;
    }

    std::vector<double> distortion;
    std::vector<double> cameraMatrix;
    int depthWidth = 0;
    int depthHeight = 0;
    TFTech::EpicEye::getDepthIntrinsicsFromEpicRaw(
        document, distortion, cameraMatrix, depthWidth, depthHeight);
    std::vector<float> lut;
    TFTech::EpicEye::getUndistortLut(
        ip, depthWidth, depthHeight, cameraMatrix, distortion, lut);

    std::vector<float> pointCloud;
    int pointCloudWidth = 0;
    int pointCloudHeight = 0;
    if (TFTech::EpicEye::decodePointCloudFromEpicRaw(
            document, lut, pointCloud, pointCloudWidth, pointCloudHeight)) {
        std::cout << "PointCloud: " << pointCloudWidth << "x" << pointCloudHeight
                  << ", floats=" << pointCloud.size() << std::endl;
    } else {
        std::cerr << "PointCloud: (none)" << std::endl;
        return 1;
    }
    return 0;
}
