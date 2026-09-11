#include "intrinsic_calibration_utils.h"

#include "epiceye.h"
#include "nlohmann_json.hpp"

// 将 SDK 返回的 JSON 结果转换成 Example 的强类型结果，避免交互流程直接操作字段名字符串。
// 解析失败不会触发任何写入；只有 writeIntrinsicCameraParameters 会修改相机内参。

static std::vector<ImageInfoData> parsePreviewImages(const nlohmann::json& value) {
    std::vector<ImageInfoData> result;
    if (!value.is_array()) {
        return result;
    }
    result.reserve(value.size());
    for (const auto& item : value) {
        if (!item.is_object()) {
            continue;
        }
        result.push_back(ImageInfoData {
            item.value("dataUri", std::string()),
            item.value("name", std::string()),
            item.value("width", 0),
            item.value("height", 0)
        });
    }
    return result;
}

static IntrinsicBoardIdentifyResult parseIdentifyResult(const nlohmann::json& value) {
    IntrinsicBoardIdentifyResult result;
    result.boardType = value.value("boardType", -1);
    result.boardHint = value.value("boardHint", std::string());
    result.previewImages = parsePreviewImages(value.value("previewImages", nlohmann::json::array()));
    return result;
}

static IntrinsicCalibImageResult parseAddCalibImageResult(const nlohmann::json& value) {
    IntrinsicCalibImageResult result;
    result.detectSuccess = value.value("detectSuccess", false);
    result.pairIndex = value.value("pairIndex", -1);
    result.pairCount = value.value("pairCount", 0);
    if (value.contains("boardPose") && value["boardPose"].is_array() && value["boardPose"].size() == 7) {
        result.boardPose = value["boardPose"].get<std::array<float, 7>>();
    }
    result.boardTiltAngle = value.value("boardTiltAngle", 0.0f);
    result.boardTiltWarning = value.value("boardTiltWarning", false);
    result.previewImages = parsePreviewImages(value.value("previewImages", nlohmann::json::array()));
    return result;
}

static IntrinsicRemoveCalibImageResult parseRemoveCalibImageResult(const nlohmann::json& value) {
    IntrinsicRemoveCalibImageResult result;
    result.pairCount = value.value("pairCount", 0);
    result.removedIndex = value.value("removedIndex", -1);
    return result;
}

static IntrinsicCalibrationResult parseCalculateResult(const nlohmann::json& value) {
    IntrinsicCalibrationResult result;
    // cameraParameters 是双深度相机的扁平计算明细；它用于展示，不能直接写入相机。
    result.cameraParameters = value.value("cameraParameters", nlohmann::json::object());
    result.parameterErrors = value.value("parameterErrors", nlohmann::json::object());
    result.colorCameraParameters = value.value("colorCameraParameters", nlohmann::json());
    result.colorParameterErrors = value.value("colorParameterErrors", nlohmann::json());
    // cameraParametersConfig 包含 DepthSrc1、DepthSrc2 以及可选 TextureSrc，是唯一完整的写入数据。
    if (value.contains("cameraParametersConfig") && value["cameraParametersConfig"].is_object()) {
        result.cameraParametersConfig = value["cameraParametersConfig"].get<TFTech::CameraParametersConfig>();
    }
    result.stereoRms = value.value("stereoRms", 0.0);
    if (value.contains("colorStereoRms") && value["colorStereoRms"].is_number()) {
        result.colorStereoRms = value["colorStereoRms"].get<double>();
    }
    result.shouldWarnRms = value.value("shouldWarnRms", false);
    return result;
}

bool identifyIntrinsicBoard(const std::string& ip, IntrinsicBoardIdentifyResult& result) {
    TFTech::IntrinsicIdentifyBoardResult resultJson;
    if (!TFTech::EpicEye::identifyBoard(ip, resultJson)) {
        return false;
    }
    result = parseIdentifyResult(resultJson);
    return true;
}

bool addCalibrationBoardPose(const std::string& ip, int boardType, IntrinsicCalibImageResult& result) {
    TFTech::IntrinsicAddCalibImageResult resultJson;
    if (!TFTech::EpicEye::addCalibImage(ip, boardType, resultJson)) {
        return false;
    }
    result = parseAddCalibImageResult(resultJson);
    return true;
}

bool removeIntrinsicCalibImage(const std::string& ip, int pairIndex, IntrinsicRemoveCalibImageResult& result) {
    TFTech::IntrinsicRemoveCalibImageResult resultJson;
    if (!TFTech::EpicEye::removeCalibImage(ip, pairIndex, resultJson)) {
        return false;
    }
    result = parseRemoveCalibImageResult(resultJson);
    return true;
}

bool calculateIntrinsicCalibration(const std::string& ip, IntrinsicCalibrationResult& result) {
    TFTech::IntrinsicCalculateResult resultJson;
    if (!TFTech::EpicEye::calculate(ip, resultJson)) {
        return false;
    }
    result = parseCalculateResult(resultJson);
    return true;
}

bool writeIntrinsicCameraParameters(const std::string& ip, const TFTech::CameraParametersConfig& cameraParametersConfig) {
    return TFTech::EpicEye::setCameraIntrinsicParameters(ip, cameraParametersConfig);
}
