#ifndef TFTECH_EPICEYE_EXAMPLES_INTRINSIC_CALIBRATION_TYPE_H
#define TFTECH_EPICEYE_EXAMPLES_INTRINSIC_CALIBRATION_TYPE_H

// 本文件只定义 Example 用于展示和交互的中间结果。
// 真正写入相机的类型是 SDK 公开的 CameraParametersConfig，不能使用下面的扁平计算明细代替。

#include "epiceye.h"

#include <optional>
#include <string>
#include <vector>

// 预览图来源与尺寸信息；dataUri 可直接作为图片 src。
struct ImageInfoData {
    std::string dataUri;
    std::string name;
    int width = 0;
    int height = 0;
};

// 内参标定板识别结果。
struct IntrinsicBoardIdentifyResult {
    // 标定板类型，识别失败时为 -1。
    int boardType = -1;
    // 标定板提示信息。
    std::string boardHint;
    // 带检测标记的结构化预览图。
    std::vector<ImageInfoData> previewImages;
};

// 添加一组内参标定图后的结果。
struct IntrinsicCalibImageResult {
    // 当前图像对是否成功检测到标定板。
    bool detectSuccess = false;
    // 当前图像对索引。
    int pairIndex = -1;
    // 当前工作区内图像对总数。
    int pairCount = 0;
    // 标定板位姿 [tx,ty,tz,qx,qy,qz,qw]，平移单位 mm；估计失败时无值。
    std::optional<std::array<float, 7>> boardPose;
    // 标定板倾斜角。
    float boardTiltAngle = 0.0f;
    // 倾斜角是否触发警告。
    bool boardTiltWarning = false;
    // 相机返回的预览图及其访问地址、名称和尺寸。
    std::vector<ImageInfoData> previewImages;
};

// 删除一组内参标定图后的结果。
struct IntrinsicRemoveCalibImageResult {
    // 删除后剩余图像对总数。
    int pairCount = 0;
    // 被删除的图像对索引。
    int removedIndex = -1;
};

// 内参标定计算结果。
struct IntrinsicCalibrationResult {
    // DepthSrc1-DepthSrc2 扁平计算结果，仅用于检查计算明细。
    nlohmann::json cameraParameters;
    nlohmann::json parameterErrors;
    // BinoWithColor 的 DepthSrc1-TextureSrc 扁平计算结果。
    nlohmann::json colorCameraParameters;
    nlohmann::json colorParameterErrors;
    // 对应 CameraParameters.json 的完整配置，唯一允许写入设备的计算结果。
    std::optional<TFTech::CameraParametersConfig> cameraParametersConfig;
    double stereoRms = 0.0;
    std::optional<double> colorStereoRms;
    bool shouldWarnRms = false;
};

#endif
