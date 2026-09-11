#pragma once

#include <filesystem>
#include <string>

namespace atom::sdk {

/**
 * 返回路径文件名的 UTF-8 表示。
 *
 * Windows 下 filesystem::path 使用宽字符保存原生路径，不能使用
 * path::string() 作为 HTTP multipart 的文件名，因为它可能按系统代码页
 * 转换成非 UTF-8 字节。u8string() 明确要求 UTF-8 编码。
 */
inline std::string filename_to_utf8(const std::filesystem::path& path) {
  const auto filename = path.filename().u8string();
#if defined(__cpp_char8_t)
  return std::string(
      reinterpret_cast<const char*>(filename.data()),
      filename.size());
#else
  return filename;
#endif
}

}  // namespace atom::sdk
