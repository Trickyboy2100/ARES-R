// 作用：触发一次拍摄，按 frameId 下载一份 EpicRaw，并从同一文档解码图像、深度和点云。
// 输入：可选 camera_ip；未指定时阻塞搜索并使用第一台相机。
// 关键点：frameId 把触发与取帧绑定，避免读取到其他拍摄产生的帧。
// 相机影响：触发一次拍摄；不修改相机配置。

using TFTech;

Console.WriteLine("SDK Version: " + EpicEye.GetSDKVersion());

string ip = ResolveIp(args);
if (ip.Length == 0)
{
    Environment.ExitCode = 1;
    return;
}

Console.WriteLine("Using IP: " + ip);
var trigger = EpicEye.TriggerCapture(ip, withPointCloud: true);
if (trigger.Status != 0 || string.IsNullOrEmpty(trigger.Data))
{
    Console.WriteLine("triggerCapture failed!");
    Environment.ExitCode = 1;
    return;
}

var (rawBytes, transmitTimeMs, speedMbps) =
    EpicEye.GetFrameInEpicRawWithTimeStats(ip, trigger.Data);
if (rawBytes is null
    || !EpicEye.TryLoadEpicRawDocumentFromBytes(rawBytes, out var document)
    || document is null)
{
    Console.WriteLine("getFrameInEpicRaw failed!");
    Environment.ExitCode = 1;
    return;
}

Console.WriteLine($"EpicRaw: {rawBytes.Length} bytes, {transmitTimeMs:F2} ms, {speedMbps:F2} Mbps");

var (imageBytes, imageWidth, imageHeight) = EpicEye.DecodeImageFromEpicRaw(document);
Console.WriteLine(imageBytes is not null
    ? $"Image: {imageWidth}x{imageHeight}, {imageBytes.Length} bytes"
    : "Image: (none)");

var (distortion, cameraMatrix, depthWidth, depthHeight) =
    EpicEye.GetDepthIntrinsicsFromEpicRaw(document);
byte[]? undistortLut = EpicEye.GetUndistortLut(
    ip,
    depthWidth,
    depthHeight,
    cameraMatrix,
    distortion);
var (pointCloudBytes, pointCloudWidth, pointCloudHeight) =
    EpicEye.DecodePointCloudFromEpicRaw(document, undistortLut);
Console.WriteLine(pointCloudBytes is not null
    ? $"PointCloud: {pointCloudWidth}x{pointCloudHeight}, {pointCloudBytes.Length / sizeof(float)} floats"
    : "PointCloud: (none)");
if (pointCloudBytes is null) Environment.ExitCode = 1;

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
