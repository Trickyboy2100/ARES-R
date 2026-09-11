#pragma once

#include "atom_sdk/core/json.hpp"

#include <cstdint>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>

namespace atom::sdk {

using ByteBuffer = std::vector<std::uint8_t>;

inline ByteBuffer to_bytes(const std::string& value) {
  return ByteBuffer(value.begin(), value.end());
}

inline std::string bytes_to_string(const ByteBuffer& value) {
  return std::string(value.begin(), value.end());
}

struct HttpResponse {
  int status_code = 0;
  std::unordered_map<std::string, std::string> headers;
  ByteBuffer content;

  std::string text() const {
    return bytes_to_string(content);
  }
};

struct DecodedResponse {
  int status = 0;
  JsonValue data;
  JsonObject raw;
  std::unordered_map<std::string, ByteBuffer> attachments;
};

struct RequestOptions {
  double timeout_seconds = 30.0;
  std::unordered_map<std::string, std::string> headers;
};

struct FilePart {
  std::string filename;
  ByteBuffer content;
  std::string content_type = "application/octet-stream";
};

struct RequestPayload {
  std::unordered_map<std::string, std::string> params;
  std::unordered_map<std::string, std::string> headers;
  std::optional<JsonValue> json_body;
  std::optional<ByteBuffer> body;
  std::optional<std::string> body_content_type;
  std::unordered_map<std::string, std::string> form_fields;
  std::unordered_map<std::string, FilePart> files;
};

}  // namespace atom::sdk
