// 作用：把纹理图像像素 (u,v) 映射为同一帧点云中的三维坐标 (X,Y,Z)。
// 输入：<ip> <u> <v> 单次查询；只给 IP 时进入交互模式。
// 流程：触发一帧 -> 读取图像/深度/点云及内外参 -> 映射到深度坐标 -> 双线性采样点云。
// 坐标约定：输入是纹理图像坐标；输出是相机坐标系点，单位由点云数据约定为 mm。
using Newtonsoft.Json.Linq;
using TFTech;
using TFTech.Models;

Console.WriteLine("SDK Version: " + EpicEye.GetSDKVersion());
Console.WriteLine("=== Texture Pixel -> Point Cloud Coordinate ===");

string ip = ResolveIp(args);
if (ip.Length == 0)
{
    Environment.ExitCode = 1;
    return;
}
Console.WriteLine("Using IP: " + ip);
Console.WriteLine();

var infoResp = EpicEye.GetInfo(ip);
if (infoResp?.Data is { } info)
    Console.WriteLine($"Camera: {info.Model} {info.Width}x{info.Height}");

// 触发
Console.WriteLine("Triggering frame...");
var trig = EpicEye.TriggerCapture(ip, withPointCloud: true);
if (trig.Status != 0 || string.IsNullOrEmpty(trig.Data))
{
    Console.WriteLine("triggerCapture failed!");
    Environment.ExitCode = 1;
    return;
}
string frameId = trig.Data;
Console.WriteLine("frameId: " + frameId);

// EpicRaw（解析内外参）
byte[]? rawBytes = EpicEye.GetFrameInEpicRaw(ip, frameId);
if (rawBytes == null || !EpicEye.TryLoadEpicRawDocumentFromBytes(rawBytes, out var doc) || doc == null)
{
    Console.WriteLine("getFrameInEpicRaw failed!");
    Environment.ExitCode = 1;
    return;
}

// 图像（可能没有彩色）
var (imgBytes, iwN, ihN) = EpicEye.DecodeImageFromEpicRaw(doc);
bool hasImage = imgBytes != null && iwN != null && ihN != null;
int imgW = iwN ?? 0, imgH = ihN ?? 0;
if (hasImage) Console.WriteLine($"Texture image: {imgW}x{imgH}");
else Console.WriteLine("No texture image available, continuing...");

// 深度
var (depthBytes, dwN, dhN) = EpicEye.DecodeDepthFromEpicRaw(doc);
if (depthBytes == null || dwN is not int depthW || dhN is not int depthH)
{
    Console.WriteLine("getDepth failed!");
    Environment.ExitCode = 1;
    return;
}
float[] depth = new float[depthBytes.Length / sizeof(float)];
Buffer.BlockCopy(depthBytes, 0, depth, 0, depthBytes.Length);
Console.WriteLine($"Depth map: {depthW}x{depthH}");

// 点云
var (distortion, cameraMatrix, lutWidth, lutHeight) =
    EpicEye.GetDepthIntrinsicsFromEpicRaw(doc);
byte[]? undistortLut = EpicEye.GetUndistortLut(
    ip,
    lutWidth,
    lutHeight,
    cameraMatrix,
    distortion);
var (pcBytes, pcwN, pchN) = EpicEye.DecodePointCloudFromEpicRaw(doc, undistortLut);
if (pcBytes == null || pcwN is not int pcW || pchN is not int pcH)
{
    Console.WriteLine("getPointCloud failed!");
    Environment.ExitCode = 1;
    return;
}
float[] pointCloud = new float[pcBytes.Length / sizeof(float)];
Buffer.BlockCopy(pcBytes, 0, pointCloud, 0, pcBytes.Length);
Console.WriteLine($"PointCloud: {pcW}x{pcH}");

// 深度内参
var (_, depthIntrinsic, _, _) = EpicEye.GetDepthIntrinsicsFromEpicRaw(doc);
if (depthIntrinsic is not { Length: >= 9 })
{
    Console.WriteLine("Failed to get depth intrinsics!");
    Environment.ExitCode = 1;
    return;
}

// 纹理内参：从 TextureBGR 元数据，退化时用深度内参（同相机同分辨率）
double[]? texIntrinsic = null;
string? texMeta = EpicEye.GetMetaDataStrFromEpicRaw(doc, EpicRawDataType.TextureBGR);
if (!string.IsNullOrEmpty(texMeta))
{
    try
    {
        var jm = JObject.Parse(texMeta);
        if (jm["CameraMatrix"] is JArray a && a.Count == 9)
            texIntrinsic = a.Select(x => (double)x!).ToArray();
    }
    catch { }
}
bool texIsIdentity = texIntrinsic is { Length: >= 9 } &&
                     texIntrinsic[0] == 1.0 && texIntrinsic[1] == 0.0 && texIntrinsic[2] == 0.0 &&
                     texIntrinsic[4] == 1.0 && texIntrinsic[5] == 0.0;
if (texIntrinsic is not { Length: >= 9 } || texIsIdentity)
{
    Console.WriteLine("No separate texture intrinsics, using depth intrinsics (same camera).");
    texIntrinsic = depthIntrinsic;
}

Console.WriteLine();
Console.WriteLine("=== Camera Parameters ===");
Console.WriteLine("Depth intrinsic (3x3): " + string.Join(" ", depthIntrinsic));
Console.WriteLine("Texture intrinsic (3x3): " + string.Join(" ", texIntrinsic));

// 映射查找
Console.WriteLine();
Console.WriteLine("=== Texture Pixel -> Point Cloud ===");

if (args.Length >= 3 &&
    double.TryParse(args[1], out double uTex) &&
    double.TryParse(args[2], out double vTex))
{
    if (TextureToPointCloud(uTex, vTex, texIntrinsic, depthIntrinsic,
            depth, depthW, depthH, pointCloud, pcW, pcH, out var x, out var y, out var z))
    {
        Console.WriteLine($"Texture pixel ({uTex},{vTex}) -> PointCloud XYZ: ({x:F3}, {y:F3}, {z:F3}) mm");
    }
}
else if (hasImage)
{
    Console.WriteLine($"Texture image is {imgW}x{imgH}");
    Console.WriteLine("Enter texture pixel coordinate (u v), or 'q' to quit:");
    while (true)
    {
        Console.Write("\n> ");
        string? line = Console.ReadLine();
        if (line == null || line == "q" || line == "quit") { Console.WriteLine("Bye."); break; }
        line = line.Trim();
        if (line.Length == 0) continue;
        var parts = line.Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
        if (parts.Length == 2 && double.TryParse(parts[0], out double uIn) && double.TryParse(parts[1], out double vIn))
        {
            if (TextureToPointCloud(uIn, vIn, texIntrinsic, depthIntrinsic,
                    depth, depthW, depthH, pointCloud, pcW, pcH, out var x, out var y, out var z))
            {
                double fxD = depthIntrinsic[0], fyD = depthIntrinsic[4], cxD = depthIntrinsic[2], cyD = depthIntrinsic[5];
                double fxT = texIntrinsic[0], fyT = texIntrinsic[4], cxT = texIntrinsic[2], cyT = texIntrinsic[5];
                double xn = (uIn - cxT) / fxT, yn = (vIn - cyT) / fyT;
                double uDepth = xn * fxD + cxD, vDepth = yn * fyD + cyD;
                double depthZ = SampleDepth(depth, depthW, depthH, uDepth, vDepth);
                Console.WriteLine($"  -> Depth pixel:  ({uDepth:F3}, {vDepth:F3})");
                Console.WriteLine($"  -> Depth Z:       {depthZ:F3} mm");
                Console.WriteLine($"  -> PointCloud XYZ: ({x:F3}, {y:F3}, {z:F3}) mm");
            }
        }
        else
        {
            Console.WriteLine("Invalid format. Use: <u> <v>");
        }
    }
}
else
{
    Console.WriteLine("No texture image and no (u v) argument given. Usage: TextureToPointCloud <ip> <u> <v>");
}

Console.WriteLine();

// ================= 映射与采样 =================

// 纹理像素 -> 深度像素 -> 双线性采样点云 XYZ（假定同相机 R=I,T=0，仅分辨率差异）
static bool TextureToPointCloud(
    double uTex, double vTex,
    double[] texIntrinsic, double[] depthIntrinsic,
    float[] depth, int depthW, int depthH,
    float[] pc, int pcW, int pcH,
    out double outX, out double outY, out double outZ)
{
    outX = outY = outZ = 0.0;
    double fxT = texIntrinsic[0], fyT = texIntrinsic[4], cxT = texIntrinsic[2], cyT = texIntrinsic[5];
    double fxD = depthIntrinsic[0], fyD = depthIntrinsic[4], cxD = depthIntrinsic[2], cyD = depthIntrinsic[5];

    double xn = (uTex - cxT) / fxT;
    double yn = (vTex - cyT) / fyT;
    double uDepth = xn * fxD + cxD;
    double vDepth = yn * fyD + cyD;

    if (uDepth < 0 || uDepth >= depthW - 1 || vDepth < 0 || vDepth >= depthH - 1)
    {
        Console.WriteLine($"  Texture pixel ({uTex},{vTex}) maps to depth ({uDepth:F2},{vDepth:F2}) - out of bounds");
        return false;
    }

    double Z = SampleDepth(depth, depthW, depthH, uDepth, vDepth);
    if (Z <= 0.0)
    {
        Console.WriteLine($"  Texture pixel ({uTex},{vTex}) -> depth ({uDepth:F2},{vDepth:F2}) - Z invalid (0)");
        return false;
    }

    SamplePointCloud(pc, pcW, pcH, uDepth, vDepth, out outX, out outY, out outZ);
    if (outZ <= 0.0)
    {
        // 点云无效则从 Z 反投影
        outX = Z * xn; outY = Z * yn; outZ = Z;
    }
    return true;
}

static float SampleDepth(float[] depth, int depthW, int depthH, double u, double v)
{
    int u0 = (int)u, v0 = (int)v;
    if (u0 < 0 || u0 >= depthW - 1 || v0 < 0 || v0 >= depthH - 1) return 0f;
    double du = u - u0, dv = v - v0;
    double w00 = (1 - du) * (1 - dv), w01 = du * (1 - dv), w10 = (1 - du) * dv, w11 = du * dv;
    int idx00 = v0 * depthW + u0;
    return (float)(depth[idx00] * w00 + depth[idx00 + 1] * w01 +
                   depth[idx00 + depthW] * w10 + depth[idx00 + depthW + 1] * w11);
}

static void SamplePointCloud(float[] pc, int pcW, int pcH, double u, double v,
    out double x, out double y, out double z)
{
    x = y = z = 0.0;
    int u0 = (int)u, v0 = (int)v;
    if (u0 < 0 || u0 >= pcW - 1 || v0 < 0 || v0 >= pcH - 1) return;
    double du = u - u0, dv = v - v0;
    double w00 = (1 - du) * (1 - dv), w01 = du * (1 - dv), w10 = (1 - du) * dv, w11 = du * dv;

    void ReadXYZ(int col, int row, out double rx, out double ry, out double rz)
    {
        int idx = (row * pcW + col) * 3;
        rx = pc[idx]; ry = pc[idx + 1]; rz = pc[idx + 2];
    }

    ReadXYZ(u0, v0, out double x00, out double y00, out double z00);
    ReadXYZ(u0 + 1, v0, out double x01, out double y01, out double z01);
    ReadXYZ(u0, v0 + 1, out double x10, out double y10, out double z10);
    ReadXYZ(u0 + 1, v0 + 1, out double x11, out double y11, out double z11);

    x = x00 * w00 + x01 * w01 + x10 * w10 + x11 * w11;
    y = y00 * w00 + y01 * w01 + y10 * w10 + y11 * w11;
    z = z00 * w00 + z01 * w01 + z10 * w10 + z11 * w11;
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
