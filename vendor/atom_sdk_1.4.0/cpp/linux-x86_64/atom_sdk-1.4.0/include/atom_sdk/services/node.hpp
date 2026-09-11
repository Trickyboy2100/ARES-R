#pragma once

#include "atom_sdk/params.hpp"
#include "atom_sdk/services/base.hpp"

#include <memory>

namespace atom::sdk {

/**
 * 主图节点服务，负责节点增删、连线、设参和读取节点输出。
 */
class NodeService : public BaseService {
 public:
  NodeService(
      std::shared_ptr<BaseTransport> transport,
      std::shared_ptr<TimestampStore> timestamps);

  /// 在主图中创建一个新节点。
  JsonObject create_node(const CreateNodeParams& params) const;
  /// 在主图中创建带动态输入输出定义的节点。
  JsonObject create_dynamic_io_node(const CreateDynamicNodeParams& params) const;
  /// 按已有节点复制出一个同类型新节点。
  JsonObject create_node_by_copy(const CopyNodeParams& params) const;
  /// 修改动态节点的输入输出定义。
  JsonObject change_node_io(const ChangeNodeIOParams& params) const;
  /// 基于现有子图创建 graph node。
  JsonObject create_graph_node(const CreateGraphNodeParams& params) const;
  /// 把一组节点打包生成新的 graph node。
  JsonObject generate_graph_node_by_nodes(
      const GenerateGraphNodeByNodesParams& params) const;
  /// 删除主图中的指定节点。
  JsonObject delete_node(const NodeRef& params) const;
  /// 连接两个节点端口。
  JsonObject connect_nodes(const NodeConnectionParams& params) const;
  /// 断开两个节点端口之间的连线。
  JsonObject disconnect_nodes(const NodeConnectionParams& params) const;
  /// 读取节点参数快照。
  JsonObject get_node_params(const NodeRef& params) const;
  /// 读取节点在图中的完整信息。
  JsonObject get_node_info_in_graph(const NodeRef& params) const;
  /// 读取普通端口输出，返回 JSON 与附件。
  PortDataResult get_node_port_data(const PortRef& params) const;
  /// 读取点云端口的原始字节。
  ByteBuffer get_points_data(const PortRef& params) const;
  /// 读取点云端口并按服务端头信息解析。
  std::vector<ParsedPointCloud> get_points_data_parsed(
      const PortRef& params) const;
  /// 为端口数据生成下载链接。
  JsonObject download_data(const PortRef& params) const;
  /// 将 JSON 值写入节点参数。
  JsonObject set_node_param_data(const NodeParamUpdate& params) const;
  /// 设置节点参数或端口的绑定名。
  JsonObject set_binding_name(const NodeBindingUpdate& params) const;
  /// 修改节点备注。
  JsonObject edit_node_comment(const EditNodeCommentParams& params) const;
  /// 激活节点，通常用于执行前检查和产出。
  JsonObject activate_node(
      const NodeRef& params,
      std::optional<double> timeout_seconds = 30.0) const;
  /// 初始化节点。
  JsonObject initial_node(const NodeRef& params) const;
  /// 更新节点配置并触发重新计算。
  JsonObject update_node(const NodeRef& params) const;
};

}  // namespace atom::sdk
