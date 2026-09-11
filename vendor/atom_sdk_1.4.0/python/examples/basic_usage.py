from atom_sdk import RuntimeFrame, RuntimeParamsUpdate, RuntimeRunParams
try:
    from .common import DEFAULT_BASE_URL, DEMO_EPICRAW_FILE, DEMO_GRAPH_NAME
except ImportError:
    from common import DEFAULT_BASE_URL, DEMO_EPICRAW_FILE, DEMO_GRAPH_NAME


def _demo_runtime_frames() -> list[RuntimeFrame]:
    return [
        RuntimeFrame(
            epicraw=DEMO_EPICRAW_FILE.read_bytes(),
            # 服务端目前只支持旋转矢量形式：[x, y, z, rx, ry, rz]（平移 + Rodrigues 旋转向量）
            cam2_base=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            roi={
                "min": {"x": -1.0, "y": -1.0, "z": -1.0},
                "max": {"x": 1.0, "y": 1.0, "z": 1.0},
                "cam2ROIFrame": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            },
        )
    ]


def main():
    from atom_sdk import AtomClient

    client = AtomClient(base_url=DEFAULT_BASE_URL)
    graph_name = DEMO_GRAPH_NAME

    loaded = client.runtime.load_graph(graph_name)
    print("loaded:", loaded)
    print("load request status:", loaded["status"])

    meta = client.runtime.get_meta_info(graph_name)
    print("meta:", meta)
    print("meta request status:", meta["status"])

    client.runtime.set_shared_params(RuntimeParamsUpdate(graph_name, {"camera_id": "cam-01"}))
    client.runtime.set_run_params(RuntimeParamsUpdate(graph_name, {"threshold": 0.5}))

    run_result = client.runtime.run_graph(RuntimeRunParams(graph_name, _demo_runtime_frames()))
    print("run result:", run_result)
    print("run request status:", run_result["status"])

    outputs = client.runtime.get_binded_outputs_info(graph_name)
    print("outputs:", outputs)


if __name__ == "__main__":
    main()
