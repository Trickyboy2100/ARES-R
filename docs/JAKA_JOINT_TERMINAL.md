# JAKA 双臂关节 Terminal 指令

## 当前安全状态

当前版本只提供关节目标的读取、输入、换算和预检，不执行机械臂运动。原因是 `config/jaka_mini2_motion.site.json` 中的现场关节上下限仍为零值占位，且 `commissioning_confirmed=false`。禁止用猜测限位开放执行。

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

实际关节运动指令保持未注册。开放前至少需要完成：机器人铭牌型号核验、两台控制器关节限位留档、软限位裕量评审、速度和加速度确认、单臂低速小步测试、急停与碰撞恢复验证，以及双臂互碰检查。最终执行入口应采用独立模式、目标预览、精确确认短语和实时限位检查，禁止直接从只读模式升级为运动。
