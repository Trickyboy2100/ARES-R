using AtomSdk;
using AtomSdk.Models;
using AtomSdkExamples;

// 子图编辑态流程：先定位外层 graph node，再操作它内部的节点。
var graphName = ExampleSettings.ArgumentOrSetting(args, 0, "ATOM_GRAPH_NAME", ExampleSettings.GraphName);
var graphNodeId = ExampleSettings.ArgumentOrSetting(args, 1, "ATOM_GRAPH_NODE_ID", ExampleSettings.GraphNodeId);
var baseUrl = ExampleSettings.ArgumentOrSetting(args, 2, "ATOM_BASE_URL", ExampleSettings.BaseUrl);
var client = new AtomClient(baseUrl);
var subgraph = new SubGraphRef(graphName, graphNodeId);

var opened = await client.GraphNode.OpenGraphInfoAsync(subgraph);
ExampleSettings.PrintStatus("打开子图", opened.Status, opened.Timestamp);

var innerNode = await client.GraphNode.CreateNodeInfoAsync(
    new SubGraphCreateNodeParams(graphName, graphNodeId, ExampleSettings.NodeName));
var innerNodeId = innerNode.NodeId ?? throw new InvalidOperationException("创建子图内部节点后没有返回 nodeId。");
Console.WriteLine($"创建内部节点：{innerNodeId}");

var innerRef = new SubGraphNodeRef(graphName, graphNodeId, innerNodeId);
var innerParams = await client.GraphNode.GetNodeParamsSnapshotAsync(innerRef);
Console.WriteLine($"内部节点参数：init_params={innerParams.InitParams.ValueKind}, run_params={innerParams.RunParams.ValueKind}");

var innerInfo = await client.GraphNode.GetNodeInfoInGraphModelAsync(innerRef);
ExampleSettings.PrintStatus("读取内部节点详情", innerInfo.Status, innerInfo.Timestamp);

await client.GraphNode.SetNodeParamDataInfoAsync(
    new SubGraphNodeParamUpdate(graphName, graphNodeId, innerNodeId, "threshold", "run_params", 0.4));
await client.GraphNode.EditNodeCommentAsync(new EditSubGraphNodeCommentParams(
    graphName, graphNodeId, innerNodeId, "updated by C# SDK example"));
await client.GraphNode.SetBindingNameInfoAsync(new SubGraphBindingUpdate(
    graphName,
    graphNodeId,
    innerNodeId,
    "outputs",
    ExampleSettings.PortName,
    ExampleSettings.BindingName));

var bindings = await client.GraphNode.GetGraphBindingsAsync(subgraph);
ExampleSettings.PrintJson("子图绑定", bindings);

var modelInfo = await client.GraphNode.GetGraphDlNodesModelInfoAsync(subgraph);
ExampleSettings.PrintJson("子图模型依赖", modelInfo);
var customNodes = await client.GraphNode.GetGraphCustomNodesAsync(subgraph);
ExampleSettings.PrintJson("子图自定义节点依赖", customNodes);

var run = await client.GraphNode.RunGraphResultAsync(subgraph);
ExampleSettings.PrintStatus("运行子图", run.Status, run.Timestamp);

if (string.Equals(Environment.GetEnvironmentVariable("ATOM_READ_POINT_CLOUD"), "true", StringComparison.OrdinalIgnoreCase))
{
    var clouds = await client.GraphNode.GetPointsDataParsedAsync(
        new SubGraphPortRef(graphName, graphNodeId, innerNodeId, ExampleSettings.PortName, "outputs"));
    Console.WriteLine($"解析子图点云数量：{clouds.Count}");
}

await client.GraphNode.ClearGraphAsync(subgraph);
await client.GraphNode.ReleaseGraphAsync(subgraph);
Console.WriteLine("子图示例完成；外层图和图定义未被删除。");
