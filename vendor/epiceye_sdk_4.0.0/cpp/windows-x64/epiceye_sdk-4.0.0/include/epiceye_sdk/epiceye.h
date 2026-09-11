#ifndef TFTECH_EPICEYESDK_EPICEYE_H
#define TFTECH_EPICEYESDK_EPICEYE_H

#include <array>
#include <optional>
#include <vector>
#include <functional>
#include <memory>
#include <map>
#include <cstdint>
#include <string>
#include <string_view>
#include "nlohmann_json.hpp"
#include "epicraw_document.hpp"
#include "epiceye_export.h"

namespace TFTech {

struct EpicEyeInfo {
    std::string Version;  //服务端版本
    std::string SN;     //序列号
    std::string IP;     //相机IP地址
    std::string model;  //相机的型号
    std::string alias;  //相机的别名,可通过Web UI进行更改
    uint32_t width;     //图像的width
    uint32_t height;    //图像的height
};

// 相机 IP 配置（字段名与 C# EpicEyeIPConfig 对齐）
struct EpicEyeIPConfig {
    std::string ip;                            // 手动模式下要设置的新 IP（DHCP 可留空）
    std::string netMask = "255.255.255.0";     // 子网掩码
    std::string type = "DHCP";                 // "DHCP" 或 "Manual"
    std::string sn = "IMPOSSIBLE_SERIAL_NUMBER"; // 目标相机当前序列号，用于防止误改其他设备
};

struct Stream2DStatus {
    bool isStreaming = false;
    int peerCount = 0;
    int cameraCount = 0;
};

struct Stream2DWebRtcOfferResult {
    std::string peerId;
    std::string answerSdp;
};

struct Stream2DRtcFrame {
    int frameIndex = 0;
    uint32_t timestamp = 0;
    int payloadType = -1;
    std::string codec;
    // 相机输出的 H264 码流帧（Annex-B Access Unit），不解码、不重新编码。
    std::vector<uint8_t> sample;
};

struct Stream2DRtcSessionOptions {
    int fps = 60;
    int cameraIndex = 0;
};

struct SimpleCameraParameter {
    std::string Id;
    std::string Name;
};

using Stream2DFrameCallback = std::function<void(const Stream2DRtcFrame &)>;

class EPICEYE_SDK_API Stream2DRtcSession {
public:
    struct Impl;

    ~Stream2DRtcSession();
    Stream2DRtcSession(const Stream2DRtcSession &) = delete;
    Stream2DRtcSession &operator=(const Stream2DRtcSession &) = delete;

    bool isRunning() const;
    int frameCount() const;
    std::string peerId() const;

private:
    explicit Stream2DRtcSession(std::shared_ptr<Impl> impl);
    void stop();

    std::shared_ptr<Impl> impl_;

    friend bool startStream2DRtcSessionImpl(std::string ip,
                                            const Stream2DRtcSessionOptions &options,
                                            const Stream2DFrameCallback &onFrame,
                                            std::unique_ptr<Stream2DRtcSession> &session);
    friend class EpicEye;
};

using DiscoveryCallback = std::function<void()>;

/** EpicRaw3 原始图像的只读描述；data 生命周期依赖输入 EpicRaw 字节。 */
struct EpicRawImage {
    EpicRaw3DataType dataType = EpicRaw3DataType::DepthSrcImg1;
    int width = 0;
    int height = 0;
    int matType = 0;
    std::string_view data;
};

enum class LineScanStatus {
    Idle,
    Starting,
    WaitingForConnection,
    Streaming,
    Finalizing,
    Saving,
    Completed,
    Stopping,
    Stopped,
    Failed,
    Unknown
};

using IntrinsicIdentifyBoardResult = nlohmann::json;
using IntrinsicAccuracyCheckResult = nlohmann::json;
using IntrinsicAddCalibImageResult = nlohmann::json;
using IntrinsicRemoveCalibImageResult = nlohmann::json;
using IntrinsicCalculateResult = nlohmann::json;

enum class HandEyeInstallationType { EyeToHand, EyeInHand };
enum class RobotRotationType { EulerPose, FixedPose, Quaternion, RotationVector };
enum class RobotEulerType { XYZ, XZY, YXZ, YZX, ZXY, ZYX, XYX, YXY, XZX, ZXZ, YZY, ZYZ };
enum class RobotAngleUnit { Degree, Radian };

struct RobotParameters {
    std::string brand;
    std::string model;
    RobotRotationType rotationType = RobotRotationType::EulerPose;
    RobotEulerType eulerType = RobotEulerType::XYZ;
    RobotAngleUnit angleUnit = RobotAngleUnit::Degree;
    bool isCustomRobot = false;
    int axisNumber = 6;
    std::string marks = "X,Y,Z,Rx,Ry,Rz";
};

struct RobotInfo : RobotParameters {
    std::string id;
    bool downloaded = false;
    std::string imgUrl;
    std::string createTime;
    bool masksOrderReverse = false;
    std::string ikSolverType;
    float payload = 0.0f;
    float reach = 0.0f;
};

using RobotLibrary = std::map<std::string, std::vector<RobotInfo>>;

struct HandEyeSpecialParams {
    std::array<float, 3> offset{{0, 0, 0}};
    std::array<float, 3> boardPosition{{0, 0, 0}};
};

struct HandEyePoint {
    int id = 0;
    std::array<float, 7> boardPoseArray{{0, 0, 0, 0, 0, 0, 1}};
    std::vector<float> robotPose;
};

struct HandEyeCalculationRequest {
    HandEyeInstallationType installationType = HandEyeInstallationType::EyeToHand;
    std::vector<HandEyePoint> handEyePoints;
    std::optional<HandEyeSpecialParams> specialParams;
};

struct HecError {
    float rotMean = 0.0f;
    float rotMax = 0.0f;
    float transMean = 0.0f;
    float transMax = 0.0f;
};

struct HecWarnData {
    std::string warnType;
    std::vector<std::array<int, 2>> warnPairs;
};

struct HandEyeCalibrationResult {
    bool success = false;
    std::vector<float> pose;
    std::array<float, 16> matrix4x4{};
    HecError hecError;
    HecWarnData hecWarnData;
};

struct CalibrationBoardPose {
    std::array<float, 7> boardPoseArray{{0, 0, 0, 0, 0, 0, 1}};
    float cameraInternalAccuracy = 0.0f;
    int gridSize = 0;
    int imageWidth = 0;
    int imageHeight = 0;
    std::string imgBase64;
    std::string pointCloudBase64;
};

struct HandEyeCalibrationData {
    HandEyeInstallationType installationType = HandEyeInstallationType::EyeToHand;
    std::optional<RobotParameters> robotParams;
    nlohmann::json calibrationPointDict;
    nlohmann::json specialParams;
    nlohmann::json calibrationResult;
};

struct RobotAccuracyPoint {
    std::array<float, 7> boardPoseArray{{0, 0, 0, 0, 0, 0, 1}};
    std::vector<float> robotPose;
    float cameraInternalAccuracy = 0.0f;
};

struct RobotAccuracyDirectionData {
    RobotAccuracyPoint startPoint;
    RobotAccuracyPoint endPoint;
};

struct RobotAccuracyRequest {
    RobotAccuracyDirectionData directionPoseData;
    std::string direction = "x";
};

struct RobotAccuracyResult {
    float boardDistance = 0.0f;
    float robotDistance = 0.0f;
    float moveDistance = 0.0f;
    float positionPrecision = 0.0f;
    std::array<float, 3> orientationPrecision{{0, 0, 0}};
};

struct HandEyeAccuracyRequest {
    std::array<float, 7> boardPoseArray{{0, 0, 0, 0, 0, 0, 1}};
    std::vector<float> robotPose;
    int gridSize = 0;
    std::string directionZ = "up";
};

struct HandEyeAccuracyResult {
    std::array<float, 7> boardPoseArray{{0, 0, 0, 0, 0, 0, 1}};
    std::array<float, 16> matrix4x4{};
    std::array<float, 16> robotMatrix4x4{};
    double x = 0.0;
    double y = 0.0;
    double x1 = 0.0;
    double y1 = 0.0;
    double x2 = 0.0;
    double y2 = 0.0;
};

enum class ReconstructorType {
    Mono = 0,
    BinoWithoutColor = 1,
    BinoWithColor = 2,
    Unknown = 999
};

enum class TransformationReference {
    DepthSrc1,
    DepthSrc2,
    TextureSrc
};

struct IntrinsicParams {
    int width = 0;
    int height = 0;
    std::array<double, 9> cameraMatrix{};
    std::array<double, 5> distortion{};
    std::array<double, 9> rotation{};
    std::array<double, 3> translation{};
};

struct SwingLineScanLightPlaneParams {
    float startAngle = 0.0f;
    float endAngle = 0.0f;
    std::vector<std::vector<float>> lightPlaneParams;
};

struct CameraParametersConfig {
    ReconstructorType reconstructorType = ReconstructorType::Mono;
    TransformationReference transformationReference = TransformationReference::DepthSrc1;
    IntrinsicParams depthSrc1;
    std::optional<IntrinsicParams> depthSrc2;
    std::optional<IntrinsicParams> textureSrc;
    std::optional<SwingLineScanLightPlaneParams> swingLineScanLightPlaneParams;
};


EPICEYE_SDK_API void to_json(nlohmann::json &json, const IntrinsicParams &params);
EPICEYE_SDK_API void from_json(const nlohmann::json &json, IntrinsicParams &params);
EPICEYE_SDK_API void to_json(nlohmann::json &json, const SwingLineScanLightPlaneParams &params);
EPICEYE_SDK_API void from_json(const nlohmann::json &json, SwingLineScanLightPlaneParams &params);
EPICEYE_SDK_API void to_json(nlohmann::json &json, const CameraParametersConfig &config);
EPICEYE_SDK_API void from_json(const nlohmann::json &json, CameraParametersConfig &config);

class EPICEYE_SDK_API EpicEye {
public:
    /** @brief 获取 SDK 版本号 */
    static std::string getSDKVersion();
    /** @brief 返回某个 ip 已缓存的相机版本号，未缓存则返回空字符串 */
    static std::string getEpicEyeVersion(std::string ip);
    /** @brief 清除版本缓存；ip 为空字符串则清空全部 */
    static void clearEpicEyeVersionCache(std::string ip = "");
    /**
     * @brief 获取相机信息（兼容 V3 裸结构与 V4 包装结构）
     * @return bool, 是否请求成功
     * @param ip,std::string 相机的ip地址
     * @param info, EpicEyeInfo 相机的详细信息,包含width，height
     */
    static bool getInfo(std::string ip, EpicEyeInfo &info);
    /**
     * @brief 获取重建器类型（V4）
     * @return bool, 是否请求成功
     */
    static bool getReconstructorType(std::string ip, ReconstructorType &type);
    /**
     * @brief 获取相机内部温度信息（V4）。
     * @param temperatureInfo 输出温度 JSON 对象；字段随相机型号变化，温度单位均为摄氏度。
     * @param useCache true 使用服务端 60 秒缓存，false 强制读取硬件。
     */
    static bool getTemperatureInfo(std::string ip, nlohmann::json &temperatureInfo, bool useCache = true);
    /**
     * @brief 在 5 秒总时间预算内自动搜索相机；IPv6 不可用时继续使用 IPv4
     * @return bool, 是否成功搜索到相机
     * @param cameraList, 以EpicEyeInfo形式返回的搜索到的相机列表，如果没有搜索到，则此列表为空
     */
    static bool searchCamera(std::vector<EpicEyeInfo> &cameraList);
    /**
     * @brief 设置相机 IP 地址配置（通过 UDP 多播下发）
     * @param destinationIP 目标相机当前 IP（用于定位要修改的相机）
     * @param config 新的 IP 配置（DHCP / 手动）
     * @return bool, 是否至少从一个网卡成功发出配置报文
     */
    static bool setEpicEyeIPConfig(std::string destinationIP, const EpicEyeIPConfig &config);
    /** 启动/停止后台相机发现。 */
    static void startDiscovery();
    static void stopDiscovery();
    /** 返回当前发现列表的快照。 */
    static void getDiscoveredCameras(std::vector<EpicEyeInfo> &cameraList);
    static void clearDiscoveredCameras();
    static void setDiscoveryCallback(DiscoveryCallback callback);

    // ------------------------- 拍摄与取数 -------------------------
    /**
    * @brief 触发拍摄一个 Frame，通过 frameID 获取 EpicRaw 数据
    * @return bool, 是否请求成功
    * @param ip,std::string 相机的ip地址
    * @param frameID, std::string 此次触发拍照返回的frameID
    * @param pointCloud, bool 是否请求点云数据
    * @param passiveBinocular, bool 是否被动双目拍摄
    */
    static bool triggerFrame(std::string ip, std::string &frameID, bool pointCloud = true, bool passiveBinocular = false);
    /**
     * @brief 根据frameID获取原始 EpicRaw 二进制流（不解码）
     * @param ip,std::string 相机ip
     * @param frameID,std::string frameId
     * @param epicRawBytes, std::vector<uint8_t> 输出的原始字节
     * @param aligned, bool 是否按2D图像坐标对齐
     */
    static bool getFrameInEpicRaw(std::string ip, std::string frameID, std::vector<uint8_t> &epicRawBytes, bool aligned = false);

    // ------------------------- 相机配置 -------------------------
    /**
     * @brief 获取当前相机配置（兼容 V3 / V4）
     */
    static bool getConfig(std::string ip, nlohmann::json &configJson);
    /**
     * @brief 更新相机配置（兼容 V3 / V4）
     */
    static bool setConfig(std::string ip, const nlohmann::json &configJson);
    /**
     * @brief 获取相机参数列表（兼容 V3 / V4）
     */
    static bool getParameterList(std::string ip, std::vector<SimpleCameraParameter> &presets);
    /**
     * @brief 通过 paramId 切换相机参数（V3 走 query，V4 走 body）
     */
    static bool setParameter(std::string ip, const std::string &paramId);
    /**
     * @brief 获取相机参数样式（兼容 V3 / V4）。V3 的 data 是被序列化过的 JSON 字符串。
     */
    static bool getConfigStyle(std::string ip, nlohmann::json &styleJson);

    // ------------------------- 内参 -------------------------
    /**
     * @brief 获取2D图像对应相机的相机矩阵（按行存储，可恢复为3x3，与OpenCV兼容）
     */
    static bool getCameraMatrix(std::string ip, std::vector<double> &cameraMatrix);
    /**
     * @brief 获取2D图像对应相机的畸变参数（与OpenCV兼容）
     */
    static bool getDistortion(std::string ip, std::vector<double> &distortion);
    /**
     * @brief 读取相机保存的完整内外参。V3 返回 legacy，V4 返回 config。
     */
    static bool getCameraParameters(std::string ip, nlohmann::json &cameraParameters);

    // ------------------------- 去畸变查找表 -------------------------
    /**
     * @brief 获取去畸变查找表（LUT），兼容 V3 / V4。
     *
     * distortion 全零时直接返回空（无需 LUT）；distortion/cameraMatrix 可用时走 V4 带参接口，
     * 否则回退 V3 无参接口。结果按组合 key 缓存：
     * V4 为 {ip}_{w}x{h}_{hash(cm)}_{hash(dist)}，V3 仅用 ip。
     * @param lut 输出 LUT（float，每像素 2 个 u/v）；无可用 LUT 时为空。
     * @return 取到非空 LUT 返回 true；全零畸变或请求失败返回 false。
     */
    static bool getUndistortLut(std::string ip, int depthWidth, int depthHeight,
                                const std::vector<double> &cameraMatrix,
                                const std::vector<double> &distortion,
                                std::vector<float> &lut);
    /**
     * @brief 清除去畸变查找表缓存。指定 ip 则清除该 ip 的全部条目（含组合 key），否则清空全部。
     */
    static void clearUndistortLutCache(std::string ip = "");

    /**
     * @brief 离线本地计算去畸变 LUT（纯 C++，不连相机、不缓存）。
     * 畸变全零或参数无效时返回 false，lut 为空。
     */
    static bool computeUndistortLut(int depthWidth, int depthHeight,
                                    const std::vector<double> &cameraMatrix,
                                    const std::vector<double> &distortion,
                                    std::vector<float> &lut);

    // ------------------------- EpicRaw 离线解析（实验室复现，无需相机） -------------------------
    /**
     * @brief 将 EpicRaw 字节加载为可复用文档。
     * EpicRaw3 元素零拷贝引用 epicRawBytes；文档使用期间该 vector 必须保持存活且不得改变容量。
     */
    static bool tryLoadEpicRawDocumentFromBytes(const std::vector<uint8_t> &epicRawBytes, EpicRawDocument &document);
    static bool getDepthIntrinsicsFromEpicRaw(const EpicRawDocument &document,
                                              std::vector<double> &distortion,
                                              std::vector<double> &cameraMatrix,
                                              int &depthWidth, int &depthHeight);
    static bool decodeImageFromEpicRaw(const EpicRawDocument &document,
                                       std::vector<uint8_t> &imageData,
                                       int &imageWidth,
                                       int &imageHeight,
                                       int &pixelByteSize);
    /**
     * @brief 读取 EpicRaw3 指定类型的原始图像，同时保留 MatType。
     * 仅返回图像元素，不执行颜色转换或对齐。
     */
    static bool decodeImageFromEpicRaw(
        const EpicRawDocument &document,
        EpicRaw3DataType dataType,
        EpicRawImage &image);
    static bool decodeDepthFromEpicRaw(const EpicRawDocument &document,
                                       std::vector<float> &depthData,
                                       int &depthWidth,
                                       int &depthHeight);
    /** @brief 解码 EpicRaw1/2/3 拍摄时保存的相机配置。 */
    static bool decodeCameraConfigFromEpicRaw(
        const EpicRawDocument &document,
        nlohmann::json &cameraConfig);
    /**
     * @brief 解码 EpicRaw3 被动双目图像。
     * 顺序固定为 DepthSrcImg1、DepthSrcImg2、可选 TextureBGR。
     */
    static bool decodePassiveBinocularImagesFromEpicRaw(
        const EpicRawDocument &document,
        std::vector<EpicRawImage> &images);
    static bool decodePointCloudFromEpicRaw(const EpicRawDocument &document,
                                            const std::vector<float> &undistortLut,
                                            std::vector<float> &pointCloudData,
                                            int &pointCloudWidth,
                                            int &pointCloudHeight);
    static bool getEpicRawElementMetaDataStr(const EpicRawDocument &document,
                                             EpicRaw3DataType dataType,
                                             std::string &metaDataStr);

    // ------------------------- 2D 流 -------------------------
    /**
     * @brief 通过WebRtcOffer开启2D流
     */
    static bool startStream2D(std::string ip, std::string offerSdp, Stream2DWebRtcOfferResult &result, int fps = 60, int cameraIndex = 0);
    /**
     * @brief 通过peerId关闭2D WebRTC流
     */
    static bool stopStream2D(std::string ip, std::string peerId);
    /**
     * @brief 停止所有2D WebRTC流
     */
    static bool stopAllStream2D(std::string ip);
    /**
     * @brief 查询2D流状态
     */
    static bool getStream2DStatus(std::string ip, Stream2DStatus &status);
    /**
     * @brief 运行 Stream2D RTC 接收会话并通过回调抛出逐帧原始码流数据（不解码）
     */
    static bool startStream2DRtcSession(std::string ip, const Stream2DRtcSessionOptions &options, const Stream2DFrameCallback &onFrame, std::unique_ptr<Stream2DRtcSession> &session);
    static void stopStream2DRtcSession(const std::unique_ptr<Stream2DRtcSession> &session);

    // ------------------------- 线扫 -------------------------
    /**
     * @brief 启动线扫流，忽略服务端返回的 frameId
     */
    static bool startLineScan(std::string ip, bool enableTexture = true, bool deferEpicRawSave = true);
    /**
     * @brief 启动线扫流并返回服务端为本次会话分配的 frameId
     */
    static bool startLineScan(std::string ip, std::string &frameId, bool enableTexture = true, bool deferEpicRawSave = true);
    /**
     * @brief 停止线扫流
     * @param statusHex,std::string 返回服务端停止状态码（16进制字符串）
     */
    static bool stopLineScan(std::string ip, std::string &statusHex);
    /**
     * @brief 查询线扫状态
     */
    static bool getLineScanStatus(std::string ip, LineScanStatus &status);
    /**
     * @brief 返回线扫状态名称
     */
    static const char *lineScanStatusToString(LineScanStatus status);
    /**
     * @brief 连接线扫 WebSocket 并持续消费数据，收到 EOT 时返回 true，错误或超时返回 false
     */
    static bool waitLineScanCompletion(std::string ip, int timeoutMs = 60000);

    // ------------------------- 标定 -------------------------
    /**
     * @brief 计算手眼标定结果
     */
    static bool getHandEyeCalibrationData(std::string ip, HandEyeCalibrationData &data);
    static bool getRobotLibrary(std::string ip, RobotLibrary &library);
    static bool configureHandEyeCalibration(std::string ip, HandEyeInstallationType installationType, const RobotParameters &robotParameters);
    static bool calculateHandEyeCalibrationResult(std::string ip, const HandEyeCalculationRequest &request, HandEyeCalibrationResult &result);
    /**
     * @brief 获取标定板位姿
     */
    static bool getCalibrationBoardPose(std::string ip, CalibrationBoardPose &result);
    static bool calculateRobotAccuracy(std::string ip, const RobotAccuracyRequest &request, RobotAccuracyResult &result);
    static bool calculateHandEyeAccuracy(std::string ip, const HandEyeAccuracyRequest &request, HandEyeAccuracyResult &result);
    /**
     * @brief 拍照并自动识别内参标定板
     */
    static bool identifyBoard(std::string ip, IntrinsicIdentifyBoardResult &resultJson);
    /**
     * @brief 拍照并执行完整内参精度检查。
     */
    static bool checkIntrinsicAccuracy(std::string ip, IntrinsicAccuracyCheckResult &resultJson);
    /**
     * @brief 采集并追加一组内参标定图
     */
    static bool addCalibImage(std::string ip, int boardType, IntrinsicAddCalibImageResult &resultJson);
    /**
     * @brief 按索引删除一组内参标定图
     */
    static bool removeCalibImage(std::string ip, int pairIndex, IntrinsicRemoveCalibImageResult &resultJson);
    /**
     * @brief 计算内参标定结果
     */
    static bool calculate(std::string ip, IntrinsicCalculateResult &resultJson);
    /**
     * @brief 写入完整相机内外参配置
     */
    static bool setCameraIntrinsicParameters(std::string ip, const CameraParametersConfig &cameraParametersConfig);
    /**
     * @brief 恢复出厂内参
     */
    static bool restoreFactoryIntrinsic(std::string ip);

    // ------------------------- 纹理对齐 -------------------------
    /**
     * @brief 将彩色纹理图按深度图重投影对齐。输出大小为 depthW*depthH*3*depthBytes 字节（matType 决定位深，16bit ×2）。（旧版）
     */
    static bool alignTextureFromDepth(
        const float *depth, int depthW, int depthH,
        const uint8_t *texture, int textureW, int textureH, int matType,
        const double depthIntrinsic[9],
        const double textureIntrinsic[9],
        const double textureDistortion[5],
        const double rotation[9],
        const double translation[3],
        uint8_t *output);

    /**
     * @brief 将彩色纹理图按深度图重投影对齐, SDK 内部分配内存。（推荐）
     * @param matType 纹理的 OpenCV 类型编码（EpicRaw3 TextureBGR 元素的 matType，如 CV_8UC3=16 / CV_16UC3=18）。
     *                决定采样与输出位深：16bit(matType&7==2) 按 uint16 采样并输出，否则 uint8。
     * @param alignedTexture 输出：对齐后的纹理图 (depthW*depthH*3 元素，位深同纹理；16bit 时字节数再 ×2)
     */
    static bool alignTextureFromDepth(
        const std::vector<float> &depth, int depthW, int depthH,
        const std::vector<uint8_t> &texture, int textureW, int textureH, int matType,
        const std::vector<double> &depthIntrinsic,
        const std::vector<double> &textureIntrinsic,
        const std::vector<double> &textureDistortion,
        const std::vector<double> &rotation,
        const std::vector<double> &translation,
        std::vector<uint8_t> &alignedTexture);

    /**
     * @brief 将彩色纹理图按点云图重投影对齐。输出大小为 pointCloudW*pointCloudH*3 元素（位深同纹理）。（旧版）
     * @param matType 纹理 OpenCV 类型编码（同上），决定采样/输出位深。
     */
    static bool alignTextureFromPointCloud(
        const float *pointCloud, int pointCloudW, int pointCloudH,
        const uint8_t *texture, int textureW, int textureH, int matType,
        const double textureIntrinsic[9],
        const double textureDistortion[5],
        const double rotation[9],
        const double translation[3],
        uint8_t *output);

    /**
     * @brief 将彩色纹理图按点云图重投影对齐, SDK 内部分配内存。（推荐）
     * @param matType 纹理 OpenCV 类型编码（EpicRaw3 TextureBGR 元素的 matType）。决定采样/输出位深。
     * @param alignedTexture 输出：对齐后的纹理图 (pcW*pcH*3 元素，位深同纹理)
     */
    static bool alignTextureFromPointCloud(
        const std::vector<float> &pointCloud, int pointCloudW, int pointCloudH,
        const std::vector<uint8_t> &texture, int textureW, int textureH, int matType,
        const std::vector<double> &textureIntrinsic,
        const std::vector<double> &textureDistortion,
        const std::vector<double> &rotation,
        const std::vector<double> &translation,
        std::vector<uint8_t> &alignedTexture);

    /**
     * @brief 从 EpicRaw3 TextureBGR 元素元数据中解析对齐所需参数。
     * @param metaDataStr TextureBGR 元素的 MetaData JSON 字符串
     * @return true 表示所有参数解析成功
     */
    static bool parseTextureExtrinsics(const std::string &metaDataStr,
                                       std::vector<double> &cameraMatrix,
                                       std::vector<double> &distortion,
                                       std::vector<double> &rotation,
                                       std::vector<double> &translation);

    /**
     * @brief 用内参双线性插值补全对齐纹理中的黑像素（无深度区域）。
     *
     * 先通过点云 3D 投影对齐 Z>0 区域，然后调用本函数将未覆盖的黑像素
     * 用 outputIntrinsic → textureIntrinsic 双线性采样填充。
     * outputIntrinsic 通常为深度内参，textureIntrinsic 为纹理内参。
     */
    static bool fillBlackPixelsByIntrinsics(
        std::vector<uint8_t> &alignedTexture, int outW, int outH,
        const std::vector<uint8_t> &texture, int textureW, int textureH, int matType,
        const std::vector<double> &outputIntrinsic,
        const std::vector<double> &textureIntrinsic);

    /**
     * @brief 用邻域 Z + 3D 投影补全对齐纹理中的黑像素（适用于外参非平凡的相机）。
     *
     * 对每个黑像素，螺旋搜索最近有效 Z 值，通过真实 R/T 做 3D 投影到纹理图采样。
     * 若搜索范围内找不到 Z，回退到内参直映射。
     * alignedTexture 尺寸必须 == (depthW, depthH)。
     */
    static bool fillBlackPixelsWithDepth(
        std::vector<uint8_t> &alignedTexture, int outW, int outH,
        const std::vector<float> &depth, int depthW, int depthH,
        const std::vector<uint8_t> &texture, int textureW, int textureH, int matType,
        const std::vector<double> &depthIntrinsic,
        const std::vector<double> &textureIntrinsic,
        const std::vector<double> &textureDistortion,
        const std::vector<double> &rotation,
        const std::vector<double> &translation);

    /**
     * @brief 用快速 uv 模型补全无效区域。
     *
     * 从已对齐有效像素抽样重建其原始 2D 图采样坐标，拟合 output 坐标到原图 uv 的仿射模型，
     * 再从原始 2D 图双线性采样填补黑色区域。该路径优先满足 1s 内计算目标。
     */
    static bool fillInvalidDepthPixelsByTextureInterpolation(
        std::vector<uint8_t> &alignedTexture,
        const std::vector<float> &depth, int depthW, int depthH,
        const std::vector<uint8_t> &texture, int textureW, int textureH, int matType,
        const std::vector<double> &depthIntrinsic,
        const std::vector<double> &textureIntrinsic,
        const std::vector<double> &textureDistortion,
        const std::vector<double> &rotation,
        const std::vector<double> &translation);

    /**
     * @brief 深度图飞点过滤
     *
     * 综合三种方法移除孤立飞点:
     *   1. 邻域中值差异检测: |Z - median(neighbors)| > medianThresh → 飞点
     *   2. 同深度邻居数量检测: 邻域内同深度像素过少 → 孤立飞点
     *   3. 深度连续连通域过滤: 面积过小的连通域 → 漂浮碎片
     *
     * @param depth 深度图 (float mm), 被修改: 飞点置0
     * @param medianWindow 中值检测窗口大小 (默认3)
     * @param medianThresh 中值差异阈值 mm (默认50)
     * @param sameDepthThresh 同深度阈值 mm (默认30)
     * @param minSameNeighbors 最少同深度邻居数 (默认3)
     * @param connectThresh 连通域深度连续阈值 mm (默认20)
     * @param minComponentArea 最小连通域面积 (默认5)
     * @return 移除的飞点数量
     */
    static size_t filterDepthOutliers(
        std::vector<float> &depth, int width, int height,
        int medianWindow = 3, double medianThresh = 50.0,
        double sameDepthThresh = 30.0, int minSameNeighbors = 3,
        double connectThresh = 20.0, int minComponentArea = 5);

    /**
     * @brief 纹理坐标空间水平条纹修复
     *
     * 对每个像素计算其在原始纹理中的坐标(u_tex,v_tex)。
     * 竖向扫描: 若v_tex与上下邻域差异大 → 水平错位 → 竖向内插纹理坐标后重采样。
     * Phase-1像素(原始有效深度)永不修改。
     */
    static bool removeHorizontalBands(
        std::vector<uint8_t> &image, int width, int height,
        const std::vector<float> &depth,
        const std::vector<double> &depthIntrinsic,
        const std::vector<double> &textureIntrinsic,
        const std::vector<double> &textureDistortion,
        const std::vector<double> &rotation,
        const std::vector<double> &translation,
        const std::vector<uint8_t> &texture, int textureW, int textureH, int matType);

    /**
     * @brief 对齐纹理图到点云（离线版，无 HTTP，推荐）。
     *
     * 调用方自行准备 depth + 外参，SDK 仅做纯计算，无网络开销。
     * @param texture   输入纹理图 (uint8 BGR, tw*th*3)
     * @param pointCloud 点云 (float XYZ, pcW*pcH*3)
     * @param depth    深度图 (mm)
     * @param textureIntrinsic 纹理内参 3×3
     * @param textureDistortion 纹理畸变 k1,k2,p1,p2,k3
     * @param rotation  R (3×3) 深度→纹理旋转
     * @param translation T (3) 深度→纹理平移
     * @param depthIntrinsic 深度内参 3×3
     */
    static bool alignTextureImage(
        const std::vector<uint8_t> &texture, int textureW, int textureH, int matType,
        const std::vector<float> &pointCloud, int pointCloudW, int pointCloudH,
        const std::vector<float> &depth, int depthW, int depthH,
        const std::vector<double> &textureIntrinsic,
        const std::vector<double> &textureDistortion,
        const std::vector<double> &rotation,
        const std::vector<double> &translation,
        const std::vector<double> &depthIntrinsic,
        std::vector<uint8_t> &alignedTexture);

    /**
     * @brief 对齐纹理图到深度图（纯计算，无 HTTP）。
     *
     * 以 depth 像素网格为输出网格，由深度图反投影并按 R/T 投影到纹理图采样；
     * 再用快速 uv 仿射模型填补剩余黑区。默认路径优先满足 1s 内计算目标。
     * @param matType 纹理 OpenCV 类型编码（TextureBGR 元素 matType），决定采样/输出位深。
     */
    static bool alignTextureImage(
        const std::vector<uint8_t> &texture, int textureW, int textureH, int matType,
        const std::vector<float> &depth, int depthW, int depthH,
        const std::vector<double> &depthIntrinsic,
        const std::vector<double> &textureIntrinsic,
        const std::vector<double> &textureDistortion,
        const std::vector<double> &rotation,
        const std::vector<double> &translation,
        std::vector<uint8_t> &alignedTexture);
};
}  // namespace TFTech

#endif
