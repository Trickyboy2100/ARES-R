// 作用：演示 EpicRaw 文档的一次加载、多项离线解析和重复复用。
// 输入：首参为现有 .epicraw 文件时完全离线；否则把首参视为相机 IP，或搜索相机获取一帧。
// 输出：拍摄配置、深度内参、图像、深度、点云、去畸变 LUT 和元素元数据。
// 相机影响：文件模式不连接相机；在线模式触发一次拍摄但不修改配置。
using Newtonsoft.Json;
using TFTech;
using TFTech.Models;

Console.WriteLine("SDK Version: " + EpicEye.GetSDKVersion());
Console.WriteLine("---------------EpicRaw Offline Parse---------------");

byte[] epicRawBytes;

// 判断参数是否为已存在的文件；否则当作 IP 或触发搜索
if (args.Length > 0 && File.Exists(args[0]))
{
    Console.WriteLine("Loading EpicRaw from file: " + args[0]);
    epicRawBytes = File.ReadAllBytes(args[0]);
    Console.WriteLine($"Loaded {epicRawBytes.Length} bytes");
}
else
{
    string ip = ResolveIp(args);
    if (ip.Length == 0)
    {
        Environment.ExitCode = 1;
        return;
    }
    Console.WriteLine("Using camera: " + ip);

    var trig = EpicEye.TriggerCapture(ip, withPointCloud: true);
    if (trig.Status != 0 || string.IsNullOrEmpty(trig.Data))
    {
        Console.WriteLine("triggerCapture failed!");
        Environment.ExitCode = 1;
        return;
    }
    Console.WriteLine("frameId: " + trig.Data);
    var raw = EpicEye.GetFrameInEpicRaw(ip, trig.Data);
    if (raw == null)
    {
        Console.WriteLine("getFrameInEpicRaw failed!");
        Environment.ExitCode = 1;
        return;
    }
    epicRawBytes = raw;
    Console.WriteLine($"Got {epicRawBytes.Length} bytes from camera");
}

// 1. 加载 EpicRaw 文档
Console.WriteLine("\n--- tryLoadEpicRawDocumentFromBytes ---");
if (!EpicEye.TryLoadEpicRawDocumentFromBytes(epicRawBytes, out var document) || document == null)
{
    Console.WriteLine("Failed to load EpicRaw document!");
    Environment.ExitCode = 1;
    return;
}
Console.WriteLine("EpicRaw loaded: " + document.FileType);

// 2. 拍摄时相机配置
Console.WriteLine("\n--- decodeCameraConfigFromEpicRaw ---");
var cameraConfig = EpicEye.DecodeCameraConfigFromEpicRaw(document);
Console.WriteLine(cameraConfig is null
    ? "(no camera config found)"
    : JsonConvert.SerializeObject(cameraConfig, Formatting.Indented));

// 3. 深度内参与深度尺寸
Console.WriteLine("\n--- getDepthIntrinsicsFromEpicRaw ---");
var (distortion, cameraMatrix, depthWidth, depthHeight) = EpicEye.GetDepthIntrinsicsFromEpicRaw(document);
Console.WriteLine($"Depth size: {depthWidth}x{depthHeight}");
if (cameraMatrix != null) Console.WriteLine("CameraMatrix: " + string.Join(" ", cameraMatrix));
if (distortion != null) Console.WriteLine("Distortion: " + string.Join(" ", distortion));

// 4. 解码图像
Console.WriteLine("\n--- decodeImageFromEpicRaw ---");
var (imgBytes, iw, ih) = EpicEye.DecodeImageFromEpicRaw(document);
if (imgBytes != null && iw != null && ih != null)
{
    int bpp = imgBytes.Length / (iw.Value * ih.Value);
    Console.WriteLine($"decodeImage success! {iw}x{ih} bytesPerPixel: {bpp}");
}
else
{
    Console.WriteLine("decodeImage: no texture element in this EpicRaw.");
}

// 5. 解码深度图
Console.WriteLine("\n--- decodeDepthFromEpicRaw ---");
var (depthBytes, ddw, ddh) = EpicEye.DecodeDepthFromEpicRaw(document);
if (depthBytes != null && ddw != null && ddh != null)
{
    Console.WriteLine($"decodeDepth success! size: {ddw}x{ddh}");
}
else
{
    Console.WriteLine("decodeDepth: no depth element in this EpicRaw.");
}

// 6. 离线计算 LUT + 解码点云
Console.WriteLine("\n--- decodePointCloudFromEpicRaw ---");
if (depthWidth > 0 && depthHeight > 0 && cameraMatrix is { Length: >= 9 })
{
    // 畸变全 0 时 ComputeUndistortLut 返回 null，DecodePointCloud 接受 null
    byte[]? lut = EpicEye.ComputeUndistortLut(depthWidth, depthHeight, cameraMatrix, distortion ?? new double[5]);
    var (pcBytes, pcw, pch) = EpicEye.DecodePointCloudFromEpicRaw(document, lut);
    if (pcBytes != null && pcw != null && pch != null)
    {
        Console.WriteLine($"decodePointCloud success! size: {pcw}x{pch}");
    }
    else
    {
        Console.WriteLine("decodePointCloud: no pointcloud/depth element in this EpicRaw.");
    }
}

// 7. 元素 MetaDataStr
Console.WriteLine("\n--- getMetaDataStrFromEpicRaw ---");
string? metaDataStr = EpicEye.GetMetaDataStrFromEpicRaw(document, EpicRawDataType.TextureBGR);
if (!string.IsNullOrEmpty(metaDataStr))
{
    Console.WriteLine("TextureBGR MetaData: " + metaDataStr);
}
else
{
    metaDataStr = EpicEye.GetMetaDataStrFromEpicRaw(document, EpicRawDataType.DepthSrcImg2);
    Console.WriteLine(!string.IsNullOrEmpty(metaDataStr)
        ? "DepthSrcImg2 MetaData: " + metaDataStr
        : "(no matching element metadata found)");
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
