# Examples

这个目录按 SDK 的能力域拆分了示例脚本，方便你按方法查用法。
现在每个示例函数也都补了简短解释，主要会说明：

- 这个方法是干什么的
- 一般在什么场景下用
- 哪些参数需要你替换成自己的真实值

这些示例默认连接本地 `http://127.0.0.1:10026`。
可以通过环境变量配置外部服务和示例资源，不需要修改源码：

```bash
export ATOM_BASE_URL=http://127.0.0.1:10026
export ATOM_GRAPH_NAME=你的图名称
export ATOM_EPICRAW_FILE=/path/to/your/frame.epicraw
```

节点、端口、绑定名和模型文件也可以通过 `ATOM_NODE_ID`、`ATOM_PORT_NAME`、
`ATOM_BINDING_NAME`、`ATOM_MODEL_FILE` 等同名环境变量覆盖，完整默认值见
`examples/common.py`。

部分示例需要真实资源文件，比如：

- `/path/to/demo_graph.atom`
- `/path/to/demo_node.py`
- `/path/to/demo.jpg`

运行前请通过对应环境变量提供真实文件路径；如果文件不存在，示例会直接报出需要设置的变量名。

Runtime 的输入工厂也有独立示例：`runtime_examples.py` 中的
`example_runtime_frame_from_bytes`、`example_runtime_frame_from_file`、
`example_runtime_passive_bino_from_bytes`、
`example_runtime_passive_bino_from_file` 和
`example_runtime_passive_bino_from_image`，分别展示内存、文件和三路图像输入。
其中 EPICRAW3 示例需要设置 `ATOM_EPICRAW3_FILE`。

当前示例文件：

- `basic_usage.py`：最基础的连通性和主流程示例
- `graph_examples.py`：`GraphService` 全部公开方法示例
- `node_examples.py`：`NodeService` 全部公开方法示例
- `graph_node_examples.py`：`GraphNodeService` 全部公开方法示例
- `runtime_examples.py`：`RuntimeService` 全部公开方法示例
- `api_catalog.py`：按命令行列出或运行上面四个模块中的任意示例函数

如果你只想快速上手，先看 `basic_usage.py`。
如果你想找某个具体接口的调用写法，直接在对应文件里搜索 `example_方法名` 即可。
如果你是不太熟代码的同学，建议先看每个文件顶部说明，再看单个 `example_` 函数上面的解释。

## 从命令行运行单个示例

在 `python/` 目录执行。先列出某个 Service 的示例：

```bash
python -m examples.api_catalog runtime
python -m examples.api_catalog graph
python -m examples.api_catalog node
python -m examples.api_catalog graph-node
```

再运行一个具体示例。命令中的名称可以省略 `example_` 前缀：

```bash
ATOM_GRAPH_NAME=demo_graph \
python -m examples.api_catalog runtime get_meta_info

ATOM_GRAPH_NAME=demo_graph \
ATOM_NODE_ID=node-id \
python -m examples.api_catalog node get_node_params
```

需要真实文件的示例会在文件不存在时直接提示对应环境变量；会修改图或节点的示例请先使用测试资源。
