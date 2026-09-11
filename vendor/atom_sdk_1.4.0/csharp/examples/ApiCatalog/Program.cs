using AtomSdk;
using AtomSdk.Models;
using AtomSdkExamples;
using System.Text.Json;

// 逐接口示例目录。
// 用法：ApiCatalog <runtime|graph|node|graph-node|input> [baseUrl] [graphName]
var mode = args.Length > 0 ? args[0] : "input";
var baseUrl = args.Length > 1
    ? args[1]
    : ExampleSettings.Get("ATOM_BASE_URL", ExampleSettings.BaseUrl);
var graphName = args.Length > 2
    ? args[2]
    : ExampleSettings.Get("ATOM_GRAPH_NAME", ExampleSettings.GraphName);

try
{
    switch (mode)
    {
        case "runtime":
            await RunRuntimeAsync(baseUrl, graphName);
            break;
        case "graph":
            await RunGraphAsync(baseUrl, graphName);
            break;
        case "node":
            await RunNodeAsync(baseUrl, graphName);
            break;
        case "graph-node":
            await RunGraphNodeAsync(baseUrl, graphName);
            break;
        case "input":
            RunInputFactories();
            break;
        default:
            Console.Error.WriteLine("mode 只能是 runtime、graph、node、graph-node 或 input。");
            return 1;
    }
}
catch (Exception exception)
{
    Console.Error.WriteLine($"C# API 示例失败：{exception.Message}");
    return 2;
}

return 0;

static async Task RunRuntimeAsync(string baseUrl, string graphName)
{
    var client = new AtomClient(baseUrl);
    var loaded = false;
    try
    {
        var graphs = await client.Runtime.ListGraphSummariesAsync();
        Console.WriteLine($"Runtime 图数量：{graphs.Length}");
        ExampleSettings.PrintJson("Runtime 节点定义", await client.Runtime.GetAllNodesInfoAsync());

        var load = await client.Runtime.LoadGraphInfoAsync(graphName);
        loaded = true;
        ExampleSettings.PrintStatus("加载 Runtime 图", load.Status);
        var meta = await client.Runtime.GetMetaInfoModelAsync(graphName);
        ExampleSettings.PrintStatus("读取元信息", meta.Status);
        var outputs = await client.Runtime.GetBindedOutputsInfoModelAsync(graphName);
        ExampleSettings.PrintStatus("读取输出绑定", outputs.Status);

        if (IsEnabled("ATOM_SET_BINDING_DATA"))
        {
            await client.Runtime.SetGraphBindingDataAsync(new RuntimeBindingDataUpdate(
                graphName,
                new Dictionary<string, object?>
                {
                    ["input_image"] = "data:image/jpg;base64,xxx",
                    ["score_threshold"] = 0.5,
                }));
        }

        var bindingName = Environment.GetEnvironmentVariable("ATOM_BINDING_NAME");
        if (!string.IsNullOrWhiteSpace(bindingName))
        {
            var binding = new BindingRef(graphName, bindingName);
            ExampleSettings.PrintJson("绑定值", await client.Runtime.GetBindedOutputValueAsync(binding));
        }

        var pointCloudBindingName = Environment.GetEnvironmentVariable("ATOM_POINT_CLOUD_BINDING_NAME");
        if (!string.IsNullOrWhiteSpace(pointCloudBindingName))
        {
            var binding = new BindingRef(graphName, pointCloudBindingName);
            var rawCloud = await client.Runtime.GetBindedPointCloudAsync(binding);
            Console.WriteLine($"绑定点云原始字节：{rawCloud.Length}");
            var parsedCloud = await client.Runtime.GetBindedPointCloudParsedAsync(
                new PointCloudRef(graphName, pointCloudBindingName, 3));
            Console.WriteLine($"绑定点云解析数量：{parsedCloud.Count}");
        }

        var nodeId = Environment.GetEnvironmentVariable("ATOM_NODE_ID");
        if (!string.IsNullOrWhiteSpace(nodeId))
        {
            var strategy = await client.Runtime.GetNodeParamsInfoWithStrategyAsync(
                new NodeRef(graphName, nodeId));
            ExampleSettings.PrintJson("策略参数", strategy);
            if (strategy.ValueKind == JsonValueKind.Object &&
                strategy.TryGetProperty("paramsData", out var paramsData))
            {
                await client.Runtime.SetParamsInStrategyAsync(
                    new RuntimeStrategyParamsUpdate(graphName, nodeId, paramsData));
            }
        }

        var paramName = Environment.GetEnvironmentVariable("ATOM_FILE_PARAM_NAME");
        if (!string.IsNullOrWhiteSpace(paramName))
        {
            var md5 = await client.Runtime.GetFileParamMd5InfoAsync(
                new FileParamRef(graphName, paramName,
                    ExampleSettings.Get("ATOM_FILE_PARAM_TYPE", "init_params")));
            ExampleSettings.PrintStatus("文件参数 MD5", md5.Status);
            Console.WriteLine($"md5={md5.Md5 ?? "<未返回>"}");
        }
    }
    finally
    {
        if (loaded)
        {
            await client.Runtime.ReleaseGraphAsync(graphName);
        }
    }
}

static async Task RunGraphAsync(string baseUrl, string graphName)
{
    var client = new AtomClient(baseUrl);
    var currentName = graphName;
    var created = await client.Graph.CreateGraphInfoAsync(
        new CreateGraphParams(currentName, "created by C# API catalog"));
    ExampleSettings.PrintStatus("创建图", created.Status, created.Timestamp);

    await client.Graph.OpenGraphInfoAsync(currentName);
    ExampleSettings.PrintJson("编辑态图列表", await client.Graph.ListGraphsAsync());
    ExampleSettings.PrintJson("全部节点定义", await client.Graph.GetAllNodesInfoAsync());
    ExampleSettings.PrintJson("自定义子图列表", await client.Graph.GetAllCustomSubgraphsNoThumbnailAsync());
    ExampleSettings.PrintJson("图绑定", await client.Graph.GetGraphBindingsAsync(currentName));
    ExampleSettings.PrintJson("DL 模型依赖", await client.Graph.GetGraphDlNodesModelInfoAsync(currentName));
    ExampleSettings.PrintJson("自定义节点依赖", await client.Graph.GetGraphCustomNodesAsync(currentName));
    ExampleSettings.PrintJson("Workcell 模型依赖", await client.Graph.GetGraphWorkcellModelsInfoAsync(currentName));
    ExampleSettings.PrintJson("图 JSON", await client.Graph.GetGraphJsonDataAsync(currentName));
    ExampleSettings.PrintJson("图时间戳", await client.Graph.GetTimestampAsync(currentName));
    await client.Graph.EditGraphCommentAsync(new EditGraphCommentParams(currentName, "updated by C# API catalog"));

    var copyName = currentName + "_copy";
    await client.Graph.CopyGraphAsync(new CopyGraphParams(currentName, copyName));
    await client.Graph.DeleteGraphAsync(copyName);

    var atomFile = Environment.GetEnvironmentVariable("ATOM_GRAPH_FILE");
    if (!string.IsNullOrWhiteSpace(atomFile) && File.Exists(atomFile))
    {
        var importedName = currentName + "_imported";
        await client.Graph.LoadGraphResultAsync(new LoadGraphParams(importedName, atomFile));
    }

    if (IsEnabled("ATOM_EXPORT_EXAMPLE_GRAPH"))
    {
        var exported = await client.Graph.ExportGraphResultAsync(new ExportGraphParams(
            currentName,
            new Dictionary<string, object?> { ["detector"] = new { version = "1.0.0" } },
            new Dictionary<string, object?> { ["SdkTestEchoNode"] = new { enableExport = true } }));
        Console.WriteLine($"导出地址：{exported.Url ?? "<未返回>"}");
    }

    if (IsEnabled("ATOM_IMPORT_EXTENSION_NODES"))
    {
        var path = ExampleSettings.Get("ATOM_CUSTOM_NODE_FILE", "/tmp/demo_node.py");
        await client.Graph.ImportExtensionNodesByPathAsync(new ImportExtensionNodesByPathParams(
            new Dictionary<string, object?>
            {
                [path] = new { forceCover = false, newNodes = new[] { "DemoNode" }, existedNodes = Array.Empty<string>() },
            }));
    }

    if (IsEnabled("ATOM_RENAME_EXAMPLE_GRAPH"))
    {
        var renamed = currentName + "_renamed";
        await client.Graph.EditGraphNameAsync(new EditGraphNameParams(currentName, renamed));
        currentName = renamed;
    }

    await client.Graph.RunGraphResultAsync(currentName);
    await client.Graph.ClearGraphTimestampAsync(currentName);
    await client.Graph.ReleaseGraphAsync(currentName);

    if (IsEnabled("ATOM_DELETE_EXAMPLE_GRAPH"))
    {
        await client.Graph.DeleteGraphAsync(currentName);
    }
}

static async Task RunNodeAsync(string baseUrl, string graphName)
{
    var nodeId = Environment.GetEnvironmentVariable("ATOM_NODE_ID");
    if (string.IsNullOrWhiteSpace(nodeId))
    {
        throw new InvalidOperationException("node 模式需要设置 ATOM_NODE_ID。");
    }

    var client = new AtomClient(baseUrl);
    var dynamicNode = await client.Node.CreateDynamicIoNodeInfoAsync(new CreateDynamicNodeParams(
        graphName,
        ExampleSettings.Get("ATOM_DYNAMIC_NODE_NAME", "DynamicIONode"),
        new Dictionary<string, object?>
        {
            ["inputs"] = new[] { new { name = "image_in", dtype = "Image" } },
            ["outputs"] = new[] { new { name = "mask_out", dtype = "BinaryImage" } },
        }));
    var dynamicId = dynamicNode.NodeId ?? throw new InvalidOperationException("动态节点没有返回 nodeId。");
    var copied = await client.Node.CreateNodeByCopyInfoAsync(
        new CopyNodeParams(graphName, "CopiedNode", nodeId));
    var copiedId = copied.NodeId ?? throw new InvalidOperationException("复制节点没有返回 nodeId。");

    await client.Node.ChangeNodeIoAsync(new ChangeNodeIOParams(
        graphName,
        dynamicId,
        new Dictionary<string, object?>
        {
            ["outputs"] = new[] { new { name = "score_out", dtype = "Float" } },
        }));
    var node = new NodeRef(graphName, nodeId);
    ExampleSettings.PrintJson("节点参数", await client.Node.GetNodeParamsAsync(node));
    ExampleSettings.PrintJson("节点详情", await client.Node.GetNodeInfoInGraphAsync(node));
    await client.Node.SetNodeParamDataInfoAsync(new NodeParamUpdate(graphName, nodeId, "threshold", "run_params", 0.5));
    await client.Node.SetBindingNameInfoAsync(new NodeBindingUpdate(
        graphName, nodeId, "outputs", ExampleSettings.PortName, ExampleSettings.BindingName));
    await client.Node.EditNodeCommentAsync(new EditNodeCommentParams(graphName, nodeId, "updated by C# API catalog"));

    if (IsEnabled("ATOM_READ_PORT_DATA"))
    {
        var port = new PortRef(graphName, nodeId, ExampleSettings.PortName, "outputs");
        ExampleSettings.PrintJson("端口数据", await client.Node.GetNodePortDataAsync(port));
        Console.WriteLine($"原始点云字节：{(await client.Node.GetPointsDataAsync(port)).Length}");
        Console.WriteLine($"解析点云数量：{(await client.Node.GetPointsDataParsedAsync(port)).Count}");
        ExampleSettings.PrintJson("下载信息", await client.Node.DownloadDataAsync(port));
    }

    var targetId = Environment.GetEnvironmentVariable("ATOM_TARGET_NODE_ID");
    if (!string.IsNullOrWhiteSpace(targetId))
    {
        var connection = new NodeConnectionParams(
            graphName, nodeId, ExampleSettings.PortName, targetId, ExampleSettings.InputPortName);
        await client.Node.ConnectNodesAsync(connection);
        await client.Node.DisconnectNodesAsync(connection);
    }

    await client.Node.InitialNodeInfoAsync(node);
    await client.Node.ActivateNodeResultAsync(node);
    await client.Node.UpdateNodeResultAsync(node);

    var subGraphName = Environment.GetEnvironmentVariable("ATOM_SUB_GRAPH_NAME");
    if (!string.IsNullOrWhiteSpace(subGraphName))
    {
        await client.Node.CreateGraphNodeInfoAsync(new CreateGraphNodeParams(graphName, "CreatedGraphNode", subGraphName));
    }
    var anotherNodeId = Environment.GetEnvironmentVariable("ATOM_GENERATE_NODE_ID");
    if (!string.IsNullOrWhiteSpace(anotherNodeId))
    {
        await client.Node.GenerateGraphNodeByNodesInfoAsync(
            new GenerateGraphNodeByNodesParams(graphName, "GeneratedGraphNode", new[] { nodeId, anotherNodeId }));
    }

    await client.Node.DeleteNodeInfoAsync(new NodeRef(graphName, copiedId));
    await client.Node.DeleteNodeInfoAsync(new NodeRef(graphName, dynamicId));
}

static async Task RunGraphNodeAsync(string baseUrl, string graphName)
{
    var graphNodeId = Environment.GetEnvironmentVariable("ATOM_GRAPH_NODE_ID");
    if (string.IsNullOrWhiteSpace(graphNodeId))
    {
        throw new InvalidOperationException("graph-node 模式需要设置 ATOM_GRAPH_NODE_ID。");
    }

    var client = new AtomClient(baseUrl);
    var subgraph = new SubGraphRef(graphName, graphNodeId);
    await client.GraphNode.OpenGraphInfoAsync(subgraph);
    ExampleSettings.PrintJson("全部内部节点定义", await client.GraphNode.GetAllNodesInfoAsync());
    ExampleSettings.PrintJson("子图绑定", await client.GraphNode.GetGraphBindingsAsync(subgraph));
    ExampleSettings.PrintJson("子图 DL 模型依赖", await client.GraphNode.GetGraphDlNodesModelInfoAsync(subgraph));
    ExampleSettings.PrintJson("子图自定义节点依赖", await client.GraphNode.GetGraphCustomNodesAsync(subgraph));

    var inner = await client.GraphNode.CreateNodeInfoAsync(
        new SubGraphCreateNodeParams(graphName, graphNodeId, ExampleSettings.NodeName));
    var innerId = inner.NodeId ?? throw new InvalidOperationException("内部节点没有返回 nodeId。");
    var innerRef = new SubGraphNodeRef(graphName, graphNodeId, innerId);
    var dynamic = await client.GraphNode.CreateDynamicIoNodeInfoAsync(new CreateDynamicSubGraphNodeParams(
        graphName, graphNodeId, "DynamicInnerNode",
        new Dictionary<string, object?>
        {
            ["inputs"] = new[] { new { name = "prompt", dtype = "String" } },
            ["outputs"] = new[] { new { name = "mask_out", dtype = "BinaryImage" } },
        }));
    var copy = await client.GraphNode.CreateNodeByCopyInfoAsync(
        new SubGraphCopyNodeParams(graphName, graphNodeId, "CopiedInnerNode", innerId));

    await client.GraphNode.ChangeNodeIoAsync(new ChangeSubGraphNodeIOParams(
        graphName, graphNodeId, innerId,
        new Dictionary<string, object?>
        {
            ["outputs"] = new[] { new { name = "score_out", dtype = "Float" } },
        }));
    ExampleSettings.PrintJson("内部节点参数", await client.GraphNode.GetNodeParamsAsync(innerRef));
    ExampleSettings.PrintJson("内部节点详情", await client.GraphNode.GetNodeInfoInGraphAsync(innerRef));
    await client.GraphNode.SetNodeParamDataInfoAsync(
        new SubGraphNodeParamUpdate(graphName, graphNodeId, innerId, "threshold", "run_params", 0.4));
    await client.GraphNode.SetBindingNameInfoAsync(new SubGraphBindingUpdate(
        graphName, graphNodeId, innerId, "outputs", ExampleSettings.PortName, ExampleSettings.BindingName));
    await client.GraphNode.EditNodeCommentAsync(new EditSubGraphNodeCommentParams(
        graphName, graphNodeId, innerId, "updated by C# API catalog"));

    if (IsEnabled("ATOM_READ_PORT_DATA"))
    {
        var port = new SubGraphPortRef(graphName, graphNodeId, innerId, ExampleSettings.PortName, "outputs");
        ExampleSettings.PrintJson("内部端口数据", await client.GraphNode.GetNodePortDataAsync(port));
        Console.WriteLine($"内部原始点云字节：{(await client.GraphNode.GetPointsDataAsync(port)).Length}");
        Console.WriteLine($"内部解析点云数量：{(await client.GraphNode.GetPointsDataParsedAsync(port)).Count}");
        ExampleSettings.PrintJson("内部下载信息", await client.GraphNode.DownloadDataAsync(port));
    }

    var targetInnerId = Environment.GetEnvironmentVariable("ATOM_INNER_TARGET_NODE_ID");
    if (!string.IsNullOrWhiteSpace(targetInnerId))
    {
        var connection = new SubGraphConnectionParams(
            graphName, graphNodeId, innerId, ExampleSettings.PortName, targetInnerId, ExampleSettings.InputPortName);
        await client.GraphNode.ConnectNodesAsync(connection);
        await client.GraphNode.DisconnectNodesAsync(connection);
    }

    await client.GraphNode.InitialNodeInfoAsync(innerRef);
    await client.GraphNode.ActivateNodeResultAsync(innerRef);
    await client.GraphNode.UpdateNodeResultAsync(innerRef);
    await client.GraphNode.RunGraphResultAsync(subgraph);

    if (IsEnabled("ATOM_EXPORT_EXAMPLE_GRAPH"))
    {
        await client.GraphNode.ExportGraphResultAsync(new ExportSubGraphParams(graphName, graphNodeId));
    }
    if (IsEnabled("ATOM_SAVE_CUSTOM_SUBGRAPH"))
    {
        await client.GraphNode.SetSubgraphAsCustomSubgraphAsync(
            new SetSubgraphAsCustomSubgraphParams(graphName, graphNodeId, "custom_subgraph_template"));
    }

    await client.GraphNode.ClearGraphAsync(subgraph);
    await client.GraphNode.DeleteNodeInfoAsync(innerRef);
    if (!string.IsNullOrWhiteSpace(copy.NodeId))
    {
        await client.GraphNode.DeleteNodeInfoAsync(new SubGraphNodeRef(graphName, graphNodeId, copy.NodeId));
    }
    if (!string.IsNullOrWhiteSpace(dynamic.NodeId))
    {
        await client.GraphNode.DeleteNodeInfoAsync(new SubGraphNodeRef(graphName, graphNodeId, dynamic.NodeId));
    }
    await client.GraphNode.ReleaseGraphAsync(subgraph);
}

static void RunInputFactories()
{
    // 普通模式：本地把点云和图像编码为 EPICRAW2，再交给 RuntimeRunParams。
    var points = new RuntimePointData(
        new[] { 0.0F, 0.0F, 1.0F, 0.1F, 0.0F, 1.0F, 0.0F, 0.1F, 1.0F, 0.1F, 0.1F, 1.0F },
        2,
        2);
    var image = new RuntimeImageData(new byte[12], 2, 2);
    var frame = RuntimeFrame.FromData(
        points,
        image,
        ExampleSettings.IdentityTransform,
        new[] { 1000.0, 0.0, 1.0, 0.0, 1000.0, 1.0, 0.0, 0.0, 1.0 },
        new[] { 0.0, 0.0, 0.0, 0.0, 0.0 });
    Console.WriteLine($"普通 EPICRAW 字节：{frame.EpicRaw.Length}");
    Console.WriteLine($"普通运行参数：{new RuntimeRunParams(ExampleSettings.GraphName, new[] { frame }).RunMode}");

    var epicRawPath = Environment.GetEnvironmentVariable("ATOM_EPICRAW_FILE");
    if (!string.IsNullOrWhiteSpace(epicRawPath) && File.Exists(epicRawPath))
    {
        var fromFile = RuntimeFrame.FromFile(epicRawPath, ExampleSettings.IdentityTransform);
        var fromBytes = RuntimeFrame.FromBytes(File.ReadAllBytes(epicRawPath), ExampleSettings.IdentityTransform);
        Console.WriteLine($"FromFile 字节：{fromFile.EpicRaw.Length}，FromBytes 字节：{fromBytes.EpicRaw.Length}");
    }

    // passive_bino 模式：图像顺序必须是 DepthSrc1、DepthSrc2、TextureSrc。
    var camera = new
    {
        CameraMatrix = new[] { 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0 },
        CameraDistortion = new[] { 0.0, 0.0, 0.0, 0.0, 0.0 },
        CameraRotation = new[] { 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0 },
        CameraTranslation = new[] { 0.0, 0.0, 0.0 },
    };
    var images = new[]
    {
        new RuntimePassiveBinoImage(new byte[4], 2, 2, 0),
        new RuntimePassiveBinoImage(new byte[4], 2, 2, 0),
        new RuntimePassiveBinoImage(new byte[12], 2, 2, 16),
    };
    var passive = RuntimeRunParams.PassiveBinoFromImages(
        ExampleSettings.GraphName,
        images,
        new { DepthSrc1 = camera, DepthSrc2 = camera, TextureSrc = camera },
        ExampleSettings.IdentityTransform);
    Console.WriteLine($"passive_bino EPICRAW3 字节：{passive.PassiveBinoFrame?.EpicRaw3.Length ?? 0}");
}

static bool IsEnabled(string name)
{
    var value = Environment.GetEnvironmentVariable(name);
    return string.Equals(value, "1", StringComparison.OrdinalIgnoreCase) ||
           string.Equals(value, "true", StringComparison.OrdinalIgnoreCase);
}
