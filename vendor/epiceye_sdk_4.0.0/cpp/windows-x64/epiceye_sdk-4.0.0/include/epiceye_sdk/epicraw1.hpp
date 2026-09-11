#ifndef TFTECH_EPICEYESDK_EPICRAW1_HPP
#define TFTECH_EPICEYESDK_EPICRAW1_HPP

#include <cstdint>
#include <string_view>
#include <vector>

namespace TFTech {

struct EpicRaw1CameraConfig {
    uint32_t projectorBrightness = 0;
    float expTime2D = 0;
    float expTime3D = 0;
    bool useHDR = false;
    float expTimeHDR = 0;
    bool usePF = false;
    bool useSF = false;
};

struct EpicRaw1 {
    static constexpr int kHeaderSize = 168;

    int width = 0;
    int height = 0;
    double cameraMatrix[9] = {};
    double distortion[5] = {};
    EpicRaw1CameraConfig cameraConfig;
    int dataType = 0;
    int depthDataLength = 0;
    int imageDataLength = 0;
    std::vector<uint8_t> depthData;
    std::vector<uint8_t> imageData;

    static bool loadFromBytes(std::string_view raw, EpicRaw1 &out);
};

}  // namespace TFTech

#endif
