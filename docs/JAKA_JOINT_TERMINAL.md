# JAKA 双臂关节 Terminal 指令

## 当前安全状态

当前版本增加独立的受控运动模式。MiniCobo/Mini2 共用的官方关节范围已经写入配置；控制器自身的现场软限位仍是最终约束。执行前必须确认工作空间无人、无障碍物、急停可触及，并在 JAKA App 中确认对应机械臂已经上电和使能。

启动只读终端：

```bash
cd /home/yikun/ARES-R
./scripts/run_terminal.sh
```

## 指令示例

读取左臂当前六关节角，同时显示弧度和角度：

```text
jaka joints left
```

预览左臂绝对关节目标，单位为度：

```text
jaka plan left deg 0 -20 35 0 45 0
```

预览右臂绝对关节目标，单位为弧度：

```text
jaka plan right rad 0 -0.2 0.4 0 0.5 0
```

以当前角度为基础，仅将左臂 J2 增加 2°：

```text
jaka step left J2 deg 2
```

预览右臂六关节全零目标：

```text
jaka home right
```

一次预览双臂绝对目标；前六个值属于左臂，后六个值属于右臂：

```text
jaka dual deg 0 -20 35 0 45 0  0 -20 35 0 -45 0
```

## 输出解释

每条目标指令都会列出：

- `current(deg)`：SDK 读取的当前关节角；
- `target(deg)`：输入目标；
- `delta(deg)`：目标相对当前值的变化；
- `target(rad)`：将来提供给 SDK 的标准弧度值；
- `BLOCKED`：未通过现场限位或配置确认门。

## 执行模式开放条件

启动受控运动模式：

```bash
ARES_R_HARDWARE_CONFIRM=YES ./scripts/run_terminal.sh --enable-hardware
```

低速移动单个关节，例如左臂 J2 增加 1°：

```text
jaka move-step left J2 deg 1
```

低速移动到附近的绝对关节角：

```text
jaka move left deg 54 -9 -32 0 0 0
```

每次执行要求输入精确确认短语 `MOVE LEFT` 或 `MOVE RIGHT`。单条指令任一关节变化超过 3°会被拒绝，执行速度固定为 0.05 rad/s。控制器出现限位、碰撞、保护停止或急停时会在调用前拒绝。

2026-09-08 起，ART 不再在主线程调用阻塞式 `joint_move(..., True, ...)`。命令采用官方非阻塞参数 `joint_move(..., False, ...)`，随后由 ART 每 100 ms 监督实际关节、`is_in_pos`、限位和碰撞状态，并显示已用时间、动态超时、最大跟踪误差和控制器速度倍率。到位误差要求不超过 0.05°；反馈连续失败、超时、限位、碰撞或 `Ctrl-C` 都调用 `motion_abort`，且不会自动重发或自动回程。

动态超时会考虑控制器 `rapid_rate`。2026-09-08 现场只读值为左右臂均 `0.7`；3°、`0.05 rad/s` 的理想时间约 1.5 秒，但旧阻塞调用超过 20 秒仍未返回，说明卡顿来自 SDK 阻塞等待而不是低速度倍率。新流程以实际关节误差和 `is_in_pos` 双条件验收。JAKA 官方错误码 `-3` 表示连接失败，因此只允许有限次数的短暂查询重试，不能将其误判为“仍在运动”。

当前模式仅控制单臂关节，不会连接底盘、相机或夹爪。该限制不等同于双臂碰撞检测；每次运动前仍须现场确认整条机械臂、TCP、夹具和负载扫掠空间。
