/*
 * 作用：把纹理图像像素 (u,v) 映射为同一帧点云中的三维坐标 (X,Y,Z)。
 * 流程：触发一帧 -> 读取图像/深度/点云和内外参 -> 映射深度坐标 -> 双线性采样。
 * 坐标约定：输入是纹理图像坐标，输出是相机坐标系三维点，单位 mm。
 * 相机影响：触发一次拍摄，不修改配置。
 */
#include "epiceye.h"
#include "nlohmann_json.hpp"

#include <iostream>
#include <iomanip>
#include <string>
#include <cmath>
#include <vector>

// ---- 双线性插值读取深度/点云数据 ----

/// 从深度图中双线性采样 Z 值
static float sampleDepth(const std::vector<float> &depth, int depthW, int depthH,
                         double u, double v) {
    int u0 = static_cast<int>(u);
    int v0 = static_cast<int>(v);
    if (u0 < 0 || u0 >= depthW - 1 || v0 < 0 || v0 >= depthH - 1) return 0.0f;
    double du = u - u0, dv = v - v0;
    double w00 = (1.0 - du) * (1.0 - dv);
    double w01 = du * (1.0 - dv);
    double w10 = (1.0 - du) * dv;
    double w11 = du * dv;
    size_t idx00 = static_cast<size_t>(v0) * depthW + u0;
    float z = static_cast<float>(
        depth[idx00] * w00 +
        depth[idx00 + 1] * w01 +
        depth[idx00 + depthW] * w10 +
        depth[idx00 + depthW + 1] * w11);
    return z;
}

/// 从点云中双线性采样 XYZ
static void samplePointCloud(const std::vector<float> &pc, int pcW, int pcH,
                             double u, double v,
                             double &x, double &y, double &z) {
    int u0 = static_cast<int>(u);
    int v0 = static_cast<int>(v);
    if (u0 < 0 || u0 >= pcW - 1 || v0 < 0 || v0 >= pcH - 1) {
        x = y = z = 0.0;
        return;
    }
    double du = u - u0, dv = v - v0;
    double w00 = (1.0 - du) * (1.0 - dv);
    double w01 = du * (1.0 - dv);
    double w10 = (1.0 - du) * dv;
    double w11 = du * dv;

    auto readXYZ = [&](int col, int row, double &rx, double &ry, double &rz) {
        size_t idx = (static_cast<size_t>(row) * pcW + col) * 3;
        rx = static_cast<double>(pc[idx]);
        ry = static_cast<double>(pc[idx + 1]);
        rz = static_cast<double>(pc[idx + 2]);
    };

    double x00, y00, z00, x01, y01, z01, x10, y10, z10, x11, y11, z11;
    readXYZ(u0,     v0,     x00, y00, z00);
    readXYZ(u0 + 1, v0,     x01, y01, z01);
    readXYZ(u0,     v0 + 1, x10, y10, z10);
    readXYZ(u0 + 1, v0 + 1, x11, y11, z11);

    x = x00 * w00 + x01 * w01 + x10 * w10 + x11 * w11;
    y = y00 * w00 + y01 * w01 + y10 * w10 + y11 * w11;
    z = z00 * w00 + z01 * w01 + z10 * w10 + z11 * w11;
}

// ---- 从无畸变纹理像素查找对应点云坐标 ----

/// 将纹理像素坐标映射到深度图/点云坐标，并返回对应的 3D 坐标和深度值。
/// 基于内参比例直接映射（适用于同一相机不同分辨率的场景）。
/// @return true 表示找到有效的对应点
static bool textureToPointCloud(
    double uTex, double vTex,
    const std::vector<double> &textureIntrinsic,
    const std::vector<double> &depthIntrinsic,
    const std::vector<float> &depth, int depthW, int depthH,
    const std::vector<float> &pointCloud, int pcW, int pcH,
    double &outX, double &outY, double &outZ) {

    outX = outY = outZ = 0.0;

    // 纹理内参
    double fxT = textureIntrinsic[0], fyT = textureIntrinsic[4];
    double cxT = textureIntrinsic[2], cyT = textureIntrinsic[5];

    // 深度内参
    double fxD = depthIntrinsic[0], fyD = depthIntrinsic[4];
    double cxD = depthIntrinsic[2], cyD = depthIntrinsic[5];

    // 归一化坐标（纹理相机空间）
    double xn = (uTex - cxT) / fxT;
    double yn = (vTex - cyT) / fyT;

    // 映射到深度图坐标（假定 R=I, T=0: 同一相机，仅分辨率不同）
    double uDepth = xn * fxD + cxD;
    double vDepth = yn * fyD + cyD;

    if (uDepth < 0 || uDepth >= depthW - 1 || vDepth < 0 || vDepth >= depthH - 1) {
        std::cerr << "  Texture pixel (" << uTex << "," << vTex
                  << ") maps to depth (" << uDepth << "," << vDepth << ") — out of bounds" << std::endl;
        return false;
    }

    // 查找 Z
    double Z = sampleDepth(depth, depthW, depthH, uDepth, vDepth);
    if (Z <= 0.0) {
        std::cerr << "  Texture pixel (" << uTex << "," << vTex
                  << ") → depth (" << uDepth << "," << vDepth << ") — Z is invalid (0)" << std::endl;
        return false;
    }

    // 从点云读取 XYZ（比从 Z 反投影更精确，因为可能在点云解码时做了去畸变）
    samplePointCloud(pointCloud, pcW, pcH, uDepth, vDepth, outX, outY, outZ);

    // 验证点云数据有效性
    if (outZ <= 0.0) {
        // 点云也无效，回退到从 Z 反投影
        outX = Z * xn;
        outY = Z * yn;
        outZ = Z;
    }

    return true;
}

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
    std::cout << "SDK Version: " << TFTech::EpicEye::getSDKVersion() << std::endl;
    std::cout << "=== Texture Pixel → Point Cloud Coordinate ===" << std::endl;

    const std::string ip = resolveIp(argc, argv);
    if (ip.empty()) {
        return 1;
    }
    std::cout << "Using IP: " << ip << std::endl;

    std::cout << std::endl;

    // ---- 获取相机信息 ----
    TFTech::EpicEyeInfo info;
    if (!TFTech::EpicEye::getInfo(ip, info)) {
        std::cerr << "getInfo failed!" << std::endl;
        return 1;
    }
    std::cout << "Camera: " << info.model << " " << info.width << "x" << info.height << std::endl;

    // ---- 触发拍摄 ----
    std::cout << "Triggering frame..." << std::endl;
    std::string frameID;
    if (!TFTech::EpicEye::triggerFrame(ip, frameID, true)) {
        std::cerr << "triggerFrame failed!" << std::endl;
        return 1;
    }
    std::cout << "frameID: " << frameID << std::endl;

    // ---- 获取 EpicRaw 原始字节（用于解析内参） ----
    std::vector<uint8_t> rawBytes;
    if (!TFTech::EpicEye::getFrameInEpicRaw(ip, frameID, rawBytes)) {
        std::cerr << "getFrameInEpicRaw failed!" << std::endl;
        return 1;
    }
    TFTech::EpicRawDocument document;
    if (!TFTech::EpicEye::tryLoadEpicRawDocumentFromBytes(rawBytes, document)) {
        std::cerr << "tryLoadEpicRawDocumentFromBytes failed!" << std::endl;
        return 1;
    }

    // ---- 解码图像 ----
    std::vector<uint8_t> imageData;
    int imgW = 0, imgH = 0, pixelByteSize = 0;
    bool hasImage = TFTech::EpicEye::decodeImageFromEpicRaw(
        document, imageData, imgW, imgH, pixelByteSize);
    if (hasImage) {
        std::cout << "Texture image: " << imgW << "x" << imgH
                  << " pixelBytes: " << pixelByteSize << std::endl;
    } else {
        std::cout << "No texture image available (textureSource=0?), continuing..." << std::endl;
    }

    // ---- 解码深度数据 ----
    std::vector<float> depthData;
    int depthW = 0, depthH = 0;
    if (!TFTech::EpicEye::decodeDepthFromEpicRaw(
            document, depthData, depthW, depthH)) {
        std::cerr << "decodeDepthFromEpicRaw failed!" << std::endl;
        return 1;
    }
    std::cout << "Depth map: " << depthW << "x" << depthH << std::endl;

    // ---- 解码点云 ----
    std::vector<float> pointCloudData;
    int pcW = 0, pcH = 0;
    std::vector<double> depthIntrinsic, depthDist;
    int dIntW = 0, dIntH = 0;
    if (!TFTech::EpicEye::getDepthIntrinsicsFromEpicRaw(
            document, depthDist, depthIntrinsic, dIntW, dIntH)) {
        std::cerr << "Failed to get depth intrinsics!" << std::endl;
        return 1;
    }
    std::vector<float> lut;
    TFTech::EpicEye::getUndistortLut(
        ip, dIntW, dIntH, depthIntrinsic, depthDist, lut);
    if (!TFTech::EpicEye::decodePointCloudFromEpicRaw(
            document, lut, pointCloudData, pcW, pcH)) {
        std::cerr << "decodePointCloudFromEpicRaw failed!" << std::endl;
        return 1;
    }
    std::cout << "PointCloud: " << pcW << "x" << pcH << std::endl;

    // ---- 解析内参 ----
    // 纹理内参和外参：从 TextureBGR 元素元数据
    std::string texMeta;
    std::vector<double> texIntrinsic, texDist, rotation, translation;
    bool hasTexExtrinsics = false;
    if (TFTech::EpicEye::getEpicRawElementMetaDataStr(
            document, TFTech::EpicRaw3DataType::TextureBGR, texMeta)) {
        hasTexExtrinsics = TFTech::EpicEye::parseTextureExtrinsics(texMeta, texIntrinsic, texDist, rotation, translation);
    }

    // 深度内参：从 Depth 元素元数据或 getDepthIntrinsicsFromEpicRaw
    // 退化：如果无纹理外参或纹理内参为占位 identity（同相机同分辨率），用深度内参作为纹理内参
    bool texIsIdentity = (texIntrinsic.size() >= 9 &&
                          texIntrinsic[0] == 1.0 && texIntrinsic[1] == 0.0 &&
                          texIntrinsic[2] == 0.0 &&
                          texIntrinsic[4] == 1.0 && texIntrinsic[5] == 0.0);
    if (!hasTexExtrinsics || texIntrinsic.size() < 9 || texIsIdentity) {
        std::cout << "No separate texture intrinsics, using depth intrinsics (same camera, same resolution)." << std::endl;
        texIntrinsic = depthIntrinsic;
        hasTexExtrinsics = true;
    }

    std::cout << std::endl;
    std::cout << "=== Camera Parameters ===" << std::endl;
    std::cout << "Depth intrinsic (3x3): ";
    for (auto v : depthIntrinsic) std::cout << v << " ";
    std::cout << std::endl;
    std::cout << "Depth dist: ";
    for (auto v : depthDist) std::cout << v << " ";
    std::cout << std::endl;
    std::cout << "Depth resolution: " << dIntW << "x" << dIntH << std::endl;

    if (hasTexExtrinsics) {
        std::cout << std::endl;
        std::cout << "Texture intrinsic (3x3): ";
        for (auto v : texIntrinsic) std::cout << v << " ";
        std::cout << std::endl;
        std::cout << "Texture dist: ";
        for (auto v : texDist) std::cout << v << " ";
        std::cout << std::endl;
        std::cout << "Rotation (3x3): ";
        for (auto v : rotation) std::cout << v << " ";
        std::cout << std::endl;
        std::cout << "Translation: ";
        for (auto v : translation) std::cout << v << " ";
        std::cout << std::endl;
    }

    // ---- 映射查找 ----
    std::cout << std::endl;
    std::cout << "=== Texture Pixel → Point Cloud ===" << std::endl;

    if (!hasImage && !hasTexExtrinsics) {
        std::cout << "Using depth intrinsics only (no texture metadata)." << std::endl;
        std::cout << "Assuming same camera, treating input as depth-pixel coordinates." << std::endl;
    }

    // 用户指定纹理像素坐标（命令行参数或交互输入）
    double uTex = 0, vTex = 0;
    bool interactive = false;

    if (argc >= 4) {
        uTex = std::stod(argv[2]);
        vTex = std::stod(argv[3]);
        std::cout << "Texture pixel: (" << uTex << ", " << vTex << ")" << std::endl;
    } else if (hasImage) {
        interactive = true;
        if (imgW > 0 && imgH > 0) {
            std::cout << "Texture image is " << imgW << "x" << imgH << std::endl;
            std::cout << "Enter texture pixel coordinate (u v), or 'q' to quit:" << std::endl;
            std::cout << "  Example: 710 710 (center of 1420x1420)" << std::endl;

            while (true) {
                std::cout << std::endl << "> ";
                std::string line;
                if (!std::getline(std::cin, line) || line == "q" || line == "quit") {
                    std::cout << "Bye." << std::endl;
                    break;
                }
                if (line.empty()) continue;

                int uIn, vIn;
                if (sscanf(line.c_str(), "%d %d", &uIn, &vIn) == 2) {
                    // === 核心映射逻辑 ===
                    double X, Y, Z;
                    if (textureToPointCloud(
                            static_cast<double>(uIn), static_cast<double>(vIn),
                            texIntrinsic, depthIntrinsic,
                            depthData, depthW, depthH,
                            pointCloudData, pcW, pcH,
                            X, Y, Z)) {
                        // 也输出深度图坐标和深度值
                        double fxD = depthIntrinsic[0], fyD = depthIntrinsic[4];
                        double cxD = depthIntrinsic[2], cyD = depthIntrinsic[5];
                        double fxT = texIntrinsic[0], fyT = texIntrinsic[4];
                        double cxT = texIntrinsic[2], cyT = texIntrinsic[5];
                        double xn = (uIn - cxT) / fxT;
                        double yn = (vIn - cyT) / fyT;
                        double uDepth = xn * fxD + cxD;
                        double vDepth = yn * fyD + cyD;
                        double depthZ = sampleDepth(depthData, depthW, depthH, uDepth, vDepth);

                        std::cout << std::fixed << std::setprecision(3);
                        std::cout << "  → Depth pixel:  (" << uDepth << ", " << vDepth << ")" << std::endl;
                        std::cout << "  → Depth Z:       " << depthZ << " mm" << std::endl;
                        std::cout << "  → PointCloud XYZ: (" << X << ", " << Y << ", " << Z << ") mm" << std::endl;
                    }
                } else {
                    std::cout << "Invalid format. Use: <u> <v>" << std::endl;
                }
            }
            return 0;
        }
    }

    // 非交互模式：输出一次查询结果
    if (!interactive) {
        double X, Y, Z;
        // 如果没有纹理内参，把输入坐标当深度像素坐标处理
        if (!hasTexExtrinsics) {
            double fxD = depthIntrinsic[0], fyD = depthIntrinsic[4];
            double cxD = depthIntrinsic[2], cyD = depthIntrinsic[5];
            double Z_d = sampleDepth(depthData, depthW, depthH, uTex, vTex);
            if (Z_d > 0) {
                X = Z_d * (uTex - cxD) / fxD;
                Y = Z_d * (vTex - cyD) / fyD;
                Z = Z_d;
                std::cout << std::fixed << std::setprecision(3);
                std::cout << "Depth pixel (" << uTex << "," << vTex << ") → Z=" << Z_d << " mm" << std::endl;
                std::cout << "PointCloud XYZ: (" << X << ", " << Y << ", " << Z << ") mm" << std::endl;
            } else {
                std::cout << "Depth pixel (" << uTex << "," << vTex << ") has no valid Z value." << std::endl;
                return 1;
            }
        } else {
            if (textureToPointCloud(uTex, vTex,
                    texIntrinsic, depthIntrinsic,
                    depthData, depthW, depthH,
                    pointCloudData, pcW, pcH,
                    X, Y, Z)) {
                std::cout << std::fixed << std::setprecision(3);
                std::cout << "Texture pixel (" << uTex << "," << vTex
                          << ") → PointCloud XYZ: (" << X << ", " << Y << ", " << Z << ") mm" << std::endl;
            } else {
                return 1;
            }
        }
    }

    std::cout << std::endl;
    return 0;
}
