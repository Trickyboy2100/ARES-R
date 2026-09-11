// 作用：提供受用户确认控制的完整内参标定流程，不会自动连续拍摄或自动写入。
// 输入：<camera_ip> [minimum_pair_count] [board_type]；未给 board_type 时先自动识别标定板。
// 流程：识别板型 -> 多位姿采集图对 -> 用户保留/删除 -> 达到最少数量后计算 -> 检查 RMS -> 用户确认写入。
// 数据规则：每次采集前必须重新放置标定板；同一位姿的重复图对不能增加有效姿态覆盖。
// 相机影响：Add/Remove/Calculate 只操作相机端临时标定工作区；只有用户选择 W 后才写入正式内参。
// 写入内容：始终使用 Calculate 返回的完整 CameraParametersConfig，保留多路深度和彩色相机的完整参数结构。

using System.Collections;
using Newtonsoft.Json;
using TFTech;
using TFTech.Models;

Console.WriteLine("SDK Version: " + EpicEye.GetSDKVersion());
Console.WriteLine("Example: interactively collect board poses, calculate intrinsic parameters, and optionally write them.");
Console.WriteLine("Usage: IntrinsicCalibration [camera_ip] [minimum_pair_count] [board_type]");

string ip = ResolveIp(args);
if (ip.Length == 0)
{
    Environment.ExitCode = 1;
    return;
}

int minimumPairCount = 4;
if (args.Length > 1 && int.TryParse(args[1], out int count)) minimumPairCount = Math.Max(4, count);

int boardType = -1;
if (args.Length > 2 && int.TryParse(args[2], out int parsedBoardType)) boardType = parsedBoardType;

if (boardType < 0)
{
    // IdentifyBoard 只识别板型并返回预览，不会增加标定图对。
    if (ReadChoice("Place the calibration board in view. [I] Identify board  [Q] Quit: ", "IQ") == 'Q')
    {
        Console.WriteLine("Exited without changing intrinsic parameters.");
        return;
    }

    var identify = EpicEye.IdentifyBoard(ip);
    if (identify.Status != 0 || identify.Data == null)
    {
        Console.WriteLine("identifyBoard failed! " + identify.ErrorMessage);
        Environment.ExitCode = 1;
        return;
    }

    boardType = identify.Data.BoardType;
    Console.WriteLine($"Board type: {boardType}");
    Console.WriteLine("Board hint: " + identify.Data.BoardHint);
    Console.WriteLine("Identify preview count: " + identify.Data.PreviewImages.Count);
}

if (boardType < 0)
{
    Console.WriteLine("Invalid board type. Pass board_type manually if auto identify failed.");
    Environment.ExitCode = 2;
    return;
}

int retainedPairCount = 0;
while (true)
{
    char action = retainedPairCount >= minimumPairCount
        ? ReadChoice($"\nRetained pairs: {retainedPairCount}. [C] Capture after repositioning board  [K] Calculate  [Q] Quit: ", "CKQ")
        : ReadChoice($"\nRetained pairs: {retainedPairCount}/{minimumPairCount}. Reposition and stabilize the board. [C] Capture  [Q] Quit: ", "CQ");

    if (action == 'Q')
    {
        Console.WriteLine("Exited without changing intrinsic parameters.");
        return;
    }

    if (action == 'C')
    {
        // AddCalibImage 会在相机端采集一组标定图并加入临时工作区。
        // 返回的 pairIndex 是后续删除该图对的唯一标识，不能用本地列表序号代替。
        var add = EpicEye.AddCalibImage(ip, boardType);
        if (add.Status != 0 || add.Data == null)
        {
            Console.WriteLine("addCalibImage failed! " + add.ErrorMessage);
            continue;
        }

        IntrinsicAddCalibImageResponse capturedPair = add.Data;
        PrintCapturedPair(capturedPair);

        if (!capturedPair.DetectSuccess)
        {
            // 检测不完整的图对必须立即从相机工作区删除，否则可能污染后续计算。
            Console.WriteLine("The calibration board was not detected in every required image. This pair cannot be used and will be removed.");
            if (!TryRemovePair(ip, capturedPair.PairIndex, out retainedPairCount))
            {
                Environment.ExitCode = 1;
                return;
            }
            continue;
        }

        char keep = ReadChoice("[K] Keep this pair  [R] Remove and recapture  [Q] Remove and quit: ", "KRQ");
        if (keep == 'K')
        {
            retainedPairCount = capturedPair.PairCount;
            Console.WriteLine($"Pair retained. Retained pair count: {retainedPairCount}");
            continue;
        }

        if (!TryRemovePair(ip, capturedPair.PairIndex, out retainedPairCount))
        {
            Environment.ExitCode = 1;
            return;
        }
        if (keep == 'Q')
        {
            Console.WriteLine("Exited without changing intrinsic parameters.");
            return;
        }
        continue;
    }

    // Calculate 只根据当前保留图对计算候选参数，不会写入正式内参。
    var calculation = EpicEye.Calculate(ip);
    if (calculation.Status != 0 || calculation.Data == null)
    {
        Console.WriteLine("calculate failed! " + calculation.ErrorMessage);
        Console.WriteLine("You can reposition the board and capture more pairs, or quit.");
        continue;
    }

    PrintCalculation(calculation.Data);
    if (calculation.Data.ShouldWarnRms)
    {
        // RMS 已超过服务端安全阈值时禁止写入，要求用户补充更有效的姿态后重新计算。
        Console.WriteLine("Calibration RMS exceeds the safe threshold. Writing is disabled; capture more valid poses or quit.");
        continue;
    }
    if (calculation.Data.CameraParametersConfig == null)
    {
        Console.WriteLine("calculate did not return cameraParametersConfig. Writing is disabled.");
        continue;
    }

    Console.WriteLine("Complete configuration proposed for writing:");
    Console.WriteLine(JsonConvert.SerializeObject(calculation.Data.CameraParametersConfig, Formatting.Indented));
    char writeChoice = ReadChoice("[W] Write this configuration to the camera  [B] Back to capture  [Q] Quit without writing: ", "WBQ");
    if (writeChoice == 'B') continue;
    if (writeChoice == 'Q')
    {
        Console.WriteLine("Exited without changing intrinsic parameters.");
        return;
    }

    // 唯一会覆盖相机正式内参的操作；必须传递完整 CameraParametersConfig，不能只传扁平 CameraParameters。
    var write = EpicEye.SetCameraIntrinsicParameters(ip, calculation.Data.CameraParametersConfig);
    if (write.Status == 0 && write.Data == true)
    {
        Console.WriteLine("Intrinsic parameters written to device.");
        return;
    }
    Console.WriteLine("writeIntrinsicCameraParameters failed! " + write.ErrorMessage);
}

static void PrintCapturedPair(IntrinsicAddCalibImageResponse result)
{
    string boardPose = result.BoardPose is { Length: 7 } ? $"[{string.Join(", ", result.BoardPose)}]" : "unavailable";
    Console.WriteLine($"Capture result: pairIndex={result.PairIndex}, pairCount={result.PairCount}, detectSuccess={result.DetectSuccess}");
    Console.WriteLine($"Board pose [tx,ty,tz,qx,qy,qz,qw]: {boardPose}");
    Console.WriteLine($"Board tilt angle: {result.BoardTiltAngle}, tilt warning: {result.BoardTiltWarning}");
    Console.WriteLine($"Preview image count: {result.PreviewImages.Count}");
    foreach (ImageInfoData preview in result.PreviewImages)
    {
        Console.WriteLine($"  {preview.Name}: {preview.Width}x{preview.Height}, {preview.DataUri}");
    }
}

static void PrintCalculation(IntrinsicCalculateResponse result)
{
    Console.WriteLine($"\nIntrinsic calibration stereoRms: {result.StereoRms}, shouldWarnRms: {result.ShouldWarnRms}");
    if (result.ColorStereoRms.HasValue)
    {
        Console.WriteLine($"Color calibration stereoRms: {result.ColorStereoRms.Value}");
        Console.WriteLine("Color camera parameters:");
        PrintHashtable(result.ColorCameraParameters);
        Console.WriteLine("Color parameter errors:");
        PrintHashtable(result.ColorParameterErrors);
    }
    Console.WriteLine("Camera parameters:");
    PrintHashtable(result.CameraParameters);
    Console.WriteLine("Parameter errors:");
    PrintHashtable(result.ParameterErrors);
}

static bool TryRemovePair(string ip, int pairIndex, out int remainingPairCount)
{
    remainingPairCount = 0;
    if (pairIndex < 0)
    {
        Console.WriteLine("The captured pair has no valid pair index. Calculation is disabled to avoid using an unknown dataset.");
        return false;
    }

    var remove = EpicEye.RemoveCalibImage(ip, pairIndex);
    if (remove.Status != 0 || remove.Data == null)
    {
        Console.WriteLine("removeCalibImage failed! Calculation is disabled to avoid using an invalid pair. " + remove.ErrorMessage);
        return false;
    }

    remainingPairCount = remove.Data.PairCount;
    Console.WriteLine($"Removed pair index {remove.Data.RemovedIndex}. Retained pair count: {remainingPairCount}");
    return true;
}

static char ReadChoice(string prompt, string allowedChoices)
{
    while (true)
    {
        Console.Write(prompt);
        string? input = Console.ReadLine();
        if (input == null) return 'Q';
        string normalized = input.Trim().ToUpperInvariant();
        if (normalized.Length == 1 && allowedChoices.Contains(normalized[0])) return normalized[0];
        Console.WriteLine("Invalid choice. Available choices: " + string.Join("/", allowedChoices.ToCharArray()));
    }
}

static void PrintHashtable(Hashtable? table)
{
    if (table == null)
    {
        Console.WriteLine("  (null)");
        return;
    }
    foreach (DictionaryEntry entry in table)
    {
        Console.WriteLine($"  {entry.Key}: {entry.Value}");
    }
}

static string ResolveIp(string[] args)
{
    if (args.Length > 0 && !string.IsNullOrWhiteSpace(args[0])) return args[0];

    var cameras = EpicEye.SearchCamera();
    if (cameras.Count == 0 || string.IsNullOrWhiteSpace(cameras[0].IP))
    {
        Console.WriteLine("Camera not found!");
        return string.Empty;
    }
    return cameras[0].IP!;
}
