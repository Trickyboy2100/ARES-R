#ifndef TFTECH_EPICEYESDK_EPICRAW2_HPP
#define TFTECH_EPICEYESDK_EPICRAW2_HPP

#include <cstdint>
#include <string_view>
#include <vector>

namespace TFTech {

struct EpicRaw2 {
    static constexpr int kHeaderSize = 40;

    int width = 0;
    int height = 0;
    int dataType = 0;
    int cameraMatrixLength = 0;
    int distortionLength = 0;
    int configStrLength = 0;
    int depthDataLength = 0;
    int imageDataLength = 0;
    std::vector<double> cameraMatrix;
    std::vector<double> distortion;
    std::vector<uint8_t> configData;
    std::vector<uint8_t> depthData;
    std::vector<uint8_t> imageData;

    static bool loadFromBytes(std::string_view raw, EpicRaw2 &out);
};

}  // namespace TFTech

#endif
