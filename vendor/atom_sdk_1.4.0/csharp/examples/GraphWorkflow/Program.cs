using AtomSdk;
using AtomSdk.Models;
using AtomSdkExamples;

// 主图编辑态流程。此示例会创建节点并修改图，请使用测试图名运行。
var graphName = ExampleSettings.ArgumentOrSetting(args, 0, "ATOM_GRAPH_NAME", "csharp_sdk_example_graph");
var baseUrl = ExampleSettings.ArgumentOrSetting(args, 1, "ATOM_BASE_URL", ExampleSettings.BaseUrl);
var client = new AtomClient(baseUrl);

var createdGraph = await client.Graph.CreateGraphInfoAsync(
    new CreateGraphParams(graphName, "created by C# SDK example"));
ExampleSettings.PrintStatus("创建图", createdGraph.Status, createdGraph.Timestamp);

var opened = await client.Graph.OpenGraphInfoAsync(graphName);
ExampleSettings.PrintStatus("打开图", opened.Status, opened.Timestamp);

var source = await client.Node.CreateNodeInfoAsync(new CreateNodeParams(graphName, ExampleSettings.NodeName));
var target = await client.Node.CreateNodeInfoAsync(new CreateNodeParams(graphName, ExampleSettings.TargetNodeName));
var sourceId = source.NodeId ?? throw new InvalidOperationException("创建源节点后没有返回 nodeId。");
var targetId = target.NodeId ?? throw new InvalidOperationException("创建目标节点后没有返回 nodeId。");
Console.WriteLine($"创建节点：source={sourceId}, target={targetId}");

// 动态 IO 节点的 nodeData 结构由具体节点类型决定，这里演示最小写法。
var dynamicNode = await client.Node.CreateDynamicIoNodeInfoAsync(
    new CreateDynamicNodeParams(
        graphName,
        "DynamicIONode",
        new Dictionary<string, object?>
        {
            ["inputs"] = new[] { new Dictionary<string, object?> { ["name"] = "image_in", ["dtype"] = "Image" } },
            ["outputs"] = new[] { new Dictionary<string, object?> { ["name"] = "mask_out", ["dtype"] = "BinaryImage" } },
        }));
Console.WriteLine($"创建动态 IO 节点：{dynamicNode.NodeId}");

await client.Node.ConnectNodesInfoAsync(new NodeConnectionParams(
    graphName,
    sourceId,
    ExampleSettings.PortName,
    targetId,
    ExampleSettings.InputPortName));

var sourceRef = new NodeRef(graphName, sourceId);
var paramsSnapshot = await client.Node.GetNodeParamsSnapshotAsync(sourceRef);
Console.WriteLine($"节点参数：init_params={paramsSnapshot.InitParams.ValueKind}, run_params={paramsSnapshot.RunParams.ValueKind}");

var nodeInfo = await client.Node.GetNodeInfoInGraphModelAsync(sourceRef);
ExampleSettings.PrintStatus("读取节点详情", nodeInfo.Status, nodeInfo.Timestamp);

await client.Node.SetNodeParamDataInfoAsync(
    new NodeParamUpdate(graphName, sourceId, "threshold", "run_params", 0.5));
await client.Node.EditNodeCommentAsync(
    new EditNodeCommentParams(graphName, sourceId, "updated by C# SDK example"));
await client.Node.SetBindingNameInfoAsync(new NodeBindingUpdate(
    graphName,
    sourceId,
    "outputs",
    ExampleSettings.PortName,
    ExampleSettings.BindingName));

var bindings = await client.Graph.GetGraphBindingsInfoAsync(graphName);
ExampleSettings.PrintStatus("读取图绑定", bindings.Status);

var run = await client.Graph.RunGraphResultAsync(graphName);
ExampleSettings.PrintStatus("运行编辑态主图", run.Status, run.Timestamp);

// 如果端口确实输出点云，可以打开下面这段读取解析结果；端口名需按自己的节点配置。
if (string.Equals(Environment.GetEnvironmentVariable("ATOM_READ_POINT_CLOUD"), "true", StringComparison.OrdinalIgnoreCase))
{
    var clouds = await client.Node.GetPointsDataParsedAsync(
        new PortRef(graphName, sourceId, ExampleSettings.PortName, "outputs"));
    Console.WriteLine($"解析点云数量：{clouds.Count}");
}

await client.Graph.ClearGraphTimestampAsync(graphName);
await client.Graph.ReleaseGraphAsync(graphName);
Console.WriteLine("主图示例完成；图定义未被删除。");
