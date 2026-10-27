# GRASP V3：真实点云完整六阶段

直接打开 **index.html**。交互点云内嵌、无需服务器/网络，原始包不必随图集携带。图片、SVG、GIF可单独使用。

## 输入与复算
数据分支 `codex/data-grasp-20261021-public`，固定提交 `dc70016a8fc95d8d0e6efb52ef935d5cec9d408e`。两份完整tar均通过SHA256，源许可见原数据目录PUBLICATION.md。
GRASP `right_pick` / ID1 / `SCENE_d9f27c83fc0949f1a709bd0c3e843b4a` / `OBS_P3_LIVE_1792565261632216610`。
CAMERA SHA256 `62d45bd32a882bb6e8d3e080cc7b0edb239cdad8fab14d28c1dc69926d4f42a6`；BODY SHA256 `56fa636b107a8bd568ea32e1b946adce0c1b287746f5c5cddb8a4a8738b43f99`。
CAMERA单位mm，BODY单位m；有效点经固定TF转为float32与归档BODY完全相等，不重复转换。
同帧双臂诊断关节与geometry一致、capture前后最大变化0；过滤revision完全一致。过滤仅覆盖模型中声明owned的OBB/sphere，不保证未知机器人部件。

## 实际结果
原始2,304,000 → 有效2,056,200 → ROI体素15,655 → 外部15,014 → 清理8,100；自体移除641。
19单AABB → 405多基元，原始未膨胀基元逐点覆盖8,100/8,100；两组统一7mm膨胀。SceneCompiler输出416 cuboids，实际编译角点映回BODY最大中心误差4.44e-16m。
膨胀盒体积和0.06411748 → 0.02015367 m³（减少68.6%，不是并集）。
原始归档清理8,086点/18簇/390多基元/401编译障碍；当前归档点全部有精确匹配，另外14点来自small-cluster保留差异。当前版本与归档并非逐点相同。

## 规划证据分组
1. **本轮严格几何A/B**：同一q0/qgoal与统一7mm，两个世界均不继承旧目标ID的contact豁免；OLD/NEW端点均碰撞，因此拒绝进入GPU求解。见compare_planning.json。不能称为OLD失败/NEW成功。
2. **本轮真实GPU重放**：原始归档refined55请求，完整保留世界、起终点、40%夹爪模型与目标contact豁免；只迁移pinned URDF/YAML路径。cuRobo SUCCESS + 独立world PASS，241样本，净空3.706mm，GPU峰值allocated 556.7MiB、reserved 656.0MiB。源request为orientation=FREE，无水平姿态证明；独立validator不独立检查self-collision。该世界与重建统一AABB消融世界不同。
3. GIF及FK静帧由本轮实际保存的关节序列驱动pinned URDF，FK TCP与保存路径误差4.91e-16m。仅骨架模型参考、非CAD外观；GIF按样本播放，不冒充native重定时或JAKA反馈。
4. contact/lift预检的历史IK失败保留；本包不能声称整次抓取可执行。未产生新的JAKA真实反馈，旧V1历史反馈曲线不可标为本GRASP帧。

## 可读性与审查
主视图BODY −Y朝+Y，纯观测、角色分层与几何包络分开；OLD/NEW固定尺度。局部裁切仅显示，不删除桌面/dock/隔板。焦点图使用同一清理后点投影范围+18%边距；原始/包络超出投影框部分可能裁切，完整三视角附图保留固定BODY范围。薄层为Z=.90/.94/.98m，点带宽±6mm。
PNG为2400×1600（剖面2000×1600），组合剖面3200×1280；SVG内点层栅格化、线/文字可编辑。完整矩阵24张，主图不把六张全景缩到一页。
体素ROI不代表解析IK可达集；无观测空间不等于自由空间；没有RGB、没有表面补洞、没有新实机运动。

## 复现
在本离线工作树执行 `bash tools/presentation_evidence/run_grasp_v3.sh`。脚本只读取固定Git对象/数据文件，处理和GPU阶段均经offline_sandbox隔离设备I/O，仅用GPU0。重放模型来自pinned ARES `b978cbd669b5a3f6bc0bd19defcbe5256692f145`，cuRobo `8e734f3ced1df898990bcd92de40abce475907db`。运行环境与代码hash见MANIFEST.json；runtime YAML为明确披露的离线派生，不等于现场commissioning。
