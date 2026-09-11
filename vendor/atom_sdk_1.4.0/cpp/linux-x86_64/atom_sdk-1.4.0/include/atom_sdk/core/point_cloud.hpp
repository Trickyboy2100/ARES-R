#pragma once

#include "atom_sdk/core/errors.hpp"
#include "atom_sdk/core/models.hpp"

#include <cstdint>
#include <cstring>
#include <optional>
#include <string>
#include <vector>

namespace atom::sdk {

struct ParsedPointCloud {
  std::vector<float> values;
  std::vector<std::size_t> shape;
};

inline std::vector<ParsedPointCloud> decode_point_cloud_payload(
    const ByteBuffer& payload,
    bool has_dim_in_header,
    std::optional<std::size_t> point_dim = std::nullopt) {
  if (payload.empty()) {
    return {};
  }
  if (payload.size() % sizeof(float) != 0U) {
    throw AtomProtocolError(
        "Point cloud payload byte length must be a multiple of 4");
  }
  if (point_dim.has_value() && *point_dim == 0U) {
    throw AtomProtocolError("point_dim must be a positive integer");
  }

  auto read_float = [&payload](std::size_t float_index) {
    const std::size_t offset = float_index * sizeof(float);
    const std::uint32_t bits =
        static_cast<std::uint32_t>(payload.at(offset)) |
        (static_cast<std::uint32_t>(payload.at(offset + 1)) << 8U) |
        (static_cast<std::uint32_t>(payload.at(offset + 2)) << 16U) |
        (static_cast<std::uint32_t>(payload.at(offset + 3)) << 24U);
    float value = 0.0F;
    std::memcpy(&value, &bits, sizeof(float));
    return value;
  };

  auto float_to_size = [](float value, const std::string& label) {
    const auto integer = static_cast<std::int64_t>(value);
    if (static_cast<float>(integer) != value) {
      throw AtomProtocolError(
          "Point cloud payload " + label + " must be an integer");
    }
    if (integer < 0) {
      throw AtomProtocolError(
          "Point cloud payload " + label + " must be non-negative");
    }
    return static_cast<std::size_t>(integer);
  };

  const std::size_t float_count = payload.size() / sizeof(float);
  const std::size_t cloud_count = float_to_size(
      read_float(0), "point cloud count");
  const std::size_t header_length =
      1U + cloud_count + (has_dim_in_header ? cloud_count : 0U);
  if (float_count < header_length) {
    throw AtomProtocolError("Point cloud payload header is truncated");
  }

  std::vector<std::size_t> sizes;
  sizes.reserve(cloud_count);
  for (std::size_t index = 0; index < cloud_count; ++index) {
    sizes.push_back(float_to_size(
        read_float(1U + index), "point cloud size"));
  }

  std::vector<std::size_t> dims;
  if (has_dim_in_header) {
    dims.reserve(cloud_count);
    for (std::size_t index = 0; index < cloud_count; ++index) {
      dims.push_back(float_to_size(
          read_float(1U + cloud_count + index),
          "point cloud dimension"));
    }
  }

  std::size_t expected_total = header_length;
  for (const auto size : sizes) {
    expected_total += size;
  }
  if (float_count != expected_total) {
    throw AtomProtocolError("Point cloud payload length mismatch");
  }

  std::vector<ParsedPointCloud> clouds;
  clouds.reserve(cloud_count);
  std::size_t offset = header_length;
  for (std::size_t index = 0; index < cloud_count; ++index) {
    ParsedPointCloud cloud;
    const auto size = sizes[index];
    cloud.values.reserve(size);
    for (std::size_t value_index = 0; value_index < size; ++value_index) {
      cloud.values.push_back(read_float(offset + value_index));
    }

    const auto current_dim =
        has_dim_in_header ? std::optional<std::size_t>(dims[index]) : point_dim;
    if (!current_dim.has_value()) {
      cloud.shape.push_back(size);
    } else {
      if (*current_dim == 0U) {
        throw AtomProtocolError("point_dim must be a positive integer");
      }
      if (size == 0U) {
        cloud.shape = {0U, *current_dim};
      } else {
        if (size % *current_dim != 0U) {
          throw AtomProtocolError(
              "Point cloud payload size is not divisible by point_dim");
        }
        cloud.shape = {size / *current_dim, *current_dim};
      }
    }
    clouds.push_back(std::move(cloud));
    offset += size;
  }
  return clouds;
}

}  // namespace atom::sdk
