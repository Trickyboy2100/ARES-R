#ifndef TOMAT_H
#define TOMAT_H
#include "opencv2/core.hpp"
#include "opencv2/imgproc.hpp"

#include <cstdint>
#include <vector>

namespace TFTech {

/**
 * @brief 将图像字节数据转换为 OpenCV Mat
 * @param data 原始图像缓冲区（行优先）
 * @param width 图像宽度
 * @param height 图像高度
 * @param pixelByteSize 每通道字节数：1=8bit，2=16bit
 * @param channelCount 通道数：1=灰度，3=BGR 彩色
 * @param convertTo8UC3 为 true 时输出 8bit 可显示 Mat：
 *        灰度路径输出 CV_8UC3（灰度扩展为 BGR），彩色路径输出 CV_8UC3；
 *        为 false 时保留原始位深（CV_8UC1 / CV_16UC1 / CV_8UC3 / CV_16UC3）
 * @return 转换后的 Mat；参数无效时返回空 Mat
 */
inline cv::Mat imageToCVMat(const void *data, int width, int height, int pixelByteSize,
                            bool convertTo8UC3 = true, int channelCount = 3) {
    if (data == nullptr || width <= 0 || height <= 0) {
        return cv::Mat();
    }
    if ((pixelByteSize != 1 && pixelByteSize != 2) ||
        (channelCount != 1 && channelCount != 3)) {
        return cv::Mat();
    }

    const int srcDepth = (pixelByteSize == 1) ? CV_8U : CV_16U;

    const cv::Mat mat(cv::Size(width, height), CV_MAKETYPE(srcDepth, channelCount), const_cast<void *>(data));

    if (!convertTo8UC3) {
        return mat.clone();
    }

    if (pixelByteSize == 1 && channelCount == 3) {
        return mat.clone();
    }

    cv::Mat result = mat;
    if (pixelByteSize == 2) {
        mat.convertTo(result, CV_MAKETYPE(CV_8U, channelCount), 0.25);
    }

    if (channelCount == 1) {
        cv::cvtColor(result, result, cv::COLOR_GRAY2BGR);
    }
    return result;
}

inline cv::Mat imageToCVMat(const std::vector<uint8_t> &imageData, int width, int height,
                            int pixelByteSize, bool convertTo8UC3 = true, int channelCount = 3) {
    return imageToCVMat(imageData.data(), width, height, pixelByteSize, convertTo8UC3, channelCount);
}

/**
 * @brief 兼容旧版 API（仅 16bit 输入）
 * @param channelCount 通道数：1=灰度，3=BGR 彩色
 */
inline cv::Mat imageToCVMat(void *data, uint32_t width, uint32_t height, bool convertTo8UC3 = true,
                            uint32_t channelCount = 1) {
    return imageToCVMat(data, static_cast<int>(width), static_cast<int>(height), 2, convertTo8UC3, static_cast<int>(channelCount));
}

inline cv::Mat depthToCVMat(void *data, uint32_t width, uint32_t height) {
    return cv::Mat(cv::Size(width, height), CV_32FC1, data).clone();
}

inline cv::Mat pointCloudToCVMat(void *data, uint32_t width, uint32_t height) {
    return cv::Mat(cv::Size(width, height), CV_32FC3, data).clone();
}

}  // namespace TFTech
#endif  // TOMAT_H
