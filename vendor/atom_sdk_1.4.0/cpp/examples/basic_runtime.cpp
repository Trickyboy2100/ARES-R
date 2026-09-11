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
    auto& runtime = client.runtime();

    const auto graphs = runtime.list_graphs();
    std::cout << "All graphs:\n" << json::serialize(graphs) << "\n\n";

    const auto load_result = runtime.load_graph(graph_name);
    std::cout << "Load graph result:\n"
              << json::serialize(load_result) << "\n\n";
    std::cout << "Load request status: "
              << load_result.at("status").get<std::int64_t>() << "\n\n";

    const auto meta = runtime.get_meta_info(graph_name);
    std::cout << "Meta info:\n" << json::serialize(meta) << "\n";
    std::cout << "Meta request status: "
              << meta.at("status").get<std::int64_t>() << "\n";
  } catch (const std::exception& ex) {
    std::cerr << "Example failed: " << ex.what() << "\n";
    return 2;
  }

  return 0;
}
