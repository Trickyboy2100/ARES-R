#pragma once

#include "atom_sdk/params.hpp"
#include "atom_sdk/services/base.hpp"

#include <memory>
#include <string>

namespace atom::sdk {

/**
 * 主图级别服务，负责图的创建、打开、导入导出和整图运行。
 */
class GraphService : public BaseService {
 public:
  GraphService(
      std::shared_ptr<BaseTransport> transport,
      std::shared_ptr<TimestampStore> timestamps);

  /// 创建一张新图，可附带描述信息。
  JsonObject create_graph(const CreateGraphParams& params) const;
  /// 列出服务端可见的全部图。
  JsonArray list_graphs() const;
  /// 复制现有图，生成一张新图。
  JsonObject copy_graph(const CopyGraphParams& params) const;
  /// 删除指定图，并清理本地时间戳缓存。
  JsonValue delete_graph(const std::string& graph_name) const;
  /// 读取服务端当前全部节点定义。
  JsonObject get_all_nodes_info() const;
  /// 读取所有自定义子图概要信息。
  JsonArray get_all_custom_subgraphs_no_thumbnail() const;
  /// 读取图中深度学习节点模型信息。
  JsonObject get_graph_dl_nodes_model_info(const std::string& graph_name) const;
  /// 读取图中自定义节点信息。
  JsonObject get_graph_custom_nodes(const std::string& graph_name) const;
  /// 读取图或指定 graph node 的 workcell 模型信息。
  JsonObject get_graph_workcell_models_info(
      const std::string& graph_name,
      std::optional<std::string> graph_node_id = std::nullopt) const;
  /// 读取指定图暴露出来的绑定信息。
  JsonObject get_graph_bindings(const std::string& graph_name) const;
  /// 从本地图文件导入图到服务端。
  JsonObject load_graph(const LoadGraphParams& params) const;
  /// 导入 load_graph 返回的 extensionNodes 对应的扩展节点文件。
  JsonValue import_extension_nodes_by_path(
      const JsonObject& extension_nodes) const;
  /// 导出图及其附带模型/自定义节点信息。
  JsonObject export_graph(const ExportGraphParams& params) const;
  /// 打开图进入编辑态。
  JsonObject open_graph(const std::string& graph_name) const;
  /// 修改图名称。
  JsonValue edit_graph_name(const EditGraphNameParams& params) const;
  /// 释放图的编辑态资源。
  JsonValue release_graph(const std::string& graph_name) const;
  /// 运行整张主图。
  JsonObject run_graph(
      const std::string& graph_name,
      std::optional<double> timeout_seconds = 30.0) const;
  /// 清理图的运行态中间状态。
  JsonObject clear_graph(const std::string& graph_name) const;
  /// 修改图备注。
  JsonValue edit_graph_comment(const EditGraphCommentParams& params) const;
  /// 获取图的原始 JSON 结构。
  JsonObject get_graph_json_data(const std::string& graph_name) const;
  /// 读取图当前时间戳。
  JsonObject get_timestamp(const std::string& graph_name) const;
};

}  // namespace atom::sdk
