// 作用：读取相机保存的完整内外参，并单独读取当前深度输出使用的相机矩阵与畸变参数。
// 输入：可选 camera_ip；未指定时阻塞搜索并使用第一台相机。
// 说明：V3 返回扁平内参，V4 返回按 DepthSrc1/DepthSrc2/TextureSrc 组织的详细结构。
// 相机影响：只读，不执行内参计算，不写入相机。
using System.Text.Json;
using TFTech;

Console.WriteLine("SDK Version: " + EpicEye.GetSDKVersion());
string ip = ResolveIp(args);
if (ip.Length == 0)
{
    Environment.ExitCode = 1;
    return;
}

Console.WriteLine($"---------------get {ip} CameraParameters---------------");
var parameters = EpicEye.GetCameraParameters(ip);
if (parameters.Status != 0)
{
    Console.WriteLine("GetCameraParameters failed: " + parameters.ErrorMessage);
    Environment.ExitCode = 1;
    return;
}
Console.WriteLine(JsonSerializer.Serialize(parameters.Data, new JsonSerializerOptions { WriteIndented = true }));

var cameraMatrix = EpicEye.GetCameraMatrix(ip);
if (cameraMatrix.Status != 0 || cameraMatrix.Data == null)
{
    Console.WriteLine("GetCameraMatrix failed!");
    Environment.ExitCode = 1;
    return;
}
Console.WriteLine("Current depth cameraMatrix (3x3 row-major): " + string.Join(" ", cameraMatrix.Data));

var distortion = EpicEye.GetDistortion(ip);
if (distortion.Status != 0 || distortion.Data == null)
{
    Console.WriteLine("GetDistortion failed!");
    Environment.ExitCode = 1;
    return;
}
Console.WriteLine("Current depth distortion (k1,k2,p1,p2,k3): " + string.Join(" ", distortion.Data));

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
