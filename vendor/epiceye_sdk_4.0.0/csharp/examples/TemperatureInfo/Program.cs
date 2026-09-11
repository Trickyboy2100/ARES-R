// 作用：读取 V4 相机内部各温度传感器的当前值。
// 输入：可选 camera_ip；未指定时阻塞搜索并使用第一台相机。
// 输出：服务端返回的温度名称和值；不同型号的键可能不同，不应在业务代码中写死键集合。
// 相机影响：只读，不触发拍摄，不修改相机配置。

using TFTech;

string ip = ResolveIp(args);
if (ip.Length == 0)
{
    Environment.ExitCode = 1;
    return;
}

Console.WriteLine($"Camera: {ip}");
var response = await EpicEye.GetTemperatureInfoAsync(ip);
if (response.Status != 0 || response.Data is null)
{
    Console.WriteLine($"GetTemperatureInfo failed: {response.ErrorMessage}");
    Environment.ExitCode = 1;
    return;
}

foreach (var item in response.Data)
{
    string value = item.Value?.ToString() ?? "N/A";
    string unit = item.Key.EndsWith("_celsius", StringComparison.Ordinal) && item.Value is not null ? " °C" : string.Empty;
    Console.WriteLine($"{item.Key}: {value}{unit}");
}

static string ResolveIp(string[] args)
{
    if (args.Length > 0 && !string.IsNullOrWhiteSpace(args[0]))
    {
        return args[0];
    }

    var cameras = EpicEye.SearchCamera();
    if (cameras.Count == 0 || string.IsNullOrWhiteSpace(cameras[0].IP))
    {
        Console.WriteLine("Camera not found!");
        return string.Empty;
    }
    return cameras[0].IP!;
}
