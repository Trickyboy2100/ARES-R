# C# 示例

这些示例按使用场景拆分，全部引用本地 `src/AtomSdk` 项目，可以直接从仓库构建。

## 示例列表

| 项目 | 用途 | 是否会修改图状态 |
| --- | --- | --- |
| `RuntimeBasic` | 现有运行时综合示例，包含图列表、加载、参数、运行和单节点直跑 | 会加载/释放运行时图 |
| `RuntimeWorkflow` | 推荐的运行时主流程，并演示可选的 `passive_bino` | 会加载/释放运行时图 |
| `RuntimeSingleNode` | 不加载图，直接运行一个节点；展示 JSON、二进制和 parsed 结果 | 不修改图定义 |
| `GraphWorkflow` | 主图创建、打开、创建节点、连线、设参、绑定、运行 | 会创建和修改图及节点 |
| `GraphNodeWorkflow` | 打开 graph node 子图，操作子图内部节点并运行 | 会修改子图及内部节点 |
| `ActivationWorkflow` | 对已有主图节点和子图内部节点执行初始化、激活、更新 | 会触发节点执行 |
| `ApiCatalog` | 按子命令逐接口展示四个 Service 和输入工厂 | 按模式决定 |

`GraphWorkflow` 默认使用 `csharp_sdk_example_graph`，建议在测试环境运行。示例最后只释放编辑态资源，不自动删除图定义；如果重复运行，请更换 `ATOM_GRAPH_NAME`，避免服务端因同名图拒绝创建。

## 配置

最常用的环境变量如下：

```bash
export ATOM_BASE_URL=http://127.0.0.1:10026
export ATOM_GRAPH_NAME=demo_graph
export ATOM_GRAPH_NODE_ID=graph-node-id
export ATOM_NODE_ID=node-id
export ATOM_INNER_NODE_ID=inner-node-id
export ATOM_NODE_NAME=Filter
export ATOM_TARGET_NODE_NAME=Filter
export ATOM_PORT_NAME=points
export ATOM_INPUT_PORT_NAME=points
export ATOM_BINDING_NAME=sdk_example_output
export ATOM_POINT_CLOUD_BINDING_NAME=point_cloud_output
```

也可以把 `graphName` 和 `baseUrl` 作为前两个命令行参数传给 `RuntimeWorkflow`、`RuntimeSingleNode` 和 `GraphWorkflow`；`GraphNodeWorkflow` 的顺序是 `graphName graphNodeId baseUrl`；`ActivationWorkflow` 的顺序是 `graphName nodeId graphNodeId innerNodeId baseUrl`。

运行时输入文件：

- `RuntimeBasic` 和 `RuntimeWorkflow` 必须设置 `ATOM_EPICRAW_FILE`；
- `RuntimeWorkflow` 如果还设置了存在的 `ATOM_EPICRAW3_FILE`，会额外演示 `passive_bino`；
- `RuntimeSingleNode` 可设置 `ATOM_IMAGE_FILE`，不设置时使用演示字节，真实节点通常需要真实图片；
- `RuntimeSingleNode` 默认运行推荐的 `parsed` 模式，也可设置 `ATOM_SINGLE_NODE_MODE=raw` 或 `json` 查看另外两种返回方式；
- 如果端口名不是 `image`，单节点示例可设置 `ATOM_SINGLE_NODE_INPUT_NAME`；
- `ATOM_READ_POINT_CLOUD=true` 时，两个 workflow 会调用解析点云接口，端口名由 `ATOM_PORT_NAME` 控制。

## 运行

```bash
cd csharp
HOME=/tmp dotnet build AtomSdk.sln

HOME=/tmp dotnet run --project examples/RuntimeWorkflow/RuntimeWorkflow.csproj
HOME=/tmp dotnet run --project examples/RuntimeSingleNode/RuntimeSingleNode.csproj
HOME=/tmp dotnet run --project examples/GraphWorkflow/GraphWorkflow.csproj
HOME=/tmp dotnet run --project examples/GraphNodeWorkflow/GraphNodeWorkflow.csproj
HOME=/tmp dotnet run --project examples/ActivationWorkflow/ActivationWorkflow.csproj
HOME=/tmp dotnet run --project examples/ApiCatalog/ApiCatalog.csproj -- input
HOME=/tmp dotnet run --project examples/ApiCatalog/ApiCatalog.csproj -- runtime
HOME=/tmp dotnet run --project examples/ApiCatalog/ApiCatalog.csproj -- graph http://127.0.0.1:10026 csharp_sdk_example_graph
HOME=/tmp dotnet run --project examples/ApiCatalog/ApiCatalog.csproj -- node http://127.0.0.1:10026 demo_graph
HOME=/tmp dotnet run --project examples/ApiCatalog/ApiCatalog.csproj -- graph-node http://127.0.0.1:10026 demo_graph
```

节点、端口、绑定名是服务端资源，不同图的实际名称通常不同；示例中的默认值只是便于阅读的占位值，运行前请按自己的图配置环境变量。每个 `Program.cs` 顶部也写了该示例的调用逻辑和注意事项。
