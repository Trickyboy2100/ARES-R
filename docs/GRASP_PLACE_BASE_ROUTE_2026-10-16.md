# GRASP → PLACE 固定底盘路线

权威记录：`config/grasp_place_base_route.json`，revision `GRASP_PLACE_BODY_ROUTE_2026_10_16_V1`。

当前实物位置登记为 GRASP。路线严格保留三段，不允许用净位移直接右移代替：

1. BODY X− 后退 0.30 m；停止并确认 settle。
2. BODY Y− 右移 0.75 m；停止并确认 settle。
3. BODY X+ 前进 0.30 m；停止并确认 settle，到达 PLACE。

总路程 1.35 m，净位移 BODY `[0,-0.75,0]` m，不旋转。当前只登记路线，未执行。速度未新增、未授权自动运行；以后必须通过既有底盘控制及真实 completion observer 执行，并在每次移动时使旧 scene 失效，机械臂后续动作前重新扫描。

## SLAM 记录及限制

地图 ID 379，名称 831。15:20:59（Asia/Shanghai）GRASP 瞬时读数为 map XY `[-0.541927,1.074800]` m，yaw `-6.330630°`。假定 SLAM yaw 是 BODY +X 在地图中的标准 SE2 朝向，则推算 PLACE XY 为 `[-0.624626,0.329373]` m，同 yaw。公式 `p_map_PLACE = p_map_GRASP + Rz(yaw) [0,-0.75]`。

PLACE **并非实际读取结果**。底盘未移动到 PLACE，本轮不能报告两个已实测站点。设备返回 IDLE，motion log/queue 未变化，但后续只读样本已有厘米级位置及数度 yaw 漂移，confidence 原始值约32–38；不将这些地图坐标当成已验收精确导航点。定位源原始 Z=0.5 不当成 BODY 原点的地面高度。

历史 `config/manipulation_stations.json` 未修改。旧 runtime 只读取单一平移，不能表达三段路径，直接替换成净位移会错误跳过后退和前进；本轮为独立、不可自动执行的路线登记。后续接入需显式调用三段 route，不应静默启动旧 PLACE_TO_PICK/PICK_TO_PLACE。

## 随后授权的一次真实往返

执行脚本 `scripts/test_grasp_place_base_roundtrip.py`，必须显式授权，不能开机自动启动。速度0.10m/s，六段均通过canonical backend，保持控制器collisiondetection=1；每段在既有observer之外再次要求新completion marker和稳定窗口，未使用旧“已完成”日志串联。任何异常停止，不自动补走。

本次六段均完成，约100.86秒；未指令旋转、双臂或夹爪动作。实际SLAM采样如下，地图379：

| 时刻 | X(m) | Y(m) | yaw(°) |
|---|---:|---:|---:|
| 出发GRASP | -0.256744 | 1.008590 | -1.695320 |
| 到达PLACE | -0.309882 | 0.437900 | 3.221530 |
| 返回GRASP | -0.351564 | 0.990690 | 4.142220 |

SLAM闭环差约96.5mm / 5.84°，不能据此宣称物理精确回到起点，也不能全部归因于定位漂移。路线执行通过与站点精度验收分开；需要独立地标或实测进一步判断物理误差。原登记瞬时读数继续保留，不覆盖为“真值”。真实PLACE样本位于配置 `last_roundtrip_test`。

完整原始记录：`worklog/evidence/base-routes/1792135867655861998/roundtrip.json`，含六段请求、canonical完成观察、逐次SLAM样本和最终返回差。
