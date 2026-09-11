"""GraphNodeService 示例。

这组示例演示“子图里的节点”怎么操作，包括动态 IO、子图导出、绑定、备注和模板化等。
适合某个节点本身还是一张子图，你需要继续深入到里面编辑时参考。
"""

from __future__ import annotations

from typing import Any

from atom_sdk import (
    ChangeSubGraphNodeIOParams,
    CreateDynamicSubGraphNodeParams,
    EditSubGraphNameParams,
    EditSubGraphNodeCommentParams,
    ExportSubGraphParams,
    SetSubgraphAsCustomSubgraphParams,
    SubGraphBindingUpdate,
    SubGraphConnectionParams,
    SubGraphCopyNodeParams,
    SubGraphCreateNodeParams,
    SubGraphNodeParamUpdate,
    SubGraphNodeRef,
    SubGraphPortRef,
    SubGraphRef,
)

from .common import (
    DEMO_BINDING_NAME,
    DEMO_GRAPH_NAME,
    DEMO_GRAPH_NODE_ID,
    DEMO_INPUT_PORT_NAME,
    DEMO_NODE_ID,
    DEMO_NODE_NAME,
    DEMO_PORT_NAME,
    DEMO_TARGET_NODE_ID,
    create_client,
)


def example_open_graph(
    graph_name: str = DEMO_GRAPH_NAME,
    graph_node_id: str = DEMO_GRAPH_NODE_ID,
) -> dict[str, Any]:
    """演示如何打开某个 graph node 的子图，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph_node.open_graph(SubGraphRef(graph_name, graph_node_id))


def example_create_node(
    graph_name: str = DEMO_GRAPH_NAME,
    graph_node_id: str = DEMO_GRAPH_NODE_ID,
) -> dict[str, Any]:
    """演示如何在子图里创建节点，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph_node.create_node(SubGraphCreateNodeParams(graph_name, graph_node_id, DEMO_NODE_NAME))


def example_create_dynamic_io_node(
    graph_name: str = DEMO_GRAPH_NAME,
    graph_node_id: str = DEMO_GRAPH_NODE_ID,
) -> dict[str, Any]:
    """演示如何在子图里创建带动态输入输出定义的节点，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph_node.create_dynamic_io_node(
        CreateDynamicSubGraphNodeParams(
            graph_name,
            graph_node_id,
            "DynamicIONode",
            {
                "inputs": [{"name": "prompt", "dtype": "String"}],
                "outputs": [{"name": "mask_out", "dtype": "BinaryImage"}],
            },
        )
    )


def example_create_node_by_copy(
    graph_name: str = DEMO_GRAPH_NAME,
    graph_node_id: str = DEMO_GRAPH_NODE_ID,
    node_id: str = DEMO_NODE_ID,
) -> dict[str, Any]:
    """演示如何复制子图里的节点，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph_node.create_node_by_copy(
        SubGraphCopyNodeParams(graph_name, graph_node_id, f"{DEMO_NODE_NAME}_copy", node_id)
    )


def example_change_node_io(
    graph_name: str = DEMO_GRAPH_NAME,
    graph_node_id: str = DEMO_GRAPH_NODE_ID,
    node_id: str = DEMO_NODE_ID,
) -> dict[str, Any]:
    """演示如何修改子图中动态节点的输入输出定义，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph_node.change_node_io(
        ChangeSubGraphNodeIOParams(
            graph_name,
            graph_node_id,
            node_id,
            {"outputs": [{"name": "score_out", "dtype": "Float"}]},
        )
    )


def example_delete_node(
    graph_name: str = DEMO_GRAPH_NAME,
    graph_node_id: str = DEMO_GRAPH_NODE_ID,
    node_id: str = DEMO_NODE_ID,
) -> dict[str, Any]:
    """演示如何删除子图中的节点，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph_node.delete_node(SubGraphNodeRef(graph_name, graph_node_id, node_id))


def example_connect_nodes(
    graph_name: str = DEMO_GRAPH_NAME,
    graph_node_id: str = DEMO_GRAPH_NODE_ID,
) -> dict[str, Any]:
    """演示如何连接子图中的两个节点，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph_node.connect_nodes(
        SubGraphConnectionParams(
            graph_name=graph_name,
            graph_node_id=graph_node_id,
            output_node_id=DEMO_NODE_ID,
            output_port_name=DEMO_PORT_NAME,
            input_node_id=DEMO_TARGET_NODE_ID,
            input_port_name=DEMO_INPUT_PORT_NAME,
        )
    )


def example_disconnect_nodes(
    graph_name: str = DEMO_GRAPH_NAME,
    graph_node_id: str = DEMO_GRAPH_NODE_ID,
) -> dict[str, Any]:
    """演示如何断开子图中的连线，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph_node.disconnect_nodes(
        SubGraphConnectionParams(
            graph_name=graph_name,
            graph_node_id=graph_node_id,
            output_node_id=DEMO_NODE_ID,
            output_port_name=DEMO_PORT_NAME,
            input_node_id=DEMO_TARGET_NODE_ID,
            input_port_name=DEMO_INPUT_PORT_NAME,
        )
    )


def example_get_node_params(
    graph_name: str = DEMO_GRAPH_NAME,
    graph_node_id: str = DEMO_GRAPH_NODE_ID,
    node_id: str = DEMO_NODE_ID,
) -> dict[str, Any]:
    """演示如何读取子图节点参数，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph_node.get_node_params(SubGraphNodeRef(graph_name, graph_node_id, node_id))


def example_get_node_info_in_graph(
    graph_name: str = DEMO_GRAPH_NAME,
    graph_node_id: str = DEMO_GRAPH_NODE_ID,
    node_id: str = DEMO_NODE_ID,
) -> dict[str, Any]:
    """演示如何读取子图节点完整信息，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph_node.get_node_info_in_graph(SubGraphNodeRef(graph_name, graph_node_id, node_id))


def example_get_node_port_data(
    graph_name: str = DEMO_GRAPH_NAME,
    graph_node_id: str = DEMO_GRAPH_NODE_ID,
    node_id: str = DEMO_NODE_ID,
) -> dict[str, Any]:
    """演示如何读取子图节点端口数据，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph_node.get_node_port_data(
        SubGraphPortRef(graph_name, graph_node_id, node_id, DEMO_PORT_NAME, "outputs")
    )


def example_get_points_data(
    graph_name: str = DEMO_GRAPH_NAME,
    graph_node_id: str = DEMO_GRAPH_NODE_ID,
    node_id: str = DEMO_NODE_ID,
) -> bytes:
    """演示如何读取子图节点的原始点云字节，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph_node.get_points_data(
        SubGraphPortRef(graph_name, graph_node_id, node_id, DEMO_PORT_NAME, "outputs")
    )


def example_get_points_data_parsed(
    graph_name: str = DEMO_GRAPH_NAME,
    graph_node_id: str = DEMO_GRAPH_NODE_ID,
    node_id: str = DEMO_NODE_ID,
) -> Any:
    """演示如何读取并解析子图节点的点云数据，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph_node.get_points_data_parsed(
        SubGraphPortRef(graph_name, graph_node_id, node_id, DEMO_PORT_NAME, "outputs")
    )


def example_download_data(
    graph_name: str = DEMO_GRAPH_NAME,
    graph_node_id: str = DEMO_GRAPH_NODE_ID,
    node_id: str = DEMO_NODE_ID,
) -> dict[str, Any]:
    """演示如何为子图节点结果生成下载链接，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph_node.download_data(
        SubGraphPortRef(graph_name, graph_node_id, node_id, DEMO_PORT_NAME, "outputs")
    )


def example_set_node_param_data(
    graph_name: str = DEMO_GRAPH_NAME,
    graph_node_id: str = DEMO_GRAPH_NODE_ID,
    node_id: str = DEMO_NODE_ID,
) -> dict[str, Any]:
    """演示如何给子图节点设置参数，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph_node.set_node_param_data(
        SubGraphNodeParamUpdate(graph_name, graph_node_id, node_id, "threshold", "run_params", 0.5)
    )


def example_set_binding_name(
    graph_name: str = DEMO_GRAPH_NAME,
    graph_node_id: str = DEMO_GRAPH_NODE_ID,
    node_id: str = DEMO_NODE_ID,
) -> dict[str, Any]:
    """演示如何给子图节点设置绑定名，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph_node.set_binding_name(
        SubGraphBindingUpdate(graph_name, graph_node_id, node_id, "outputs", DEMO_PORT_NAME, DEMO_BINDING_NAME)
    )


def example_edit_node_comment(
    graph_name: str = DEMO_GRAPH_NAME,
    graph_node_id: str = DEMO_GRAPH_NODE_ID,
    node_id: str = DEMO_NODE_ID,
) -> dict[str, Any]:
    """演示如何修改子图节点备注，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph_node.edit_node_comment(
        EditSubGraphNodeCommentParams(graph_name, graph_node_id, node_id, "updated by SDK example")
    )


def example_get_graph_bindings(
    graph_name: str = DEMO_GRAPH_NAME,
    graph_node_id: str = DEMO_GRAPH_NODE_ID,
) -> dict[str, Any]:
    """演示如何读取子图当前绑定情况，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph_node.get_graph_bindings(SubGraphRef(graph_name, graph_node_id))


def example_edit_graph_name(
    graph_name: str = DEMO_GRAPH_NAME,
    graph_node_id: str = DEMO_GRAPH_NODE_ID,
) -> Any:
    """演示如何修改子图名称，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph_node.edit_graph_name(
        EditSubGraphNameParams(graph_name, graph_node_id, "subgraph_v2")
    )


def example_get_graph_dl_nodes_model_info(
    graph_name: str = DEMO_GRAPH_NAME,
    graph_node_id: str = DEMO_GRAPH_NODE_ID,
) -> Any:
    """演示如何查询子图导出所需的 DL 模型信息，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph_node.get_graph_dl_nodes_model_info(SubGraphRef(graph_name, graph_node_id))


def example_get_graph_custom_nodes(
    graph_name: str = DEMO_GRAPH_NAME,
    graph_node_id: str = DEMO_GRAPH_NODE_ID,
) -> Any:
    """演示如何查询子图依赖了哪些自定义节点，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph_node.get_graph_custom_nodes(SubGraphRef(graph_name, graph_node_id))


def example_export_graph(
    graph_name: str = DEMO_GRAPH_NAME,
    graph_node_id: str = DEMO_GRAPH_NODE_ID,
) -> dict[str, Any]:
    """演示如何导出某个 graph node 内部子图，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph_node.export_graph(
        ExportSubGraphParams(
            graph_name,
            graph_node_id,
            dl_models_info={"detector": {"version": "1.0.0"}},
            custom_nodes={"SdkTestEchoNode": {"enableExport": True}},
        )
    )


def example_release_graph(
    graph_name: str = DEMO_GRAPH_NAME,
    graph_node_id: str = DEMO_GRAPH_NODE_ID,
) -> Any:
    """演示如何释放一个已经打开的子图，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph_node.release_graph(SubGraphRef(graph_name, graph_node_id))


def example_clear_graph(
    graph_name: str = DEMO_GRAPH_NAME,
    graph_node_id: str = DEMO_GRAPH_NODE_ID,
) -> dict[str, Any]:
    """演示如何清理子图运行残留数据，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph_node.clear_graph(SubGraphRef(graph_name, graph_node_id))


def example_get_all_nodes_info() -> dict[str, Any]:
    """演示如何读取子图编辑场景下全部可用节点定义，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph_node.get_all_nodes_info()


def example_set_subgraph_as_custom_subgraph(
    graph_name: str = DEMO_GRAPH_NAME,
    graph_node_id: str = DEMO_GRAPH_NODE_ID,
) -> dict[str, Any]:
    """演示如何把子图保存成可复用的自定义子图模板，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph_node.set_subgraph_as_custom_subgraph(
        SetSubgraphAsCustomSubgraphParams(graph_name, graph_node_id, "custom_subgraph_template")
    )


def example_activate_node(
    graph_name: str = DEMO_GRAPH_NAME,
    graph_node_id: str = DEMO_GRAPH_NODE_ID,
    node_id: str = DEMO_NODE_ID,
) -> dict[str, Any]:
    """演示如何从子图中的某个节点开始激活执行，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph_node.activate_node(SubGraphNodeRef(graph_name, graph_node_id, node_id))


def example_initial_node(
    graph_name: str = DEMO_GRAPH_NAME,
    graph_node_id: str = DEMO_GRAPH_NODE_ID,
    node_id: str = DEMO_NODE_ID,
) -> dict[str, Any]:
    """演示如何初始化子图节点，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph_node.initial_node(SubGraphNodeRef(graph_name, graph_node_id, node_id))


def example_update_node(
    graph_name: str = DEMO_GRAPH_NAME,
    graph_node_id: str = DEMO_GRAPH_NODE_ID,
    node_id: str = DEMO_NODE_ID,
) -> dict[str, Any]:
    """演示如何更新子图中的单个节点，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph_node.update_node(SubGraphNodeRef(graph_name, graph_node_id, node_id))


def example_run_graph(
    graph_name: str = DEMO_GRAPH_NAME,
    graph_node_id: str = DEMO_GRAPH_NODE_ID,
) -> dict[str, Any]:
    """演示如何直接运行整个子图，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph_node.run_graph(SubGraphRef(graph_name, graph_node_id))
