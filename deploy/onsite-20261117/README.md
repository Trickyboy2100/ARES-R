# 11月17日现场准备包

用于 `/home/yikun/ARES-R-RC1-20261019` 的既有部署。依赖现场 SDK v2.2.2 头文件、`libjakaAPI.so`、pinned ARES 模型、现有 CenterRestore ROS overlay，以及现有 `.venv` 中的 NumPy、SciPy、PyYAML。安装器在替换代码前检查这些 Python 依赖。

本包包含双向关节点镜像接口、一键按钮、全局车体模型禁用、扫描与失败提示修复。镜像默认速度为 `0.08 rad/s`，BODY 对称面为 `Y=0`。验收指标为 J1–J6 中心的位置误差，J6 末端自转取就近解。TCP 位置和朝向同时受左右工具标定影响。

## 安装与只读检查

在解压后的目录执行。安装时任务处于空闲状态。

```bash
python3 install.py
python3 install.py --apply --restart-services
/home/yikun/ARES-R-RC1-20261019/.venv/bin/python check.py --read-hardware --scan
```

第一条校验全部文件 SHA256。第二条先备份现场文件、编译 native，再部署与重载 backend/WebUI/planner，使旧 scene 失效。配置更新为全局车体几何策略，现场其他配置继续提供相机标定、泊位偏置和工具 TCP。

第三条只读检查双臂 native actual 与控制器 10004 反馈的一致性，并做一次静止相机扫描。报告中所有检查应为 true。每步均不启动机械臂任务。

源代码备份位于 `worklog/preservation/onsite-ready-时间戳/`，`changes.json` 记录原文件及备份路径。编译失败会在替换源码前退出。安装器源码与参数均在包内。

## 实机验收

打开 `http://172.28.172.210:8765/operations`，刷新页面，确认版本为 `2026.11.17-onsite-ready-mirror-v1`、车体模型显示全局禁用。

1. 现场确认两臂静止、空手、工作区净空、急停可用，点击“左臂镜像右臂”。
2. 等待到位，核对六个关节点及结果中的 `joint_point_error_mm`。初次速度为 0.08 rad/s。
3. 再点击“右臂镜像左臂”，检查反方向。若两臂原本已对称，此次主要覆盖到位确认；完整右臂运动验收需要另一组非对称起点。
4. “停止镜像运动”使用同一 backend 的停止锁存。出现失败时，查看短说明并展开具体关节、实际值、预期值和日志。每次任务重新读取实际状态并求解。

按钮也位于主页面和 Demo Console。页面加载和服务启动只恢复入口与记录。

## ART 与 HTTP

ART 使用相同后端。

```text
arm mirror left from right
arm mirror right from left
arm mirror status
arm mirror stop
```

HTTP 启动接口为 `POST /api/operations/mirror`。

```json
{
  "source_arm": "right",
  "destination_arm": "left",
  "authorization": "MIRROR LEFT FROM RIGHT",
  "command_id": "唯一请求ID"
}
```

反方向交换 source/destination，并使用 `MIRROR RIGHT FROM LEFT`。状态为 `GET /api/operations/run-status`，停止为 `POST /api/operations/stop`，请求体 `{}`。

请求返回 RUNNING 后由后端完成解算、路径检查、JAKA MoveJ 和到位回读。源臂保持静止，由独立的控制器 10004 反馈监测。双臂互碰、自碰撞、真实场景障碍和控制器保护继续参与执行检查。

## 验证状态

- 本地真实 pinned 模型与记录关节已完成两个方向的解算；左臂镜像右臂完成81点路径回放及外部障碍阻断回归。反方向完整路径以现场新鲜状态验收。
- C++ 程序完成真实厂商头文件语法检查和 SDK 替身协议测试。
- 11月16日镜像实机尝试在发送运动前因起点读数不一致退出。新版采用每进程单 SDK 连接、逐臂 actual 快照和独立源臂反馈，待现场验证。
- 原 ROS Demo01 于11月16日完整实机成功，总耗时约77.9秒。该结果记录在随包报告中。
- 车体禁用覆盖当前 geometry exporter、SceneCompiler、生产 cuRobo worker 和镜像接口；历史定义保存在 disabled 字段及备份中。扫描得到的真实环境障碍照常处理。

完整离线结果见 `validation/`。任务证据保存到现场 `worklog/evidence/operations-execution/mirror-时间戳/`。

## 明天的边界

本包是既有部署的增量准备包，尚未完成 Linux 动态链接和实机镜像验收。安装不触发运动，也不替换 Golden Demo 参数、泊位偏置、工具 TCP 或已交付 ROS Action 定义。原有文件的完整备份保存在上述 preservation 目录；若离场后现场又有修改，应先比较备份与安装内容再验收。
