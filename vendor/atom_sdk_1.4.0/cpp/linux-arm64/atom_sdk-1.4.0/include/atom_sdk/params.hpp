#pragma once

#include "atom_sdk/core/errors.hpp"
#include "atom_sdk/core/models.hpp"
#include "atom_sdk/core/point_cloud.hpp"

#include "atom_sdk/core/json.hpp"

#include <array>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <optional>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <variant>
#include <vector>

namespace atom::sdk {

struct CreateGraphParams {
  std::string graph_name;
  std::optional<std::string> description = std::nullopt;
};

struct CopyGraphParams {
  std::string graph_name;
  std::string new_graph_name;
};

struct EditGraphNameParams {
  std::string graph_name;
  std::string new_graph_name;
};

struct EditGraphCommentParams {
  std::string graph_name;
  std::string comment;
};

struct LoadGraphParams {
  std::string graph_name;
  std::filesystem::path file_path;
};

struct ExportGraphParams {
  std::string graph_name;
  JsonObject dl_models_info = {};
  JsonObject custom_nodes = {};
};

struct NodeRef {
  std::string graph_name;
  std::string node_id;
};

using SingleNodeInput =
    std::variant<JsonValue, ByteBuffer, std::filesystem::path>;
using SingleNodeInputs = std::unordered_map<std::string, SingleNodeInput>;
using SingleNodeResult = std::variant<JsonValue, ByteBuffer>;

struct ParsedImage {
  ByteBuffer data;
  std::string format;
  std::string data_type;
};

using SingleNodeParsedOutput =
    std::variant<JsonValue, std::vector<ParsedPointCloud>, std::vector<ParsedImage>>;

struct SingleNodeParsedResult {
  JsonValue raw;
  std::unordered_map<std::string, SingleNodeParsedOutput> outputs;
};

struct SingleNodeParams {
  std::string node_name;
  SingleNodeInputs inputs = {};
  JsonObject run_params = {};
  JsonObject init_params = {};
  std::unordered_map<std::string, std::string> output_data_types = {};
  std::unordered_map<std::string, std::size_t> output_point_dims = {};
  std::unordered_map<std::string, std::string> input_data_types = {};
  std::unordered_map<std::string, std::size_t> input_point_dims = {};
};

struct CreateNodeParams {
  std::string graph_name;
  std::string node_name;
};

struct CreateDynamicNodeParams {
  std::string graph_name;
  std::string node_name;
  JsonObject node_data = {};
};

struct CopyNodeParams {
  std::string graph_name;
  std::string node_name;
  std::string node_id;
};

struct ChangeNodeIOParams {
  std::string graph_name;
  std::string node_id;
  JsonObject node_data = {};
};

struct CreateGraphNodeParams {
  std::string graph_name;
  std::string node_name;
  std::string sub_graph_name;
};

struct GenerateGraphNodeByNodesParams {
  std::string graph_name;
  std::string graph_node_name;
  std::vector<std::string> node_ids = {};
};

struct NodeConnectionParams {
  std::string graph_name;
  std::string output_node_id;
  std::string output_port_name;
  std::string input_node_id;
  std::string input_port_name;
};

struct PortRef {
  std::string graph_name;
  std::string node_id;
  std::string port_name;
  std::string io_type;
};

using NodeParamValue = std::variant<JsonValue, std::filesystem::path>;

struct NodeParamUpdate {
  std::string graph_name;
  std::string node_id;
  std::string param_name;
  std::string param_type;
  NodeParamValue value;
};

struct NodeBindingUpdate {
  std::string graph_name;
  std::string node_id;
  std::string binding_type;
  std::string origin_name;
  std::string binding_name;
};

struct EditNodeCommentParams {
  std::string graph_name;
  std::string node_id;
  std::string comment;
};

struct SubGraphRef {
  std::string graph_name;
  std::string graph_node_id;
};

struct SubGraphCreateNodeParams {
  std::string graph_name;
  std::string graph_node_id;
  std::string node_name;
};

struct CreateDynamicSubGraphNodeParams {
  std::string graph_name;
  std::string graph_node_id;
  std::string node_name;
  JsonObject node_data = {};
};

struct SubGraphCopyNodeParams {
  std::string graph_name;
  std::string graph_node_id;
  std::string node_name;
  std::string node_id;
};

struct ChangeSubGraphNodeIOParams {
  std::string graph_name;
  std::string graph_node_id;
  std::string node_id;
  JsonObject node_data = {};
};

struct SubGraphNodeRef {
  std::string graph_name;
  std::string graph_node_id;
  std::string node_id;
};

struct EditSubGraphNameParams {
  std::string graph_name;
  std::string graph_node_id;
  std::string new_sub_graph_name;
};

struct SubGraphConnectionParams {
  std::string graph_name;
  std::string graph_node_id;
  std::string output_node_id;
  std::string output_port_name;
  std::string input_node_id;
  std::string input_port_name;
};

struct SubGraphPortRef {
  std::string graph_name;
  std::string graph_node_id;
  std::string node_id;
  std::string port_name;
  std::string io_type;
};

using SubGraphNodeParamValue = NodeParamValue;

struct SubGraphNodeParamUpdate {
  std::string graph_name;
  std::string graph_node_id;
  std::string node_id;
  std::string param_name;
  std::string param_type;
  SubGraphNodeParamValue value;
};

struct SubGraphBindingUpdate {
  std::string graph_name;
  std::string graph_node_id;
  std::string node_id;
  std::string binding_type;
  std::string origin_name;
  std::string binding_name;
};

struct ExportSubGraphParams {
  std::string graph_name;
  std::string graph_node_id;
  JsonObject dl_models_info = {};
  JsonObject custom_nodes = {};
};

struct SetSubgraphAsCustomSubgraphParams {
  std::string graph_name;
  std::string graph_node_id;
  std::string custom_subgraph_name;
};

struct EditSubGraphNodeCommentParams {
  std::string graph_name;
  std::string graph_node_id;
  std::string node_id;
  std::string comment;
};

struct BindingRef {
  std::string graph_name;
  std::string binding_name;
};

struct PointCloudRef {
  std::string graph_name;
  std::string binding_name;
  std::optional<std::size_t> point_dim = std::nullopt;
};

struct RuntimeParamsUpdate {
  std::string graph_name;
  JsonObject params_data;
};

struct RuntimeImageData {
  ByteBuffer data;
  std::int32_t width;
  std::int32_t height;
  std::int32_t channels = 3;
  std::int32_t bytes_per_channel = 1;
};

struct RuntimePointData {
  std::vector<float> data;
  std::int32_t width;
  std::int32_t height;
  std::int32_t channels = 3;
};

ByteBuffer make_epicraw(
    const RuntimePointData& points,
    const RuntimeImageData& image,
    const JsonValue& intrinsic,
    const JsonValue& distortion,
    std::optional<std::int32_t> version = std::nullopt,
    const JsonObject& camera_params = {});

/**
 * 校验 cam2_base（相机到基座变换）是服务端目前唯一支持的旋转矢量形式：
 * 长度为 6 的 [x, y, z, rx, ry, rz]（平移 + Rodrigues 旋转向量）。
 *
 * 服务端节点按 len(cam2Base) == 6 过滤输入，非 6 长度的值会被直接丢弃而
 * 不报错，因此这里提前拦截，避免用户传入 4x4/3x4 矩阵后请求被静默丢弃。
 */
inline void require_cam2_base_shape(const JsonValue& cam_to_base) {
  if (!cam_to_base.is_array() || cam_to_base.size() != 6U) {
    throw std::invalid_argument(
        "cam2_base 服务端目前只支持旋转矢量形式：长度为 6 的 [x, y, z, rx, ry, rz]"
        "（平移 + Rodrigues 旋转向量），不支持矩阵形式，实际传入了 " +
        cam_to_base.dump());
  }
}

/** 校验 roi["cam2ROIFrame"]（若提供）同样是长度为 6 的旋转矢量形式。 */
inline void validate_roi_shape(const std::optional<JsonValue>& roi) {
  if (!roi.has_value() || !roi->is_object()) {
    return;
  }
  const auto* cam2roi_frame = json::if_contains(*roi, "cam2ROIFrame");
  if (cam2roi_frame == nullptr) {
    return;
  }
  if (!cam2roi_frame->is_array() || cam2roi_frame->size() != 6U) {
    throw std::invalid_argument(
        "roi[\"cam2ROIFrame\"] 服务端目前只支持旋转矢量形式：长度为 6 的 "
        "[x, y, z, rx, ry, rz]（平移 + Rodrigues 旋转向量），不支持矩阵形式，实际传入了 " +
        cam2roi_frame->dump());
  }
}

/** Runtime 普通模式的一帧 EPICRAW 输入。 */
struct RuntimeFrame {
  ByteBuffer epicraw;
  JsonValue cam_to_base;
  std::optional<JsonValue> roi = std::nullopt;

  RuntimeFrame(
      ByteBuffer epicraw_bytes,
      JsonValue cam_to_base_value,
      std::optional<JsonValue> roi_value = std::nullopt)
      : epicraw(std::move(epicraw_bytes)),
        cam_to_base(std::move(cam_to_base_value)),
        roi(std::move(roi_value)) {
    if (epicraw.empty()) {
      throw AtomError("runtime frame is missing EPICRAW bytes");
    }
    require_cam2_base_shape(cam_to_base);
    validate_roi_shape(roi);
  }

  static RuntimeFrame from_bytes(
      ByteBuffer epicraw_bytes,
      JsonValue cam_to_base_value,
      std::optional<JsonValue> roi_value = std::nullopt) {
    return RuntimeFrame(
        std::move(epicraw_bytes),
        std::move(cam_to_base_value),
        std::move(roi_value));
  }

  static RuntimeFrame from_file(
      const std::filesystem::path& epicraw_path,
      JsonValue cam_to_base_value,
      std::optional<JsonValue> roi_value = std::nullopt) {
    std::ifstream file(epicraw_path, std::ios::binary);
    if (!file) {
      throw std::runtime_error("failed to open EPICRAW file: " + epicraw_path.string());
    }
    return from_bytes(
        ByteBuffer(std::istreambuf_iterator<char>(file), std::istreambuf_iterator<char>()),
        std::move(cam_to_base_value),
        std::move(roi_value));
  }

  static RuntimeFrame from_data(
      const RuntimePointData& points,
      const RuntimeImageData& image,
      JsonValue cam_to_base_value,
      JsonValue intrinsic,
      JsonValue distortion,
      std::optional<std::int32_t> version = std::nullopt,
      JsonObject camera_params = {},
      std::optional<JsonValue> roi_value = std::nullopt) {
    return from_bytes(
        make_epicraw(points, image, intrinsic, distortion, version, camera_params),
        std::move(cam_to_base_value),
        std::move(roi_value));
  }
};

/**
 * 用于本地构造 passive_bino EPICRAW3 的单张图像。
 *
 * data 为原始像素字节；width/height 为图像尺寸；mat_type 使用 OpenCV Mat
 * type 编码，例如 CV_8UC1=0、CV_16UC1=2、CV_8UC3=16。
 */
struct RuntimePassiveBinoImage {
  ByteBuffer data;
  std::int32_t width;
  std::int32_t height;
  std::int32_t mat_type;
};

namespace detail {

inline void append_i32_le(ByteBuffer& output, std::int32_t value) {
  const auto unsigned_value = static_cast<std::uint32_t>(value);
  output.push_back(static_cast<std::uint8_t>(unsigned_value & 0xffU));
  output.push_back(static_cast<std::uint8_t>((unsigned_value >> 8U) & 0xffU));
  output.push_back(static_cast<std::uint8_t>((unsigned_value >> 16U) & 0xffU));
  output.push_back(static_cast<std::uint8_t>((unsigned_value >> 24U) & 0xffU));
}

inline ByteBuffer read_binary_file(const std::filesystem::path& path) {
  std::ifstream file(path, std::ios::binary);
  if (!file) {
    throw std::runtime_error("failed to open EPICRAW3 file: " + path.string());
  }
  return ByteBuffer(
      std::istreambuf_iterator<char>(file),
      std::istreambuf_iterator<char>());
}

inline ByteBuffer json_value_to_bytes(const JsonValue& value) {
  const auto text = value.dump();
  return ByteBuffer(text.begin(), text.end());
}

inline const JsonValue& required_passive_bino_param(
    const JsonObject& params,
    const char* key) {
  const auto* value = json::if_contains(params, key);
  if (value == nullptr) {
    throw std::invalid_argument(std::string("passive_bino params missing key: ") + key);
  }
  if (!value->is_object()) {
    throw std::invalid_argument(std::string(key) + " params must be an object");
  }
  static constexpr std::array<const char*, 4> kCameraFields{
      "CameraMatrix",
      "CameraDistortion",
      "CameraRotation",
      "CameraTranslation",
  };
  const auto& object = *value;
  for (const char* field : kCameraFields) {
    if (!object.contains(field)) {
      throw std::invalid_argument(std::string(key) + " params missing key: " + field);
    }
  }
  return *value;
}

inline ByteBuffer make_epicraw3_element(
    std::int32_t data_type,
    const RuntimePassiveBinoImage& image,
    const ByteBuffer& metadata) {
  if (image.width <= 0 || image.height <= 0) {
    throw std::invalid_argument("passive_bino image width and height must be positive");
  }
  const auto header_length =
      static_cast<std::int32_t>(7 * 4 + metadata.size());
  ByteBuffer element;
  element.reserve(static_cast<std::size_t>(header_length) + image.data.size());
  append_i32_le(element, header_length);
  append_i32_le(element, data_type);
  append_i32_le(element, static_cast<std::int32_t>(image.data.size()));
  append_i32_le(element, image.width);
  append_i32_le(element, image.height);
  append_i32_le(element, image.mat_type);
  append_i32_le(element, static_cast<std::int32_t>(metadata.size()));
  element.insert(element.end(), metadata.begin(), metadata.end());
  element.insert(element.end(), image.data.begin(), image.data.end());
  return element;
}

inline ByteBuffer make_passive_bino_epicraw3(
    const std::vector<RuntimePassiveBinoImage>& image_list,
    const JsonObject& params) {
  if (image_list.size() != 3U) {
    throw std::invalid_argument("passive_bino from_images requires exactly three images");
  }

  const std::vector<ByteBuffer> elements = {
      make_epicraw3_element(
          0,
          image_list[0],
          json_value_to_bytes(required_passive_bino_param(params, "DepthSrc1"))),
      make_epicraw3_element(
          1,
          image_list[1],
          json_value_to_bytes(required_passive_bino_param(params, "DepthSrc2"))),
      make_epicraw3_element(
          2,
          image_list[2],
          json_value_to_bytes(required_passive_bino_param(params, "TextureSrc"))),
  };

  const auto header_length =
      static_cast<std::int32_t>(8 + 4 + 4 + 4 * elements.size() + 4);
  ByteBuffer output;
  output.reserve(static_cast<std::size_t>(header_length));
  const std::string magic = "EPICRAW3";
  output.insert(output.end(), magic.begin(), magic.end());
  append_i32_le(output, header_length);
  append_i32_le(output, static_cast<std::int32_t>(elements.size()));
  for (const auto& element : elements) {
    append_i32_le(output, static_cast<std::int32_t>(element.size()));
  }
  append_i32_le(output, 0);
  for (const auto& element : elements) {
    output.insert(output.end(), element.begin(), element.end());
  }
  return output;
}

}  // namespace detail

inline ByteBuffer make_epicraw(
    const RuntimePointData& points,
    const RuntimeImageData& image,
    const JsonValue& intrinsic,
    const JsonValue& distortion,
    std::optional<std::int32_t> version,
    const JsonObject& camera_params) {
  if (points.width <= 0 || points.height <= 0 || points.channels < 3 ||
      points.data.size() <
          static_cast<std::size_t>(points.width * points.height * points.channels)) {
    throw std::invalid_argument("points require a non-empty HxWx3 or more shape");
  }
  if (image.width != points.width || image.height != points.height ||
      image.channels != 3 || (image.bytes_per_channel != 1 && image.bytes_per_channel != 2)) {
    throw std::invalid_argument("image must be matching HxWx3 uint8 or uint16 data");
  }
  const auto expected_image_size = static_cast<std::size_t>(
      image.width * image.height * image.channels * image.bytes_per_channel);
  if (image.data.size() != expected_image_size) {
    throw std::invalid_argument("image byte length does not match its shape");
  }

  const bool has_extended =
      camera_params.contains("DepthSrc1") ||
      camera_params.contains("DepthSrc2") ||
      camera_params.contains("TextureSrc");
  const auto selected_version = version.value_or(has_extended ? 3 : 2);
  if (selected_version != 2 && selected_version != 3) {
    throw std::invalid_argument("Unsupported EpicRaw version");
  }

  ByteBuffer depth(static_cast<std::size_t>(points.width * points.height) * sizeof(float));
  for (std::size_t index = 0; index < depth.size() / sizeof(float); ++index) {
    const float value = points.data[index * static_cast<std::size_t>(points.channels) + 2U];
    std::memcpy(depth.data() + index * sizeof(float), &value, sizeof(float));
  }

  if (selected_version == 2) {
    if (intrinsic.is_null() || distortion.is_null()) {
      throw std::invalid_argument("intrinsic and distortion are required for EPICRAW2");
    }
    std::vector<double> matrix;
    std::vector<double> distortion_values;
    for (const auto& value : intrinsic) {
      if (value.is_array()) {
        for (const auto& nested : value) {
          matrix.push_back(nested.get<double>());
        }
      } else {
        matrix.push_back(value.get<double>());
      }
    }
    for (const auto& value : distortion) {
      distortion_values.push_back(value.get<double>());
    }
    if (matrix.size() != 9U || distortion_values.empty()) {
      throw std::invalid_argument("invalid intrinsic or distortion");
    }
    const auto config = to_bytes(
        R"({"SmoothLevel":0,"ProjectorBrightness":0,"PatternMode":4,"Gain2D":1,"ExpTime2D":100,"FlashLightOn":false,"ParamsBatch3D":[{"ExpTime3D":20,"Gain3D":1}]})");
    ByteBuffer encoded_image(image.data.size() * 2U);
    for (std::size_t i = 0; i < image.data.size(); ++i) {
      const std::int16_t value = static_cast<std::int16_t>(image.data[i]) * 4;
      std::memcpy(encoded_image.data() + i * 2U, &value, 2U);
    }
    ByteBuffer output;
    const std::string magic = "EPICRAW2";
    output.insert(output.end(), magic.begin(), magic.end());
    for (const auto value : {
             points.width,
             points.height,
             8,
             static_cast<std::int32_t>(matrix.size() * sizeof(double)),
             static_cast<std::int32_t>(distortion_values.size() * sizeof(double)),
             static_cast<std::int32_t>(config.size()),
             static_cast<std::int32_t>(depth.size()),
             static_cast<std::int32_t>(encoded_image.size())}) {
      detail::append_i32_le(output, value);
    }
    const auto append_raw = [&output](const auto& values) {
      const auto* begin = reinterpret_cast<const std::uint8_t*>(values.data());
      output.insert(output.end(), begin, begin + values.size() * sizeof(values[0]));
    };
    append_raw(matrix);
    append_raw(distortion_values);
    output.insert(output.end(), config.begin(), config.end());
    output.insert(output.end(), depth.begin(), depth.end());
    output.insert(output.end(), encoded_image.begin(), encoded_image.end());
    return output;
  }

  JsonObject depth_meta;
  depth_meta["CameraMatrix"] = intrinsic;
  depth_meta["CameraDistortion"] = distortion;
  JsonValue texture_meta = camera_params.contains("TextureSrc")
      ? camera_params.at("TextureSrc")
      : JsonValue(depth_meta);
  RuntimePassiveBinoImage depth_image{depth, points.width, points.height, 5};
  RuntimePassiveBinoImage texture_image{
      image.data,
      image.width,
      image.height,
      image.bytes_per_channel == 1 ? 16 : 18};
  const std::vector<ByteBuffer> elements = {
      detail::make_epicraw3_element(
          3, depth_image, detail::json_value_to_bytes(depth_meta)),
      detail::make_epicraw3_element(
          2, texture_image, detail::json_value_to_bytes(texture_meta)),
  };
  ByteBuffer output;
  const std::string magic = "EPICRAW3";
  output.insert(output.end(), magic.begin(), magic.end());
  detail::append_i32_le(output, 8 + 4 + 4 + 4 * 2 + 4);
  detail::append_i32_le(output, 2);
  for (const auto& element : elements) {
    detail::append_i32_le(output, static_cast<std::int32_t>(element.size()));
  }
  detail::append_i32_le(output, 0);
  for (const auto& element : elements) {
    output.insert(output.end(), element.begin(), element.end());
  }
  return output;
}

/**
 * Runtime passive_bino 模式输入。服务端会从 EPICRAW3 中解析三张图、
 * 被动双目参数、内参和畸变，SDK metadata 只额外传 cam2Base。
 */
struct RuntimePassiveBinoFrame {
  /// 完整 EPICRAW3 原始字节。
  ByteBuffer epicraw3;
  /// 相机到基座坐标系的变换，旋转矢量形式：长度为 6 的 [x, y, z, rx, ry, rz]
  /// （平移 + Rodrigues 旋转向量）；服务端目前只支持这一种形式，不支持矩阵。
  JsonValue cam_to_base;
  /// 可选 ROI；其中 cam2ROIFrame 同样只支持长度为 6 的旋转矢量形式。
  std::optional<JsonValue> roi = std::nullopt;

  static RuntimePassiveBinoFrame from_bytes(
      ByteBuffer epicraw3_bytes,
      JsonValue cam_to_base_value,
      std::optional<JsonValue> roi_value = std::nullopt) {
    if (epicraw3_bytes.empty()) {
      throw AtomError("passive_bino frame is missing EPICRAW3 bytes");
    }
    require_cam2_base_shape(cam_to_base_value);
    validate_roi_shape(roi_value);
    return RuntimePassiveBinoFrame{
        std::move(epicraw3_bytes),
        std::move(cam_to_base_value),
        std::move(roi_value)};
  }

  static RuntimePassiveBinoFrame from_file(
      const std::filesystem::path& epicraw3_path,
      JsonValue cam_to_base_value,
      std::optional<JsonValue> roi_value = std::nullopt) {
    return from_bytes(
        detail::read_binary_file(epicraw3_path),
        std::move(cam_to_base_value),
        std::move(roi_value));
  }

  static RuntimePassiveBinoFrame from_images(
      std::vector<RuntimePassiveBinoImage> image_list,
      JsonObject params,
      JsonValue cam_to_base_value,
      std::optional<JsonValue> roi_value = std::nullopt) {
    return from_bytes(
        detail::make_passive_bino_epicraw3(image_list, params),
        std::move(cam_to_base_value),
        std::move(roi_value));
  }
};

struct RuntimeRunParams {
  std::string graph_name;
  std::vector<RuntimeFrame> frames;
  std::string run_mode = "others";
  std::optional<RuntimePassiveBinoFrame> passive_bino_frame = std::nullopt;

  static RuntimeRunParams passive_bino_from_bytes(
      std::string graph_name_value,
      ByteBuffer epicraw3_bytes,
      JsonValue cam_to_base_value,
      std::optional<JsonValue> roi_value = std::nullopt) {
    return RuntimeRunParams{
        std::move(graph_name_value),
        {},
        "passive_bino",
        RuntimePassiveBinoFrame::from_bytes(
            std::move(epicraw3_bytes),
            std::move(cam_to_base_value),
            std::move(roi_value))};
  }

  static RuntimeRunParams passive_bino_from_file(
      std::string graph_name_value,
      const std::filesystem::path& epicraw3_path,
      JsonValue cam_to_base_value,
      std::optional<JsonValue> roi_value = std::nullopt) {
    return passive_bino_from_bytes(
        std::move(graph_name_value),
        detail::read_binary_file(epicraw3_path),
        std::move(cam_to_base_value),
        std::move(roi_value));
  }

  static RuntimeRunParams passive_bino_from_images(
      std::string graph_name_value,
      std::vector<RuntimePassiveBinoImage> image_list,
      JsonObject params,
      JsonValue cam_to_base_value,
      std::optional<JsonValue> roi_value = std::nullopt) {
    return passive_bino_from_bytes(
        std::move(graph_name_value),
        detail::make_passive_bino_epicraw3(image_list, params),
        std::move(cam_to_base_value),
        std::move(roi_value));
  }

  static RuntimeRunParams passive_bino_from_image(
      std::string graph_name_value,
      std::vector<RuntimePassiveBinoImage> image_list,
      JsonObject params,
      JsonValue cam_to_base_value,
      std::optional<JsonValue> roi_value = std::nullopt) {
    return passive_bino_from_images(
        std::move(graph_name_value),
        std::move(image_list),
        std::move(params),
        std::move(cam_to_base_value),
        std::move(roi_value));
  }
};

struct RuntimeBindingDataUpdate {
  std::string graph_name;
  JsonObject binding_data;
};

/**
 * Runtime 策略参数更新。
 *
 * 当前仅适用于 PoseListFilter、PickPointFilter、PoseListSorterInXOY、
 * PickPointSorterInXOY、PickPointSorterNew、PoseListSorter。
 *
 * params_data 一般来自 RuntimeService::get_node_params_info_with_strategy
 * 返回值中的 paramsData。调用方修改需要更新的字段后，把完整 paramsData 传回。
 */
struct RuntimeStrategyParamsUpdate {
  std::string graph_name;
  std::string node_id;
  JsonObject params_data;
};

struct FileParamRef {
  std::string graph_name;
  std::string param_name;
  std::string param_type = "init_params";
};

}  // namespace atom::sdk
