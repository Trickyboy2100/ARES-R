#pragma once

#include "atom_sdk/core/codecs.hpp"
#include "atom_sdk/core/errors.hpp"
#include "atom_sdk/core/models.hpp"
#include "atom_sdk/core/point_cloud.hpp"
#include "atom_sdk/core/transport.hpp"
#include "atom_sdk/params.hpp"

#include <memory>
#include <string>

namespace atom::sdk {

/**
 * 运行时服务，负责加载现成图、设置运行参数并执行。
 */
class RuntimeService {
 public:
  explicit RuntimeService(std::shared_ptr<BaseTransport> transport);

  /// 加载服务端已存在的图，供后续运行时调用使用。
  JsonObject load_graph(const std::string& graph_name) const;
  /// 列出服务端可见的全部图。
  JsonArray list_graphs() const;
  /// 读取服务端当前注册的全部节点定义。
  JsonObject get_all_nodes_info() const;
  /// 释放已加载的运行时图资源。
  JsonObject release_graph(const std::string& graph_name) const;
  /// 读取图暴露出来的 shared/runtime 参数元信息。
  JsonObject get_meta_info(const std::string& graph_name) const;
  /// 按绑定名读取单个输出值，返回原始 JSON 值。
  JsonValue get_binded_output_value(const BindingRef& params) const;
  /// 读取图当前所有输出绑定的描述信息。
  JsonObject get_binded_outputs_info(const std::string& graph_name) const;
  /// 按绑定名读取点云类输出的原始字节。
  ByteBuffer get_binded_point_cloud(const BindingRef& params) const;
  /// 按绑定名读取点云类输出并解析成结构化结果。
  std::vector<ParsedPointCloud> get_binded_point_cloud_parsed(
      const PointCloudRef& params) const;
  /// 写入多次运行可复用的共享参数。
  JsonValue set_shared_params(const RuntimeParamsUpdate& params) const;
  /// 写入本次执行使用的运行参数。
  JsonValue set_run_params(const RuntimeParamsUpdate& params) const;
  /// 使用多帧输入执行图。
  JsonObject run_graph(const RuntimeRunParams& params) const;
  /// 直接按绑定名写入图输入数据。
  JsonValue set_graph_binding_data(
      const RuntimeBindingDataUpdate& params) const;
  /// 读取支持策略参数的节点描述信息；当前仅支持 PoseListFilter、
  /// PickPointFilter、PoseListSorterInXOY、PickPointSorterInXOY、
  /// PickPointSorterNew、PoseListSorter。返回值中的 paramsData 通常作为
  /// set_params_in_strategy 的输入模板。
  JsonObject get_node_params_info_with_strategy(const NodeRef& params) const;
  /// 向支持策略参数的节点批量写入参数；支持范围同
  /// get_node_params_info_with_strategy。params.params_data 一般来自
  /// get_node_params_info_with_strategy 返回值中的 paramsData，修改后整体传回。
  JsonValue set_params_in_strategy(
      const RuntimeStrategyParamsUpdate& params) const;
  /// 查询文件型参数在服务端记录的 md5。
  JsonObject get_file_param_md5(const FileParamRef& params) const;
  /// 在不创建图的前提下直接运行单节点，返回 JSON 或二进制。
  SingleNodeResult run_single_node_no_graph(
      const SingleNodeParams& params) const;
  /// 单节点直跑，并按输出端口类型解析 outputs 中的点云和图像值。
  SingleNodeParsedResult run_single_node_no_graph_parsed(
      const SingleNodeParams& params) const;
  /// 单节点直跑，只接受 JSON 结果。
  JsonValue run_single_node_json(const SingleNodeParams& params) const;
  /// 单节点直跑，只接受二进制结果。
  ByteBuffer run_single_node_binary(const SingleNodeParams& params) const;

 private:
  std::shared_ptr<BaseTransport> transport_;

  DecodedResponse request_json(
      const std::string& method,
      const std::string& path,
      const RequestPayload& payload = {}) const;
  ByteBuffer request_raw(
      const std::string& method,
      const std::string& path,
      const RequestPayload& payload = {}) const;
  ByteBuffer build_runtime_frame_payload(
      const RuntimeRunParams& params) const;
};

}  // namespace atom::sdk
