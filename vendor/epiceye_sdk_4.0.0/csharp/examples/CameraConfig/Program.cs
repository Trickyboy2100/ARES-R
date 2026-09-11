// 作用：演示相机配置、参数预设列表和配置样式的完整读写链路。
// 输入：可选 camera_ip；未指定时阻塞搜索并使用第一台相机。
// 流程：读取当前配置 -> 读取参数列表/样式 -> 原样回写配置 -> 切换到列表中的首个参数预设。
// 相机影响：会调用 SetConfig 和 SetParameter。原样回写不改变字段值，但最后一步可能切换当前参数预设。
using System.Collections;
using TFTech;
using TFTech.Models;
using Newtonsoft.Json;

Console.WriteLine("SDK Version: " + EpicEye.GetSDKVersion());
string ip = ResolveIp(args);
if (ip.Length == 0)
{
    Environment.ExitCode = 1;
    return;
}

// 读取当前配置
Console.WriteLine($"---------------getConfig ({ip})---------------");
var config = EpicEye.GetConfig(ip);
if (config.Status != 0 || config.Data == null)
{
    Console.WriteLine("getConfig failed!");
    Environment.ExitCode = 1;
    return;
}
Console.WriteLine(JsonConvert.SerializeObject(config.Data, Formatting.Indented));

// SDK 按相机版本严格校验协议字段，对外统一提供 Id/Name。
Console.WriteLine($"---------------getParameterList ({ip})---------------");
var parameterList = EpicEye.GetParameterList(ip);
if (parameterList.Status == 0 && parameterList.Data != null)
{
    Console.WriteLine(JsonConvert.SerializeObject(parameterList.Data, Formatting.Indented));
}
else
{
    Console.WriteLine("getParameterList failed!");
    Environment.ExitCode = 1;
    return;
}

// 参数样式较长，只显示前 500 个字符。
Console.WriteLine($"---------------getConfigStyle ({ip})---------------");
var configStyle = EpicEye.GetConfigStyle(ip);
if (configStyle.Status == 0 && configStyle.Data != null)
{
    string styleStr = JsonConvert.SerializeObject(configStyle.Data, Formatting.Indented);
    Console.WriteLine(styleStr.Substring(0, Math.Min(500, styleStr.Length)));
}
else
{
    Console.WriteLine("getConfigStyle failed!");
    Environment.ExitCode = 1;
}

// 回写配置验证
Console.WriteLine($"---------------setConfig ({ip})---------------");
var setRes = EpicEye.SetConfig(ip, config.Data);
Console.WriteLine(setRes.Status == 0 ? "setConfig success!" : "setConfig failed!");
if (setRes.Status != 0) Environment.ExitCode = 1;

// 按 paramId 切换参数（取列表第一个的 Id）
Console.WriteLine($"---------------setParameter ({ip})---------------");
if (parameterList.Status == 0 && parameterList.Data != null && parameterList.Data.Count > 0)
{
    SimpleCameraParameter firstPreset = parameterList.Data[0];
    Console.WriteLine($"selecting param: {firstPreset.Name} ({firstPreset.Id})");
    var setParamRes = EpicEye.SetParameter(ip, firstPreset.Id);
    Console.WriteLine(setParamRes.Status == 0 ? "setParameter success!" : "setParameter failed!");
    if (setParamRes.Status != 0) Environment.ExitCode = 1;
}
else
{
    Console.WriteLine("setParameter failed: parameter list is empty");
    Environment.ExitCode = 1;
}
Console.WriteLine();

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
