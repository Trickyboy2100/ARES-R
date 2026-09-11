/*
 * 作用：提供用户逐步确认的完整内参标定流程，不自动连续拍摄或自动写入。
 * 流程：识别板型 -> 多位姿采集 -> 保留/删除图对 -> 计算 -> 检查 RMS -> 用户确认写入。
 * 数据规则：每次采集前必须重新放置标定板；无效图对必须从相机临时工作区删除。
 * 相机影响：只有最终确认写入才覆盖正式内参；识别、采集、删除和计算只操作临时数据。
 */
#include "epiceye.h"
#include "intrinsic_calibration_utils.h"

#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>

static std::string resolveIp(int argc, char** argv) {
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

static char readChoice(const std::string& prompt, const std::string& allowedChoices) {
    while (true) {
        std::cout << prompt;
        std::string input;
        if (!std::getline(std::cin, input)) {
            return 'Q';
        }
        if (input.size() == 1) {
            const char choice = static_cast<char>(std::toupper(static_cast<unsigned char>(input[0])));
            if (allowedChoices.find(choice) != std::string::npos) {
                return choice;
            }
        }
        std::cout << "Invalid choice. Available choices: ";
        for (std::size_t i = 0; i < allowedChoices.size(); ++i) {
            if (i > 0) std::cout << '/';
            std::cout << allowedChoices[i];
        }
        std::cout << std::endl;
    }
}

static void printCaptureResult(const IntrinsicCalibImageResult& result) {
    std::cout << "Capture result: pairIndex=" << result.pairIndex
              << ", pairCount=" << result.pairCount
              << ", detectSuccess=" << (result.detectSuccess ? "true" : "false") << std::endl;
    if (result.boardPose) {
        const auto& pose = *result.boardPose;
        std::cout << "Board pose [tx,ty,tz,qx,qy,qz,qw]: [" << pose[0] << ", " << pose[1] << ", " << pose[2] << ", " << pose[3] << ", " << pose[4] << ", " << pose[5] << ", " << pose[6] << "]" << std::endl;
    } else {
        std::cout << "Board pose [tx,ty,tz,qx,qy,qz,qw]: unavailable" << std::endl;
    }
    std::cout << "Board tilt angle: " << result.boardTiltAngle
              << ", tilt warning: " << (result.boardTiltWarning ? "true" : "false") << std::endl;
    std::cout << "Preview image count: " << result.previewImages.size() << std::endl;
    for (const ImageInfoData& preview : result.previewImages) {
        std::cout << "  " << preview.name << ": " << preview.width << 'x' << preview.height << ", " << preview.dataUri << std::endl;
    }
}

static bool removePair(const std::string& ip, int pairIndex, int& remainingPairCount) {
    if (pairIndex < 0) {
        std::cerr << "The captured pair has no valid pair index. Calculation is disabled to avoid using an unknown dataset." << std::endl;
        return false;
    }

    IntrinsicRemoveCalibImageResult removeResult;
    if (!removeIntrinsicCalibImage(ip, pairIndex, removeResult)) {
        std::cerr << "removeCalibImage failed! Calculation is disabled to avoid using an invalid pair." << std::endl;
        return false;
    }

    remainingPairCount = removeResult.pairCount;
    std::cout << "Removed pair index " << removeResult.removedIndex
              << ". Retained pair count: " << remainingPairCount << std::endl;
    return true;
}

static void printCalculation(const IntrinsicCalibrationResult& result) {
    std::cout << std::endl
              << "Intrinsic calibration stereoRms: " << result.stereoRms
              << ", shouldWarnRms: " << (result.shouldWarnRms ? "true" : "false") << std::endl;
    if (result.colorStereoRms.has_value()) {
        std::cout << "Color calibration stereoRms: " << result.colorStereoRms.value() << std::endl;
        std::cout << "Color camera parameters:" << std::endl << result.colorCameraParameters.dump(2) << std::endl;
        std::cout << "Color parameter errors:" << std::endl << result.colorParameterErrors.dump(2) << std::endl;
    }
    std::cout << "Camera parameters:" << std::endl << result.cameraParameters.dump(2) << std::endl;
    std::cout << "Parameter errors:" << std::endl << result.parameterErrors.dump(2) << std::endl;
}

int main(int argc, char** argv) {
    std::cout << "SDK Version: " << TFTech::EpicEye::getSDKVersion() << std::endl;
    std::cout << "Example: interactively collect board poses, calculate intrinsic parameters, and optionally write them." << std::endl;
    std::cout << "Usage: IntrinsicCalibration [camera_ip] [minimum_pair_count] [board_type]" << std::endl;

    const std::string ip = resolveIp(argc, argv);
    if (ip.empty()) {
        return 1;
    }

    int minimumPairCount = 4;
    if (argc > 2) {
        minimumPairCount = std::max(4, std::atoi(argv[2]));
    }

    int boardType = -1;
    if (argc > 3) {
        boardType = std::atoi(argv[3]);
    }

    try {
        if (boardType < 0) {
            // 只识别板型并生成预览，不会向标定工作区增加图对。
            if (readChoice("Place the calibration board in view. [I] Identify board  [Q] Quit: ", "IQ") == 'Q') {
                std::cout << "Exited without changing intrinsic parameters." << std::endl;
                return 0;
            }

            IntrinsicBoardIdentifyResult identifyResult;
            if (!identifyIntrinsicBoard(ip, identifyResult)) {
                std::cerr << "identifyIntrinsicBoard failed!" << std::endl;
                return 1;
            }
            boardType = identifyResult.boardType;
            std::cout << "Board type: " << boardType << std::endl;
            std::cout << "Board hint: " << identifyResult.boardHint << std::endl;
            std::cout << "Identify preview count: " << identifyResult.previewImages.size() << std::endl;
        }

        if (boardType < 0) {
            std::cerr << "Invalid board type. Pass board_type manually if auto identify failed." << std::endl;
            return 1;
        }

        int retainedPairCount = 0;
        while (true) {
            std::string prompt;
            std::string allowedChoices;
            if (retainedPairCount >= minimumPairCount) {
                prompt = "\nRetained pairs: " + std::to_string(retainedPairCount) + ". [C] Capture after repositioning board  [K] Calculate  [Q] Quit: ";
                allowedChoices = "CKQ";
            } else {
                prompt = "\nRetained pairs: " + std::to_string(retainedPairCount) + "/" + std::to_string(minimumPairCount) + ". Reposition and stabilize the board. [C] Capture  [Q] Quit: ";
                allowedChoices = "CQ";
            }

            const char action = readChoice(prompt, allowedChoices);
            if (action == 'Q') {
                std::cout << "Exited without changing intrinsic parameters." << std::endl;
                return 0;
            }

            if (action == 'C') {
                // 采集结果进入相机端临时工作区，pairIndex 是删除该图对的唯一标识。
                IntrinsicCalibImageResult captureResult;
                if (!addCalibrationBoardPose(ip, boardType, captureResult)) {
                    std::cerr << "addCalibrationBoardPose failed!" << std::endl;
                    continue;
                }

                printCaptureResult(captureResult);
                if (!captureResult.detectSuccess) {
                    // 检测不完整的图对必须立即删除，避免污染后续计算。
                    std::cout << "The calibration board was not detected in every required image. This pair cannot be used and will be removed." << std::endl;
                    if (!removePair(ip, captureResult.pairIndex, retainedPairCount)) return 1;
                    continue;
                }

                const char keep = readChoice("[K] Keep this pair  [R] Remove and recapture  [Q] Remove and quit: ", "KRQ");
                if (keep == 'K') {
                    retainedPairCount = captureResult.pairCount;
                    std::cout << "Pair retained. Retained pair count: " << retainedPairCount << std::endl;
                    continue;
                }

                if (!removePair(ip, captureResult.pairIndex, retainedPairCount)) return 1;
                if (keep == 'Q') {
                    std::cout << "Exited without changing intrinsic parameters." << std::endl;
                    return 0;
                }
                continue;
            }

            // 这里只计算候选参数，不会写入正式内参。
            IntrinsicCalibrationResult result;
            if (!calculateIntrinsicCalibration(ip, result)) {
                std::cerr << "calculateIntrinsicCalibration failed! You can capture more pairs or quit." << std::endl;
                continue;
            }

            printCalculation(result);
            if (result.shouldWarnRms) {
                // RMS 超过服务端安全阈值时禁止写入，必须补充更有效的姿态后重算。
                std::cerr << "Calibration RMS exceeds the safe threshold. Writing is disabled; capture more valid poses or quit." << std::endl;
                continue;
            }
            if (!result.cameraParametersConfig.has_value()) {
                std::cerr << "calculate did not return cameraParametersConfig. Writing is disabled." << std::endl;
                continue;
            }

            std::cout << "Complete configuration proposed for writing:" << std::endl;
            std::cout << nlohmann::json(*result.cameraParametersConfig).dump(2) << std::endl;
            const char writeChoice = readChoice("[W] Write this configuration to the camera  [B] Back to capture  [Q] Quit without writing: ", "WBQ");
            if (writeChoice == 'B') continue;
            if (writeChoice == 'Q') {
                std::cout << "Exited without changing intrinsic parameters." << std::endl;
                return 0;
            }

            // 唯一会覆盖正式内参的步骤；写入完整 CameraParametersConfig，保留所有深度和彩色相机参数。
            if (writeIntrinsicCameraParameters(ip, *result.cameraParametersConfig)) {
                std::cout << "Intrinsic parameters written to device." << std::endl;
                return 0;
            }
            std::cerr << "writeIntrinsicCameraParameters failed!" << std::endl;
        }
    } catch (const std::exception& exception) {
        std::cerr << "IntrinsicCalibration sample error: " << exception.what() << std::endl;
        return 1;
    }
}
