// 作用：查询 Stream2D 状态并启动一个由 SDK 托管的 WebRTC 会话。
// 输入：可选 camera_ip 和接收帧数；fps 只透传给相机接口，SDK 不做节流或丢帧。
// 输出：回调直接收到相机输出的 Annex-B H264 编码数据；不解码、不重新编码。
// 生命周期：Example 达到目标帧数后调用 StopStream2DRtcSession；相机不支持视频流时连接可能超时。

using TFTech;
using TFTech.Models;

Console.WriteLine("SDK Version: " + EpicEye.GetSDKVersion());

string ip = ResolveIp(args);
if (ip.Length == 0)
{
    Environment.ExitCode = 1;
    return;
}
Console.WriteLine("Using IP: " + ip);

// 查询 2D 流状态
Console.WriteLine("---------------getStream2DStatus---------------");
var status = EpicEye.GetStream2DStatus(ip);
if (status.Status == 0 && status.Data != null)
{
    Console.WriteLine($"isStreaming: {status.Data.IsStreaming}");
    Console.WriteLine($"peerCount: {status.Data.PeerCount}");
    Console.WriteLine($"cameraCount: {status.Data.CameraCount}");
}
else
{
    Console.WriteLine("getStream2DStatus failed!");
}

// 启动 RTC 会话。接收 5 帧后由 Example 主动停止，SDK 本身不限制帧数。
Console.WriteLine("\n---------------startStream2DRtcSession---------------");
const int targetFrameCount = 5;
var targetReached = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
var result = await EpicEye.StartStream2DRtcSessionAsync(
    ip,
    onFrame: frame =>
    {
        Console.WriteLine($"Frame #{frame.FrameIndex} timestamp: {frame.Timestamp} " +
                          $"codec: {frame.Codec} pt: {frame.PayloadType} size: {frame.Payload.Length} bytes");
        if (frame.FrameIndex >= targetFrameCount)
        {
            targetReached.TrySetResult();
        }
    },
    fps: 60,
    cameraIndex: 0);

if (result.Status == 0 && result.Data != null)
{
    await using var session = result.Data;
    try
    {
        await targetReached.Task.WaitAsync(TimeSpan.FromSeconds(15));
    }
    catch (TimeoutException)
    {
        Console.WriteLine("No 5 frames were received within 15 seconds.");
        Environment.ExitCode = 1;
    }
    await EpicEye.StopStream2DRtcSessionAsync(session);
    Console.WriteLine($"Session stopped. Total frames: {session.FrameCount}");
}
else
{
    Console.WriteLine("startStream2DRtcSession failed: " + result.ErrorMessage);
    Environment.ExitCode = 1;
}

// 会话关闭后再看一次状态
Console.WriteLine("\n---------------getStream2DStatus (after session)---------------");
var statusAfter = EpicEye.GetStream2DStatus(ip);
if (statusAfter.Status == 0 && statusAfter.Data != null)
{
    Console.WriteLine($"isStreaming: {statusAfter.Data.IsStreaming}");
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
