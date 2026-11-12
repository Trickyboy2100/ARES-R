# 2026-11-12 离场前保全与离线交接

## 已保全

现场 `/home/yikun/ARES-R-RC1-20261019` 源码清单703份，共4,143,618字节。与本地ROS发布工作树比较：491份相同、52份不同、160份原本缺失。差异基线为此次同步前工作树，不代表每份差异都是bug。

原始源码包和内部703份文件SHA256全部一致；公开快照见`release/site-source-20261112/`，包括WebUI、canonical backend、Demo脚本/参数、底盘路线、泊位/TCP偏置、cuRobo worker、native源码、ROS包、测试和部署定义。没有覆盖其他工作树，没有自动合并回生产主线。

私有证据/依赖包134份，原始约35.65MB、压缩9,052,903字节，逐文件SHA256全部一致。包括本轮成功和两次故障记录、扫描精确SceneSnapshot绑定的点云/世界、planner请求/轨迹/native打包和反馈、对正前后姿态、SDK C++头文件/库、已运行sender及其原版本、pinned ARES URDF/STL、robot.yml和三个Python环境pip freeze。公开仓库只保存摘要，不公开本轮原始点云和SDK文件。

## 本地位置

私有目录：`/Users/andyee/Documents/ChatGPT/local/site-private-20261112-offline-handoff/`。

- `rc1-source-private-20261112.tar.gz`：SHA256 `2c2bcbf7c8108dd8979417124092dda9c08fbf3034de5b9dda6620b97366a1f4`。
- `ros-center-evidence-dependencies-private-20261112.tar.gz`：SHA256 `48ca29537487a6f8565451511054dffc223301e76c475886de5511432878a9a0`。
- `source/`、`evidence-and-dependencies/`：解包并校验后的原始文件。
- `local-site-gap.json`：逐文件差异与初步凭据扫描清单。

## 真实回归

ROS v0.2请求 `ros1-v02-axis-aligned-return-20261112`，console run `c232e12b15e2476c8039b2bc5ce74b44`。结果AT_CENTER / ARRIVED_CONFIRMED，位置误差 2.050563mm，姿态误差 0.002935°。native 13.285s，149采样，Servo退出确认；3次独立新鲜读数连续通过，到位确认耗时 2.132s。10项到位检查测试、5项ROS模拟测试通过；之前native相关19项回归通过。

## 仍缺/不能宣称完成

- 没有复制完整venv、Torch/CUDA安装包和完整cuRobo源码。仅有版本清单，离线GPU需预先准备依赖。
- Python JAKA/EpicEye厂家SDK安装环境并非完整可迁移包；本轮保全的是C++ SDK头文件/运行库和相机环境版本。实际部署需按合法SDK来源补齐。
- 现场旧历史全部点云/照片、tmp及其他同事研究材料没有全盘搬运；已保全的是当前源码和这次回center闭环精确证据。
- SLAM读数置信度与站位是当时快照，不是离线获得的实机导航许可。
- 本轮没有在另一台Ubuntu GPU做新测试，不能宣称离线GPU已可复现。

## 离开现场后可做

纯Python到位/故障测试、ROS模拟Action测试、任务分层/参数编辑、代码差异审计、原始轨迹/点云/持物模型可视化、规划输入与耗时分析。具备匹配GPU环境后可用冻结请求测试不同planner设置，先禁用所有硬件适配器，不能连接实机执行。
