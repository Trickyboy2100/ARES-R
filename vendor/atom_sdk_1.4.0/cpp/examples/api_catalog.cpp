#include "atom_sdk/client.hpp"

#include "atom_sdk/core/json.hpp"

#include <cstdlib>
#include <exception>
#include <filesystem>
#include <iostream>
#include <optional>
#include <string>
#include <vector>

namespace json = atom::sdk::json;
namespace fs = std::filesystem;

namespace {

std::string setting(const char* name, const std::string& fallback = "") {
  if (const char* value = std::getenv(name); value != nullptr && *value != '\0') {
    return value;
  }
  return fallback;
}

bool enabled(const char* name) {
  const auto value = setting(name);
  return value == "1" || value == "true" || value == "TRUE";
}

fs::path required_file(const char* name) {
  const auto value = setting(name);
  if (value.empty() || !fs::exists(value)) {
    throw std::runtime_error(
        std::string("请设置 ") + name + "，并指向真实存在的文件。当前值：" +
        (value.empty() ? "<未设置>" : value));
  }
  return value;
}

template <typename T>
void print_json(const std::string& label, const T& value) {
  std::cout << label << ":\n" << json::serialize(value) << "\n\n";
}

void print_status(const std::string& label, const json::object& object) {
  std::cout << label << "：";
  if (const auto* status = json::if_contains(object, "status")) {
    std::cout << " status=" << json::serialize(*status);
  }
  if (const auto* timestamp = json::if_contains(object, "timestamp")) {
    std::cout << " timestamp=" << json::serialize(*timestamp);
  }
  std::cout << "\n";
}

json::value identity_transform() {
  return json::parse("[0,0,0,0,0,0]");
}

json::value default_roi() {
  return json::parse(
      R"({"min":{"x":-1,"y":-1,"z":-1},"max":{"x":1,"y":1,"z":1},"cam2ROIFrame":[0,0,0,0,0,0]})");
}

atom::sdk::RuntimeFrame make_demo_frame() {
  atom::sdk::RuntimePointData points;
  points.width = 2;
  points.height = 2;
  points.channels = 3;
  points.data = {0.0F, 0.0F, 1.0F, 0.1F, 0.0F, 1.0F,
                 0.0F, 0.1F, 1.0F, 0.1F, 0.1F, 1.0F};

  atom::sdk::RuntimeImageData image;
  image.width = points.width;
  image.height = points.height;
  image.channels = 3;
  image.bytes_per_channel = 1;
  image.data = {0, 0, 0, 32, 32, 32, 64, 64, 64, 96, 96, 96};

  return atom::sdk::RuntimeFrame::from_data(
      points,
      image,
      identity_transform(),
      json::parse("[1000,0,1,0,1000,1,0,0,1]"),
      json::parse("[0,0,0,0,0]"),
      std::nullopt,
      {},
      default_roi());
}

void run_runtime(const std::string& base_url, const std::string& graph_name) {
  atom::sdk::AtomClient client(base_url);
  auto& runtime = client.runtime();
  bool loaded = false;
  const auto release = [&]() {
    if (loaded) {
      print_json("释放 Runtime 图", runtime.release_graph(graph_name));
      loaded = false;
    }
  };

  try {
    print_json("Runtime 图列表", runtime.list_graphs());
    print_json("Runtime 节点定义", runtime.get_all_nodes_info());

    const auto load_result = runtime.load_graph(graph_name);
    loaded = true;
    print_status("加载图", load_result);
    print_json("Runtime 元信息", runtime.get_meta_info(graph_name));

    runtime.set_shared_params(
        {graph_name, json::parse(R"({"camera_id":"cam-01"})")});
    runtime.set_run_params(
        {graph_name, json::parse(R"({"threshold":0.5})")});

    const auto epicraw_path = setting("ATOM_EPICRAW_FILE");
    const auto frame = epicraw_path.empty()
        ? make_demo_frame()
        : atom::sdk::RuntimeFrame::from_file(
              required_file("ATOM_EPICRAW_FILE"), identity_transform(), default_roi());
    const auto run_result = runtime.run_graph({graph_name, {frame}});
    print_status("执行普通 Runtime 图", run_result);
    print_json("输出绑定说明", runtime.get_binded_outputs_info(graph_name));

    if (!setting("ATOM_BINDING_NAME").empty()) {
      const atom::sdk::BindingRef binding{graph_name, setting("ATOM_BINDING_NAME")};
      print_json("绑定值", runtime.get_binded_output_value(binding));
    }
    if (!setting("ATOM_POINT_CLOUD_BINDING_NAME").empty()) {
      const atom::sdk::BindingRef binding{graph_name, setting("ATOM_POINT_CLOUD_BINDING_NAME")};
      std::cout << "绑定点云原始字节长度："
                << runtime.get_binded_point_cloud(binding).size() << "\n";
      std::cout << "绑定点云解析数量："
                << runtime.get_binded_point_cloud_parsed(
                       {graph_name, binding.binding_name, 3})
                       .size()
                << "\n";
    }

    if (enabled("ATOM_SET_BINDING_DATA")) {
      runtime.set_graph_binding_data(
          {graph_name,
           json::parse(R"({"input_image":"data:image/jpg;base64,xxx","score_threshold":0.5})")
               });
    }

    if (!setting("ATOM_NODE_ID").empty()) {
      const atom::sdk::NodeRef node{graph_name, setting("ATOM_NODE_ID")};
      const auto strategy = runtime.get_node_params_info_with_strategy(node);
      print_json("策略参数信息", strategy);
      if (json::if_contains(strategy, "paramsData") != nullptr &&
          strategy.at("paramsData").is_object()) {
        runtime.set_params_in_strategy(
            {graph_name, setting("ATOM_NODE_ID"), strategy.at("paramsData")});
      }
    }

    if (!setting("ATOM_FILE_PARAM_NAME").empty()) {
      print_json(
          "文件参数 MD5",
          runtime.get_file_param_md5(
              {graph_name, setting("ATOM_FILE_PARAM_NAME"), setting("ATOM_FILE_PARAM_TYPE", "init_params")}));
    }

    if (!setting("ATOM_EPICRAW3_FILE").empty()) {
      const auto epicraw3 = required_file("ATOM_EPICRAW3_FILE");
      const auto passive = atom::sdk::RuntimeRunParams::passive_bino_from_file(
          graph_name, epicraw3, identity_transform(), default_roi());
      print_status("执行 passive_bino 图", runtime.run_graph(passive));
    }
  } catch (...) {
    release();
    throw;
  }
  release();
}

void run_graph_api(const std::string& base_url, std::string graph_name) {
  atom::sdk::AtomClient client(base_url);
  auto& graph = client.graph();

  print_json("编辑态图列表", graph.list_graphs());
  print_json("可用节点定义", graph.get_all_nodes_info());
  print_json("自定义子图列表", graph.get_all_custom_subgraphs_no_thumbnail());

  const auto created = graph.create_graph({graph_name, "created by C++ API catalog"});
  print_status("创建图", created);
  print_status("打开图", graph.open_graph(graph_name));
  print_json("图绑定", graph.get_graph_bindings(graph_name));
  print_json("DL 模型依赖", graph.get_graph_dl_nodes_model_info(graph_name));
  print_json("自定义节点依赖", graph.get_graph_custom_nodes(graph_name));
  print_json("Workcell 模型依赖", graph.get_graph_workcell_models_info(graph_name));
  print_json("图 JSON", graph.get_graph_json_data(graph_name));
  print_json("图时间戳", graph.get_timestamp(graph_name));

  if (enabled("ATOM_RENAME_EXAMPLE_GRAPH")) {
    const auto renamed = graph_name + "_renamed";
    print_json("修改图名", graph.edit_graph_name({graph_name, renamed}));
    graph_name = renamed;
  }

  const auto copied_name = graph_name + "_copy";
  print_json("复制图", graph.copy_graph({graph_name, copied_name}));
  print_json("删除复制图", graph.delete_graph(copied_name));

  if (!setting("ATOM_GRAPH_FILE").empty()) {
    const auto imported = setting("ATOM_IMPORTED_GRAPH_NAME", graph_name + "_imported");
    print_json("导入 .atom 图", graph.load_graph({imported, required_file("ATOM_GRAPH_FILE")}));
  }

  if (enabled("ATOM_EXPORT_EXAMPLE_GRAPH")) {
    print_json(
        "导出图",
        graph.export_graph({
            graph_name,
            json::parse(R"({"detector":{"version":"1.0.0"}})"),
            json::parse(R"({"SdkTestEchoNode":{"enableExport":true}})")}));
  }

  if (enabled("ATOM_IMPORT_EXTENSION_NODES")) {
    const auto path = setting("ATOM_CUSTOM_NODE_FILE", "/tmp/demo_node.py");
    json::object extension_nodes;
    extension_nodes[path] = json::parse(
        R"({"forceCover":false,"newNodes":["DemoNode"],"existedNodes":[]})");
    print_json(
        "导入扩展节点",
        graph.import_extension_nodes_by_path(extension_nodes));
  }

  print_status("运行编辑态图", graph.run_graph(graph_name));
  print_json("清理图运行状态", graph.clear_graph(graph_name));
  print_json("释放编辑态图", graph.release_graph(graph_name));

  if (enabled("ATOM_DELETE_EXAMPLE_GRAPH")) {
    print_json("删除示例图", graph.delete_graph(graph_name));
  }
}

void run_node_api(const std::string& base_url, const std::string& graph_name) {
  const auto node_id = setting("ATOM_NODE_ID");
  if (node_id.empty()) {
    throw std::runtime_error("node 示例需要设置 ATOM_NODE_ID。");
  }

  atom::sdk::AtomClient client(base_url);
  const atom::sdk::NodeRef node{graph_name, node_id};
  const auto dynamic = client.node().create_dynamic_io_node({
      graph_name,
      setting("ATOM_DYNAMIC_NODE_NAME", "DynamicIONode"),
      json::parse(R"({"inputs":[{"name":"image_in","dtype":"Image"}],"outputs":[{"name":"mask_out","dtype":"BinaryImage"}]})")
          });
  print_json("动态节点", dynamic);

  const auto copied = client.node().create_node_by_copy({
      graph_name, setting("ATOM_COPY_NODE_NAME", "CopiedNode"), node_id});
  print_json("复制节点", copied);
  const auto copied_id = copied.at("nodeId").get<std::string>();

  const atom::sdk::ChangeNodeIOParams change_io{
      graph_name,
      json::value_to<std::string>(dynamic.at("nodeId")),
      json::parse(R"({"outputs":[{"name":"score_out","dtype":"Float"}]})")};
  print_json("修改动态 IO", client.node().change_node_io(change_io));

  print_json("节点参数", client.node().get_node_params(node));
  print_json("节点详情", client.node().get_node_info_in_graph(node));
  print_json("设置节点参数", client.node().set_node_param_data(
      {graph_name, node_id, "threshold", "run_params", json::value(0.5)}));
  print_json("设置绑定名", client.node().set_binding_name(
      {graph_name, node_id, "outputs", setting("ATOM_PORT_NAME", "output"), setting("ATOM_BINDING_NAME", "demo_binding")}));
  print_json("修改节点备注", client.node().edit_node_comment(
      {graph_name, node_id, "updated by C++ API catalog"}));

  if (enabled("ATOM_READ_PORT_DATA")) {
    const atom::sdk::PortRef port{graph_name, node_id, setting("ATOM_PORT_NAME", "output"), "outputs"};
    print_json("端口数据", client.node().get_node_port_data(port).data);
    std::cout << "原始点云字节长度：" << client.node().get_points_data(port).size() << "\n";
    std::cout << "解析点云数量：" << client.node().get_points_data_parsed(port).size() << "\n";
    print_json("端口下载信息", client.node().download_data(port));
  }

  const auto target_id = setting("ATOM_TARGET_NODE_ID");
  if (!target_id.empty()) {
    const atom::sdk::NodeConnectionParams connection{
        graph_name, node_id, setting("ATOM_PORT_NAME", "output"), target_id,
        setting("ATOM_INPUT_PORT_NAME", "input")};
    print_json("连接节点", client.node().connect_nodes(connection));
    print_json("断开节点", client.node().disconnect_nodes(connection));
  }

  print_status("初始化节点", client.node().initial_node(node));
  print_status("激活节点", client.node().activate_node(node));
  print_status("更新节点", client.node().update_node(node));

  if (!setting("ATOM_SUB_GRAPH_NAME").empty()) {
    print_json("创建 Graph Node", client.node().create_graph_node(
        {graph_name, "CreatedGraphNode", setting("ATOM_SUB_GRAPH_NAME")}));
  }
  if (!setting("ATOM_GENERATE_NODE_IDS").empty()) {
    print_json("按节点生成 Graph Node", client.node().generate_graph_node_by_nodes(
        {graph_name, "GeneratedGraphNode", {node_id, setting("ATOM_GENERATE_NODE_IDS")}}));
  }

  print_json("删除复制节点", client.node().delete_node({graph_name, std::string(copied_id)}));
  print_json("删除动态节点", client.node().delete_node(
      {graph_name, std::string(dynamic.at("nodeId").get<std::string>())}));
}

void run_graph_node_api(const std::string& base_url, const std::string& graph_name) {
  const auto graph_node_id = setting("ATOM_GRAPH_NODE_ID");
  if (graph_node_id.empty()) {
    throw std::runtime_error("graph-node 示例需要设置 ATOM_GRAPH_NODE_ID。");
  }

  atom::sdk::AtomClient client(base_url);
  const atom::sdk::SubGraphRef subgraph{graph_name, graph_node_id};
  print_status("打开子图", client.graph_node().open_graph(subgraph));
  print_json("子图节点定义", client.graph_node().get_all_nodes_info());
  print_json("子图绑定", client.graph_node().get_graph_bindings(subgraph));
  print_json("子图 DL 模型依赖", client.graph_node().get_graph_dl_nodes_model_info(subgraph));
  print_json("子图自定义节点依赖", client.graph_node().get_graph_custom_nodes(subgraph));

  const auto inner = client.graph_node().create_node({
      graph_name, graph_node_id, setting("ATOM_NODE_NAME", "Filter")});
  const auto inner_id = inner.at("nodeId").get<std::string>();
  const auto inner_ref = atom::sdk::SubGraphNodeRef{graph_name, graph_node_id, std::string(inner_id)};
  print_json("创建子图内部节点", inner);
  const auto copied = client.graph_node().create_node_by_copy(
      {graph_name, graph_node_id, "CopiedInnerNode", std::string(inner_id)});
  const auto copied_id = json::value_to<std::string>(copied.at("nodeId"));
  print_json("复制子图内部节点", copied);
  const auto dynamic_node = client.graph_node().create_dynamic_io_node({
      graph_name, graph_node_id, "DynamicInnerNode",
      json::parse(R"({"inputs":[{"name":"prompt","dtype":"String"}],"outputs":[{"name":"mask_out","dtype":"BinaryImage"}]})")
          });
  const auto dynamic_id = json::value_to<std::string>(dynamic_node.at("nodeId"));
  print_json("创建动态内部节点", dynamic_node);
  print_json("内部节点参数", client.graph_node().get_node_params(inner_ref));
  print_json("内部节点详情", client.graph_node().get_node_info_in_graph(inner_ref));
  const atom::sdk::ChangeSubGraphNodeIOParams change_inner_io{
      graph_name, graph_node_id, std::string(inner_id),
      json::parse(R"({"outputs":[{"name":"score_out","dtype":"Float"}]})")};
  print_json("修改内部节点 IO", client.graph_node().change_node_io(change_inner_io));
  print_json("设置内部节点参数", client.graph_node().set_node_param_data(
      {graph_name, graph_node_id, std::string(inner_id), "threshold", "run_params", json::value(0.4)}));
  print_json("设置内部绑定名", client.graph_node().set_binding_name({
      graph_name, graph_node_id, std::string(inner_id), "outputs",
      setting("ATOM_PORT_NAME", "output"), setting("ATOM_BINDING_NAME", "demo_binding")}));
  print_json("修改内部节点备注", client.graph_node().edit_node_comment({
      graph_name, graph_node_id, std::string(inner_id), "updated by C++ API catalog"}));

  if (enabled("ATOM_READ_PORT_DATA")) {
    const atom::sdk::SubGraphPortRef port{
        graph_name, graph_node_id, std::string(inner_id), setting("ATOM_PORT_NAME", "output"), "outputs"};
    print_json("内部端口数据", client.graph_node().get_node_port_data(port).data);
    std::cout << "内部原始点云字节长度："
              << client.graph_node().get_points_data(port).size() << "\n";
    std::cout << "内部解析点云数量："
              << client.graph_node().get_points_data_parsed(port).size() << "\n";
    print_json("内部端口下载信息", client.graph_node().download_data(port));
  }

  print_status("初始化内部节点", client.graph_node().initial_node(inner_ref));
  print_status("激活内部节点", client.graph_node().activate_node(inner_ref));
  print_status("更新内部节点", client.graph_node().update_node(inner_ref));
  print_status("运行子图", client.graph_node().run_graph(subgraph));

  if (enabled("ATOM_EXPORT_EXAMPLE_GRAPH")) {
    print_json("导出子图", client.graph_node().export_graph({
        graph_name, graph_node_id,
        json::parse(R"({"detector":{"version":"1.0.0"}})"),
        json::parse(R"({"SdkTestEchoNode":{"enableExport":true}})")}));
  }
  if (enabled("ATOM_SAVE_CUSTOM_SUBGRAPH")) {
    print_json("保存自定义子图", client.graph_node().set_subgraph_as_custom_subgraph(
        {graph_name, graph_node_id, "custom_subgraph_template"}));
  }

  print_json("清理子图", client.graph_node().clear_graph(subgraph));
  print_json("删除示例内部节点", client.graph_node().delete_node(inner_ref));
  print_json("删除复制内部节点", client.graph_node().delete_node(
      {graph_name, graph_node_id, copied_id}));
  print_json("删除动态内部节点", client.graph_node().delete_node(
      {graph_name, graph_node_id, dynamic_id}));
  print_json("释放子图", client.graph_node().release_graph(subgraph));
}

void run_single_node(const std::string& base_url) {
  const auto node_name = setting("ATOM_SINGLE_NODE_NAME", "DemoNode");
  atom::sdk::AtomClient client(base_url);
  atom::sdk::SingleNodeParams params;
  params.node_name = node_name;
  params.inputs[setting("ATOM_SINGLE_NODE_INPUT_NAME", "value")] = json::value(123);
  params.run_params["threshold"] = 0.5;
  params.init_params["model"] = "demo";
  params.output_data_types[setting("ATOM_OUTPUT_NAME", "preview")] = "ColorImage";

  const auto mode = setting("ATOM_SINGLE_NODE_MODE", "parsed");
  if (mode == "raw") {
    const auto result = client.runtime().run_single_node_no_graph(params);
    if (std::holds_alternative<json::value>(result)) {
      print_json("单节点原始 JSON", std::get<json::value>(result));
    } else {
      std::cout << "单节点原始二进制长度：" << std::get<atom::sdk::ByteBuffer>(result).size() << "\n";
    }
  } else if (mode == "json") {
    print_json("单节点 JSON", client.runtime().run_single_node_json(params));
  } else if (mode == "binary") {
    std::cout << "单节点二进制长度："
              << client.runtime().run_single_node_binary(params).size() << "\n";
  } else if (mode == "parsed") {
    const auto result = client.runtime().run_single_node_no_graph_parsed(params);
    std::cout << "单节点解析输出数量：" << result.outputs.size() << "\n";
  } else {
    throw std::runtime_error("ATOM_SINGLE_NODE_MODE 只能是 raw、json、binary 或 parsed。");
  }
}

void run_activation(const std::string& base_url, const std::string& graph_name) {
  const auto node_id = setting("ATOM_NODE_ID");
  const auto graph_node_id = setting("ATOM_GRAPH_NODE_ID");
  const auto inner_node_id = setting("ATOM_INNER_NODE_ID");
  if (node_id.empty() || graph_node_id.empty() || inner_node_id.empty()) {
    throw std::runtime_error("activation 示例需要设置 ATOM_NODE_ID、ATOM_GRAPH_NODE_ID、ATOM_INNER_NODE_ID。");
  }

  atom::sdk::AtomClient client(base_url);
  print_status("打开主图", client.graph().open_graph(graph_name));
  const atom::sdk::NodeRef node{graph_name, node_id};
  print_status("初始化主图节点", client.node().initial_node(node));
  print_status("激活主图节点", client.node().activate_node(node));
  print_status("更新主图节点", client.node().update_node(node));

  const atom::sdk::SubGraphRef subgraph{graph_name, graph_node_id};
  print_status("打开子图", client.graph_node().open_graph(subgraph));
  const atom::sdk::SubGraphNodeRef inner{graph_name, graph_node_id, inner_node_id};
  print_status("初始化内部节点", client.graph_node().initial_node(inner));
  print_status("激活内部节点", client.graph_node().activate_node(inner));
  print_status("更新内部节点", client.graph_node().update_node(inner));
  client.graph_node().release_graph(subgraph);
  client.graph().release_graph(graph_name);
}

void usage(const char* program) {
  std::cerr << "用法：" << program << " <runtime|graph|node|graph-node|single-node|activation> [base_url] [graph_name]\n";
  std::cerr << "默认服务地址读取 ATOM_BASE_URL，默认图名读取 ATOM_GRAPH_NAME。\n";
}

}  // namespace

int main(int argc, char** argv) {
  if (argc < 2) {
    usage(argv[0]);
    return 1;
  }

  const std::string mode = argv[1];
  const std::string base_url = argc >= 3 ? argv[2] : setting("ATOM_BASE_URL", "http://127.0.0.1:10026");
  const std::string graph_name = argc >= 4 ? argv[3] : setting("ATOM_GRAPH_NAME", "demo_graph");

  try {
    if (mode == "runtime") {
      run_runtime(base_url, graph_name);
    } else if (mode == "graph") {
      run_graph_api(base_url, graph_name);
    } else if (mode == "node") {
      run_node_api(base_url, graph_name);
    } else if (mode == "graph-node") {
      run_graph_node_api(base_url, graph_name);
    } else if (mode == "single-node") {
      run_single_node(base_url);
    } else if (mode == "activation") {
      run_activation(base_url, graph_name);
    } else {
      usage(argv[0]);
      return 1;
    }
  } catch (const std::exception& exception) {
    std::cerr << "C++ API 示例失败：" << exception.what() << "\n";
    return 2;
  }
  return 0;
}
