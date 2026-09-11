#pragma once

#include "atom_sdk/core/json.hpp"

#include <optional>
#include <string>
#include <unordered_map>

namespace atom::sdk {

class TimestampStore {
 public:
  std::optional<double> get(const std::string& graph_name) const;
  std::optional<JsonValue> get_value(
      const std::string& graph_name) const;
  void set(const std::string& graph_name, double timestamp);
  void set_value(
      const std::string& graph_name,
      const JsonValue& timestamp);
  void clear(const std::string& graph_name);
  double require(const std::string& graph_name) const;

 private:
  std::unordered_map<std::string, double> values_;
  std::unordered_map<std::string, JsonValue> raw_values_;
};

}  // namespace atom::sdk
