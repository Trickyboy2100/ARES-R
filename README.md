# BJUT Robot Workspace

北京工业大学团队用于双臂移动机器人视觉抓放任务的独立工作区。

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
- `src/bjut_robot/`：后续正式模块代码。
- `config/`：机器人、相机、工位、TCP 和运行参数。
- `scripts/`：启动与现场辅助脚本。
- `tests/`：不驱动真机的单元测试和协议解析测试。
- `docs/`：接口、架构和调试记录。
- `logs/`：本地运行日志，不提交 Git。

## 原型入口

当前基线入口为：

```bash
python3 prototype/0_test.py
```

警告：该脚本会连接并控制真实设备。当前原型尚未完成安全检查，也存在 API 不匹配；在修复并完成 dry-run 之前不要直接运行。

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
git commit -m "Initial BJUT robot workspace"
git push -u origin main
```

提交前必须检查配置和日志中是否包含密码、Token、设备序列号或现场敏感信息。
