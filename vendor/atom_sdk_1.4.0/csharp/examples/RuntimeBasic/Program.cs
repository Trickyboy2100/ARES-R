using System;
using AtomSdk;
using AtomSdk.Models;

var baseUrl = GetSetting("ATOM_BASE_URL", "http://127.0.0.1:10026");
var graphName = GetSetting("ATOM_GRAPH_NAME", "demo_graph");
var graphNodeId = GetSetting("ATOM_GRAPH_NODE_ID", "graph-node-id");
var nodeName = GetSetting("ATOM_NODE_NAME", "DemoNode");
var epicRaw = ReadRequiredFile("ATOM_EPICRAW_FILE");
var imageBytes = ReadRequiredFile("ATOM_IMAGE_FILE");
var client = new AtomClient(baseUrl);

Console.WriteLine("0. 先看看编辑态图列表");
var graphSummaries = await client.Graph.ListGraphSummariesAsync();
Console.WriteLine($"graph count: {graphSummaries.Length}");

Console.WriteLine("0.1 也可以直接在图里创建和操作节点");
var createdNode = await client.Node.CreateNodeInfoAsync(new CreateNodeParams(graphName, nodeName));
Console.WriteLine($"created node: {createdNode.NodeId}, status={createdNode.Status}");

Console.WriteLine("0.2 如果某个节点本身是子图，还可以继续深入到子图内部");
var subgraph = await client.GraphNode.OpenGraphInfoAsync(new SubGraphRef(graphName, graphNodeId));
Console.WriteLine(subgraph.Graph);

Console.WriteLine("1. 获取运行时图列表");
var graphs = await client.Runtime.ListGraphsAsync();
Console.WriteLine(graphs);

Console.WriteLine("2. 加载图");
var loadResult = await client.Runtime.LoadGraphAsync<RuntimeGraphReference>(graphName);
Console.WriteLine($"loaded graph: {loadResult.GraphName}, status={loadResult.Status}");

Console.WriteLine("3. 查看图的运行时元信息");
var metaInfo = await client.Runtime.GetMetaInfoModelAsync(graphName);
Console.WriteLine($"shared params count: {metaInfo.SharedParams.Count}");
Console.WriteLine($"runtime params count: {metaInfo.RuntimeParams.Count}");

Console.WriteLine("4. 根据需要设置共享参数和运行参数");
await client.Runtime.SetSharedParamsAsync(new RuntimeParamsUpdate(graphName, new
{
    camera_id = "cam-01",
}));

await client.Runtime.SetRunParamsAsync(new RuntimeParamsUpdate(graphName, new
{
    threshold = 0.8,
}));

Console.WriteLine("5. 构造一帧运行时输入并执行图");
var frame = RuntimeFrame.FromBytes(
    epicRaw: epicRaw,
    // cam2Base 服务端目前只支持旋转矢量形式：[x, y, z, rx, ry, rz]（平移 + Rodrigues 旋转向量）
    cam2Base: new[] { 0.0, 0.0, 0.0, 0.0, 0.0, 0.0 },
    roi: new
    {
        min = new { x = 0, y = 0, z = 0 },
        max = new { x = 100, y = 100, z = 100 },
        cam2ROIFrame = new[] { 0.0, 0.0, 0.0, 0.0, 0.0, 0.0 },
    });
var runResult = await client.Runtime.RunGraphAsync<RuntimeRunGraphResult>(new RuntimeRunParams(graphName, new[] { frame }));
Console.WriteLine($"run graph: {runResult.ProStatus}, status={runResult.Status}");

Console.WriteLine("6. 如果图上有输出绑定，还可以继续读取输出结果");
var outputsInfo = await client.Runtime.GetBindedOutputsInfoAsync(graphName);
Console.WriteLine(outputsInfo);

Console.WriteLine("6.1 也可以直接执行单个节点，不先创建图");
var singleNodeResult = await client.Runtime.RunSingleNodeNoGraphAsync(
    new SingleNodeParams(
        nodeName,
        new Dictionary<string, object?>
        {
            ["image"] = imageBytes,
            ["scoreThreshold"] = 0.5,
        },
        new Dictionary<string, object?>
        {
            ["mode"] = "fast",
        },
        new Dictionary<string, object?>
        {
            ["modelName"] = "demo-model",
        }));

if (singleNodeResult.IsBinary)
{
    Console.WriteLine($"Single node binary bytes: {singleNodeResult.BinaryData!.Length}");
}
else
{
    Console.WriteLine(singleNodeResult.JsonData!.Value);
    Console.WriteLine($"single node status: {singleNodeResult.JsonData.Value.GetProperty("status").GetInt32()}");
}

var singleNodeJson = await client.Runtime.RunSingleNodeNoGraphJsonAsync<RuntimeSingleNodeJsonResult>(
    new SingleNodeParams(
        nodeName,
        new Dictionary<string, object?>
        {
            ["image"] = imageBytes,
        }));
Console.WriteLine($"single node typed status: {singleNodeJson.Status}");
Console.WriteLine(singleNodeJson.Outputs);

Console.WriteLine("7. 用完后释放图");
var releaseResult = await client.Runtime.ReleaseGraphAsync(graphName);
Console.WriteLine(releaseResult);

static string GetSetting(string name, string fallback)
{
    return string.IsNullOrWhiteSpace(Environment.GetEnvironmentVariable(name))
        ? fallback
        : Environment.GetEnvironmentVariable(name)!;
}

static byte[] ReadRequiredFile(string variableName)
{
    var path = Environment.GetEnvironmentVariable(variableName);
    if (string.IsNullOrWhiteSpace(path) || !File.Exists(path))
    {
        throw new InvalidOperationException(
            $"Set {variableName} to an existing input file before running this example.");
    }

    return File.ReadAllBytes(path);
}
