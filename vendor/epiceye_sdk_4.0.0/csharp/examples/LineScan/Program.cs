// 作用：演示完整线扫生命周期：查询状态 -> 启动 -> 等待 EOT 完成 -> 查询最终状态。
// 输入：可选 camera_ip；仅支持配置为摆动线扫或固定线扫的相机。
// 清理规则：正常完成后不主动 Stop；超时、取消或异常时才调用 Stop，避免留下活动任务。
// 相机影响：会启动真实线扫运动/采集，请确认设备周围安全且线扫参数已正确配置。
using TFTech;

Console.WriteLine("SDK Version: " + EpicEye.GetSDKVersion());

string ip = ResolveIp(args);
if (ip.Length == 0)
{
    Environment.ExitCode = 1;
    return;
}
Console.WriteLine("Using IP: " + ip);

// 查询线扫状态
Console.WriteLine("---------------getLineScanStatus---------------");
var status = EpicEye.GetLineScanStatus(ip);
if (status == null || status.Status != 0)
{
    Console.WriteLine("getLineScanStatus failed!");
    Environment.ExitCode = 1;
    return;
}
Console.WriteLine($"status: {status.Data}");

// 启动线扫
Console.WriteLine("\n---------------startLineScan---------------");
var start = EpicEye.StartLineScan(ip, enableTexture: false);
if (start == null || start.Status != 0 || start.Data == null)
{
    Console.WriteLine("startLineScan failed!");
    Environment.ExitCode = 1;
    return;
}
Console.WriteLine($"startLineScan success! frameId: {start.Data.FrameId}");

// 阻塞等待线扫完成
Console.WriteLine("\n---------------waitLineScanCompletion---------------");
var wait = EpicEye.WaitLineScanCompletion(ip, timeoutMs: 60000);
if (wait != null && wait.Status == 0 && wait.Data)
{
    Console.WriteLine("LineScan completed!");

    byte[]? epicRawBytes = EpicEye.GetFrameInEpicRaw(ip, start.Data.FrameId, timeout: 30_000);
    if (epicRawBytes is not { Length: > 0 })
    {
        Console.Error.WriteLine("getFrameInEpicRaw failed after LineScan completion!");
        Environment.ExitCode = 1;
        return;
    }
    Console.WriteLine($"EpicRaw bytes: {epicRawBytes.Length}");
}
else
{
    Console.WriteLine("waitLineScanCompletion timed out!");

    // 超时则手动停止
    Console.WriteLine("\n---------------stopLineScan---------------");
    var stop = EpicEye.StopLineScan(ip);
    if (stop != null && stop.Status == 0 && stop.Data != null)
    {
        Console.WriteLine("stopLineScan success! status: " + stop.Data.Status);
    }
    else
    {
        Console.WriteLine("stopLineScan failed!");
    }
    Environment.ExitCode = 1;
}

// 最终状态
Console.WriteLine("\n---------------getLineScanStatus (final)---------------");
var finalStatus = EpicEye.GetLineScanStatus(ip);
if (finalStatus != null && finalStatus.Status == 0)
{
    Console.WriteLine($"status: {finalStatus.Data}");
}

Console.WriteLine("\nDone.");

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
