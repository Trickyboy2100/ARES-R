#ifndef TFTECH_EPICEYESDK_EPICRAW_DOCUMENT_HPP
#define TFTECH_EPICEYESDK_EPICRAW_DOCUMENT_HPP

#include <string>

#include "epicraw1.hpp"
#include "epicraw2.hpp"
#include "epicraw3.hpp"

namespace TFTech {

/**
 * @brief 已解析 EpicRaw 文档。
 * 由 EpicEye::tryLoadEpicRawDocumentFromBytes 创建，仅持有 Raw1 / Raw2 / Raw3 之一。
 * EpicRaw3 元素零拷贝引用传入字节容器，文档使用期间该容器必须保持存活且不得改变容量。
 */
struct EpicRawDocument {
    std::string fileType;
    EpicRaw1 raw1;
    EpicRaw2 raw2;
    EpicRaw3 raw3;
    bool hasRaw1 = false;
    bool hasRaw2 = false;
    bool hasRaw3 = false;
};

}  // namespace TFTech

#endif
