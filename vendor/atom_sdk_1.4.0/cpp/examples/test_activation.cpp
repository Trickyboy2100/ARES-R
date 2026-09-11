#include "atom_sdk/client.hpp"

#include "atom_sdk/core/json.hpp"

#include <exception>
#include <iostream>
#include <string>

namespace json = atom::sdk::json;

namespace {

void print_result(const std::string& label, const atom::sdk::JsonObject& result) {
  std::cout << label << " succeeded";
  if (const auto* timestamp = atom::sdk::json::if_contains(result, "timestamp")) {
    std::cout << ", timestamp=" << json::serialize(*timestamp);
  }
  std::cout << '\n';
}

}  // namespace

int main(int argc, char** argv) {
  if (argc < 6) {
    std::cerr << "Usage: " << argv[0]
              << " <base_url> <graph_name> <node_id> <graph_node_id> <inner_node_id>\n";
    return 1;
  }

  const std::string base_url = argv[1];
  const std::string graph_name = argv[2];
  const std::string node_id = argv[3];
  const std::string graph_node_id = argv[4];
  const std::string inner_node_id = argv[5];

  try {
    atom::sdk::AtomClient client(base_url);

    print_result("open graph", client.graph().open_graph(graph_name));

    for (int index = 1; index <= 3; ++index) {
      print_result(
          "activate node " + std::to_string(index),
          client.node().activate_node({graph_name, node_id}));
    }

    print_result("reopen graph", client.graph().open_graph(graph_name));
    print_result(
        "open node graph",
        client.graph_node().open_graph({graph_name, graph_node_id}));

    for (int index = 1; index <= 3; ++index) {
      print_result(
          "activate graph node " + std::to_string(index),
          client.graph_node().activate_node(
              {graph_name, graph_node_id, inner_node_id}));
    }
  } catch (const std::exception& exception) {
    std::cerr << "C++ activation example failed: " << exception.what() << '\n';
    return 1;
  }

  return 0;
}
