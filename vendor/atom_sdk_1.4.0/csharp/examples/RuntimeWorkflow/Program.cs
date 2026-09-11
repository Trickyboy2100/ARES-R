using AtomSdk;
using AtomSdk.Models;
using AtomSdkExamples;

// 运行时完整流程：加载图 -> 读取元信息 -> 设置参数 -> 执行 -> 读取输出 -> 释放。
// 第一个参数是图名，第二个参数是服务地址；不传时读取环境变量。
var graphName = ExampleSettings.ArgumentOrSetting(args, 0, "ATOM_GRAPH_NAME", ExampleSettings.GraphName);
var baseUrl = ExampleSettings.ArgumentOrSetting(args, 1, "ATOM_BASE_URL", ExampleSettings.BaseUrl);
var epicRawPath = Environment.GetEnvironmentVariable("ATOM_EPICRAW_FILE");

if (string.IsNullOrWhiteSpace(epicRawPath) || !File.Exists(epicRawPath))
{
    throw new InvalidOperationException("运行此示例需要设置 ATOM_EPICRAW_FILE，并指向真实的 EPICRAW 文件。");
}

var client = new AtomClient(baseUrl);
var loadedGraph = false;
try
{
    var graphs = await client.Runtime.ListGraphSummariesAsync();
    Console.WriteLine($"运行时图数量：{graphs.Length}");

    var loaded = await client.Runtime.LoadGraphInfoAsync(graphName);
    loadedGraph = true;
    ExampleSettings.PrintStatus("加载图", loaded.Status);

    var meta = await client.Runtime.GetMetaInfoModelAsync(graphName);
    ExampleSettings.PrintStatus("读取元信息", meta.Status);
    Console.WriteLine($"共享参数：{meta.SharedParams.Count} 个，运行参数：{meta.RuntimeParams.Count} 个");

    await client.Runtime.SetSharedParamsAsync(new RuntimeParamsUpdate(graphName, new
    {
        camera_id = "cam-01",
    }));
    await client.Runtime.SetRunParamsAsync(new RuntimeParamsUpdate(graphName, new
    {
        threshold = 0.7,
    }));

    var frame = RuntimeFrame.FromFile(
        epicRawPath,
        ExampleSettings.IdentityTransform,
        ExampleSettings.DefaultRoi);
    var runResult = await client.Runtime.RunGraphResultAsync(
        new RuntimeRunParams(graphName, new[] { frame }));
    ExampleSettings.PrintStatus("执行运行时图", runResult.Status);
    Console.WriteLine($"ProStatus：{runResult.ProStatus ?? "<未返回>"}");

    var outputs = await client.Runtime.GetBindedOutputsInfoModelAsync(graphName);
    ExampleSettings.PrintStatus("读取输出绑定说明", outputs.Status);
    foreach (var output in outputs.Outputs)
    {
        Console.WriteLine($"输出绑定：{output.BindingName}, 类型={output.DataType}");
    }

    // 如果知道绑定名，可以直接读取绑定值；点云则优先使用解析后的接口。
    var bindingName = Environment.GetEnvironmentVariable("ATOM_BINDING_NAME");
    if (!string.IsNullOrWhiteSpace(bindingName))
    {
        var value = await client.Runtime.GetBindedOutputValueAsync(
            new BindingRef(graphName, bindingName));
        ExampleSettings.PrintJson("绑定值", value);
    }

    // passive_bino 模式需要 EPICRAW3 文件。设置 ATOM_EPICRAW3_FILE 后才会执行这一步。
    var epicRaw3Path = Environment.GetEnvironmentVariable("ATOM_EPICRAW3_FILE");
    if (!string.IsNullOrWhiteSpace(epicRaw3Path) && File.Exists(epicRaw3Path))
    {
        var passiveBinoParams = RuntimeRunParams.PassiveBinoFromFile(
            graphName,
            epicRaw3Path,
            ExampleSettings.IdentityTransform,
            ExampleSettings.DefaultRoi);
        var passiveResult = await client.Runtime.RunGraphResultAsync(passiveBinoParams);
        ExampleSettings.PrintStatus("执行 passive_bino 图", passiveResult.Status);
    }
}
finally
{
    // 释放运行时图，不删除服务器上的图定义。
    if (loadedGraph)
    {
        await client.Runtime.ReleaseGraphAsync(graphName);
    }
}
