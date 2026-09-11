/*
 * 作用：完成一次不依赖 OpenCV 的 3D 采集和本地文件保存。
 * 流程：触发拍摄 -> 一次下载 EpicRaw -> 离线解码图像/深度/点云 -> 纹理对齐 -> 保存 PNG/PLY。
 * 关键点：所有结果来自同一 EpicRaw，避免多次在线请求造成帧不一致。
 * 相机影响：触发一次拍摄，不修改配置；文件写入当前目录。
 */
#include "epiceye.h"
#include "lodepng.h"

#include <algorithm>
#include <chrono>
#include <iostream>
#include <fstream>
#include <iomanip>
#include <string>
#include <cmath>
#include <cstring>
#include <cstdint>
#include <limits>

static bool to8bitBgr(const std::vector<uint8_t>& imageData, int width, int height,
                      int pixelByteSize, std::vector<uint8_t>& image8bit) {
    if (width <= 0 || height <= 0 || (pixelByteSize != 1 && pixelByteSize != 2)) {
        return false;
    }
    const size_t w = static_cast<size_t>(width);
    const size_t h = static_cast<size_t>(height);
    const size_t pixelCount = w * h;
    const size_t expectedSize = pixelCount * 3 * static_cast<size_t>(pixelByteSize);
    if (imageData.size() < expectedSize) {
        return false;
    }
    image8bit.resize(w * h * 3);

    if (pixelByteSize == 1) {
        image8bit.assign(imageData.begin(), imageData.begin() + static_cast<std::ptrdiff_t>(pixelCount * 3));
        return true;
    }

    for (size_t index = 0; index < pixelCount * 3; ++index) {
        const size_t offset = index * 2;
        const uint16_t value = static_cast<uint16_t>(imageData[offset]) |
                               static_cast<uint16_t>(static_cast<uint16_t>(imageData[offset + 1]) << 8);
        image8bit[index] = static_cast<uint8_t>(std::min<uint16_t>(value / 4, 255));
    }
    return true;
}

static bool savePng(int width, int height, int bitDepth, int channels,
                    const std::string& filename, const uint8_t* data) {
    lodepng::State state;
    if (channels == 3) {
        state.info_raw.colortype = LCT_RGB;
        state.info_png.color.colortype = LCT_RGB;
    } else if (channels == 1) {
        state.info_raw.colortype = LCT_GREY;
        state.info_png.color.colortype = LCT_GREY;
    }
    state.info_raw.bitdepth = bitDepth;
    state.info_png.color.bitdepth = bitDepth;

    std::vector<unsigned char> buffer;
    unsigned error = lodepng::encode(buffer, data, width, height, state);
    if (error) {
        std::cout << "encoder error " << error << ": " << lodepng_error_text(error) << std::endl;
        return false;
    }
    error = lodepng::save_file(buffer, filename);
    if (error) {
        std::cout << "file error " << error << ": " << lodepng_error_text(error) << std::endl;
        return false;
    }
    return true;
}

static bool saveBgrPng(int width, int height, const std::string& filename, const std::vector<uint8_t>& bgrData) {
    const size_t pixelCount = static_cast<size_t>(width) * static_cast<size_t>(height);
    if (width <= 0 || height <= 0 || bgrData.size() < pixelCount * 3) {
        return false;
    }

    std::vector<uint8_t> rgbData(pixelCount * 3);
    for (size_t index = 0; index < pixelCount; ++index) {
        const size_t offset = index * 3;
        rgbData[offset] = bgrData[offset + 2];
        rgbData[offset + 1] = bgrData[offset + 1];
        rgbData[offset + 2] = bgrData[offset];
    }
    return savePng(width, height, 8, 3, filename, rgbData.data());
}

static bool saveDepthGrey(int width, int height, const std::string& filename, const std::vector<float>& depthData) {
    float maxDepth = 0.0f;
    float minDepth = std::numeric_limits<float>::max();
    for (size_t i = 0; i < depthData.size(); i++) {
        float v = depthData[i];
        if (maxDepth < v) maxDepth = v;
        if (minDepth > v) minDepth = v;
    }
    float depthRange = maxDepth - minDepth;
    if (depthRange <= 0.0f) depthRange = 1.0f;
    std::vector<uint8_t> greyBuf(width * height);
    for (int i = 0; i < width; i++) {
        for (int j = 0; j < height; j++) {
            int index = i * height + j;
            greyBuf[index] = (uint8_t)(std::round((depthData[index] - minDepth) / depthRange * 255));
        }
    }
    return savePng(width, height, 8, 1, filename, greyBuf.data());
}

static void writeFloatLittleEndian(float value, uint8_t* destination) {
    uint32_t bits = 0;
    static_assert(sizeof(bits) == sizeof(value), "float must be 32-bit");
    std::memcpy(&bits, &value, sizeof(bits));
    destination[0] = static_cast<uint8_t>(bits);
    destination[1] = static_cast<uint8_t>(bits >> 8);
    destination[2] = static_cast<uint8_t>(bits >> 16);
    destination[3] = static_cast<uint8_t>(bits >> 24);
}

static bool saveBinaryPointCloudPly(const std::vector<float>& cloudData,
                                    const std::vector<uint8_t>* imageData,
                                    const std::string& savePath, int width, int height) {
    if (width <= 0 || height <= 0) {
        return false;
    }
    const size_t pointCount = static_cast<size_t>(width) * static_cast<size_t>(height);
    if (cloudData.size() < pointCount * 3 || (imageData != nullptr && imageData->size() < pointCount * 3)) {
        return false;
    }
    std::ofstream outfile(savePath, std::ios::binary);
    if (!outfile.is_open()) {
        return false;
    }
    outfile << "ply\n"
            << "format binary_little_endian 1.0\n"
            << "obj_info EpicEye PLY PointCloud (Width = " << width << "; Height = " << height << ")\n"
            << "obj_info num_cols " << width << "\n"
            << "obj_info num_rows " << height << "\n"
            << "element vertex " << width * height << "\n"
            << "property float x\n"
            << "property float y\n"
            << "property float z\n"
            << "property uchar red\n"
            << "property uchar green\n"
            << "property uchar blue\n"
            << "end_header\n";

    constexpr size_t vertexSize = sizeof(float) * 3 + 3;
    std::vector<uint8_t> vertexData(pointCount * vertexSize);
    for (size_t pointIndex = 0; pointIndex < pointCount; ++pointIndex) {
        const size_t sourceOffset = pointIndex * 3;
        uint8_t* vertex = vertexData.data() + pointIndex * vertexSize;
        writeFloatLittleEndian(cloudData[sourceOffset], vertex);
        writeFloatLittleEndian(cloudData[sourceOffset + 1], vertex + 4);
        writeFloatLittleEndian(cloudData[sourceOffset + 2], vertex + 8);
        if (imageData == nullptr) {
            vertex[12] = 255;
            vertex[13] = 255;
            vertex[14] = 255;
        } else {
            vertex[12] = (*imageData)[sourceOffset + 2];
            vertex[13] = (*imageData)[sourceOffset + 1];
            vertex[14] = (*imageData)[sourceOffset];
        }
    }
    outfile.write(reinterpret_cast<const char*>(vertexData.data()), static_cast<std::streamsize>(vertexData.size()));
    outfile.close();
    return !outfile.fail();
}

static bool savePointCloudAsPly(const std::vector<float>& cloudData,
                                const std::string& savePath, int width, int height) {
    return saveBinaryPointCloudPly(cloudData, nullptr, savePath, width, height);
}

static bool savePointCloudWithTexture(const std::vector<float>& cloudData,
                                      const std::vector<uint8_t>& imageData,
                                      const std::string& savePath, int width, int height) {
    return saveBinaryPointCloudPly(cloudData, &imageData, savePath, width, height);
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

int main(int argc, char** argv) {
    std::cout << "SDK Version: " << TFTech::EpicEye::getSDKVersion() << std::endl;

    const std::string ip = resolveIp(argc, argv);
    if (ip.empty()) {
        return 1;
    }

    std::cout << std::endl;
    std::cout << "Using IP: " << ip << std::endl;

    // getInfo
    std::cout << "---------------get " << ip << " EpicEyeInfo---------------" << std::endl;
    TFTech::EpicEyeInfo info;
    if (!TFTech::EpicEye::getInfo(ip, info)) {
        std::cout << "getInfo failed!" << std::endl;
        return 1;
    }
    std::cout << "SN: " << info.SN << std::endl;
    std::cout << "IP: " << info.IP << std::endl;
    std::cout << "model: " << info.model << std::endl;
    std::cout << "alias: " << info.alias << std::endl;
    std::cout << "resolution: " << info.width << "x" << info.height << std::endl;

    // getConfig
    std::cout << "---------------getConfig---------------" << std::endl;
    nlohmann::json configJson;
    if (TFTech::EpicEye::getConfig(ip, configJson)) {
        std::cout << "configJson: " << configJson.dump(4) << std::endl;
    }

    // trigger one frame
    std::cout << "---------------triggerFrame---------------" << std::endl;
    std::string frameID;
    bool requestPointCloud = true;
    if (!TFTech::EpicEye::triggerFrame(ip, frameID, requestPointCloud)) {
        std::cout << "triggerFrame failed!" << std::endl;
        return 1;
    }
    std::cout << "frameID: " << frameID << std::endl;

    // ---- 1 次 HTTP 下载 EpicRaw，后续全部离线解码 ----
    std::cout << "---------------fetch EpicRaw (once)---------------" << std::endl;
    auto tFetch = std::chrono::high_resolution_clock::now();
    std::vector<uint8_t> rawBytes;
    if (!TFTech::EpicEye::getFrameInEpicRaw(ip, frameID, rawBytes)) {
        std::cout << "getFrameInEpicRaw failed!" << std::endl;
        return 1;
    }
    auto tFetched = std::chrono::high_resolution_clock::now();
    std::cout << "EpicRaw: " << rawBytes.size() << " bytes ("
              << std::chrono::duration_cast<std::chrono::milliseconds>(tFetched - tFetch).count() << " ms)" << std::endl;
    TFTech::EpicRawDocument document;
    if (!TFTech::EpicEye::tryLoadEpicRawDocumentFromBytes(rawBytes, document)) {
        std::cout << "tryLoadEpicRawDocumentFromBytes failed!" << std::endl;
        return 1;
    }

    // ---- 解析 TextureBGR 外参 ----
    std::vector<double> texInt, texDist, rot, trans;
    std::string texMeta;
    if (TFTech::EpicEye::getEpicRawElementMetaDataStr(
            document, TFTech::EpicRaw3DataType::TextureBGR, texMeta)) {
        TFTech::EpicEye::parseTextureExtrinsics(texMeta, texInt, texDist, rot, trans);
    }

    // ---- 解析深度内参 ----
    std::vector<double> depthInt, depthDist;
    int intrinsicWidth = 0, intrinsicHeight = 0;
    TFTech::EpicEye::getDepthIntrinsicsFromEpicRaw(
        document, depthDist, depthInt, intrinsicWidth, intrinsicHeight);

    // ---- 离线解码图像 ----
    std::cout << "---------------decodeImage (offline)---------------" << std::endl;
    std::vector<uint8_t> imageData;
    std::vector<uint8_t> image8bit;
    int imageWidth = 0, imageHeight = 0, pixelByteSize = 0;
    bool hasImage = TFTech::EpicEye::decodeImageFromEpicRaw(
        document, imageData, imageWidth, imageHeight, pixelByteSize);
    if (hasImage) {
        std::cout << "Image: " << imageWidth << "x" << imageHeight
                  << " pixelByteSize: " << pixelByteSize
                  << " (" << (pixelByteSize == 1 ? "8bit" : pixelByteSize == 2 ? "16bit" : "?")
                  << " per channel)"
                  << " dataSize: " << imageData.size() << " bytes" << std::endl;

        if (to8bitBgr(imageData, imageWidth, imageHeight, pixelByteSize, image8bit)) {
            if (!saveBgrPng(imageWidth, imageHeight, "image8bit.png", image8bit)) {
                std::cerr << "save image8bit.png failed" << std::endl;
                return 1;
            }
            std::cout << "saved: image8bit.png" << std::endl;
        } else {
            hasImage = false;
        }
    } else {
        std::cout << "decodeImage: no TextureBGR element in EPICRAW3 (camera may not have color sensor)" << std::endl;
    }

    // ---- 离线解码深度图 ----
    std::cout << "---------------decodeDepth (offline)---------------" << std::endl;
    std::vector<float> depthData;
    int depthWidth = 0, depthHeight = 0;
    if (TFTech::EpicEye::decodeDepthFromEpicRaw(
            document, depthData, depthWidth, depthHeight)) {
        std::cout << "Depth: " << depthWidth << "x" << depthHeight
                  << " dataSize: " << depthData.size() << " floats" << std::endl;
        if (!saveDepthGrey(depthWidth, depthHeight, "depthGrey.png", depthData)) {
            std::cerr << "save depthGrey.png failed" << std::endl;
            return 1;
        }
        std::cout << "saved: depthGrey.png" << std::endl;
    } else {
        std::cout << "decodeDepthFromEpicRaw: no depth element" << std::endl;
    }

    // ---- 离线解码点云 ----
    if (requestPointCloud) {
        std::cout << "---------------decodePointCloud (offline)---------------" << std::endl;
        std::vector<float> pointCloudData;
        int pointCloudWidth = 0, pointCloudHeight = 0;
        std::vector<float> lut;
        if (depthInt.size() >= 9 && depthWidth > 0 && depthHeight > 0) {
            TFTech::EpicEye::getUndistortLut(
                ip, depthWidth, depthHeight, depthInt, depthDist, lut);
        }
        if (TFTech::EpicEye::decodePointCloudFromEpicRaw(
                document, lut, pointCloudData, pointCloudWidth, pointCloudHeight)) {
            std::cout << "PointCloud: " << pointCloudWidth << "x" << pointCloudHeight
                      << " dataSize: " << pointCloudData.size() << " floats" << std::endl;
            if (!savePointCloudAsPly(pointCloudData, "pointcloud.ply", pointCloudWidth, pointCloudHeight)) {
                std::cerr << "save pointcloud.ply failed" << std::endl;
                return 1;
            }
            std::cout << "saved: pointcloud.ply" << std::endl;

            // alignTextureImage — 将 2D 纹理对齐到点云空间（使用 TextureBGR 元数据中的外参）
            if (hasImage) {
                std::cout << "---------------alignTextureImage---------------" << std::endl;
                std::vector<uint8_t> alignedTexture;
                auto t0 = std::chrono::high_resolution_clock::now();
                // 离线对齐：以 depth 为输入，0 次 HTTP，避免点云/LUT 解码差异引入横移
                // image8bit 已转成 8bit BGR，故 matType = CV_8UC3(16)；若直接用 16bit 纹理则传 CV_16UC3(18)
                const int textureMatType = 16;  // CV_8UC3
                bool alignOk = TFTech::EpicEye::alignTextureImage(
                        image8bit, imageWidth, imageHeight, textureMatType,
                        depthData, depthWidth, depthHeight,
                        depthInt, texInt, texDist, rot, trans,
                        alignedTexture);
                auto t1 = std::chrono::high_resolution_clock::now();
                auto alignMs = std::chrono::duration_cast<std::chrono::milliseconds>(t1 - t0).count();
                if (alignOk) {
                    bool plySaved = savePointCloudWithTexture(pointCloudData, alignedTexture,
                                                              "pointcloudWithAlignedTexture.ply",
                                                              pointCloudWidth, pointCloudHeight);
                    bool pngSaved = saveBgrPng(pointCloudWidth, pointCloudHeight, "aligned_texture.png", alignedTexture);
                    if (!plySaved || !pngSaved) {
                        std::cerr << "save aligned texture outputs failed" << std::endl;
                        return 1;
                    }
                    std::cout << "saved: aligned_texture.png, pointcloudWithAlignedTexture.ply"
                              << " (pure compute: " << alignMs << " ms, no extra HTTP)" << std::endl;
                } else {
                    std::cout << "alignTextureImage: no TextureBGR extrinsics or alignment failed" << std::endl;
                }
            }
        } else {
            std::cout << "decodePointCloudFromEpicRaw failed" << std::endl;
            return 1;
        }
    }

    std::cout << std::endl;
    return 0;
}
