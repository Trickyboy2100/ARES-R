# JAKA 双臂关节 Terminal 指令

## 当前安全状态

当前版本增加独立的受控运动模式。MiniCobo/Mini2 共用的官方关节范围已经写入配置；控制器自身的现场软限位仍是最终约束。执行前必须确认工作空间无人、无障碍物、急停可触及，并在 JAKA App 中确认对应机械臂已经上电和使能。

启动只读终端：

```bash
cd /home/yikun/ARES-R
./scripts/run_terminal.sh --mode jaka-readonly
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
ARES_R_HARDWARE_CONFIRM=YES ./scripts/run_terminal.sh --mode jaka-motion
```

低速移动单个关节，例如左臂 J2 增加 1°：

```text
jaka move-step left J2 deg 1
```

低速移动到附近的绝对关节角：

```text
jaka move left deg 54 -9 -32 0 0 0
```

每次执行要求输入精确确认短语 `MOVE LEFT` 或 `MOVE RIGHT`。单条指令任一关节变化超过 3°会被拒绝，执行速度固定为 0.05 rad/s。控制器出现限位、碰撞、保护停止或急停时会在调用前拒绝。运动期间按 `Ctrl-C` 会触发 `motion_abort`。`jaka abort left|right` 用于无阻塞状态下主动发送中止。

当前模式仅控制单臂关节，不会连接底盘、相机或夹爪。该限制不等同于双臂碰撞检测；每次运动前仍须现场确认整条机械臂、TCP、夹具和负载扫掠空间。
