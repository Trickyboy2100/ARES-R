// 作用：提供一套不依赖相机网页的完整手眼标定控制台流程。
// 输入：可选 camera_ip；未指定时阻塞搜索。机器人位姿由用户按所选型号的 Marks 顺序输入。
// 流程：读取完整机器人库 -> 默认选择首品牌首型号 -> 配置安装方式/机器人规则 -> 成对采集位姿 -> 计算 -> 可选精度检查。
// 数据规则：每个 BoardPoseArray 必须与同一静止时刻的 RobotPose 配对；移动机器人后不能复用上一点的数据。
// 相机影响：配置步骤会保存安装方式和 RobotParams；计算成功后服务端会保存手眼结果。不会写入相机内参。

using System.Globalization;
using TFTech;
using TFTech.Models;

Console.WriteLine("SDK Version: " + EpicEye.GetSDKVersion());
Console.WriteLine("Hand-eye calibration console workflow.");
Console.WriteLine("Usage: HandEyeCalibration [camera_ip]");

string ip = ResolveIp(args);
if (ip.Length == 0)
{
    Environment.ExitCode = 1;
    return;
}

// 机器人库决定 robotPose 的轴数、旋转表达、欧拉顺序、角度单位和字段顺序。
// Example 必须自行完成这一步，不能依赖用户曾在相机网页中选择过机器人。
ApiResponse<Dictionary<string, List<RobotInfo>>> robotLibraryResponse = EpicEye.GetRobotLibrary(ip);
if (robotLibraryResponse.Status != 0 || robotLibraryResponse.Data == null || robotLibraryResponse.Data.Count == 0)
{
    Console.WriteLine("Failed to read robot library: " + robotLibraryResponse.ErrorMessage);
    Environment.ExitCode = 1;
    return;
}

KeyValuePair<string, List<RobotInfo>> firstBrand = robotLibraryResponse.Data.First();
if (firstBrand.Value.Count == 0)
{
    Console.WriteLine($"Robot brand {firstBrand.Key} has no models.");
    Environment.ExitCode = 1;
    return;
}
RobotInfo firstRobot = firstBrand.Value[0];
var robotParameters = new RobotParameters
{
    Brand = firstRobot.Brand,
    Model = firstRobot.Model,
    RotationType = firstRobot.RotationType,
    EulerType = firstRobot.EulerType,
    AngleUnit = firstRobot.AngleUnit,
    IsCustomRobot = false,
    AxisNumber = firstRobot.AxisNumber,
    Marks = firstRobot.Marks
};
Console.WriteLine($"Robot library loaded: {robotLibraryResponse.Data.Count} brands. Default robot: [{robotParameters.Brand}] {robotParameters.Model}");
HandEyeInstallationType installationType = ReadChoice("Installation type: 0=Eye-To-Hand, 1=Eye-In-Hand", 0, 1) == 0 ? HandEyeInstallationType.ETH : HandEyeInstallationType.EIH;

// CalculateHandEyeCalibrationResult 在相机端读取这里保存的 RobotParams 来解释后续 robotPose。
ApiResponse<bool> configureResponse = EpicEye.ConfigureHandEyeCalibration(ip, new ConfigureHandEyeCalibrationParams
{
    InstallationType = installationType,
    RobotParams = robotParameters
});
if (configureResponse.Status != 0 || configureResponse.Data != true)
{
    Console.WriteLine("Failed to save robot parameters: " + configureResponse.ErrorMessage);
    Environment.ExitCode = 1;
    return;
}

Console.WriteLine($"Configured: installation={installationType}, robot=[{robotParameters.Brand}] {robotParameters.Model}, axis={robotParameters.AxisNumber}, rotation={robotParameters.RotationType}, euler={robotParameters.EulerType}, unit={robotParameters.AngleUnit}");
Console.WriteLine("Robot pose values must use the order shown below and the configured unit.");
Console.WriteLine("Pose fields: " + GetPoseMarks(robotParameters));

var points = new List<HandEyePointData>();
while (true)
{
    Console.WriteLine();
    Console.WriteLine("1=Capture point  2=Calculate  3=Robot accuracy check  4=List points  5=Clear points  0=Exit");
    int action = ReadChoice("Select action", 0, 5);
    if (action == 0)
    {
        break;
    }
    if (action == 1)
    {
        CapturePoint(ip, robotParameters, points);
        continue;
    }
    if (action == 2)
    {
        CalibrationResult? result = Calculate(ip, installationType, robotParameters, points);
        if (result?.Success == true && ReadYesNo("Run hand-eye result accuracy check now?"))
        {
            RunHandEyeAccuracyCheck(ip, installationType, robotParameters);
        }
        continue;
    }
    if (action == 3)
    {
        RunRobotAccuracyCheck(ip, robotParameters);
        continue;
    }
    if (action == 4)
    {
        PrintPoints(points);
        continue;
    }
    points.Clear();
    Console.WriteLine("All collected points were cleared.");
}

static void CapturePoint(string ip, RobotParameters robot, List<HandEyePointData> points)
{
    // 先让用户完成机械移动并稳定，再触发相机拍摄和标定板位姿检测。
    // 检测成功后立即输入当前机器人位姿，保证两份数据属于同一个物理点位。
    Console.Write("Move the calibration board/robot to a new pose, then press Enter to capture.");
    Console.ReadLine();
    ApiResponse<CalibrationBoardPoseData> response = EpicEye.GetCalibrationBoardPose(ip, 30000);
    if (response.Status != 0 || response.Data?.BoardPoseArray?.Length != 7)
    {
        Console.WriteLine("Capture failed: " + response.ErrorMessage);
        return;
    }

    var point = new HandEyePointData
    {
        Id = points.Count == 0 ? 1 : points.Max(value => value.Id) + 1,
        BoardPoseArray = response.Data.BoardPoseArray,
        RobotPose = ReadRobotPose(robot)
    };
    points.Add(point);
    Console.WriteLine($"Point #{point.Id} captured. Board pose=[{string.Join(", ", point.BoardPoseArray)}], intrinsic accuracy={response.Data.CameraInternalAccuracy}");
}

static CalibrationResult? Calculate(string ip, HandEyeInstallationType installationType, RobotParameters robot, List<HandEyePointData> points)
{
    if (points.Count == 0)
    {
        Console.WriteLine("No calibration points have been collected.");
        return null;
    }

    SpecialParams? specialParams = null;
    if (robot.AxisNumber is 3 or 4)
    {
        // 3/4 轴机器人自由度不足，需要额外提供工具偏移和标定板参考位置；6 轴不需要。
        Console.WriteLine("Three/four-axis calibration requires the additional parameters defined by the camera workflow.");
        specialParams = new SpecialParams
        {
            Offset = ReadFloatArray("Offset", 3),
            BoardPosition = ReadFloatArray("Board position", 3)
        };
    }

    // 该调用不仅返回计算结果；相机服务端还会把成功结果保存到手眼标定数据中。
    ApiResponse<CalibrationResult> response = EpicEye.CalculateHandEyeCalibrationResult(ip, new CalculateHandEyeCalibrationResultParams
    {
        InstallationType = installationType,
        HandEyePoints = points,
        SpecialParams = specialParams
    }, 60000);
    if (response.Status != 0 || response.Data == null)
    {
        Console.WriteLine("Calculation failed: " + response.ErrorMessage);
        return null;
    }

    CalibrationResult result = response.Data;
    Console.WriteLine($"Calibration success: {result.Success}");
    Console.WriteLine("Pose [x,y,z,rx,ry,rz]: " + string.Join(", ", result.Pose));
    Console.WriteLine($"Error: rotation mean/max={result.HecError.RotMean}/{result.HecError.RotMax} deg, translation mean/max={result.HecError.TransMean}/{result.HecError.TransMax} mm");
    Console.WriteLine("Warning type: " + result.HecWarnData.WarnType);
    foreach (HecWarnPair pair in result.HecWarnData.WarnPairs)
    {
        Console.WriteLine($"Warning pair: {pair.Item1}, {pair.Item2}");
    }
    Console.WriteLine("The camera stores the calculation result as part of its hand-eye calibration data.");
    return result;
}

static void RunRobotAccuracyCheck(string ip, RobotParameters robot)
{
    // 机器人精度检查比较“机器人报告的移动量”和“相机检测到的标定板移动量”。
    // 起点和终点都必须重新采集标定板位姿，并输入各自对应的机器人位姿。
    string direction = ReadChoice("Direction: 0=X, 1=Y, 2=Z", 0, 2) switch
    {
        1 => "y",
        2 => "z",
        _ => "x"
    };
    RobotAccuracyPoint? start = CaptureAccuracyPoint(ip, robot, "start");
    if (start == null)
    {
        return;
    }
    RobotAccuracyPoint? end = CaptureAccuracyPoint(ip, robot, "end");
    if (end == null)
    {
        return;
    }

    ApiResponse<RobotAccuracyResult> response = EpicEye.CalculateRobotAccuracy(ip, new CalculateRobotAccuracyParams
    {
        Direction = direction,
        DirectionPoseData = new RobotAccuracyDirectionData
        {
            StartPoint = start,
            EndPoint = end
        }
    }, 30000);
    if (response.Status != 0 || response.Data == null)
    {
        Console.WriteLine("Robot accuracy calculation failed: " + response.ErrorMessage);
        return;
    }
    RobotAccuracyResult result = response.Data;
    Console.WriteLine($"Robot accuracy: boardDistance={result.BoardDistance}, robotDistance={result.RobotDistance}, difference={result.MoveDistance}, positionPrecision={result.PositionPrecision}, orientation=[{string.Join(", ", result.OrientationPrecision)}]");
}

static RobotAccuracyPoint? CaptureAccuracyPoint(string ip, RobotParameters robot, string name)
{
    Console.Write($"Move to the {name} pose, then press Enter to capture.");
    Console.ReadLine();
    ApiResponse<CalibrationBoardPoseData> response = EpicEye.GetCalibrationBoardPose(ip, 30000);
    if (response.Status != 0 || response.Data?.BoardPoseArray?.Length != 7)
    {
        Console.WriteLine("Capture failed: " + response.ErrorMessage);
        return null;
    }
    return new RobotAccuracyPoint
    {
        BoardPoseArray = response.Data.BoardPoseArray,
        RobotPose = ReadRobotPose(robot),
        CameraInternalAccuracy = response.Data.CameraInternalAccuracy
    };
}

static void RunHandEyeAccuracyCheck(string ip, HandEyeInstallationType installationType, RobotParameters robot)
{
    // 使用刚保存的手眼结果，把新检测的标定板位姿转换到机器人基坐标系。
    // Eye-in-Hand 还需要当前机器人位姿；Eye-to-Hand 的相机固定，因此 robotPose 为空。
    Console.Write("Place the board in the view, then press Enter to capture for result verification.");
    Console.ReadLine();
    ApiResponse<CalibrationBoardPoseData> boardResponse = EpicEye.GetCalibrationBoardPose(ip, 30000);
    if (boardResponse.Status != 0 || boardResponse.Data?.BoardPoseArray?.Length != 7)
    {
        Console.WriteLine("Capture failed: " + boardResponse.ErrorMessage);
        return;
    }

    float[] robotPose = installationType == HandEyeInstallationType.EIH ? ReadRobotPose(robot) : [];
    string direction = ReadChoice("Board Z direction: 0=Up, 1=Down", 0, 1) == 0 ? "up" : "down";
    ApiResponse<HandEyeAccuracyResult> response = EpicEye.CalculateHandEyeAccuracy(ip, new CalculateHandEyeAccuracyParams
    {
        BoardPoseArray = boardResponse.Data.BoardPoseArray,
        RobotPose = robotPose,
        GridSize = boardResponse.Data.GridSize,
        DirectionZ = direction
    }, 30000);
    if (response.Status != 0 || response.Data == null)
    {
        Console.WriteLine("Hand-eye accuracy check failed: " + response.ErrorMessage);
        return;
    }
    Console.WriteLine("Board pose in robot base coordinates: " + string.Join(", ", response.Data.BoardPoseArray));
}

static float[] ReadRobotPose(RobotParameters robot)
{
    // 四元数姿态为 7 个值；欧拉角、固定角和旋转向量均为 6 个值。
    // 字段名和单位直接来自机器人库，不能按通用 XYZ/RPY 顺序自行猜测。
    int count = robot.RotationType == RobotRotationType.Quaternion ? 7 : 6;
    return ReadFloatArray($"Robot pose ({GetPoseMarks(robot)})", count);
}

static string GetPoseMarks(RobotParameters robot)
{
    if (!string.IsNullOrWhiteSpace(robot.Marks))
    {
        return robot.Marks;
    }
    return robot.RotationType == RobotRotationType.Quaternion ? "X,Y,Z,Qx,Qy,Qz,Qw" : "X,Y,Z,Rx,Ry,Rz";
}

static float[] ReadFloatArray(string label, int count)
{
    while (true)
    {
        Console.Write($"{label}; enter {count} values separated by spaces: ");
        string[] tokens = (Console.ReadLine() ?? string.Empty).Split([' ', '\t', ','], StringSplitOptions.RemoveEmptyEntries);
        if (tokens.Length == count && tokens.All(value => float.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out _)))
        {
            return tokens.Select(value => float.Parse(value, CultureInfo.InvariantCulture)).ToArray();
        }
        Console.WriteLine("Invalid input.");
    }
}

static int ReadChoice(string prompt, int min, int max, int[]? allowed = null)
{
    while (true)
    {
        Console.Write(prompt + ": ");
        if (int.TryParse(Console.ReadLine(), out int value) && value >= min && value <= max && (allowed == null || allowed.Contains(value)))
        {
            return value;
        }
        Console.WriteLine("Invalid choice.");
    }
}

static bool ReadYesNo(string prompt)
{
    return ReadChoice(prompt + " 0=No, 1=Yes", 0, 1) == 1;
}

static void PrintPoints(IReadOnlyList<HandEyePointData> points)
{
    if (points.Count == 0)
    {
        Console.WriteLine("No points collected.");
        return;
    }
    foreach (HandEyePointData point in points)
    {
        Console.WriteLine($"#{point.Id}: board=[{string.Join(", ", point.BoardPoseArray)}], robot=[{string.Join(", ", point.RobotPose)}]");
    }
}

static string ResolveIp(string[] args)
{
    if (args.Length > 0 && !string.IsNullOrWhiteSpace(args[0]))
    {
        return args[0];
    }
    List<EpicEyeInfo> cameras = EpicEye.SearchCamera();
    if (cameras.Count == 0 || string.IsNullOrWhiteSpace(cameras[0].IP))
    {
        Console.WriteLine("Camera not found.");
        return string.Empty;
    }
    return cameras[0].IP!;
}
