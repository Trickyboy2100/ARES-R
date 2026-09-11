#include "atom_sdk/client.hpp"

#include "atom_sdk/core/json.hpp"

#include <exception>
#include <iostream>
#include <string>

namespace json = atom::sdk::json;

int main(int argc, char** argv) {
  if (argc < 3) {
    std::cerr << "Usage: " << argv[0]
              << " <graph_name> <graph_node_id> [base_url]\n";
    return 1;
  }

  const std::string graph_name = argv[1];
  const std::string graph_node_id = argv[2];
  const std::string base_url =
      argc >= 4 ? argv[3] : "http://127.0.0.1:10026";

  try {
    atom::sdk::AtomClient client(base_url);

    const auto opened = client.graph_node().open_graph({graph_name, graph_node_id});
    std::cout << "Open subgraph:\n"
              << json::serialize(opened) << "\n\n";
    std::cout << "Open subgraph request status: "
              << opened.at("status").get<std::int64_t>() << "\n\n";

    const auto inner_node =
        client.graph_node().create_node({graph_name, graph_node_id, "Filter"});
    const auto inner_node_id =
        json::value_to<std::string>(inner_node.at("nodeId"));
    std::cout << "Create inner node:\n"
              << json::serialize(inner_node) << "\n\n";
    std::cout << "Create inner node request status: "
              << inner_node.at("status").get<std::int64_t>() << "\n\n";

    const auto set_param = client.graph_node().set_node_param_data(
        {graph_name, graph_node_id, inner_node_id, "threshold", "run_params", json::value(0.4)});
    std::cout << "Set inner node param:\n"
              << json::serialize(set_param) << "\n\n";

    const auto run_result = client.graph_node().run_graph({graph_name, graph_node_id});
    std::cout << "Run subgraph:\n"
              << json::serialize(run_result) << "\n";
    std::cout << "Run subgraph request status: "
              << run_result.at("status").get<std::int64_t>() << "\n";
  } catch (const std::exception& ex) {
    std::cerr << "Example failed: " << ex.what() << "\n";
    return 2;
  }

  return 0;
}
