"""NodeService 示例。

这组示例专门演示“主图里的节点”怎么操作，比如创建节点、动态改 IO、生成 graph node、
设置备注、下载端口结果等。
"""

from __future__ import annotations

from typing import Any

from atom_sdk import (
    ChangeNodeIOParams,
    CopyNodeParams,
    CreateDynamicNodeParams,
    CreateGraphNodeParams,
    CreateNodeParams,
    EditNodeCommentParams,
    GenerateGraphNodeByNodesParams,
    NodeBindingUpdate,
    NodeConnectionParams,
    NodeParamUpdate,
    NodeRef,
    PortRef,
)

from .common import (
    DEMO_BINDING_NAME,
    DEMO_GRAPH_NAME,
    DEMO_INPUT_PORT_NAME,
    DEMO_NODE_ID,
    DEMO_NODE_NAME,
    DEMO_PORT_NAME,
    DEMO_TARGET_NODE_ID,
    DEMO_TARGET_NODE_NAME,
    create_client,
)


def example_create_node(graph_name: str = DEMO_GRAPH_NAME) -> dict[str, Any]:
    """演示如何在主图中创建一个节点，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.node.create_node(CreateNodeParams(graph_name, DEMO_NODE_NAME))


def example_create_dynamic_io_node(graph_name: str = DEMO_GRAPH_NAME) -> dict[str, Any]:
    """演示如何创建带动态输入输出定义的节点，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.node.create_dynamic_io_node(
        CreateDynamicNodeParams(
            graph_name,
            "DynamicIONode",
            {
                "inputs": [{"name": "image_in", "dtype": "Image"}],
                "outputs": [{"name": "mask_out", "dtype": "BinaryImage"}],
            },
        )
    )


def example_create_node_by_copy(
    graph_name: str = DEMO_GRAPH_NAME,
    node_id: str = DEMO_NODE_ID,
) -> dict[str, Any]:
    """演示如何复制主图里一个已有节点，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.node.create_node_by_copy(CopyNodeParams(graph_name, f"{DEMO_NODE_NAME}_copy", node_id))


def example_change_node_io(
    graph_name: str = DEMO_GRAPH_NAME,
    node_id: str = DEMO_NODE_ID,
) -> dict[str, Any]:
    """演示如何修改动态节点的输入输出定义，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.node.change_node_io(
        ChangeNodeIOParams(
            graph_name,
            node_id,
            {
                "outputs": [{"name": "score_out", "dtype": "Float"}],
            },
        )
    )


def example_create_graph_node(graph_name: str = DEMO_GRAPH_NAME) -> dict[str, Any]:
    """演示如何基于已有子图创建一个 graph node，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.node.create_graph_node(
        CreateGraphNodeParams(graph_name, "WrappedSubgraph", "custom_subgraph_template")
    )


def example_generate_graph_node_by_nodes(graph_name: str = DEMO_GRAPH_NAME) -> dict[str, Any]:
    """演示如何把多个节点打包成新的 graph node，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.node.generate_graph_node_by_nodes(
        GenerateGraphNodeByNodesParams(graph_name, "GroupedSubgraph", [DEMO_NODE_ID, DEMO_TARGET_NODE_ID])
    )


def example_delete_node(
    graph_name: str = DEMO_GRAPH_NAME,
    node_id: str = DEMO_NODE_ID,
) -> dict[str, Any]:
    """演示如何删除主图中的一个节点，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.node.delete_node(NodeRef(graph_name, node_id))


def example_connect_nodes(graph_name: str = DEMO_GRAPH_NAME) -> dict[str, Any]:
    """演示如何把两个节点连起来，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.node.connect_nodes(
        NodeConnectionParams(
            graph_name=graph_name,
            output_node_id=DEMO_NODE_ID,
            output_port_name=DEMO_PORT_NAME,
            input_node_id=DEMO_TARGET_NODE_ID,
            input_port_name=DEMO_INPUT_PORT_NAME,
        )
    )


def example_disconnect_nodes(graph_name: str = DEMO_GRAPH_NAME) -> dict[str, Any]:
    """演示如何断开两个节点之间的连线，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.node.disconnect_nodes(
        NodeConnectionParams(
            graph_name=graph_name,
            output_node_id=DEMO_NODE_ID,
            output_port_name=DEMO_PORT_NAME,
            input_node_id=DEMO_TARGET_NODE_ID,
            input_port_name=DEMO_INPUT_PORT_NAME,
        )
    )


def example_get_node_params(
    graph_name: str = DEMO_GRAPH_NAME,
    node_id: str = DEMO_NODE_ID,
) -> dict[str, Any]:
    """演示如何读取节点参数，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.node.get_node_params(NodeRef(graph_name, node_id))


def example_get_node_info_in_graph(
    graph_name: str = DEMO_GRAPH_NAME,
    node_id: str = DEMO_NODE_ID,
) -> dict[str, Any]:
    """演示如何读取图中某个节点的完整信息，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.node.get_node_info_in_graph(NodeRef(graph_name, node_id))


def example_get_node_port_data(
    graph_name: str = DEMO_GRAPH_NAME,
    node_id: str = DEMO_NODE_ID,
) -> dict[str, Any]:
    """演示如何读取节点某个端口的展示数据，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.node.get_node_port_data(PortRef(graph_name, node_id, DEMO_PORT_NAME, "outputs"))


def example_get_points_data(
    graph_name: str = DEMO_GRAPH_NAME,
    node_id: str = DEMO_NODE_ID,
) -> bytes:
    """演示如何读取端口上的原始点云字节，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.node.get_points_data(PortRef(graph_name, node_id, DEMO_PORT_NAME, "outputs"))


def example_get_points_data_parsed(
    graph_name: str = DEMO_GRAPH_NAME,
    node_id: str = DEMO_NODE_ID,
) -> Any:
    """演示如何读取并解析端口上的点云数据，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.node.get_points_data_parsed(PortRef(graph_name, node_id, DEMO_PORT_NAME, "outputs"))


def example_download_data(
    graph_name: str = DEMO_GRAPH_NAME,
    node_id: str = DEMO_NODE_ID,
) -> dict[str, Any]:
    """演示如何为节点端口结果生成下载链接，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.node.download_data(PortRef(graph_name, node_id, DEMO_PORT_NAME, "outputs"))


def example_set_node_param_data(
    graph_name: str = DEMO_GRAPH_NAME,
    node_id: str = DEMO_NODE_ID,
) -> dict[str, Any]:
    """演示如何给节点设置参数，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.node.set_node_param_data(
        NodeParamUpdate(graph_name, node_id, "threshold", "run_params", 0.5)
    )


def example_set_binding_name(
    graph_name: str = DEMO_GRAPH_NAME,
    node_id: str = DEMO_NODE_ID,
) -> dict[str, Any]:
    """演示如何给节点端口设置绑定名，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.node.set_binding_name(
        NodeBindingUpdate(graph_name, node_id, "outputs", DEMO_PORT_NAME, DEMO_BINDING_NAME)
    )


def example_edit_node_comment(
    graph_name: str = DEMO_GRAPH_NAME,
    node_id: str = DEMO_NODE_ID,
) -> dict[str, Any]:
    """演示如何修改节点备注，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.node.edit_node_comment(EditNodeCommentParams(graph_name, node_id, "updated by SDK example"))


def example_activate_node(
    graph_name: str = DEMO_GRAPH_NAME,
    node_id: str = DEMO_NODE_ID,
) -> dict[str, Any]:
    """演示如何从某个节点开始激活后续流程，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.node.activate_node(NodeRef(graph_name, node_id))


def example_initial_node(
    graph_name: str = DEMO_GRAPH_NAME,
    node_id: str = DEMO_NODE_ID,
) -> dict[str, Any]:
    """演示如何单独初始化某个节点，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.node.initial_node(NodeRef(graph_name, node_id))


def example_update_node(
    graph_name: str = DEMO_GRAPH_NAME,
    node_id: str = DEMO_NODE_ID,
) -> dict[str, Any]:
    """演示如何更新单个节点，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.node.update_node(NodeRef(graph_name, node_id))
