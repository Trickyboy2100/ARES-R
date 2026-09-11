from __future__ import annotations

import os
from pathlib import Path

from atom_sdk import AtomClient

DEFAULT_BASE_URL = os.getenv("ATOM_BASE_URL", "http://127.0.0.1:10026")
DEMO_GRAPH_NAME = os.getenv("ATOM_GRAPH_NAME", "demo_graph")
DEMO_RENAMED_GRAPH_NAME = os.getenv("ATOM_RENAMED_GRAPH_NAME", "demo_graph_v2")
DEMO_COPY_GRAPH_NAME = os.getenv("ATOM_COPY_GRAPH_NAME", "demo_graph_copy")
DEMO_NODE_NAME = os.getenv("ATOM_NODE_NAME", "Input")
DEMO_TARGET_NODE_NAME = os.getenv("ATOM_TARGET_NODE_NAME", "Output")
DEMO_GRAPH_NODE_ID = os.getenv("ATOM_GRAPH_NODE_ID", "graph-node-id")
DEMO_NODE_ID = os.getenv("ATOM_NODE_ID", "node-id")
DEMO_TARGET_NODE_ID = os.getenv("ATOM_TARGET_NODE_ID", "target-node-id")
DEMO_PORT_NAME = os.getenv("ATOM_PORT_NAME", "output")
DEMO_INPUT_PORT_NAME = os.getenv("ATOM_INPUT_PORT_NAME", "input")
DEMO_BINDING_NAME = os.getenv("ATOM_BINDING_NAME", "demo_binding")
DEMO_CUSTOM_NODE_NAME = os.getenv("ATOM_CUSTOM_NODE_NAME", "SdkTestEchoNode")
DEMO_GRAPH_FILE = Path(os.getenv("ATOM_GRAPH_FILE", "/path/to/demo_graph.atom"))
DEMO_CUSTOM_NODE_FILE = Path(os.getenv("ATOM_CUSTOM_NODE_FILE", "/path/to/demo_node.py"))
DEMO_IMAGE_FILE = Path(os.getenv("ATOM_IMAGE_FILE", "/path/to/demo.jpg"))
DEMO_MODEL_FILE = Path(os.getenv("ATOM_MODEL_FILE", "/path/to/demo_model.bin"))
DEMO_EPICRAW_FILE = Path(os.getenv("ATOM_EPICRAW_FILE", "/path/to/demo.epicraw"))


def require_file(path: Path, environment_name: str) -> Path:
    """检查示例所需文件，并用环境变量名给出可操作的错误提示。"""
    if not path.exists():
        raise FileNotFoundError(f"请设置 {environment_name}，并指向真实文件：{path}")
    return path


def create_client(base_url: str = DEFAULT_BASE_URL) -> AtomClient:
    """创建一个指向本地 Atom 服务的客户端。"""
    return AtomClient(base_url=base_url)
