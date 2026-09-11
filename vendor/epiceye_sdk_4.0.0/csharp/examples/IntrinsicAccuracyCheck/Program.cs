// 作用：执行一次内参精度检查，输出标定板位姿、深度/彩色尺寸误差和双目/彩色对齐误差。
// 输入：可选 camera_ip；未指定时阻塞搜索并使用第一台相机。
// 前提：标定板完整位于视野中，并满足页面输出的距离、尺寸和倾角要求。
// 相机影响：触发拍摄和检查计算，但不会写入或覆盖相机内参。

using TFTech;
using TFTech.Models;

string ip = ResolveIp(args);
if (ip.Length == 0)
{
    Environment.ExitCode = 1;
    return;
}
Console.WriteLine($"Camera: {ip}");

ApiResponse<IntrinsicAccuracyCheckResult> response = await EpicEye.CheckIntrinsicAccuracyAsync(ip);
if (response.Status != 0 || response.Data == null)
{
    Console.Error.WriteLine($"CheckIntrinsicAccuracy failed: {response.ErrorMessage}");
    Environment.ExitCode = 1;
    return;
}

PrintResult(response.Data);

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

static void PrintResult(IntrinsicAccuracyCheckResult result)
{
    Console.WriteLine($"Board type: {result.BoardTypeDetected}");
    Console.WriteLine($"Board hint: {result.BoardHint}");
    Console.WriteLine($"Depth camera accuracy: {result.CalibrationBoardSizeRatio:F6}, pass: {result.CameraAccuracyPass}");
    Console.WriteLine($"Depth average alignment error: {result.StereoAveragePixelError:F6}, pass: {result.StereoAveragePass}");
    Console.WriteLine($"Depth max alignment error: {result.StereoMaxPixelError:F6}, pass: {result.StereoMaxPass}");
    Console.WriteLine($"Color camera accuracy: {result.ColorCalibrationBoardSizeRatio:F6}, pass: {result.ColorCameraAccuracyPass}");
    Console.WriteLine($"Color average alignment error: {result.ColorStereoAveragePixelError:F6}, pass: {result.ColorStereoAveragePass}");
    Console.WriteLine($"Color max alignment error: {result.ColorStereoMaxPixelError:F6}, pass: {result.ColorStereoMaxPass}");
    Console.WriteLine($"Stereo metrics valid: {result.StereoMetricsValid}");
    Console.WriteLine($"Board tilt angle: {result.BoardTiltAngle:F6}, warning: {result.BoardTiltWarning}");
    Console.WriteLine($"Preview image count: {result.PreviewImages.Count}");

    if (result.BoardPositionValid && result.BoardPose is { Length: >= 3 })
    {
        float x = result.BoardPose[0];
        float y = result.BoardPose[1];
        float z = result.BoardPose[2];
        double distance = Math.Sqrt(x * x + y * y + z * z);
        Console.WriteLine($"Board position (mm): X={x:F1}, Y={y:F1}, Z={z:F1}");
        Console.WriteLine($"Board distance (mm): {distance:F1}");
    }
    else
    {
        Console.WriteLine("Board position: invalid");
    }

    bool colorMetricsPresent = result.ColorCalibrationBoardSizeRatio > 0
        || result.ColorStereoAveragePixelError > 0
        || result.ColorStereoMaxPixelError > 0;
    bool checkPassed = result.CameraAccuracyPass
        && (!result.StereoMetricsValid || result.StereoAveragePass && result.StereoMaxPass)
        && (!colorMetricsPresent || result.ColorCameraAccuracyPass && result.ColorStereoAveragePass && result.ColorStereoMaxPass);
    Console.WriteLine($"Intrinsic accuracy check passed: {checkPassed}");
}
