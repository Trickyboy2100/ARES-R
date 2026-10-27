# ARES-R GRASP 真实点云与配套 study 数据

2026-10-28 在本机 Mac 找到并交付。用于 GRASP V3 六阶段可视化的原始输入，不是10月10日 PLACE/preland 数据，也不是已经生成的 V3 图件。

原始目录：`/Users/andyee/Documents/ChatGPT/local/site-private-20261021/`。
本次仅复制，原文件不修改、不删除；没有访问机器人或重新采集现场。

## 从GitHub获取（Ubuntu / Mac）

本数据位于独立归档分支 `codex/data-grasp-20261021-public`，没有合并生产分支。
两个原始包由普通Git直接保存，**不是LFS指针**，无需LFS权限或访问Mac/NAS。

```sh
git clone --single-branch --branch codex/data-grasp-20261021-public https://github.com/Trickyboy2100/ARES-R.git ARES-R-grasp-data
cd ARES-R-grasp-data/worklog/evidence/2026-10-21-grasp-source-data
sha256sum -c SHA256SUMS
```

Ubuntu校验用 `sha256sum`，Mac可用下文 `shasum -a 256`。通过后再解压；这里只读取历史数据，不连接机器人。
该分支基于GitHub main建立，仅新增本数据目录，不包含其他本地未推送Demo代码。

## 文件

- `20261021-study-clouds.tar.gz`：41,684,942 bytes；原始 CAMERA/mm 点云、未经 self-filter 的 canonical BODY/m 点云及两份 manifest。
- `20261021-center-grasp-planner-study.tar.gz`：18,069,187 bytes；194个文件，包含 pick epoch、双臂 before/after、FK/工具信息、标定、whole robot geometry、scene snapshot、残余点云、support decomposition、规划请求/结果、耗时与对比证据。
- `SHA256SUMS`：两个压缩包的 SHA256。
- `DATA_INDEX.json`：关键文件索引、同源绑定和已核验哈希。

## 校验与解压

在本目录执行：

```sh
shasum -a 256 -c SHA256SUMS
mkdir -p unpacked
tar -xzf 20261021-study-clouds.tar.gz -C unpacked
tar -xzf 20261021-center-grasp-planner-study.tar.gz -C unpacked
```

完整解压约需402MB；保留压缩包以便原样传输。包内文件保留现场原结构。

## 关键输入（相对于 unpacked）

1. CAMERA 原始点云：`logs/body_cloud/captures/20261021_144732_60b67baa/pointcloud_camera_mm.npy`。
2. CAMERA manifest：同目录 `manifest.json`。
3. BODY 点云：`logs/body_cloud/artifacts/20261021_144734_5a364d75/body_cloud.npz`。
4. BODY manifest：同目录 `manifest.json`，含固定 `T_body_camera`、单位和标定版本。
5. study根：`worklog/evidence/20261021-center-grasp-planner-study/`。
6. 同帧绑定：study下 `pick-epoch/manipulation_observation.json`、`pick-epoch/live_scene/capture_pointer.json`。
7. 同帧双臂状态：`pick-epoch/robot_state_before/{left,right}.json`、`pick-epoch/robot_state_after/{left,right}.json`。
8. 场景与模型：`pick-epoch/live_scene/whole_robot_geometry.json`、`pick-epoch/live_scene/{left,right}_fk_audit.json`，以及其 `scene/` 子目录。

## 已核验事实

- 原始点云 SHA256 与 capture manifest、BODY manifest 的source及 study observation 的 `pointcloud_sha256` 一致。
- 原始点数2,304,000，有效点2,056,200；原始单位mm，canonical BODY单位m。BODY文件不能再除1000或再次应用外参。
- observation：`OBS_P3_LIVE_1792565261632216610`；profile=`right_pick`；命令=`320,2,1,1,1,0`。
- snapshot：`SCENE_d9f27c83fc0949f1a709bd0c3e843b4a`。
- 点云 frame：`2411_16d6eb04-b33e-49dd-9008-2cee1aa48551`。
- 两个tar的目录索引均可读，未发现绝对路径、上级穿越、符号/硬链接成员；复制后另核验压缩包SHA256。

## 使用边界

包内 `/home/yikun/ARES-R-RC1-20261019/...` 是现场来源路径，不代表接收设备有这些路径。离线使用时按本索引映射到 `unpacked/`，不要覆盖原始证据。
本包没有声称包含完整生产代码、全部机器人资产或所有六阶段中间结果；重算时需另核对处理代码与参数版本。
SynologyDrive目标目录已写入，不等同于已确认NAS/其他设备完成远端同步。
2026-10-28已获得明确公开授权，允许发布这两份原始现场包及必要现场信息；详见 `PUBLICATION.md`。
