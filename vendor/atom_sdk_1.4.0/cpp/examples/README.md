# C++ 示例

这里的示例都使用本地 Atom 服务进行演示。默认服务地址是
`http://127.0.0.1:10026`；如果服务地址不同，可以通过命令行参数或
`ATOM_BASE_URL` 指定。

## 1. 编译示例

在仓库根目录执行：

```bash
cmake -S cpp -B build/cpp -DATOM_SDK_BUILD_EXAMPLES=ON
cmake --build build/cpp --parallel
```

编译成功后，可执行文件位于 `build/cpp/`。SDK 已经包含所需的 HTTP 和 JSON 第三方头文件，
不需要安装 Boost，也不需要配置外部第三方库路径。

使用发布 ZIP 时，示例 CMake 只使用包内的 `include/atom_sdk`、`lib` 和 Windows 的 `bin`；
运行时只需保证 `atom_sdk_cpp.dll` 位于示例程序目录或系统 `PATH` 中。

## 2. 示例一览

| 示例 | 用途 | 命令行参数 |
| --- | --- | --- |
| `basic_runtime` | 查询图列表、加载图并读取元信息 | `graph_name [base_url]` |
| `runtime_workflow` | 演示 Runtime 图的加载、参数设置、运行和输出读取 | `graph_name [base_url]` |
| `run_single_node` | 演示单节点直跑和 JSON 结果读取 | `node_name [base_url]` |
| `graph_workflow` | 演示创建主图、创建节点、设置参数和运行图 | `graph_name [base_url]` |
| `graph_node_workflow` | 演示打开子图、创建内部节点、设置参数和运行子图 | `graph_name graph_node_id [base_url]` |
| `test_activation` | 演示主图节点和子图内部节点的初始化、激活、更新 | `base_url graph_name node_id graph_node_id inner_node_id` |
| `api_catalog` | 按服务分类集中演示更多 API | `service [base_url] [graph_name]` |

## 3. 运行基础示例

```bash
./build/cpp/atom_sdk_cpp_example_basic_runtime demo_graph
./build/cpp/atom_sdk_cpp_example_runtime_workflow demo_graph
./build/cpp/atom_sdk_cpp_example_run_single_node DemoNode
./build/cpp/atom_sdk_cpp_example_graph_workflow demo_graph
./build/cpp/atom_sdk_cpp_example_graph_node_workflow demo_graph graph-node-id
./build/cpp/atom_sdk_cpp_example_test_activation \
  http://127.0.0.1:10026 demo_graph node-id graph-node-id inner-node-id
```

说明：

- `demo_graph`、`DemoNode` 和各类节点 ID 只是示例值，请替换成服务中真实存在的资源。
- `graph_workflow` 会创建图和节点，并修改服务端数据；建议使用专门的测试图名。
- `runtime_workflow` 中的输入数据是占位 EPICRAW 字节，实际运行时需要替换为真实输入。
- 每个示例都会捕获异常并输出错误信息；进程返回码为 `0` 表示示例执行完成，返回码为 `1` 或 `2` 表示参数或服务调用失败。

## 4. API Catalog

`api_catalog` 将 API 按服务拆分为 6 个入口：

```text
runtime       Runtime 图生命周期、参数、运行和输出读取
graph         主图创建、复制、导入导出、清理和删除
node          主图节点创建、复制、动态 IO、参数、端口和激活
graph-node    子图节点操作、子图运行和自定义子图
single-node   单节点直跑的 raw、json、binary、parsed 四种读取方式
activation    主图节点和子图内部节点的初始化、激活、更新
```

最小运行示例：

```bash
# 使用环境变量中的默认服务地址和图名
./build/cpp/atom_sdk_cpp_example_api_catalog runtime

# 显式指定服务地址和图名
./build/cpp/atom_sdk_cpp_example_api_catalog graph \
  http://127.0.0.1:10026 csharp_sdk_example_graph

# 对已有图中的节点执行节点 API 示例
ATOM_NODE_ID=node-id \
  ./build/cpp/atom_sdk_cpp_example_api_catalog node \
  http://127.0.0.1:10026 demo_graph

# 对已有图中的 Graph Node 执行子图 API 示例
ATOM_GRAPH_NODE_ID=graph-node-id \
  ./build/cpp/atom_sdk_cpp_example_api_catalog graph-node \
  http://127.0.0.1:10026 demo_graph

# 单节点直跑，默认使用 parsed 模式
ATOM_SINGLE_NODE_NAME=DemoNode \
  ./build/cpp/atom_sdk_cpp_example_api_catalog single-node

# 执行主图节点和子图内部节点的激活流程
ATOM_NODE_ID=node-id \
ATOM_GRAPH_NODE_ID=graph-node-id \
ATOM_INNER_NODE_ID=inner-node-id \
  ./build/cpp/atom_sdk_cpp_example_api_catalog activation
```

### 4.1 通用环境变量

| 变量 | 默认值 | 作用 |
| --- | --- | --- |
| `ATOM_BASE_URL` | `http://127.0.0.1:10026` | 服务地址；命令行第 2 个参数优先级更高 |
| `ATOM_GRAPH_NAME` | `demo_graph` | 默认图名；命令行第 3 个参数优先级更高 |
| `ATOM_NODE_ID` | 无 | 已有主图节点 ID；`node`、`activation` 需要 |
| `ATOM_GRAPH_NODE_ID` | 无 | 已有 Graph Node ID；`graph-node`、`activation` 需要 |
| `ATOM_INNER_NODE_ID` | 无 | 子图内部节点 ID；`activation` 需要 |
| `ATOM_SINGLE_NODE_NAME` | `DemoNode` | 单节点直跑的节点名称 |
| `ATOM_SINGLE_NODE_MODE` | `parsed` | 单节点结果模式：`raw`、`json`、`binary` 或 `parsed` |
| `ATOM_SINGLE_NODE_INPUT_NAME` | `value` | 单节点输入端口名称 |
| `ATOM_OUTPUT_NAME` | `preview` | 单节点输出名称 |

### 4.2 启用真实资源相关操作

`api_catalog` 默认只执行不需要额外文件或 ID 的操作。下面这些变量设置后，
才会执行对应的真实资源调用：

| 变量 | 作用 |
| --- | --- |
| `ATOM_EPICRAW_FILE` | 使用真实 EPICRAW 文件运行普通 Runtime 图 |
| `ATOM_EPICRAW3_FILE` | 使用真实 EPICRAW3 文件运行 `passive_bino` 图 |
| `ATOM_BINDING_NAME` | 读取指定输出绑定的值，也用于设置节点绑定名 |
| `ATOM_POINT_CLOUD_BINDING_NAME` | 读取指定输出绑定的原始和解析点云 |
| `ATOM_FILE_PARAM_NAME` | 读取文件参数 MD5；可配合 `ATOM_FILE_PARAM_TYPE` 指定参数类型 |
| `ATOM_SET_BINDING_DATA=true` | 写入一组示例图绑定数据 |
| `ATOM_READ_PORT_DATA=true` | 读取节点端口数据、点云和下载信息 |
| `ATOM_PORT_NAME` | 端口操作使用的端口名，默认 `output` |
| `ATOM_TARGET_NODE_ID` | 设置后演示节点连线和断线 |
| `ATOM_INPUT_PORT_NAME` | 目标节点输入端口名，默认 `input` |
| `ATOM_GRAPH_FILE` | 导入指定 `.atom` 图文件 |
| `ATOM_IMPORTED_GRAPH_NAME` | 导入图名称，默认在当前图名后追加 `_imported` |
| `ATOM_EXPORT_EXAMPLE_GRAPH=true` | 导出主图或子图 |
| `ATOM_IMPORT_EXTENSION_NODES=true` | 导入扩展节点；文件路径由 `ATOM_CUSTOM_NODE_FILE` 指定 |
| `ATOM_RENAME_EXAMPLE_GRAPH=true` | 修改 API Catalog 创建的图名 |
| `ATOM_DELETE_EXAMPLE_GRAPH=true` | 删除 API Catalog 创建的主图；默认不删除 |
| `ATOM_SUB_GRAPH_NAME` | 演示创建 Graph Node |
| `ATOM_GENERATE_NODE_IDS` | 演示按多个节点生成 Graph Node，值为逗号分隔的节点 ID |
| `ATOM_SAVE_CUSTOM_SUBGRAPH=true` | 将示例子图保存为自定义子图模板 |

例如，使用真实 EPICRAW 文件运行 Runtime 示例：

```bash
ATOM_EPICRAW_FILE=/path/to/input.epicraw \
ATOM_BINDING_NAME=output_binding \
  ./build/cpp/atom_sdk_cpp_example_api_catalog runtime \
  http://127.0.0.1:10026 demo_graph
```

## 5. 资源和清理注意事项

- `runtime` 会加载并在结束时释放图。
- `graph` 会创建一张图，复制的临时图会自动删除；主图默认只释放、不删除。
- 设置 `ATOM_DELETE_EXAMPLE_GRAPH=true` 后，`graph` 才会删除它创建的主图。
- `node` 和 `graph-node` 会创建临时节点，并在正常结束时删除这些临时节点；运行失败时请在服务端检查并清理残留资源。
- `test_activation` 和 `activation` 不会创建节点，但要求传入真实的图和节点 ID。
- 这些示例用于展示 SDK 调用方式，不会替用户准备图、节点、绑定或模型资源。

## 6. 相关源码

- [basic_runtime.cpp](basic_runtime.cpp)
- [runtime_workflow.cpp](runtime_workflow.cpp)
- [run_single_node.cpp](run_single_node.cpp)
- [graph_workflow.cpp](graph_workflow.cpp)
- [graph_node_workflow.cpp](graph_node_workflow.cpp)
- [test_activation.cpp](test_activation.cpp)
- [api_catalog.cpp](api_catalog.cpp)
- [C++ SDK 总说明](../README.md)
