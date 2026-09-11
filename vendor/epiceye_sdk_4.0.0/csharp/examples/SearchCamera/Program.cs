// 作用：通过 UDP 广播执行一次阻塞式搜索，并打印局域网内的 EpicEye 相机列表。
// 输入：无；搜索结果包含 IP、SN、型号和分辨率等信息。
// 限制：仅适合测试脚本和临时诊断；正式应用应使用 StartDiscovery/StopDiscovery 与发现事件。
// 相机影响：只发送/接收发现报文，不修改相机。
using TFTech;
using TFTech.Models;

Console.WriteLine("SDK Version: " + EpicEye.GetSDKVersion());
Console.WriteLine("---------------search EpicEye camera---------------");

List<EpicEyeInfo> cameraList = EpicEye.SearchCamera();
if (cameraList.Count > 0)
{
    Console.WriteLine("Camera found: " + cameraList.Count);
    for (int i = 0; i < cameraList.Count; i++)
    {
        // 左对齐 IP 与 SN，便于快速查看设备列表。
        Console.WriteLine($"{i,3}: {cameraList[i].IP,-20}{cameraList[i].SN,-30}");
    }
}
else
{
    Console.WriteLine("Camera not found!");
    Environment.ExitCode = 1;
}
