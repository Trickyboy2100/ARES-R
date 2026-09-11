"""Python 示例运行器。

这个文件不重复实现 SDK 接口，而是把四个 Service 示例模块里的
``example_*`` 函数统一暴露为命令行入口，方便用户先列出示例，再只运行
自己需要的一个接口。
"""

from __future__ import annotations

import argparse
import importlib
import json
from typing import Any


MODULES = {
    "graph": "examples.graph_examples",
    "node": "examples.node_examples",
    "graph-node": "examples.graph_node_examples",
    "runtime": "examples.runtime_examples",
}


def _load_module(service: str):
    """按服务名加载对应的示例模块。"""
    return importlib.import_module(MODULES[service])


def _example_names(module: Any) -> list[str]:
    """返回模块中的示例函数名（去掉统一的 example_ 前缀）。"""
    return sorted(
        name[len("example_") :]
        for name in dir(module)
        if name.startswith("example_") and callable(getattr(module, name))
    )


def _print_result(result: Any) -> None:
    """以便于阅读的方式打印不同类型的示例返回值。"""
    if isinstance(result, bytes):
        print(f"bytes: {len(result)} bytes")
    elif hasattr(result, "__dict__") and result.__class__.__module__.startswith("atom_sdk"):
        print(result)
    else:
        try:
            print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        except TypeError:
            print(result)


def main() -> int:
    """列出或运行一个 Python 示例。"""
    parser = argparse.ArgumentParser(
        description="列出或运行 Atom SDK Python 示例。"
    )
    parser.add_argument(
        "service",
        nargs="?",
        choices=sorted(MODULES),
        help="服务名：graph、node、graph-node 或 runtime。",
    )
    parser.add_argument(
        "example",
        nargs="?",
        help="示例函数名，不需要写 example_ 前缀。",
    )
    args = parser.parse_args()

    if args.service is None:
        print("可用服务：" + ", ".join(sorted(MODULES)))
        print("示例：python -m examples.api_catalog runtime get_meta_info")
        return 0

    module = _load_module(args.service)
    names = _example_names(module)
    if args.example is None:
        print(f"{args.service} 可用示例：")
        for name in names:
            print(f"  {name}")
        return 0

    function_name = args.example
    if not function_name.startswith("example_"):
        function_name = "example_" + function_name
    function = getattr(module, function_name, None)
    if not callable(function):
        raise SystemExit(
            f"找不到示例 {args.service}/{args.example}。可先运行："
            f"python -m examples.api_catalog {args.service}"
        )

    _print_result(function())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
