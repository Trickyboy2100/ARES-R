# ARES-R

ARES-R 是 BJUT-BBMG 团队用于双臂移动机器人视觉抓放任务的独立工作区。

目标流程：

1. 底盘到达取料工位并停稳。
2. Epic Pro 检测抓取对象。
3. 规划并执行到预抓取位。
4. 短距离直线接近、夹取并抬升。
5. 底盘到达放置工位并停稳。
6. Epic Pro 再次检测 dock。
7. 规划并执行到预放置位。
8. 垂直放置、释放并退出。

## 目录

- `prototype/`：从原项目复制的现场原型及其最小本地依赖，暂时保持原样。
- `src/ares_r/`：后续正式模块代码。
- `config/`：机器人、相机、工位、TCP 和运行参数。
- `scripts/`：启动与现场辅助脚本。
- `tests/`：不驱动真机的单元测试和协议解析测试。
- `docs/`：接口、架构和调试记录。
- `logs/`：本地运行日志，不提交 Git。
- `worklog/`：人工工作记录、事后补录和交接模板，随 Git 提交。

## 原型入口

当前基线入口为：

```bash
python3 prototype/0_test.py
```

警告：该脚本会连接并控制真实设备。当前原型尚未完成安全检查，也存在 API 不匹配；在修复并完成 dry-run 之前不要直接运行。

## 安全终端框架

新框架默认使用 Mock 设备，不会连接或驱动真机：

```bash
./scripts/run_terminal.sh
```

可在终端中依次执行：

```text
status
nav pick
detect pick
pick
nav place
detect place 1
place
```

也可以用 `cycle 1` 完成一次 Mock 流程。`camera-only` 模式只连接 Epic 相机，机械臂、夹爪和底盘仍为 Mock：

```bash
./scripts/run_terminal.sh --mode camera-only
```

`hardware` 模式目前有双重锁定，并且在真实设备 Adapter 完成验收前会拒绝启动。

进入 `camera-only` 后，以下命令只触发 Epic 检测并显示抓取坐标，不会操作机械臂、夹爪或底盘：

```text
epic status
epic detect pick
```

终端调试时可随手留痕：

```text
note Epic返回了6维抓取位姿，单位待核实
```

更完整的开发或事后补录使用：

```bash
./scripts/worklog add "完成内容" --author "姓名" --source manual \
  --files src/ares_r/example.py --tests "验证方式" --next "下一步"
```

详细规则见 `worklog/README.md` 和 `CONTRIBUTING.md`。

## 外部依赖

- ROS 1 / `rospy` / `std_msgs`
- JAKA SDK V2.1.5 的 `jkrc.so` 和 `libjakaAPI.so`
- NumPy、SciPy、OpenCV
- websockets
- pyserial
- keyboard

## GitHub 准备

本目录已初始化为 Git 仓库，默认分支为 `main`。创建远程仓库后再执行：

```bash
git remote add origin <repository-url>
git add .
git commit -m "Initial ARES-R workspace"
git push -u origin main
```

提交前必须检查配置和日志中是否包含密码、Token、设备序列号或现场敏感信息。
