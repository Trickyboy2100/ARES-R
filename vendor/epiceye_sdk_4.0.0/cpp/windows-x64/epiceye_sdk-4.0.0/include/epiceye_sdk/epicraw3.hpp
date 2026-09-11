#ifndef TFTECH_EPICEYESDK_EPICRAW3_HPP
#define TFTECH_EPICEYESDK_EPICRAW3_HPP

#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

namespace TFTech {

/** 与 C# TFTech.Models.EpicRawDataType 数值一致 */
enum class EpicRaw3DataType {
    DepthSrcImg1 = 0,
    DepthSrcImg2 = 1,
    TextureBGR = 2,
    Depth = 3,
    PointCloud = 4,
    PointCloudNormal = 5
};

struct EpicRaw3Element {
    int headerLength = 0;
    int dataType = -1;
    int dataLength = 0;
    int width = 0;
    int height = 0;
    int matType = 0;  // OpenCV Mat 类型编码(决定通道数/位深)；与 C# EpicRaw3ElementHeader.MatType 一致。
    int metaLength = 0;
    std::string meta;
    // 元素数据：指向 loadFromBytes 传入 raw 的切片（零拷贝，不复制）。
    // 只读，接口与 vector 兼容（data()/size()/empty()/begin()/end()）；raw 须存活 ≥ 本 EpicRaw3。
    std::string_view data;
};

struct EpicRaw3 {
    int headerLength = 0;
    int elementsCount = 0;
    std::vector<int> elementLengths;
    int headerMetaLength = 0;
    std::string headerMeta;
    std::vector<EpicRaw3Element> elements;

    // 注意：elements[].data 是 raw 的视图，raw 须在返回的 out 存活期间保持有效。
    static bool loadFromBytes(std::string_view raw, EpicRaw3 &out);
    const EpicRaw3Element *findElement(EpicRaw3DataType type) const;
};

}  // namespace TFTech

#endif
