#pragma once

#include "atom_sdk/params.hpp"
#include "atom_sdk/services/base.hpp"

#include <memory>

namespace atom::sdk {

/**
 * 子图节点服务，负责 graph node 内部子图的节点编辑与运行。
 */
class GraphNodeService : public BaseService {
 public:
  GraphNodeService(
      std::shared_ptr<BaseTransport> transport,
      std::shared_ptr<TimestampStore> timestamps);

  /// 打开某个 graph node 内部的子图。
  JsonObject open_graph(const SubGraphRef& params) const;
  /// 在子图内部创建节点。
  JsonObject create_node(const SubGraphCreateNodeParams& params) const;
  /// 在子图内部创建带动态输入输出定义的节点。
  JsonObject create_dynamic_io_node(
      const CreateDynamicSubGraphNodeParams& params) const;
  /// 在子图内部按已有节点复制出一个新节点。
  JsonObject create_node_by_copy(const SubGraphCopyNodeParams& params) const;
  /// 修改子图内动态节点的输入输出定义。
  JsonObject change_node_io(const ChangeSubGraphNodeIOParams& params) const;
  /// 删除子图内部节点。
  JsonObject delete_node(const SubGraphNodeRef& params) const;
  /// 连接子图内部两个节点端口。
  JsonObject connect_nodes(const SubGraphConnectionParams& params) const;
  /// 断开子图内部两个节点端口的连线。
  JsonObject disconnect_nodes(const SubGraphConnectionParams& params) const;
  /// 读取子图内部节点参数快照。
  JsonObject get_node_params(const SubGraphNodeRef& params) const;
  /// 读取子图内部节点详情。
  JsonObject get_node_info_in_graph(const SubGraphNodeRef& params) const;
  /// 读取子图内部普通端口输出。
  PortDataResult get_node_port_data(const SubGraphPortRef& params) const;
  /// 读取子图内部点云端口的原始字节。
  ByteBuffer get_points_data(const SubGraphPortRef& params) const;
  /// 读取子图内部点云端口并按服务端头信息解析。
  std::vector<ParsedPointCloud> get_points_data_parsed(
      const SubGraphPortRef& params) const;
  /// 为子图端口数据生成下载链接。
  JsonObject download_data(const SubGraphPortRef& params) const;
  /// 将 JSON 值写入子图内部节点参数。
  JsonObject set_node_param_data(
      const SubGraphNodeParamUpdate& params) const;
  /// 设置子图内部节点参数或端口的绑定名。
  JsonObject set_binding_name(const SubGraphBindingUpdate& params) const;
  /// 修改子图内部节点备注。
  JsonObject edit_node_comment(
      const EditSubGraphNodeCommentParams& params) const;
  /// 读取子图当前绑定信息。
  JsonObject get_graph_bindings(const SubGraphRef& params) const;
  /// 修改子图名称。
  JsonValue edit_graph_name(const EditSubGraphNameParams& params) const;
  /// 读取子图中的深度学习节点模型信息。
  JsonObject get_graph_dl_nodes_model_info(const SubGraphRef& params) const;
  /// 读取子图中的自定义节点信息。
  JsonObject get_graph_custom_nodes(const SubGraphRef& params) const;
  /// 导出子图及附带模型、自定义节点信息。
  JsonObject export_graph(const ExportSubGraphParams& params) const;
  /// 释放子图编辑态资源。
  JsonValue release_graph(const SubGraphRef& params) const;
  /// 清理子图运行态中间状态。
  JsonObject clear_graph(const SubGraphRef& params) const;
  /// 读取子图编辑场景下可用的全部节点定义。
  JsonObject get_all_nodes_info() const;
  /// 将当前子图保存为自定义子图模板。
  JsonObject set_subgraph_as_custom_subgraph(
      const SetSubgraphAsCustomSubgraphParams& params) const;
  /// 激活子图内部节点。
  JsonObject activate_node(
      const SubGraphNodeRef& params,
      std::optional<double> timeout_seconds = 30.0) const;
  /// 初始化子图内部节点。
  JsonObject initial_node(const SubGraphNodeRef& params) const;
  /// 更新子图内部节点配置并触发重新计算。
  JsonObject update_node(const SubGraphNodeRef& params) const;
  /// 运行 graph node 内部的子图。
  JsonObject run_graph(
      const SubGraphRef& params,
      std::optional<double> timeout_seconds = 30.0) const;
};

}  // namespace atom::sdk
