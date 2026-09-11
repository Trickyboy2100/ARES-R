#pragma once

// JSON is part of the SDK's own public type surface. The implementation is
// vendored under cpp/thirdparty so consumers do not need a separately
// installed JSON package.
#include <atom_sdk/thirdparty/nlohmann_json.hpp>

#include <string>
#include <system_error>
#include <utility>

namespace atom::sdk {

using JsonValue = nlohmann::json;
using JsonObject = nlohmann::json;
using JsonArray = nlohmann::json;

namespace json {

using value = nlohmann::json;
using object = nlohmann::json;
using array = nlohmann::json;

inline value parse(const std::string& text) {
  return nlohmann::json::parse(text);
}

inline value parse(const std::string& text, std::error_code& error_code) {
  try {
    error_code.clear();
    return nlohmann::json::parse(text);
  } catch (const nlohmann::json::parse_error&) {
    error_code = std::make_error_code(std::errc::invalid_argument);
    return value();
  }
}

inline std::string serialize(const value& input) {
  return input.dump();
}

template <typename T>
T value_to(const value& input) {
  return input.get<T>();
}

template <typename T>
value value_from(T&& input) {
  return value(std::forward<T>(input));
}

inline const value* if_contains(const value& input, const std::string& key) {
  if (!input.is_object()) {
    return nullptr;
  }
  const auto iterator = input.find(key);
  return iterator == input.end() ? nullptr : &iterator.value();
}

}  // namespace json

}  // namespace atom::sdk
