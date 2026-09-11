"""RuntimeService 示例。

这组示例不是给“编辑图”用的，而是给“把 Atom 当执行引擎”用的。
适合外部程序加载图、喂入运行数据、读取绑定输出时参考。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np

from atom_sdk import (
    BindingRef,
    FileParamRef,
    NodeRef,
    PointCloudRef,
    RuntimeBindingDataUpdate,
    RuntimeFrame,
    RuntimeParamsUpdate,
    RuntimeRunParams,
    RuntimeStrategyParamsUpdate,
    SingleNodeParams,
)
from .common import DEMO_BINDING_NAME, DEMO_GRAPH_NAME, DEMO_NODE_ID, create_client


def _demo_runtime_frames() -> list[RuntimeFrame]:
    height, width = 2, 3
    image = np.zeros((height, width, 3), dtype=np.uint8)
    points = np.zeros((height, width, 3), dtype=np.float32)
    points[:, :, 2] = 1.0

    return [
        RuntimeFrame.from_data(
            points=points,
            image=image,
            intrinsic=[
                [1000.0, 0.0, width / 2],
                [0.0, 1000.0, height / 2],
                [0.0, 0.0, 1.0],
            ],
            distortion=[0.0, 0.0, 0.0, 0.0, 0.0],
            # 服务端目前只支持旋转矢量形式：[x, y, z, rx, ry, rz]（平移 + Rodrigues 旋转向量）
            cam2_base=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            roi={
                "min": {"x": -0.5, "y": -0.5, "z": 0.1},
                "max": {"x": 0.5, "y": 0.5, "z": 2.0},
                "cam2ROIFrame": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            },
        )
    ]


def _demo_camera_params() -> dict[str, Any]:
    return {
        "CameraMatrix": [
            2113.997971632298,
            0.0,
            1956.222038925553,
            0.0,
            2113.7299751270057,
            1505.0473199581195,
            0.0,
            0.0,
            1.0,
        ],
        "CameraDistortion": [
            0.049901632334,
            -0.037810281265,
            -0.00048319461,
            -0.000276258172,
            -0.026886293015,
        ],
        "CameraRotation": [
            0.9995132330503337,
            -0.005059159488191983,
            -0.030784766728731865,
            0.004951704878090689,
            0.9999813828533568,
            -0.003565748937897527,
            0.030802233296787017,
            0.003411576169582241,
            0.999519676430619,
        ],
        "CameraTranslation": [
            -25.837377992238334,
            -0.6852264771262435,
            -4.372034519324568,
        ],
    }


def _demo_passive_bino_params() -> dict[str, Any]:
    """构造 passive_bino 三路图像对应的完整 metadata 示例。"""
    return {
        "DepthSrc1": _demo_camera_params(),
        "DepthSrc2": _demo_camera_params(),
        "TextureSrc": _demo_camera_params(),
    }


def example_load_graph(graph_name: str = DEMO_GRAPH_NAME) -> dict[str, Any]:
    """演示如何按运行时方式加载图。

    适合外部程序正式执行图前先把图加载到运行时环境。
    """
    client = create_client()
    return client.runtime.load_graph(graph_name)


def example_list_graphs() -> Any:
    """演示如何查看运行时可见的图列表。

    如果你不确定某张图能不能被 Runtime 使用，可以先调用这个方法。
    """
    client = create_client()
    return client.runtime.list_graphs()


def example_get_all_nodes_info() -> dict[str, Any]:
    """演示如何读取运行时可见的节点定义。

    适合排查运行时环境与编辑态环境的节点差异。
    """
    client = create_client()
    return client.runtime.get_all_nodes_info()


def example_release_graph(graph_name: str = DEMO_GRAPH_NAME) -> dict[str, Any]:
    """演示如何释放运行时图。

    适合执行完成后释放资源时调用。
    """
    client = create_client()
    return client.runtime.release_graph(graph_name)


def example_get_meta_info(graph_name: str = DEMO_GRAPH_NAME) -> dict[str, Any]:
    """演示如何查看图的运行时元信息。

    通常可以从这里看到共享参数、运行参数和绑定结构。
    """
    client = create_client()
    return client.runtime.get_meta_info(graph_name)


def example_get_binded_output_value(
    graph_name: str = DEMO_GRAPH_NAME,
    binding_name: str = DEMO_BINDING_NAME,
) -> Any:
    """演示如何读取某个输出绑定当前的值。

    适合图跑完后，按绑定名直接拿结果。
    """
    client = create_client()
    return client.runtime.get_binded_output_value(BindingRef(graph_name, binding_name))


def example_get_binded_outputs_info(graph_name: str = DEMO_GRAPH_NAME) -> dict[str, Any]:
    """演示如何查看图上所有输出绑定的说明。

    适合你先想知道有哪些结果可以读，再决定读哪个绑定。
    """
    client = create_client()
    return client.runtime.get_binded_outputs_info(graph_name)


def example_get_binded_point_cloud(
    graph_name: str = DEMO_GRAPH_NAME,
    binding_name: str = DEMO_BINDING_NAME,
) -> bytes:
    """演示如何读取输出绑定对应的原始点云字节。

    如果绑定结果是点云或其他原始二进制内容，就这样取。
    """
    client = create_client()
    return client.runtime.get_binded_point_cloud(BindingRef(graph_name, binding_name))


def example_get_binded_point_cloud_parsed(
    graph_name: str = DEMO_GRAPH_NAME,
    binding_name: str = DEMO_BINDING_NAME,
) -> Any:
    """演示如何读取并解析输出绑定里的点云。

    普通业务代码优先用这个接口，返回值已经是结构化点云列表。
    """
    client = create_client()
    return client.runtime.get_binded_point_cloud_parsed(PointCloudRef(graph_name, binding_name, point_dim=3))


def example_set_shared_params(graph_name: str = DEMO_GRAPH_NAME) -> Any:
    """演示如何设置共享参数。

    共享参数通常是多次运行都可能复用的公共输入。
    """
    client = create_client()
    return client.runtime.set_shared_params(RuntimeParamsUpdate(graph_name, {"camera_id": "cam-01"}))


def example_set_run_params(graph_name: str = DEMO_GRAPH_NAME) -> Any:
    """演示如何设置运行参数。

    运行参数更像这一次执行的临时配置，比如阈值、开关等。
    """
    client = create_client()
    return client.runtime.set_run_params(RuntimeParamsUpdate(graph_name, {"threshold": 0.5}))


def example_run_graph(graph_name: str = DEMO_GRAPH_NAME) -> dict[str, Any]:
    """演示如何按运行时协议执行一张图。

    这里用小型 NumPy 图像和点云调用 RuntimeFrame.from_data；只有普通内参和
    畸变时会自动编码成 EPICRAW2，真实使用时换成你的传感器数据。
    """
    client = create_client()
    return client.runtime.run_graph(RuntimeRunParams(graph_name, _demo_runtime_frames()))


def example_runtime_frame_from_bytes() -> RuntimeFrame:
    """演示用已有 EPICRAW bytes 构造一帧普通运行时输入。

    适合相机 SDK 已经把一帧保存到内存，而不是保存成临时文件的场景。
    """
    if not DEMO_EPICRAW_FILE.exists():
        raise FileNotFoundError(
            f"请设置 ATOM_EPICRAW_FILE，并指向真实文件：{DEMO_EPICRAW_FILE}"
        )
    return RuntimeFrame.from_bytes(
        DEMO_EPICRAW_FILE.read_bytes(),
        cam2_base=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        roi={"cam2ROIFrame": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]},
    )


def example_runtime_frame_from_file() -> RuntimeFrame:
    """演示直接从 EPICRAW 文件构造普通运行时输入。"""
    if not DEMO_EPICRAW_FILE.exists():
        raise FileNotFoundError(
            f"请设置 ATOM_EPICRAW_FILE，并指向真实文件：{DEMO_EPICRAW_FILE}"
        )
    return RuntimeFrame.from_file(
        DEMO_EPICRAW_FILE,
        cam2_base=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    )


def example_run_graph_passive_bino(graph_name: str = DEMO_GRAPH_NAME) -> dict[str, Any]:
    """演示 passive_bino 模式：从 EPICRAW3 文件读取输入并执行图。

    这种模式要求图里 EpicProInput 的 run_mode 是 passive_bino。服务端会从
    EPICRAW3 里解析三张图、内参、畸变和 passive_bino_params，SDK 只额外传
    cam2_base。
    """
    client = create_client()
    run_params = RuntimeRunParams.passive_bino_from_file(
        graph_name,
        "/path/to/passive_bino.epicraw",
        cam2_base=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    )
    return client.runtime.run_graph(run_params)


def example_runtime_passive_bino_from_bytes() -> RuntimeRunParams:
    """演示从已有 EPICRAW3 bytes 生成 passive_bino 运行参数。"""
    path = Path(os.getenv("ATOM_EPICRAW3_FILE", "/path/to/passive_bino.epicraw3"))
    if not path.exists():
        raise FileNotFoundError(
            f"请设置 ATOM_EPICRAW3_FILE，或创建默认文件：{path}"
        )
    return RuntimeRunParams.passive_bino_from_bytes(
        DEMO_GRAPH_NAME,
        path.read_bytes(),
        cam2_base=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    )


def example_runtime_passive_bino_from_file() -> RuntimeRunParams:
    """演示从 EPICRAW3 文件生成 passive_bino 运行参数。"""
    path = Path(os.getenv("ATOM_EPICRAW3_FILE", "/path/to/passive_bino.epicraw3"))
    if not path.exists():
        raise FileNotFoundError(f"请设置 ATOM_EPICRAW3_FILE，并指向真实文件：{path}")
    return RuntimeRunParams.passive_bino_from_file(
        DEMO_GRAPH_NAME,
        path,
        cam2_base=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    )


def example_runtime_passive_bino_from_image() -> RuntimeRunParams:
    """演示 passive_bino_from_image 兼容别名；参数格式与 from_images 相同。"""
    height, width = 4, 4
    image_list = [
        np.zeros((height, width), dtype=np.uint8),
        np.zeros((height, width), dtype=np.uint8),
        np.zeros((height, width, 3), dtype=np.uint8),
    ]
    return RuntimeRunParams.passive_bino_from_image(
        DEMO_GRAPH_NAME,
        image_list=image_list,
        params=_demo_passive_bino_params(),
        cam2_base=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    )


def example_run_graph_passive_bino_from_images(graph_name: str = DEMO_GRAPH_NAME) -> dict[str, Any]:
    """演示 passive_bino 模式：由三张图像和参数生成 EPICRAW3 后执行图。

    `image_list` 顺序固定为 DepthSrc1、DepthSrc2、TextureSrc。SDK 会在本地
    生成 EPICRAW3 bytes，再按 passive_bino 协议发送给 Runtime/RunGraph。
    """
    client = create_client()
    height, width = 480, 640
    image_list = [
        np.zeros((height, width), dtype=np.uint8),
        np.zeros((height, width), dtype=np.uint8),
        np.zeros((height, width, 3), dtype=np.uint8),
    ]
    passive_bino_params = _demo_passive_bino_params()
    run_params = RuntimeRunParams.passive_bino_from_images(
        graph_name,
        image_list=image_list,
        params=passive_bino_params,
        cam2_base=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    )
    return client.runtime.run_graph(run_params)


def example_set_graph_binding_data(graph_name: str = DEMO_GRAPH_NAME) -> Any:
    """演示如何直接按 binding 名给图喂数据。

    适合你的业务层已经只关心绑定名，而不想再关心具体节点端口名。
    """
    client = create_client()
    return client.runtime.set_graph_binding_data(
        RuntimeBindingDataUpdate(
            graph_name,
            {
                "input_image": "data:image/jpg;base64,xxx",
                "score_threshold": 0.5,
            },
        )
    )


def example_get_node_params_info_with_strategy(
    graph_name: str = DEMO_GRAPH_NAME,
    node_id: str = DEMO_NODE_ID,
) -> dict[str, Any]:
    """演示如何读取带策略信息的节点参数。

    目前只适用于 PoseListFilter、PickPointFilter、PoseListSorterInXOY、
    PickPointSorterInXOY、PickPointSorterNew、PoseListSorter。返回值里的
    paramsData 通常作为 set_params_in_strategy 的输入模板。
    """
    client = create_client()
    return client.runtime.get_node_params_info_with_strategy(NodeRef(graph_name, node_id))


def example_set_params_in_strategy(
    graph_name: str = DEMO_GRAPH_NAME,
    node_id: str = DEMO_NODE_ID,
) -> Any:
    """演示如何设置策略中的参数值。

    目前只适用于 PoseListFilter、PickPointFilter、PoseListSorterInXOY、
    PickPointSorterInXOY、PickPointSorterNew、PoseListSorter。
    """
    client = create_client()
    strategy = client.runtime.get_node_params_info_with_strategy(NodeRef(graph_name, node_id))
    params_data = strategy["paramsData"]
    params_data["run_params"]["strategies_config"] = {
        "value": [
            {
                "BY_SCORE": {
                    "order": "HIGHEST",
                    "differenceThreshold": 1,
                    "groupInterval": 0.75,
                }
            }
        ]
    }
    return client.runtime.set_params_in_strategy(
        RuntimeStrategyParamsUpdate(
            graph_name,
            node_id,
            params_data,
        )
    )


def example_get_file_param_md5(graph_name: str = DEMO_GRAPH_NAME) -> dict[str, Any]:
    """演示如何读取文件型参数当前引用文件的 md5。

    适合你想确认模型文件是不是已经更新成功时调用。
    """
    client = create_client()
    return client.runtime.get_file_param_md5(FileParamRef(graph_name, "modelFile", param_type="init_params"))


def example_run_single_node_no_graph_parsed() -> Any:
    """演示推荐的单节点直跑方式：自动解析 outputs。

    普通业务代码优先用 parsed 接口；它会保持输出 key 不变，只把点云和图像
    value 解析成更好用的结构化对象。
    """
    client = create_client()
    return client.runtime.run_single_node_no_graph_parsed(
        SingleNodeParams(
            "DemoNode",
            inputs={"image": b"demo-image-bytes"},
            output_data_types={"preview": "ColorImage"},
        )
    )


def example_run_single_node_no_graph() -> Any:
    """演示如何保留单节点直跑的原始返回值。

    适合调试服务端真实返回，或需要自己控制输出解析逻辑时调用。
    """
    client = create_client()
    return client.runtime.run_single_node_no_graph(
        SingleNodeParams(
            "DemoNode",
            inputs={"image": b"demo-image-bytes"},
            run_params={"threshold": 0.6},
            init_params={"device": "cuda:0"},
        )
    )


if __name__ == "__main__":
    print(example_run_graph("hte"))
