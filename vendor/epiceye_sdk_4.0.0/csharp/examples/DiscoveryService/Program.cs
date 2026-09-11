// 作用：启动常驻发现服务，持续监听相机多播广播，并通过事件输出在线相机列表变化。
// 与 SearchCamera 的区别：SearchCamera 是阻塞式一次性测试；本示例适合应用程序长期维护设备列表。
// 生命周期：先订阅事件，再 StartDiscovery；用户按 Enter 后 StopDiscovery 并取消订阅。
// 相机影响：只监听广播，不连接相机业务接口，不修改设备。

using TFTech;
using TFTech.Models;

Console.WriteLine("SDK Version: " + EpicEye.GetSDKVersion());
Console.WriteLine("---------------EpicEye Continuous Discovery---------------");

EpicEye.DiscoveredCamerasChanged += () =>
{
    var list = EpicEye.GetDiscoveredCameras();
    Console.WriteLine($"\n[Updated] Camera count: {list.Count}");
    for (int i = 0; i < list.Count; i++)
    {
        Console.WriteLine($"{i,3}: {list[i].IP,-20}{list[i].SN,-30}");
    }
};

EpicEye.StartDiscovery();
Console.WriteLine("Continuous discovery started. Listening for cameras...");
Console.WriteLine("Press Enter to stop.\n");
Console.ReadLine();

EpicEye.StopDiscovery();
Console.WriteLine("Continuous discovery stopped.");
