/*
 * 作用：加载一份 EpicRaw，并离线解析拍摄配置、内参、图像、深度、点云和元数据。
 * 输入：首参为 .epicraw 文件时完全离线；否则按相机 IP 或阻塞搜索获取一帧。
 * 关键点：文档只解析一次，后续各项解码复用同一对象。
 * 相机影响：文件模式不连接相机；在线模式触发一次拍摄但不修改配置。
 */
#include "epiceye.h"

#include <iostream>
#include <filesystem>
#include <fstream>
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

int main(int argc, char** argv) {
    std::cout << "SDK Version: " << TFTech::EpicEye::getSDKVersion() << std::endl;
    std::cout << "---------------EpicRaw Offline Parse---------------" << std::endl;

    std::string ip;
    std::vector<uint8_t> epicRawBytes;

    if (argc > 1 && std::filesystem::is_regular_file(argv[1])) {
        // 从文件加载 EpicRaw
        std::cout << "Loading EpicRaw from file: " << argv[1] << std::endl;
        std::ifstream file(argv[1], std::ios::binary | std::ios::ate);
        if (!file.is_open()) {
            std::cerr << "Cannot open file: " << argv[1] << std::endl;
            return 1;
        }
        std::streamsize size = file.tellg();
        file.seekg(0, std::ios::beg);
        epicRawBytes.resize(static_cast<size_t>(size));
        if (size > 0) {
            file.read(reinterpret_cast<char *>(epicRawBytes.data()), size);
        }
        file.close();
        std::cout << "Loaded " << size << " bytes" << std::endl;
    } else {
        // 从相机获取一帧 EpicRaw
        ip = resolveIp(argc, argv);
        if (ip.empty()) {
            std::cerr << "Pass an EpicRaw file path or camera IP as the first argument." << std::endl;
            return 1;
        }
        std::cout << "Using camera: " << ip << std::endl;

        std::string frameID;
        if (!TFTech::EpicEye::triggerFrame(ip, frameID, true)) {
            std::cerr << "triggerFrame failed!" << std::endl;
            return 1;
        }
        std::cout << "frameID: " << frameID << std::endl;

        if (!TFTech::EpicEye::getFrameInEpicRaw(ip, frameID, epicRawBytes)) {
            std::cerr << "getFrameInEpicRaw failed!" << std::endl;
            return 1;
        }
        std::cout << "Got " << epicRawBytes.size() << " bytes from camera" << std::endl;
    }

    // 1. 加载 EpicRaw 文档
    std::cout << std::endl << "--- tryLoadEpicRawDocumentFromBytes ---" << std::endl;
    TFTech::EpicRawDocument document;
    if (!TFTech::EpicEye::tryLoadEpicRawDocumentFromBytes(epicRawBytes, document)) {
        std::cerr << "Failed to load EpicRaw document!" << std::endl;
        return 1;
    }
    std::cout << "EpicRaw loaded: " << document.fileType << std::endl;

    // 2. 拍摄时相机配置
    std::cout << std::endl << "--- decodeCameraConfigFromEpicRaw ---" << std::endl;
    nlohmann::json cameraConfig;
    if (TFTech::EpicEye::decodeCameraConfigFromEpicRaw(document, cameraConfig)) {
        std::cout << cameraConfig.dump(2) << std::endl;
    } else {
        std::cout << "(no camera config found)" << std::endl;
    }

    // 3. 获取深度内参（同时拿到 depth 尺寸）
    std::cout << std::endl << "--- getDepthIntrinsicsFromEpicRaw ---" << std::endl;
    std::vector<double> distortion, cameraMatrix;
    int depthWidth = 0, depthHeight = 0;
    if (TFTech::EpicEye::getDepthIntrinsicsFromEpicRaw(document, distortion, cameraMatrix,
                                                       depthWidth, depthHeight)) {
        std::cout << "Depth size: " << depthWidth << "x" << depthHeight << std::endl;
        std::cout << "CameraMatrix: ";
        for (auto v : cameraMatrix) std::cout << v << " ";
        std::cout << std::endl;
        std::cout << "Distortion: ";
        for (auto v : distortion) std::cout << v << " ";
        std::cout << std::endl;
    }

    // 4. 解码图像
    std::cout << std::endl << "--- decodeImageFromEpicRaw ---" << std::endl;
    std::vector<uint8_t> imageBuffer;
    int imgW = 0, imgH = 0, pixelByteSize = 0;
    if (TFTech::EpicEye::decodeImageFromEpicRaw(
            document, imageBuffer, imgW, imgH, pixelByteSize)) {
        std::cout << "decodeImage success! " << imgW << "x" << imgH
                  << " pixelByteSize: " << pixelByteSize << std::endl;
    } else {
        std::cout << "decodeImage: no image data in this EpicRaw." << std::endl;
    }

    std::cout << std::endl << "--- decodeImageFromEpicRaw by type ---" << std::endl;
    TFTech::EpicRawImage rawImage;
    if (TFTech::EpicEye::decodeImageFromEpicRaw(
            document, TFTech::EpicRaw3DataType::TextureBGR, rawImage)) {
        std::cout << "raw image: type=" << static_cast<int>(rawImage.dataType)
                  << " size=" << rawImage.width << "x" << rawImage.height
                  << " matType=" << rawImage.matType
                  << " bytes=" << rawImage.data.size() << std::endl;
    } else {
        std::cout << "raw image: requested element not found or invalid." << std::endl;
    }

    // 5. 解码深度图
    std::cout << std::endl << "--- decodeDepthFromEpicRaw ---" << std::endl;
    std::vector<float> depthBuffer;
    int decodedDepthWidth = 0, decodedDepthHeight = 0;
    if (TFTech::EpicEye::decodeDepthFromEpicRaw(
            document, depthBuffer, decodedDepthWidth, decodedDepthHeight)) {
        std::cout << "decodeDepth success! size: "
                  << decodedDepthWidth << "x" << decodedDepthHeight << std::endl;
    } else {
        std::cout << "decodeDepth: no depth element in this EpicRaw." << std::endl;
    }

    // 6. 离线计算 LUT + 解码点云
    std::cout << std::endl << "--- decodePointCloudFromEpicRaw ---" << std::endl;
    if (depthWidth > 0 && depthHeight > 0 && cameraMatrix.size() >= 9) {
        std::vector<float> lut;
        TFTech::EpicEye::computeUndistortLut(depthWidth, depthHeight, cameraMatrix, distortion, lut);

        std::vector<float> pcBuffer;
        int pcw = 0, pch = 0;
        if (TFTech::EpicEye::decodePointCloudFromEpicRaw(
                document, lut, pcBuffer, pcw, pch)) {
            std::cout << "decodePointCloud success! size: " << pcw << "x" << pch << std::endl;
        } else {
            std::cout << "decodePointCloud: no pointcloud/depth element in this EpicRaw." << std::endl;
        }
    }

    // 7. 获取 MetaDataStr
    std::cout << std::endl << "--- getEpicRawElementMetaDataStr ---" << std::endl;
    std::string metaDataStr;
    if (TFTech::EpicEye::getEpicRawElementMetaDataStr(document,
          TFTech::EpicRaw3DataType::TextureBGR, metaDataStr)) {
        std::cout << "TextureBGR MetaData: " << metaDataStr << std::endl;
    } else if (TFTech::EpicEye::getEpicRawElementMetaDataStr(document,
          TFTech::EpicRaw3DataType::DepthSrcImg2, metaDataStr)) {
        std::cout << "DepthSrcImg2 MetaData: " << metaDataStr << std::endl;
    } else {
        std::cout << "(no matching element metadata found)" << std::endl;
    }

    std::cout << std::endl << "Done." << std::endl;
    return 0;
}
