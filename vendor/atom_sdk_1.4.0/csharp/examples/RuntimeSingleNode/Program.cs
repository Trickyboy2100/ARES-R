using AtomSdk;
using AtomSdk.Models;
using AtomSdkExamples;

// 单节点直跑不需要先加载一张图。
var nodeName = ExampleSettings.ArgumentOrSetting(args, 0, "ATOM_SINGLE_NODE_NAME", ExampleSettings.SingleNodeName);
var baseUrl = ExampleSettings.ArgumentOrSetting(args, 1, "ATOM_BASE_URL", ExampleSettings.BaseUrl);
var imageBytes = ExampleSettings.OptionalFileBytes("ATOM_IMAGE_FILE", "replace-with-real-image-bytes");
var mode = ExampleSettings.Get("ATOM_SINGLE_NODE_MODE", "parsed").ToLowerInvariant();
var client = new AtomClient(baseUrl);

var input = new Dictionary<string, object?>
{
    // 如果节点的真实输入端口不是 image，请设置 ATOM_SINGLE_NODE_INPUT_NAME。
    [ExampleSettings.Get("ATOM_SINGLE_NODE_INPUT_NAME", "image")] = imageBytes,
};
var parameters = new SingleNodeParams(
    nodeName,
    input,
    runParams: new Dictionary<string, object?> { ["threshold"] = 0.5 },
    initParams: new Dictionary<string, object?> { ["device"] = "cuda:0" });

switch (mode)
{
    case "raw":
    {
        // 原始接口同时兼容 JSON 和二进制，适合调试服务端真实返回。
        var raw = await client.Runtime.RunSingleNodeNoGraphAsync(parameters);
        if (raw.IsBinary)
        {
            Console.WriteLine($"原始结果是二进制：{raw.BinaryData!.Length} bytes");
        }
        else
        {
            ExampleSettings.PrintJson("原始 JSON 结果", raw.JsonData!.Value);
        }

        break;
    }
    case "json":
    {
        // 已经知道服务端返回是 JSON 时，可以用强类型结果，避免手动读取字段。
        var jsonResult = await client.Runtime.RunSingleNodeNoGraphJsonAsync<RuntimeSingleNodeJsonResult>(parameters);
        ExampleSettings.PrintStatus("强类型 JSON 结果", jsonResult.Status);
        Console.WriteLine($"JSON 输出数量：{jsonResult.Outputs.Count}");
        break;
    }
    case "parsed":
    {
        // 推荐业务代码使用 Parsed 接口：点云、图片会按输出端口类型解析，输出键名保持不变。
        // 若节点返回的 output 不是点云/图片，也会保留原始 JSON 值。
        var parsed = await client.Runtime.RunSingleNodeNoGraphParsedAsync(new SingleNodeParams(
            nodeName,
            input,
            outputDataTypes: new Dictionary<string, string>
            {
                [ExampleSettings.Get("ATOM_OUTPUT_NAME", "preview")] = "ColorImage",
            }));
        Console.WriteLine($"解析后的输出数量：{parsed.Outputs.Count}");
        Console.WriteLine($"原始 JSON 是否存在：{parsed.RawJsonData.HasValue}");
        Console.WriteLine($"原始二进制大小：{parsed.RawBinaryData?.Length ?? 0} bytes");
        break;
    }
    default:
        throw new ArgumentException("ATOM_SINGLE_NODE_MODE 只能是 raw、json 或 parsed。", nameof(mode));
}
