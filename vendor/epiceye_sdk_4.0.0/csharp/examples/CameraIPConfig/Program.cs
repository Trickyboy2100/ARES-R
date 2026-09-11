// 作用：识别目标相机后，通过 UDP 目标单播和组播兼容路径下发 DHCP 或静态 IP 配置。
// 输入：<targetIP> [newIP] [netMask] [DHCP|Manual]；未指定 newIP 时默认切换 DHCP。
// 相机影响：会修改相机网络配置，成功后旧 IP 可能立即失效。
// 重要：SetEpicEyeIPConfig 只表示配置报文已发送，不包含相机确认；应重新搜索相机验证最终 IP。

using TFTech;
using TFTech.Models;

Console.WriteLine("SDK Version: " + EpicEye.GetSDKVersion());
Console.WriteLine("---------------Camera IP Config---------------");

string? specifiedTargetIP = args.Length > 0 && !string.IsNullOrWhiteSpace(args[0]) ? GetHost(args[0]) : null;
List<EpicEyeInfo> cameraList = EpicEye.SearchCamera();
if (cameraList.Count == 0)
{
    Console.WriteLine("Camera not found!");
}
else
{
    Console.WriteLine("Camera found: " + cameraList.Count);
    for (int i = 0; i < cameraList.Count; i++)
    {
        Console.WriteLine($"{i,3}: {cameraList[i].IP,-20}{cameraList[i].SN,-30}");
    }
}

if (specifiedTargetIP is null)
{
    Console.WriteLine();
    Console.WriteLine("Usage: CameraIPConfig <targetIP> [newIP] [netMask] [DHCP|Manual]");
    Console.WriteLine("Example (DHCP):   CameraIPConfig 192.168.1.100");
    Console.WriteLine("Example (Manual): CameraIPConfig 192.168.1.100 192.168.1.200 255.255.255.0 Manual");
    Console.WriteLine();
    Console.WriteLine("No target IP given; the sample only searches and displays cameras to avoid changing network settings accidentally.");
    return;
}

string targetIP = specifiedTargetIP;
Console.WriteLine("DestinationIP: " + targetIP);

EpicEyeInfo? targetCamera = cameraList.FirstOrDefault(camera => string.Equals(GetHost(camera.IP), targetIP, StringComparison.Ordinal));
if (targetCamera is null)
{
    var info = EpicEye.GetInfo($"{targetIP}:5000", timeout: 3000);
    targetCamera = info?.Status == 0 ? info.Data : null;
}
if (targetCamera is null || string.IsNullOrWhiteSpace(targetCamera.SN) || targetCamera.SN.Contains("EpicEyeSN", StringComparison.Ordinal))
{
    Console.WriteLine("Cannot identify the target camera. Confirm that the target IP is reachable or discoverable, then retry.");
    Environment.ExitCode = 1;
    return;
}

var config = new EpicEyeIPConfig
{
    SN = targetCamera.SN
};
Console.WriteLine("Target camera SN: " + targetCamera.SN);

if (args.Length >= 2) config.IP = args[1];
if (args.Length >= 3) config.NetMask = args[2];
if (args.Length >= 4) config.Type = args[3];

Console.WriteLine($"Config: type={config.Type} ip={config.IP} netMask={config.NetMask}");

// 返回 void：仅表示已发出 UDP 配置报文，不代表相机已应用
EpicEye.SetEpicEyeIPConfig(targetIP, config);
Console.WriteLine("setEpicEyeIPConfig request sent (UDP has no ack; verify the new address by rediscovery).");

static string GetHost(string endpoint)
{
    return Uri.TryCreate($"http://{endpoint}", UriKind.Absolute, out var uri) ? uri.Host : endpoint;
}
