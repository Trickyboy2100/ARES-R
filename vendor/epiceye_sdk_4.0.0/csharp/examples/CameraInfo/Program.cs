// 作用：读取相机身份、版本、网络地址、型号和重建器类型。
// 输入：可选 camera_ip；未指定时阻塞搜索并使用第一台相机。
// 输出：EpicEyeInfo 的全部主要字段，以及 V4 相机的 ReconstructorType。
// 相机影响：只读，不触发拍摄，不修改相机配置。
using TFTech;
using TFTech.Models;

Console.WriteLine("SDK Version: " + EpicEye.GetSDKVersion());
string ip = ResolveIp(args);
if (ip.Length == 0)
{
    Environment.ExitCode = 1;
    return;
}

Console.WriteLine($"---------------get {ip} EpicEyeInfo---------------");
var infoResp = EpicEye.GetInfo(ip);
if (infoResp == null || infoResp.Status != 0 || infoResp.Data == null)
{
    Console.WriteLine("getInfo failed!");
    Environment.ExitCode = 1;
    return;
}
var info = infoResp.Data;
Console.WriteLine("SN: " + info.SN);
Console.WriteLine("IP: " + info.IP);
Console.WriteLine("Version: " + info.Version);
Console.WriteLine("model: " + info.Model);
Console.WriteLine("alias: " + info.Alias);
Console.WriteLine($"resolution: {info.Width}x{info.Height}");

var recResp = EpicEye.GetReconstructorType(ip);
if (recResp != null && recResp.Status == 0)
{
    Console.WriteLine($"ReconstructorType: {(int)recResp.Data} ({recResp.Data})");
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
