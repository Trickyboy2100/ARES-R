#pragma once

#include "atom_sdk/core/json.hpp"

#include <optional>
#include <stdexcept>
#include <string>
#include <utility>

namespace atom::sdk {

class AtomError : public std::runtime_error {
 public:
  explicit AtomError(const std::string& message)
      : std::runtime_error(message) {}
};

class AtomHttpError : public AtomError {
 public:
  AtomHttpError(std::string message, int status_code = 0)
      : AtomError(message), status_code_(status_code) {}

  int status_code() const noexcept { return status_code_; }

 private:
  int status_code_;
};

class AtomProtocolError : public AtomError {
 public:
  explicit AtomProtocolError(const std::string& message)
      : AtomError(message) {}
};

class AtomTimeoutError : public AtomError {
 public:
  AtomTimeoutError(
      std::string message,
      std::string path,
      std::optional<double> timeout_seconds,
      int attempts,
      JsonValue last_data)
      : AtomError(std::move(message)),
        path_(std::move(path)),
        timeout_seconds_(timeout_seconds),
        attempts_(attempts),
        last_data_(std::move(last_data)) {}

  const std::string& path() const noexcept { return path_; }
  std::optional<double> timeout_seconds() const noexcept {
    return timeout_seconds_;
  }
  int attempts() const noexcept { return attempts_; }
  const JsonValue& last_data() const noexcept { return last_data_; }

 private:
  std::string path_;
  std::optional<double> timeout_seconds_;
  int attempts_ = 0;
  JsonValue last_data_;
};

class AtomApiError : public AtomError {
 public:
  AtomApiError(std::string message, int status)
      : AtomError(std::move(message)), status_(status) {}

  int status() const noexcept { return status_; }

 private:
  int status_;
};

}  // namespace atom::sdk
