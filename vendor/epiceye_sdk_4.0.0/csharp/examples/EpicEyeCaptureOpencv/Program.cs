// 作用：演示使用 OpenCvSharp 处理在线图像、深度、点云和纹理对齐结果。
// 流程：触发一帧 -> 在线读取图像/深度/点云 -> 对齐纹理 -> 保存图像和 PLY。
// 说明：为兼容 CI/服务器，只调用 Cv2.ImWrite，不弹出 imshow 窗口。
// 相机影响：触发一次拍摄；不修改相机配置。多个在线读取必须使用同一 frameId。

using System.Text;
using Newtonsoft.Json.Linq;
using OpenCvSharp;
using TFTech;
using TFTech.Models;

string ip = ResolveIp(args);
if (ip.Length == 0)
{
    Environment.ExitCode = 1;
    return;
}
Console.WriteLine("Using IP: " + ip);

var infoResp = EpicEye.GetInfo(ip);
if (infoResp?.Data is { } info)
    Console.WriteLine($"SN: {info.SN} model: {info.Model} resolution: {info.Width}x{info.Height}");

// 触发
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

byte[]? rawBytes = EpicEye.GetFrameInEpicRaw(ip, frameId);
if (rawBytes is null
    || !EpicEye.TryLoadEpicRawDocumentFromBytes(rawBytes, out var doc)
    || doc is null)
{
    Console.WriteLine("getFrameInEpicRaw failed!");
    Environment.ExitCode = 1;
    return;
}

Console.WriteLine("---------------decodeImageFromEpicRaw---------------");
var (imageBytes, iw, ih) = EpicEye.DecodeImageFromEpicRaw(doc);
if (imageBytes == null || iw is not int imageWidth || ih is not int imageHeight)
{
    Console.WriteLine("getImage failed!");
    Environment.ExitCode = 1;
    return;
}
int bpp = imageBytes.Length / (imageWidth * imageHeight); // 3=8bit BGR, 6=16bit BGR
byte[] image8bit = To8bitBgr(imageBytes, imageWidth, imageHeight, bpp);
using (Mat image = new Mat(imageHeight, imageWidth, MatType.CV_8UC3, image8bit))
{
    Cv2.ImWrite("image.png", image);
}
Console.WriteLine("saved: image.png");

Console.WriteLine("---------------decodeDepthFromEpicRaw---------------");
var (depthBytes, dw, dh) = EpicEye.DecodeDepthFromEpicRaw(doc);
if (depthBytes == null || dw is not int depthWidth || dh is not int depthHeight)
{
    Console.WriteLine("getDepth failed!");
    Environment.ExitCode = 1;
    return;
}
float[] depth = new float[depthBytes.Length / sizeof(float)];
Buffer.BlockCopy(depthBytes, 0, depth, 0, depthBytes.Length);
using (Mat depthMat = new Mat(depthHeight, depthWidth, MatType.CV_32FC1, depthBytes))
using (Mat depthU8 = new Mat())
using (Mat depthColor = new Mat())
{
    depthMat.ConvertTo(depthU8, MatType.CV_8UC1, 1 / 10.0);
    Cv2.ApplyColorMap(depthU8, depthColor, ColormapTypes.Jet);
    Cv2.ImWrite("depth.png", depthColor);
}
Console.WriteLine("saved: depth.png");

Console.WriteLine("---------------decodePointCloudFromEpicRaw---------------");
var (distortion, cameraMatrix, lutWidth, lutHeight) =
    EpicEye.GetDepthIntrinsicsFromEpicRaw(doc);
byte[]? undistortLut = EpicEye.GetUndistortLut(
    ip,
    lutWidth,
    lutHeight,
    cameraMatrix,
    distortion);
var (pcBytes, pcw, pch) = EpicEye.DecodePointCloudFromEpicRaw(doc, undistortLut);
if (pcBytes == null || pcw is not int pcWidth || pch is not int pcHeight)
{
    Console.WriteLine("getPointCloud failed!");
    Environment.ExitCode = 1;
    return;
}
float[] pc = new float[pcBytes.Length / sizeof(float)];
Buffer.BlockCopy(pcBytes, 0, pc, 0, pcBytes.Length);
SavePointCloudPly(pc, pcWidth, pcHeight, "pointcloud.ply");
Console.WriteLine("saved: pointcloud.ply");

// 纹理对齐：复用同一个 EpicRawDocument 解析内外参
{
    string? texMeta = EpicEye.GetMetaDataStrFromEpicRaw(doc, EpicRawDataType.TextureBGR);
    ParseTextureExtrinsics(texMeta, out var texInt, out var texDist, out var rot, out var trans);
    var (_, depthCm, _, _) = EpicEye.GetDepthIntrinsicsFromEpicRaw(doc);

    if (depthCm is { Length: >= 9 } && texInt is { Length: >= 9 } &&
        texDist is { Length: >= 5 } && rot is { Length: >= 9 } && trans is { Length: >= 3 })
    {
        // matType=CV_8UC3(16)，image8bit 为 8bit BGR；16bit 纹理则传 CV_16UC3(18)
        byte[]? aligned = EpicEye.AlignTextureFromDepth(
            depth, depthWidth, depthHeight,
            image8bit, imageWidth, imageHeight, 16,
            ToMatrix(depthCm), ToMatrix(texInt), ToDistortion(texDist), ToMatrix(rot), trans);
        if (aligned != null)
        {
            using (Mat alignedMat = new Mat(depthHeight, depthWidth, MatType.CV_8UC3, aligned))
            {
                Cv2.ImWrite("aligned_texture.png", alignedMat);
            }
            SavePointCloudWithTexturePly(pc, aligned, pcWidth, pcHeight, "pointcloudWithAlignedTexture.ply");
            Console.WriteLine("saved: aligned_texture.png, pointcloudWithAlignedTexture.ply");
        }
        else
        {
            Console.WriteLine("alignTextureFromDepth failed, skip textured point cloud");
        }
    }
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

static void ParseTextureExtrinsics(string? meta, out double[]? cm, out double[]? dist, out double[]? rot, out double[]? trans)
{
    cm = dist = rot = trans = null;
    if (string.IsNullOrEmpty(meta)) return;
    try
    {
        var j = JObject.Parse(meta);
        cm = ReadArray(j, "CameraMatrix", 9);
        dist = ReadArray(j, "CameraDistortion", 5);
        rot = ReadArray(j, "CameraRotation", 9);
        trans = ReadArray(j, "CameraTranslation", 3);
    }
    catch { }
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

static byte[] To8bitBgr(byte[] data, int width, int height, int bytesPerPixel)
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
    throw new ArgumentException("unsupported bytesPerPixel: " + bytesPerPixel);
}

static void SavePointCloudPly(float[] pc, int width, int height, string path)
{
    SaveBinaryPointCloudPly(pc, null, width, height, path);
}

// OpenCV 和 SDK 返回 BGR；PLY 的颜色属性声明为 RGB，因此仅在写文件时交换红蓝通道。
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
