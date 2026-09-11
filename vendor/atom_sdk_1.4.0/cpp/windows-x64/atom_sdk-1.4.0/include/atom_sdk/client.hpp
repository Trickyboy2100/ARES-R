#pragma once

#include "atom_sdk/core/state.hpp"
#include "atom_sdk/core/transport.hpp"
#include "atom_sdk/services/graph.hpp"
#include "atom_sdk/services/graph_node.hpp"
#include "atom_sdk/services/node.hpp"
#include "atom_sdk/services/runtime.hpp"

#include <memory>
#include <string>

namespace atom::sdk {

class AtomClient {
 public:
  explicit AtomClient(
      const std::string& base_url,
      std::shared_ptr<BaseTransport> transport = nullptr,
      RequestOptions options = {});

  GraphService& graph() noexcept { return graph_; }
  const GraphService& graph() const noexcept { return graph_; }
  GraphNodeService& graph_node() noexcept { return graph_node_; }
  const GraphNodeService& graph_node() const noexcept { return graph_node_; }
  NodeService& node() noexcept { return node_; }
  const NodeService& node() const noexcept { return node_; }
  RuntimeService& runtime() noexcept { return runtime_; }
  const RuntimeService& runtime() const noexcept { return runtime_; }
  TimestampStore& timestamps() noexcept { return *timestamps_; }
  const TimestampStore& timestamps() const noexcept { return *timestamps_; }

 private:
  std::shared_ptr<BaseTransport> transport_;
  std::shared_ptr<TimestampStore> timestamps_;
  GraphService graph_;
  GraphNodeService graph_node_;
  NodeService node_;
  RuntimeService runtime_;
};

}  // namespace atom::sdk
