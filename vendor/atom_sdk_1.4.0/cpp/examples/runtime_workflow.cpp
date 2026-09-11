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

    const auto load_result = runtime.load_graph(graph_name);
    std::cout << "Load request status: "
              << load_result.at("status").get<std::int64_t>() << "\n\n";

    const auto meta = runtime.get_meta_info(graph_name);
    std::cout << "Meta info:\n" << json::serialize(meta) << "\n\n";

    runtime.set_shared_params(
        {graph_name, json::parse(R"({"camera_id":"cam-01"})")});
    runtime.set_run_params(
        {graph_name, json::parse(R"({"threshold":0.7})")});

    const auto frame = atom::sdk::RuntimeFrame::from_bytes(
        atom::sdk::to_bytes("replace-with-real-epicraw-bytes"),
        json::parse("[0,0,0,0,0,0]"),  // 旋转矢量形式：[x, y, z, rx, ry, rz]
        std::nullopt);

    const auto run_result = runtime.run_graph({graph_name, {frame}});
    std::cout << "Run graph result:\n"
              << json::serialize(run_result) << "\n\n";
    std::cout << "Run request status: "
              << run_result.at("status").get<std::int64_t>() << "\n\n";

    const auto outputs = runtime.get_binded_outputs_info(graph_name);
    std::cout << "Output bindings:\n"
              << json::serialize(outputs) << "\n";
  } catch (const std::exception& ex) {
    std::cerr << "Example failed: " << ex.what() << "\n";
    return 2;
  }

  return 0;
}
