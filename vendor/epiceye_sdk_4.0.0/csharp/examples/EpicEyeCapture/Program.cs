// 作用：演示纯托管的一次完整 3D 采集，不依赖 OpenCV。
// 流程：触发拍摄 -> 仅一次 HTTP 下载 EpicRaw -> 离线解码图像/深度/点云 -> 纹理对齐 -> 保存 PNG/PLY。
// 关键点：图像、深度和点云均来自同一 EpicRaw，避免分别请求造成帧不一致。
// 相机影响：触发一次拍摄；不修改相机配置。文件写入当前输出目录。

using System.Text;
using Newtonsoft.Json.Linq;
using SixLabors.ImageSharp;
using SixLabors.ImageSharp.PixelFormats;
using TFTech;
using TFTech.Models;

string ip = ResolveIp(args);
if (ip.Length == 0)
{
    Environment.ExitCode = 1;
    return;
}
Console.WriteLine("Using IP: " + ip);

// getInfo
var infoResp = EpicEye.GetInfo(ip);
if (infoResp?.Data is { } info)
{
    Console.WriteLine($"SN: {info.SN} model: {info.Model} resolution: {info.Width}x{info.Height}");
}

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

// 一次 HTTP 取 EpicRaw，后续全部离线
Console.WriteLine("---------------fetch EpicRaw (once)---------------");
byte[]? rawBytes = EpicEye.GetFrameInEpicRaw(ip, frameId);
if (rawBytes == null)
{
    Console.WriteLine("getFrameInEpicRaw failed!");
    Environment.ExitCode = 1;
    return;
}
Console.WriteLine($"EpicRaw: {rawBytes.Length} bytes");

// 解析一次 document，供多次解码复用（热路径）
if (!EpicEye.TryLoadEpicRawDocumentFromBytes(rawBytes, out var doc) || doc == null)
{
    Console.WriteLine("TryLoadEpicRawDocumentFromBytes failed!");
    Environment.ExitCode = 1;
    return;
}

// ---- 解析纹理外参（TextureBGR 元数据）----
double[]? texInt = null, texDist = null, rot = null, trans = null;
string? texMeta = EpicEye.GetMetaDataStrFromEpicRaw(doc, EpicRawDataType.TextureBGR);
if (!string.IsNullOrEmpty(texMeta))
{
    ParseTextureExtrinsics(texMeta, out texInt, out texDist, out rot, out trans);
}

// ---- 深度内参 ----
var (_, depthCm, _, _) = EpicEye.GetDepthIntrinsicsFromEpicRaw(doc);

// ---- 离线解码图像 ----
Console.WriteLine("---------------decodeImage (offline)---------------");
byte[]? image8bit = null;
int imageWidth = 0, imageHeight = 0;
var (imgBytes, iw, ih) = EpicEye.DecodeImageFromEpicRaw(doc);
if (imgBytes != null && iw is int w0 && ih is int h0 && w0 > 0 && h0 > 0)
{
    imageWidth = w0;
    imageHeight = h0;
    int bpp = imgBytes.Length / (w0 * h0); // 3 = 8bit BGR, 6 = 16bit BGR
    Console.WriteLine($"Image: {imageWidth}x{imageHeight} bytesPerPixel: {bpp} dataSize: {imgBytes.Length}");
    image8bit = To8bitBgr(imgBytes, imageWidth, imageHeight, bpp);
    if (image8bit != null)
    {
        SaveBgr24Png(image8bit, imageWidth, imageHeight, "image8bit.png");
        Console.WriteLine("saved: image8bit.png");
    }
}
else
{
    Console.WriteLine("decodeImage: no TextureBGR element (camera may have no color sensor)");
}

// ---- 离线解码深度图 ----
Console.WriteLine("---------------decodeDepth (offline)---------------");
float[]? depth = null;
int depthWidth = 0, depthHeight = 0;
var (depthBytes, dw, dh) = EpicEye.DecodeDepthFromEpicRaw(doc);
if (depthBytes != null && dw is int dwv && dh is int dhv)
{
    depthWidth = dwv;
    depthHeight = dhv;
    depth = new float[depthBytes.Length / sizeof(float)];
    Buffer.BlockCopy(depthBytes, 0, depth, 0, depthBytes.Length);
    Console.WriteLine($"Depth: {depthWidth}x{depthHeight} dataSize: {depth.Length} floats");
    SaveDepthGreyPng(depth, depthWidth, depthHeight, "depthGrey.png");
    Console.WriteLine("saved: depthGrey.png");
}
else
{
    Console.WriteLine("decodeDepth: no depth element in this EpicRaw.");
}

// ---- 离线解码点云 ----
Console.WriteLine("---------------decodePointCloud (offline)---------------");
byte[]? lut = null;
if (depthCm is { Length: >= 9 } && depthWidth > 0 && depthHeight > 0)
{
    // 深度畸变一般为 0，此时 ComputeUndistortLut 返回 null，点云解码时按 null 处理即可
    lut = EpicEye.ComputeUndistortLut(depthWidth, depthHeight, depthCm, new double[] { 0, 0, 0, 0, 0 });
}
var (pcBytes, pcw, pch) = EpicEye.DecodePointCloudFromEpicRaw(doc, lut);
if (pcBytes != null && pcw is int pcwv && pch is int pchv)
{
    float[] pc = new float[pcBytes.Length / sizeof(float)];
    Buffer.BlockCopy(pcBytes, 0, pc, 0, pcBytes.Length);
    Console.WriteLine($"PointCloud: {pcwv}x{pchv} dataSize: {pc.Length} floats");
    SavePointCloudPly(pc, pcwv, pchv, "pointcloud.ply");
    Console.WriteLine("saved: pointcloud.ply");

    // ---- 纹理对齐（离线，以深度为输入，0 次 HTTP）----
    if (image8bit != null && depth != null &&
        depthCm is { Length: >= 9 } && texInt is { Length: >= 9 } &&
        texDist is { Length: >= 5 } && rot is { Length: >= 9 } && trans is { Length: >= 3 })
    {
        Console.WriteLine("---------------alignTextureImage---------------");
        // matType=CV_8UC3(16)，image8bit 为 8bit BGR；若直接对齐 16bit 纹理则传 CV_16UC3(18)
        byte[]? aligned = EpicEye.AlignTextureFromDepth(
            depth, depthWidth, depthHeight,
            image8bit, imageWidth, imageHeight, 16,
            ToMatrix(depthCm), ToMatrix(texInt), ToDistortion(texDist), ToMatrix(rot), trans);
        if (aligned != null)
        {
            SaveBgr24Png(aligned, depthWidth, depthHeight, "aligned_texture.png");
            SavePointCloudWithTexturePly(pc, aligned, pcwv, pchv, "pointcloudWithAlignedTexture.ply");
            Console.WriteLine("saved: aligned_texture.png, pointcloudWithAlignedTexture.ply");
        }
        else
        {
            Console.WriteLine("alignTextureFromDepth failed.");
        }
    }
}
else
{
    Console.WriteLine("decodePointCloud failed.");
    Environment.ExitCode = 1;
}

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

// 从 TextureBGR 元数据 JSON 解析内参(9)/畸变(5)/旋转(9)/平移(3)
static void ParseTextureExtrinsics(string meta, out double[]? cm, out double[]? dist, out double[]? rot, out double[]? trans)
{
    cm = dist = rot = trans = null;
    try
    {
        var j = JObject.Parse(meta);
        cm = ReadArray(j, "CameraMatrix", 9);
        dist = ReadArray(j, "CameraDistortion", 5);
        rot = ReadArray(j, "CameraRotation", 9);
        trans = ReadArray(j, "CameraTranslation", 3);
    }
    catch { /* 无外参则保持 null */ }
}

static double[]? ReadArray(JObject j, string key, int len)
{
    if (j[key] is JArray a && a.Count == len)
        return a.Select(x => (double)x!).ToArray();
    return null;
}

static Matrix3x3 ToMatrix(double[] m) => new()
{
    M00 = m[0], M01 = m[1], M02 = m[2],
    M10 = m[3], M11 = m[4], M12 = m[5],
    M20 = m[6], M21 = m[7], M22 = m[8]
};

static Distortion ToDistortion(double[] d) => new()
{
    K1 = d[0], K2 = d[1], P1 = d[2], P2 = d[3], K3 = d[4]
};

// 将图像转为 8bit BGR 三字节（3 字节/像素直接返回；6 字节/像素为 16bit，右移到 8bit）
static byte[]? To8bitBgr(byte[] data, int width, int height, int bytesPerPixel)
{
    int n = width * height;
    var outBuf = new byte[n * 3];
    if (bytesPerPixel == 3)
    {
        Array.Copy(data, outBuf, n * 3);
        return outBuf;
    }
    if (bytesPerPixel == 6)
    {
        for (int i = 0; i < n * 3; i++)
        {
            ushort v = (ushort)(data[i * 2] | (data[i * 2 + 1] << 8));
            outBuf[i] = (byte)Math.Min(v / 4, 255);
        }
        return outBuf;
    }
    Console.WriteLine("unsupported bytesPerPixel: " + bytesPerPixel);
    return null;
}

// BGR 字节存为 PNG（ImageSharp 的 Bgr24 内存布局即 B,G,R）
static void SaveBgr24Png(byte[] bgr, int width, int height, string path)
{
    using var img = Image.LoadPixelData<Bgr24>(bgr, width, height);
    img.Save(path);
}

// 深度归一化为灰度 PNG
static void SaveDepthGreyPng(float[] depth, int width, int height, string path)
{
    float min = float.MaxValue, max = 0f;
    foreach (var v in depth) { if (v > max) max = v; if (v < min) min = v; }
    float range = max - min;
    if (range <= 0f) range = 1f;
    var grey = new L8[width * height];
    for (int i = 0; i < depth.Length; i++)
        grey[i] = new L8((byte)Math.Round((depth[i] - min) / range * 255));
    using var img = Image.LoadPixelData<L8>(grey, width, height);
    img.Save(path);
}

// 与真实相机一致：二进制小端 PLY，每个顶点为 float32 x/y/z + uint8 RGB；无纹理时使用白色。
static void SavePointCloudPly(float[] pc, int width, int height, string path)
{
    SaveBinaryPointCloudPly(pc, null, width, height, path);
}

// 对齐纹理在内存中保持 BGR；PLY 字段声明为 RGB，写入时只在输出边界交换红蓝通道。
static void SavePointCloudWithTexturePly(float[] pc, byte[] bgr, int width, int height, string path)
{
    SaveBinaryPointCloudPly(pc, bgr, width, height, path);
}

static void SaveBinaryPointCloudPly(float[] pc, byte[]? bgr, int width, int height, string path)
{
    int pointCount = checked(width * height);
    if (width <= 0 || height <= 0 || pc.Length < pointCount * 3 || (bgr != null && bgr.Length < pointCount * 3))
    {
        throw new ArgumentException("Point cloud or texture dimensions do not match the input data.");
    }

    string header = "ply\n"
        + "format binary_little_endian 1.0\n"
        + $"obj_info EpicEye PLY PointCloud (Width = {width}; Height = {height})\n"
        + $"obj_info num_cols {width}\n"
        + $"obj_info num_rows {height}\n"
        + $"element vertex {pointCount}\n"
        + "property float x\n"
        + "property float y\n"
        + "property float z\n"
        + "property uchar red\n"
        + "property uchar green\n"
        + "property uchar blue\n"
        + "end_header\n";

    using FileStream stream = File.Create(path);
    stream.Write(Encoding.ASCII.GetBytes(header));
    using var writer = new BinaryWriter(stream, Encoding.ASCII, leaveOpen: false);
    for (int pointIndex = 0; pointIndex < pointCount; pointIndex++)
    {
        int offset = pointIndex * 3;
        writer.Write(pc[offset]);
        writer.Write(pc[offset + 1]);
        writer.Write(pc[offset + 2]);
        writer.Write(bgr == null ? (byte)255 : bgr[offset + 2]);
        writer.Write(bgr == null ? (byte)255 : bgr[offset + 1]);
        writer.Write(bgr == null ? (byte)255 : bgr[offset]);
    }
}
