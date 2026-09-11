#pragma once

#include "atom_sdk/core/models.hpp"

#include <memory>
#include <string>

namespace atom::sdk {

class BaseTransport {
 public:
  virtual ~BaseTransport() = default;

  virtual HttpResponse request(
      const std::string& method,
      const std::string& path,
      const RequestPayload& payload = {}) = 0;
};

class HttpTransport : public BaseTransport {
 public:
  explicit HttpTransport(std::string base_url, RequestOptions options = {});

  HttpResponse request(
      const std::string& method,
      const std::string& path,
      const RequestPayload& payload = {}) override;

 private:
  struct ParsedBaseUrl {
    std::string host;
    std::string port;
    std::string base_path;
  };

  ParsedBaseUrl parsed_;
  RequestOptions options_;
};

}  // namespace atom::sdk
