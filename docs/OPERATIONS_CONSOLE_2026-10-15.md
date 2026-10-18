# ARES-R 操作台与六泊位注册表

开发基线：`.32` 的 `a9ec30e` 加当时未提交源码的只读快照。新增功能由
`ares_r.operations.OperationsRegistry` 持久化，ART、HTTP、TaskRuntime 使用同一来源。

## 界面入口

`http://172.28.172.210:8765/operations`，原三维页面顶部也有操作台入口。

- 六泊位：上／下两层，每层 left / middle / right；保存占用和六维角点偏置，推荐本次取／放泊位。
- 手动操作：双臂实时状态读取，BODY 平移／旋转 JOG 规划，关节增量规划，任意 BODY 目标，底盘相对请求检查。
- 参数：环境点云避障 AUTO / ON / OFF、中央禁区开关、速度草稿、软件关节范围和单关节总位移限制，以及现有 site 参数来源。
- 记录：BODY 关键点与当前预览轨迹保存。现有三维画面和 Task Studio 继续可用。

右臂网页执行复用 `scripts/run_scene_aware_supervised.py`、现有 native sender 和 preflight，
只执行已经预览并绑定 hash 的轨迹。网页停止通过持久 abort 标志和 PTY 请求原 runner abort。
底盘通过原 AmrHttpBase 与 BaseMotionObserver；开始移动使 scene 失效，观察到 settle 后才更新 base revision。
左臂规划和状态读取可用，generic 左臂 native execution 原本尚未 commission，页面不冒充支持。

## 六泊位与识别角点

稳定 ID：`lower_left / lower_middle / lower_right / upper_left / upper_middle / upper_right`。
left/right 的含义为面向烘干箱时的左右；实际方向由角点匹配局部坐标轴和现场六组偏置共同确定。

`T_BODY_TARGET = T_BODY_CORNER @ T_CORNER_SLOT`，使用完整 SE(3)，不是简单相加。
网页偏置输入 XYZ mm、RPY deg，落盘统一 m/rad。默认偏置为空，不能将六个零偏置当作已标定。
每个 offset 保持 CANDIDATE，需后续现场核对；Epic 5700 返回的是匹配角点，不能沿用旧泊位 TCP 的语义。

界面提供 space/config/camera 参数和 profile 名称。界面初始 2/4/1 来自历史烘干箱 candidate，
须按实际已改成角点匹配的 Epic 项目核实后保存，绝不会自动触发识别。
保存的新角点 profile 标记 UNCOMMISSIONED，不继承旧 rightmost profile 的 commissioning。
点击“5700 检测角点＋fresh 点云观测”后，复用 ObservationTransactionV2 并行检测和点云，
括号式检查双臂 joints、MAP pose/map ID，成功后用 profile 声明的 arm-base→BODY 链绑定角点。
若相机的返回坐标不是已声明的 arm-base/ZYX，必须先核对配置。

角点绑定记录 observation epoch、base revision、时间和矩阵 hash；换站、新 epoch、超时后拒绝旧角点。
矩阵手动绑定入口面向调试，需提供当前观测的完整 T_BODY_CORNER，不提供自动 commissioning。

## 取放分配与事务

初始占用 UNKNOWN；推荐只从确认 EMPTY（放）或 OCCUPIED（取）且未预留的泊位选择。
取放分配顺序可配置。获取推荐不会修改占用；`reserve` 返回 token，完成动作并有验证 evidence ID 后
才 `complete`，取消使用 `cancel`。崩溃后保留 reservation 供人工核查，不自动把它当空泊位。
进程锁、原子替换、expected_revision 防止 ART / WebUI / 多个任务覆盖彼此。

Task Studio 新增 `resource.select_berth / resource.reserve_berth / resource.complete_berth`，
RealCapabilityProvider 在 execute 阶段调用相同 registry，prepare 不修改占用。
现有抓放 Scheme 未被自动改成使用尚未标定的六泊位。

## ART 示例

```text
ops status
ops telemetry
berth list
berth set lower_middle EMPTY
berth select PLACE
berth offset lower_middle 100 0 200 0 0 0
berth detect-corner
berth target lower_middle
ops policy
ops avoidance AUTO
ops central off
ops speed save experiment_012 0.12 0.20
trajectory save preland_trial
```

`berth offset` 的示例数字仅说明 mm/deg 输入格式，不是现场标定值。
`ops update ACTION 'JSON'` 可访问预留、完成、角点、速度和 software_limits 的完整版本化接口。
JSON 写入必须包含 `expected_revision`；先由 `ops status` 获取。
BODY JOG：`ops jog '{"arm":"right","mode":"BODY","delta_m_rad":[0.01,0,0,0,0,0],"speed_profile":"right_scene_aware_0_20"}'`。

## 避障与限制的作用范围

默认环境模式 AUTO：fresh scene 中的全部障碍参与当前 generic SceneAwareMotion 规划。
ON 显式保留；OFF 只排除 provenance 证明来自点云／桌面观测的环境 cuboids。
inactive arm、gripper/tool、chassis 和来源未知的保护几何保留；cuRobo self collision 仍开启。
独立 validator 读取同一 derived world，记录 source scene digest、planning world digest、移除的对象 ID。
中央禁区默认关闭，可逐次请求覆盖；位姿请求与参数版本写入 handle / execution candidate。

generic SceneAwareMotion 的统一入口已接入默认策略。历史独立 one-shot、golden fallback、
直接 JAKA SDK / MoveJ 路径仍有自己的限制，不应称为已全量迁移。它们的参数来源保留在来源清单与代码中，
本轮没有为了一个全局按钮改写这些现场已使用的独立路径。

software_limits 仅控制额外的应用层关节范围／总位移，可设 null 关闭。
site/controller 关节范围、急停、碰撞保护、tracking 与 deadline 保留。
速度可用数值和滑块配置；编辑后保存为 UNCOMMISSIONED draft，`draft:NAME` 可用于规划预览，
但不能借用原参数的 commissioning 执行资格。实际执行仍要求安装的 profile 和 site/native ceiling 一致。
现场存在 generic 0.20 profile 与 site 0.10 ceiling 不一致的历史配置；页面如实显示，不能静默认作均已生效。

## 数据目录与复现

`worklog/runtime/operations/state.json`：占用、offset、角点、策略、草稿、关键点；重启保留。
`events.jsonl`：带版本和输入的修改日志。
`recordings/<id>/`：原请求、原规划、handle 和逐文件 SHA256，保持 scene/calibration/tool/geometry 绑定。
`worklog/evidence/dryer-corner/<id>/observation_v2.json`：真实角点观测原始证据。
`worklog/evidence/operations-execution/<id>/`：监督执行证据。

## 验证边界

本轮测试和界面检查不触发设备运动。角点 profile 和六组 offset 需要现场匹配与测量。
已定位现存测试 `test_center_is_not_ready_alias` 对来源文字的过时断言，在未修改的现场代码同样失败。
其要求 `coworker dirty patch`，当前配置来源已是正则化后的 visibility_clear_target 记录。
本轮将该过时的字面断言改为“来源非空且不同于 ready”，保留原先 center／ready 关节值不同的断言。
现场 center 位姿和来源数据不变。

界面组织参考 MoveIt 的当前状态／目标／场景／规划预览方式：
https://moveit.github.io/moveit_tutorials/doc/quickstart_in_rviz/quickstart_in_rviz_tutorial.html
