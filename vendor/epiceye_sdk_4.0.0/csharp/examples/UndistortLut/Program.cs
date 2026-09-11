// 作用：演示在线获取、离线计算和清理去畸变 LUT 缓存。
// 数据格式：LUT 为 width*height*2 个 float（CV_32FC2），每个像素保存映射坐标 (u',v')。
// 在线路径读取相机内参；离线路径只依赖给定矩阵和畸变参数。全零畸变不需要 LUT。
// 相机影响：只读；ClearUndistortedLUTCache 仅清理当前 SDK 进程缓存，不修改相机。
using TFTech;

Console.WriteLine("SDK Version: " + EpicEye.GetSDKVersion());
Console.WriteLine("---------------Undistort LUT---------------");

string ip = ResolveIp(args);
if (ip.Length == 0)
{
    Console.WriteLine("Camera not found!");
    // 离线演示：不需要在线相机
    Console.WriteLine("\n--- computeUndistortLut (offline, no camera) ---");
    double[] demoCm = { 1420.0, 0.0, 710.0, 0.0, 1420.0, 710.0, 0.0, 0.0, 1.0 };
    double[] demoDist = { -0.05, 0.01, 0.0, 0.0, 0.0 };
    byte[]? lut = EpicEye.ComputeUndistortLut(1420, 1420, demoCm, demoDist);
    if (lut != null)
    {
        float[] f = ToFloats(lut, 4);
        Console.WriteLine($"computeUndistortLut success! lut bytes: {lut.Length} ({lut.Length / 8} points)");
        Console.WriteLine($"lut[0..3]: {f[0]}, {f[1]}, {f[2]}, {f[3]}");
    }
    else
    {
        Console.WriteLine("computeUndistortLut failed / returned null (distortion all zero?).");
        Environment.ExitCode = 1;
    }
    return;
}

Console.WriteLine("Using camera: " + ip + "\n");

var infoResp = EpicEye.GetInfo(ip);
if (infoResp?.Data is not { } info)
{
    Console.WriteLine("getInfo failed!");
    Environment.ExitCode = 1;
    return;
}
Console.WriteLine($"Camera resolution: {info.Width}x{info.Height}");

var cmResp = EpicEye.GetCameraMatrix(ip);
if (cmResp.Status != 0 || cmResp.Data == null)
{
    Console.WriteLine("getCameraMatrix failed!");
    Environment.ExitCode = 1;
    return;
}
double[] cameraMatrix = cmResp.Data;
double[] distortion = EpicEye.GetDistortion(ip).Data ?? new double[5];

Console.WriteLine("cameraMatrix: " + string.Join(" ", cameraMatrix));
Console.WriteLine("distortion: " + string.Join(" ", distortion) + "\n");

// 在线获取
Console.WriteLine("--- getUndistortLut (online, from camera) ---");
byte[]? lutOnline = EpicEye.GetUndistortLut(ip, info.Width, info.Height, cameraMatrix, distortion);
if (lutOnline != null && lutOnline.Length >= 16)
{
    float[] f = ToFloats(lutOnline, 4);
    Console.WriteLine($"getUndistortLut success! lut bytes: {lutOnline.Length}");
    Console.WriteLine($"lut[0..3]: {f[0]}, {f[1]}, {f[2]}, {f[3]}");
}
else
{
    Console.WriteLine("getUndistortLut returned empty (distortion all zero or failed)");
}

// 离线计算
Console.WriteLine("\n--- computeUndistortLut (offline) ---");
byte[]? lutOffline = EpicEye.ComputeUndistortLut(info.Width, info.Height, cameraMatrix, distortion);
Console.WriteLine(lutOffline != null
    ? $"computeUndistortLut success! lut bytes: {lutOffline.Length}"
    : "computeUndistortLut returned null (distortion all zero?).");

// 清除缓存
Console.WriteLine("\n--- clearUndistortedLUTCache ---");
EpicEye.ClearUndistortedLUTCache(ip);
Console.WriteLine("Cache cleared for: " + ip);

// ================= 辅助 =================

// 从 LUT 字节流读取前 n 个 float
static float[] ToFloats(byte[] lut, int n)
{
    var f = new float[n];
    Buffer.BlockCopy(lut, 0, f, 0, n * sizeof(float));
    return f;
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
