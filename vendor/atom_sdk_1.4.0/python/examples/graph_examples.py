"""GraphService 示例。

这组示例专门演示“图本身”的操作，比如创建图、改图名、查询导出依赖、导入导出图。
适合你想管理整张图，而不是只改某个节点时参考。
"""

from __future__ import annotations

from typing import Any

from atom_sdk import (
    CopyGraphParams,
    CreateGraphParams,
    EditGraphCommentParams,
    EditGraphNameParams,
    ExportGraphParams,
    ImportExtensionNodesByPathParams,
    LoadGraphParams,
)

from .common import (
    DEMO_COPY_GRAPH_NAME,
    DEMO_GRAPH_FILE,
    DEMO_GRAPH_NAME,
    DEMO_GRAPH_NODE_ID,
    DEMO_RENAMED_GRAPH_NAME,
    create_client,
)


def example_create_graph(graph_name: str = DEMO_GRAPH_NAME) -> dict[str, Any]:
    """演示如何新建一张图，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph.create_graph(CreateGraphParams(graph_name, description="SDK example graph"))


def example_list_graphs() -> Any:
    """演示如何获取当前所有主图列表，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph.list_graphs()


def example_get_all_custom_subgraphs_no_thumbnail() -> Any:
    """演示如何获取所有自定义子图模板列表，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph.get_all_custom_subgraphs_no_thumbnail()


def example_copy_graph(
    graph_name: str = DEMO_GRAPH_NAME,
    new_graph_name: str = DEMO_COPY_GRAPH_NAME,
) -> dict[str, Any]:
    """演示如何复制一张现有图，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph.copy_graph(CopyGraphParams(graph_name, new_graph_name))


def example_delete_graph(graph_name: str = DEMO_GRAPH_NAME) -> Any:
    """演示如何删除一张图，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph.delete_graph(graph_name)


def example_get_all_nodes_info() -> dict[str, Any]:
    """演示如何查看服务端支持哪些节点，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph.get_all_nodes_info()


def example_get_graph_dl_nodes_model_info(graph_name: str = DEMO_GRAPH_NAME) -> Any:
    """演示如何查看图导出时需要打包的 DL 模型信息，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph.get_graph_dl_nodes_model_info(graph_name)


def example_get_graph_custom_nodes(graph_name: str = DEMO_GRAPH_NAME) -> Any:
    """演示如何查看图里依赖了哪些自定义节点，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph.get_graph_custom_nodes(graph_name)


def example_get_graph_workcell_models_info(
    graph_name: str = DEMO_GRAPH_NAME,
    graph_node_id: str = DEMO_GRAPH_NODE_ID,
) -> Any:
    """演示如何查看图或指定 graph node 关联的 workcell 模型信息，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph.get_graph_workcell_models_info(graph_name, graph_node_id=graph_node_id)


def example_get_graph_bindings(graph_name: str = DEMO_GRAPH_NAME) -> dict[str, Any]:
    """演示如何读取一张图当前的绑定情况，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph.get_graph_bindings(graph_name)


def example_load_graph(graph_name: str = DEMO_GRAPH_NAME) -> dict[str, Any]:
    """演示如何把本地 `.atom` 文件导入到 Atom，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph.load_graph(LoadGraphParams(graph_name, DEMO_GRAPH_FILE))


def example_import_extension_nodes_by_path() -> Any:
    """演示如何导入 `load_graph` 解压出的扩展节点文件，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph.import_extension_nodes_by_path(
        ImportExtensionNodesByPathParams(
            {
                "/tmp/demo_node.py": {
                    "forceCover": False,
                    "newNodes": ["DemoNode"],
                    "existedNodes": [],
                }
            }
        )
    )


def example_export_graph(graph_name: str = DEMO_GRAPH_NAME) -> dict[str, Any]:
    """演示如何导出图，并带出模型和自定义节点信息，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph.export_graph(
        ExportGraphParams(
            graph_name,
            dl_models_info={"detector": {"version": "1.0.0"}},
            custom_nodes={"SdkTestEchoNode": {"enableExport": True}},
        )
    )


def example_open_graph(graph_name: str = DEMO_GRAPH_NAME) -> dict[str, Any]:
    """演示如何打开一张图进入编辑态，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph.open_graph(graph_name)


def example_edit_graph_name(graph_name: str = DEMO_GRAPH_NAME) -> Any:
    """演示如何修改图名称，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph.edit_graph_name(EditGraphNameParams(graph_name, DEMO_RENAMED_GRAPH_NAME))


def example_release_graph(graph_name: str = DEMO_GRAPH_NAME) -> Any:
    """演示如何释放一张已经打开的图，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph.release_graph(graph_name)


def example_run_graph(graph_name: str = DEMO_GRAPH_NAME) -> dict[str, Any]:
    """演示如何运行整张图，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph.run_graph(graph_name)


def example_clear_graph(graph_name: str = DEMO_GRAPH_NAME) -> dict[str, Any]:
    """演示如何清掉图上的运行残留数据，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph.clear_graph(graph_name)


def example_edit_graph_comment(graph_name: str = DEMO_GRAPH_NAME) -> Any:
    """演示如何更新图备注，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph.edit_graph_comment(EditGraphCommentParams(graph_name, "updated by SDK example"))


def example_get_graph_json_data(graph_name: str = DEMO_GRAPH_NAME) -> dict[str, Any]:
    """演示如何获取图的原始 JSON 结构，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph.get_graph_json_data(graph_name)


def example_get_timestamp(graph_name: str = DEMO_GRAPH_NAME) -> dict[str, Any]:
    """演示如何主动读取图的最新时间戳，方便你快速对照 SDK 调用。"""
    client = create_client()
    return client.graph.get_timestamp(graph_name)
