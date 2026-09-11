#include "atom_sdk/client.hpp"

#include "atom_sdk/core/json.hpp"

#include <exception>
#include <iostream>
#include <string>

namespace json = atom::sdk::json;

int main(int argc, char** argv) {
  if (argc < 2) {
    std::cerr << "Usage: " << argv[0]
              << " <graph_name> [base_url]\n";
    return 1;
  }

  const std::string graph_name = argv[1];
  const std::string base_url =
      argc >= 3 ? argv[2] : "http://127.0.0.1:10026";

  try {
    atom::sdk::AtomClient client(base_url);

    const auto created = client.graph().create_graph({
        graph_name,
        "created by atom_sdk_cpp_example_graph_workflow"});
    std::cout << "Create graph:\n"
              << json::serialize(created) << "\n\n";
    std::cout << "Create request status: "
              << created.at("status").get<std::int64_t>() << "\n\n";

    const auto opened = client.graph().open_graph(graph_name);
    std::cout << "Open graph:\n"
              << json::serialize(opened) << "\n\n";

    const auto node = client.node().create_node({graph_name, "Filter"});
    const auto node_id = json::value_to<std::string>(node.at("nodeId"));
    std::cout << "Create node:\n"
              << json::serialize(node) << "\n\n";
    std::cout << "Create node request status: "
              << node.at("status").get<std::int64_t>() << "\n\n";

    const auto set_param = client.node().set_node_param_data(
        {graph_name, node_id, "threshold", "run_params", json::value(0.5)});
    std::cout << "Set node param:\n"
              << json::serialize(set_param) << "\n\n";

    const auto run_result = client.graph().run_graph(graph_name);
    std::cout << "Run graph:\n"
              << json::serialize(run_result) << "\n";
    std::cout << "Run request status: "
              << run_result.at("status").get<std::int64_t>() << "\n";
  } catch (const std::exception& ex) {
    std::cerr << "Example failed: " << ex.what() << "\n";
    return 2;
  }

  return 0;
}
