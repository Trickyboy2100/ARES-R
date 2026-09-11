#ifndef TFTECH_EPICEYE_EXAMPLES_INTRINSIC_CALIBRATION_UTILS_H
#define TFTECH_EPICEYE_EXAMPLES_INTRINSIC_CALIBRATION_UTILS_H

#include "intrinsic_calibration_type.h"

#include <string>

/**
 * @brief 拍照并自动识别内参标定板类型。
 * @param ip 相机 IP。
 * @param result 输出标定板类型、提示信息和预览图。
 * @return true 表示识别 API 调用和结果解析成功。
 */
bool identifyIntrinsicBoard(const std::string& ip, IntrinsicBoardIdentifyResult& result);

/**
 * @brief 采集并追加一组标定板位姿/内参标定图。
 * @param ip 相机 IP。
 * @param boardType 标定板类型，通常来自 identifyIntrinsicBoard。
 * @param result 输出当前图像对索引、总数、检测状态和标定板姿态摘要。
 * @return true 表示 API 调用和结果解析成功。
 */
bool addCalibrationBoardPose(const std::string& ip, int boardType, IntrinsicCalibImageResult& result);

/**
 * @brief 从服务端内参标定工作区删除一组图像。
 * @param ip 相机 IP。
 * @param pairIndex 要删除的图像对索引。
 * @param result 输出删除后的图像对数量和被删除索引。
 * @return true 表示删除成功。
 */
bool removeIntrinsicCalibImage(const std::string& ip, int pairIndex, IntrinsicRemoveCalibImageResult& result);

/**
 * @brief 使用工作区内已采集的图像对计算内参。
 * @param ip 相机 IP。
 * @param result 输出深度/彩色计算结果、完整可写配置和 RMS。
 * @return true 表示计算 API 调用和结果解析成功。
 */
bool calculateIntrinsicCalibration(const std::string& ip, IntrinsicCalibrationResult& result);

/**
 * @brief 将计算得到的内参数据写入设备。
 * @param ip 相机 IP。
 * @param cameraParametersConfig calculateIntrinsicCalibration 返回的完整相机参数配置。
 * @return true 表示写入成功。
 */
bool writeIntrinsicCameraParameters(const std::string& ip, const TFTech::CameraParametersConfig& cameraParametersConfig);

#endif
