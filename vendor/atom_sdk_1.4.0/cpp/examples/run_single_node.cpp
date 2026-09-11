#include "atom_sdk/client.hpp"

#include "atom_sdk/core/json.hpp"

#include <cstdint>
#include <exception>
#include <iostream>
#include <string>
#include <variant>

namespace json = atom::sdk::json;

int main(int argc, char** argv) {
  if (argc < 2) {
    std::cerr << "Usage: " << argv[0]
              << " <node_name> [base_url]\n";
    return 1;
  }

  const std::string node_name = argv[1];
  const std::string base_url =
      argc >= 3 ? argv[2] : "http://127.0.0.1:10026";

  try {
    atom::sdk::AtomClient client(base_url);

    atom::sdk::SingleNodeInputs inputs;
    inputs["value"] = atom::sdk::JsonValue(123);
    inputs["name"] = atom::sdk::JsonValue("demo");

    const auto result = client.runtime().run_single_node_json({
        node_name,
        inputs,
        json::parse(R"({"threshold":0.5})"),
        json::parse(R"({"model":"demo"})")});
    std::cout << "JSON result:\n"
              << json::serialize(result) << "\n";
    std::cout << "Request status: "
              << result.at("status").get<std::int64_t>() << "\n";
  } catch (const std::exception& ex) {
    std::cerr << "Example failed: " << ex.what() << "\n";
    return 2;
  }

  return 0;
}
