// 作用：一次下载 EpicRaw，区分完整 SDK 获取耗时和响应体网络传输耗时，再从同一文档解码深度图。
// 输入：可选 camera_ip；未指定时阻塞搜索并使用第一台相机。
// 输出：字节数、网络耗时、下载速率、完整调用耗时和深度图尺寸；不会为统计重复下载帧。
// 相机影响：读取当前帧数据，不修改相机配置。

using SixLabors.ImageSharp;
using TFTech;

string ip = ResolveIp(args);
if (ip.Length == 0)
{
    Environment.ExitCode = 1;
    return;
}
Console.WriteLine("Using IP: " + ip);

// 触发拍摄
Console.WriteLine("---------------triggerCapture---------------");
var trig = EpicEye.TriggerCapture(ip, withPointCloud: true);
if (trig.Status != 0 || string.IsNullOrEmpty(trig.Data))
{
    Console.WriteLine("triggerCapture failed!");
    Environment.ExitCode = 1;
    return;
}
string frameId = trig.Data;
Console.WriteLine("frameId: " + frameId);

Console.WriteLine("---------------getFrameInEpicRawWithTimeStats---------------");
var (rawBytes, networkTransmitTimeMs, networkSpeedMbps) =
    EpicEye.GetFrameInEpicRawWithTimeStats(ip, frameId);
if (rawBytes is null
    || !EpicEye.TryLoadEpicRawDocumentFromBytes(rawBytes, out var document)
    || document is null)
{
    Console.WriteLine("getFrameInEpicRaw failed!");
    Environment.ExitCode = 1;
    return;
}

var (depthBytes, dw, dh) = EpicEye.DecodeDepthFromEpicRaw(document);
if (depthBytes == null || dw is not int w || dh is not int h)
{
    Console.WriteLine("decodeDepthFromEpicRaw failed!");
    Environment.ExitCode = 1;
    return;
}

Console.WriteLine($"Depth: {w}x{h}, {depthBytes.Length} bytes");
Console.WriteLine($"Network transmit time: {networkTransmitTimeMs:F2} ms");
Console.WriteLine($"Network speed: {networkSpeedMbps:F2} Mbps");

// float32 深度 → 归一化灰度 PNG
float[] depth = new float[depthBytes.Length / sizeof(float)];
Buffer.BlockCopy(depthBytes, 0, depth, 0, depthBytes.Length);
SaveDepthGreyPng(depth, w, h, "depth_grey.png");
Console.WriteLine("saved: depth_grey.png");

Console.WriteLine("Done.");

// ================= 辅助函数 =================

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

static void SaveDepthGreyPng(float[] depth, int width, int height, string path)
{
    float min = float.MaxValue, max = 0f;
    foreach (var v in depth) { if (v > max) max = v; if (v < min) min = v; }
    float range = max - min;
    if (range <= 0f) range = 1f;
    var grey = new SixLabors.ImageSharp.PixelFormats.L8[width * height];
    for (int i = 0; i < depth.Length; i++)
        grey[i] = new SixLabors.ImageSharp.PixelFormats.L8((byte)Math.Round((depth[i] - min) / range * 255));
    using var img = SixLabors.ImageSharp.Image.LoadPixelData<SixLabors.ImageSharp.PixelFormats.L8>(grey, width, height);
    img.Save(path);
}
