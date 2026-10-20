# 离线缺口与后续只读收集

现场根目录 `/home/yikun/ARES-R-RC1-20261019`。当前不尝试连接硬件控制接口。恢复网络后先只读复制以下目录，再逐文件SHA256比对：

1. `worklog/evidence/demo-runs/right_arm_grasp_place_roundtrip_v1/web_1792406688987650626/`
2. `worklog/evidence/operations-single/20261019-v17-approved-place160-return/`
3. `worklog/evidence/20261019-v17-payload160x100-place-preparation-v2/`
4. `worklog/evidence/scene-aware-motion/PLAN_fef112e7a5a04b368f26eda1794344ad/`
5. `worklog/evidence/scene-aware-motion/PLAN_632f7aae64444033b448dbb7786617cb/`
6. 以上request/manifest引用的scene、CAMERA/BODY点云、机器人状态、URDF/mesh/YAML、native sender、校准和工具版本；递归依赖收集，不仅复制顶层JSON。
7. `logs/roundtrip-web-1792406688987650626.log`；相应planner stdout/stderr、超时取消日志、GPU环境和服务定义。
8. 原始源码树只读hash清单，与source-manifest逐文件对照；保留同事dirty差异，不覆盖。

预览包12个文件缺口见prepared-artifact-gaps。最终执行采用fresh重规划，其轨迹不是预览轨迹；最终执行plan原始文件也必须独立补齐。

私有现场数据单独受控传输；公共Git只保存源码、许可范围内配置、报告与哈希。上传到公共仓库前必须单独确认原始现场图像/点云公开许可。历史对任务参数公开的许可不等于原始点云公开许可。

交付完成标准：Ubuntu可按manifest取得每一依赖、hash全部一致、可重建scene并运行真实cuRobo回放。不能以Mac绝对路径或只有README代替交付。

2026-10-20实际核验：1799个源码文件hash一致；229个本地数据文件已hash；进一步读取2217个压缩包成员后，预览包12项仍只有2项找到同SHA文件。另外 `RC1_2619cb4.tar.gz` 发生gzip流截断，必须重新收集，不能视为完整备份。保留原损坏文件，不覆盖或删除。
