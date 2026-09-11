/*
 * 作用：使用 OpenCV 获取、显示或保存图像/深度/点云及纹理对齐结果。
 * 流程：触发一次拍摄，后续在线接口始终使用同一 frameId。
 * 关键点：图像、深度和点云必须绑定同一 frameId，不能分别读取“最新帧”。
 * 相机影响：触发一次拍摄，不修改配置；结果文件写入当前目录。
 */
#include "epiceye.h"
#include "to_cv_mat.hpp"
#include "opencv2/core.hpp"
#include "opencv2/imgproc.hpp"
#include "opencv2/highgui.hpp"

#include <iostream>
#include <fstream>
#include <iomanip>
#include <cstring>
#include <cstdint>
#include <string>
#include <vector>

static cv::Mat depthToCVMat(const std::vector<float>& depthData,
                              int width, int height) {
    return cv::Mat(cv::Size(width, height), CV_32FC1, (void*)depthData.data()).clone();
}

static cv::Mat pointCloudToCVMat(const std::vector<float>& cloudData,
                                  int width, int height) {
    return cv::Mat(cv::Size(width, height), CV_32FC3, (void*)cloudData.data()).clone();
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

static bool saveBinaryPointCloudPly(const cv::Mat& cloudMap, const cv::Mat* bgrImage,
                                    const std::string& savePath) {
    if (cloudMap.empty() || cloudMap.type() != CV_32FC3) {
        return false;
    }

    cv::Mat bgr8;
    if (bgrImage != nullptr) {
        if (bgrImage->size() != cloudMap.size()) {
            return false;
        }
        if (bgrImage->type() == CV_8UC3) {
            bgr8 = *bgrImage;
        } else if (bgrImage->type() == CV_16UC3) {
            bgrImage->convertTo(bgr8, CV_8UC3, 0.25);
        } else {
            return false;
        }
    }

    std::ofstream outfile(savePath, std::ios::binary);
    if (!outfile.is_open()) {
        return false;
    }
    outfile << "ply\n"
            << "format binary_little_endian 1.0\n"
            << "obj_info EpicEye PLY PointCloud (Width = " << cloudMap.cols << "; Height = " << cloudMap.rows << ")\n"
            << "obj_info num_cols " << cloudMap.cols << "\n"
            << "obj_info num_rows " << cloudMap.rows << "\n"
            << "element vertex " << cloudMap.rows * cloudMap.cols << "\n"
            << "property float x\n"
            << "property float y\n"
            << "property float z\n"
            << "property uchar red\n"
            << "property uchar green\n"
            << "property uchar blue\n"
            << "end_header\n";

    const size_t pointCount = cloudMap.total();
    constexpr size_t vertexSize = sizeof(float) * 3 + 3;
    std::vector<uint8_t> vertexData(pointCount * vertexSize);
    for (int i = 0; i < cloudMap.rows; i++) {
        for (int j = 0; j < cloudMap.cols; j++) {
            const size_t pointIndex = static_cast<size_t>(i) * cloudMap.cols + j;
            uint8_t* vertex = vertexData.data() + pointIndex * vertexSize;
            const cv::Vec3f point = cloudMap.at<cv::Vec3f>(i, j);
            writeFloatLittleEndian(point[0], vertex);
            writeFloatLittleEndian(point[1], vertex + 4);
            writeFloatLittleEndian(point[2], vertex + 8);
            if (bgrImage == nullptr) {
                vertex[12] = 255;
                vertex[13] = 255;
                vertex[14] = 255;
            } else {
                const cv::Vec3b color = bgr8.at<cv::Vec3b>(i, j);
                vertex[12] = color[2];
                vertex[13] = color[1];
                vertex[14] = color[0];
            }
        }
    }
    outfile.write(reinterpret_cast<const char*>(vertexData.data()), static_cast<std::streamsize>(vertexData.size()));
    outfile.close();
    return !outfile.fail();
}

static bool savePointCloudAsPly(const cv::Mat& cloudMap, const std::string& savePath) {
    return saveBinaryPointCloudPly(cloudMap, nullptr, savePath);
}

static bool savePointCloudWithTexture(const cv::Mat& cloudMap, const cv::Mat& image,
                                      const std::string& savePath) {
    return saveBinaryPointCloudPly(cloudMap, &image, savePath);
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

    std::cout << std::endl << "Using IP: " << ip << std::endl;

    // getInfo
    TFTech::EpicEyeInfo info;
    if (!TFTech::EpicEye::getInfo(ip, info)) {
        std::cout << "getInfo failed!" << std::endl;
        return 1;
    }
    std::cout << "SN: " << info.SN << " model: " << info.model
              << " resolution: " << info.width << "x" << info.height << std::endl;

    // trigger
    std::cout << "---------------triggerFrame---------------" << std::endl;
    std::string frameID;
    bool requestPointCloud = true;
    if (!TFTech::EpicEye::triggerFrame(ip, frameID, requestPointCloud)) {
        std::cout << "triggerFrame failed!" << std::endl;
        return 1;
    }
    std::cout << "frameID: " << frameID << std::endl;

    std::vector<uint8_t> rawBytes;
    if (!TFTech::EpicEye::getFrameInEpicRaw(ip, frameID, rawBytes)) {
        std::cout << "getFrameInEpicRaw failed!" << std::endl;
        return 1;
    }
    TFTech::EpicRawDocument document;
    if (!TFTech::EpicEye::tryLoadEpicRawDocumentFromBytes(rawBytes, document)) {
        std::cout << "tryLoadEpicRawDocumentFromBytes failed!" << std::endl;
        return 1;
    }

    std::cout << "---------------decodeImageFromEpicRaw---------------" << std::endl;
    std::vector<uint8_t> imageData;
    int imageWidth = 0, imageHeight = 0, pixelByteSize = 0;
    if (!TFTech::EpicEye::decodeImageFromEpicRaw(
            document, imageData, imageWidth, imageHeight, pixelByteSize)) {
        std::cout << "decodeImageFromEpicRaw failed!" << std::endl;
        return 1;
    }
    cv::Mat image = TFTech::imageToCVMat(imageData, imageWidth, imageHeight, pixelByteSize);
    cv::namedWindow("image", cv::WINDOW_KEEPRATIO);
    cv::resizeWindow("image", 960, 800);
    cv::imshow("image", image);
    cv::waitKey(1);
    cv::imwrite("image.png", image);
    std::cout << "saved: image.png" << std::endl;

    std::cout << "---------------decodeDepthFromEpicRaw---------------" << std::endl;
    std::vector<float> depthData;
    int depthWidth = 0, depthHeight = 0;
    if (!TFTech::EpicEye::decodeDepthFromEpicRaw(
            document, depthData, depthWidth, depthHeight)) {
        std::cout << "decodeDepthFromEpicRaw failed!" << std::endl;
        return 1;
    }
    cv::Mat depth = depthToCVMat(depthData, depthWidth, depthHeight);
    depth.convertTo(depth, CV_8UC1, 1 / 10.0);
    cv::applyColorMap(depth, depth, cv::COLORMAP_JET);
    cv::namedWindow("depth", cv::WINDOW_KEEPRATIO);
    cv::resizeWindow("depth", 960, 800);
    cv::imshow("depth", depth);
    cv::waitKey(1);
    cv::imwrite("depth.png", depth);
    std::cout << "saved: depth.png" << std::endl;

    // decodePointCloudFromEpicRaw — vector
    if (requestPointCloud) {
        std::cout << "---------------decodePointCloudFromEpicRaw---------------" << std::endl;
        std::vector<float> pointCloudData;
        int pointCloudWidth = 0, pointCloudHeight = 0;
        std::vector<double> depthDist, depthInt;
        int metaDepthW = 0, metaDepthH = 0;
        TFTech::EpicEye::getDepthIntrinsicsFromEpicRaw(
            document, depthDist, depthInt, metaDepthW, metaDepthH);
        std::vector<float> lut;
        TFTech::EpicEye::getUndistortLut(
            ip, metaDepthW, metaDepthH, depthInt, depthDist, lut);
        if (!TFTech::EpicEye::decodePointCloudFromEpicRaw(
                document, lut, pointCloudData,
                pointCloudWidth, pointCloudHeight)) {
            std::cout << "decodePointCloudFromEpicRaw failed!" << std::endl;
            return 1;
        }
        cv::Mat pointCloud = pointCloudToCVMat(pointCloudData, pointCloudWidth, pointCloudHeight);
        if (!savePointCloudAsPly(pointCloud, "pointcloud.ply")) {
            std::cerr << "save pointcloud.ply failed" << std::endl;
            return 1;
        }
        std::cout << "saved: pointcloud.ply" << std::endl;

        std::vector<double> texInt, texDist, rot, trans;
        std::string texMeta;
        if (TFTech::EpicEye::getEpicRawElementMetaDataStr(
                document, TFTech::EpicRaw3DataType::TextureBGR, texMeta)) {
            TFTech::EpicEye::parseTextureExtrinsics(texMeta, texInt, texDist, rot, trans);
        }

        std::vector<uint8_t> alignedTexture;
        // matType 由每通道字节数决定：1→CV_8UC3(16)，2→CV_16UC3(18)。对齐输出与输入纹理同位深。
        int textureMatType = (pixelByteSize == 2) ? 18 : 16;
        if (TFTech::EpicEye::alignTextureImage(imageData, imageWidth, imageHeight, textureMatType,
                                               depthData, depthWidth, depthHeight,
                                               depthInt, texInt, texDist, rot, trans,
                                               alignedTexture)) {
            // alignedTexture 输出尺寸为 depthWidth x depthHeight，位深与输入纹理一致
            cv::Mat alignedTextureMat = TFTech::imageToCVMat(alignedTexture, depthWidth, depthHeight, pixelByteSize);
            cv::imwrite("aligned_texture.png", alignedTextureMat);
            std::cout << "saved: aligned_texture.png" << std::endl;
            if (!savePointCloudWithTexture(pointCloud, alignedTextureMat, "pointcloudWithAlignedTexture.ply")) {
                std::cerr << "save pointcloudWithAlignedTexture.ply failed" << std::endl;
                return 1;
            }
            std::cout << "saved: pointcloudWithAlignedTexture.ply" << std::endl;
        } else {
            std::cout << "alignTextureImage failed, skip textured point cloud" << std::endl;
        }
    }

    cv::destroyAllWindows();
    std::cout << std::endl << "Done." << std::endl;
    return 0;
}
