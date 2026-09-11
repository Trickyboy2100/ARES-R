using System.Text.Json;

namespace AtomSdkExamples;

/// <summary>
/// 示例程序共用的配置和输出辅助方法。
/// 所有值都可以通过环境变量覆盖，避免用户为了换一张图而修改示例源码。
/// </summary>
public static class ExampleSettings
{
    public static string BaseUrl => Get("ATOM_BASE_URL", "http://127.0.0.1:10026");

    public static string GraphName => Get("ATOM_GRAPH_NAME", "demo_graph");

    public static string GraphNodeId => Get("ATOM_GRAPH_NODE_ID", "graph-node-id");

    public static string NodeId => Get("ATOM_NODE_ID", "node-id");

    public static string InnerNodeId => Get("ATOM_INNER_NODE_ID", "inner-node-id");

    public static string NodeName => Get("ATOM_NODE_NAME", "Filter");

    public static string TargetNodeName => Get("ATOM_TARGET_NODE_NAME", "Filter");

    public static string PortName => Get("ATOM_PORT_NAME", "points");

    public static string InputPortName => Get("ATOM_INPUT_PORT_NAME", "points");

    public static string BindingName => Get("ATOM_BINDING_NAME", "sdk_example_output");

    public static string SingleNodeName => Get("ATOM_SINGLE_NODE_NAME", NodeName);

    public static string Get(string name, string fallback)
    {
        var value = Environment.GetEnvironmentVariable(name);
        return string.IsNullOrWhiteSpace(value) ? fallback : value;
    }

    public static string ArgumentOrSetting(string[] args, int index, string environmentName, string fallback)
    {
        return args.Length > index && !string.IsNullOrWhiteSpace(args[index])
            ? args[index]
            : Get(environmentName, fallback);
    }

    public static string RequiredFile(string environmentName)
    {
        var path = Environment.GetEnvironmentVariable(environmentName);
        if (string.IsNullOrWhiteSpace(path) || !File.Exists(path))
        {
            throw new InvalidOperationException(
                $"请先把 {environmentName} 设置为真实存在的文件路径。当前值：{path ?? "<未设置>"}");
        }

        return path;
    }

    public static byte[] OptionalFileBytes(string environmentName, string fallbackText)
    {
        var path = Environment.GetEnvironmentVariable(environmentName);
        return !string.IsNullOrWhiteSpace(path) && File.Exists(path)
            ? File.ReadAllBytes(path)
            : System.Text.Encoding.UTF8.GetBytes(fallbackText);
    }

    public static object IdentityTransform => new[] { 0.0, 0.0, 0.0, 0.0, 0.0, 0.0 };

    public static object DefaultRoi => new
    {
        min = new { x = -1.0, y = -1.0, z = -1.0 },
        max = new { x = 1.0, y = 1.0, z = 1.0 },
        cam2ROIFrame = IdentityTransform,
    };

    public static void PrintJson(string label, JsonElement value)
    {
        Console.WriteLine($"{label}:\n{JsonSerializer.Serialize(value, new JsonSerializerOptions { WriteIndented = true })}");
    }

    public static void PrintStatus(string label, int? status, double? timestamp = null)
    {
        var suffix = timestamp.HasValue ? $", timestamp={timestamp}" : string.Empty;
        Console.WriteLine($"{label}: status={status?.ToString() ?? "<未返回>"}{suffix}");
    }
}
