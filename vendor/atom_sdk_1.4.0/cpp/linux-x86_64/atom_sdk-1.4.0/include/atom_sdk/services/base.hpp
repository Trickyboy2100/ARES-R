#pragma once

#include "atom_sdk/core/codecs.hpp"
#include "atom_sdk/core/models.hpp"
#include "atom_sdk/core/point_cloud.hpp"
#include "atom_sdk/core/state.hpp"
#include "atom_sdk/core/transport.hpp"
#include "atom_sdk/params.hpp"

#include <filesystem>
#include <memory>
#include <optional>
#include <string>

namespace atom::sdk {

struct PortDataResult {
  JsonObject data;
  std::unordered_map<std::string, ByteBuffer> attachments;
};

class BaseService {
 public:
  BaseService(
      std::shared_ptr<BaseTransport> transport,
      std::shared_ptr<TimestampStore> timestamps);

 protected:
  std::shared_ptr<BaseTransport> transport_;
  std::shared_ptr<TimestampStore> timestamps_;

  DecodedResponse request_json(
      const std::string& method,
      const std::string& path,
      const RequestPayload& payload = {},
      const std::string& timestamp_graph_name = "") const;
  ByteBuffer request_raw(
      const std::string& method,
      const std::string& path,
      const RequestPayload& payload = {}) const;
  DecodedResponse request_until_finish(
      const std::string& method,
      const std::string& path,
      const RequestPayload& payload = {},
      const std::string& timestamp_graph_name = "",
      const std::string& finish_key = "finish",
      std::optional<double> timeout_seconds = 30.0,
      double sleep_seconds = 1.0) const;
  void maybe_save_timestamp(
      const std::string& graph_name,
      const JsonValue& data) const;
  JsonObject timestamp_payload(
      const std::string& graph_name,
      JsonObject extra = {}) const;
  RequestPayload build_param_request_payload(
      const JsonObject& payload,
      const JsonValue& value) const;
  RequestPayload build_param_request_payload(
      const JsonObject& payload,
      const std::filesystem::path& value) const;
  JsonValue data_with_request_status(const DecodedResponse& decoded) const;
  JsonObject object_with_request_status(
      const DecodedResponse& decoded,
      const std::string& context) const;
  PortDataResult merge_attachments(const DecodedResponse& decoded) const;
  std::vector<ParsedPointCloud> decode_point_cloud_payload(
      const ByteBuffer& payload,
      bool has_dim_in_header,
      std::optional<std::size_t> point_dim = std::nullopt) const;
};

}  // namespace atom::sdk
