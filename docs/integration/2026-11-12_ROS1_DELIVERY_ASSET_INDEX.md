# ROS功能块离场资产索引

## 公开代码

- `release/ros1-blocks-center-restore/`：独立runner、canonical进程扩展、ROS Action、测试与操作说明。
- `release/ros1-blocks-center-restore/MANIFEST.json`：代码SHA、真实两腿验收摘要、ROS ABI和私有归档字节SHA。
- `release/ros1-blocks-center-restore/CAPABILITIES.json`：当前可验收/待重新验收的能力目录。
- `release/site-source-20261112/`：此前保存的现场RC1源码基线，不直接覆盖生产树。

## 本轮私有增量（Mac）

目录：`/Users/andyee/Documents/ChatGPT/local/site-private-20261112-center-restore/`。原11月12日归档在相邻`site-private-20261112-offline-handoff/`，未改旧包。

| 包 | 归档范围 | 内部校验文件数 |
|---|---|---:|
| P0-current-source-ros-evidence.tar.gz | 当前源码、配置、ROS生成工作空间、原始运行材料 | 1052 |
| center-restore-final-private-20261112.tar.gz | 两腿完整scene/轨迹/native/ROS/实际关节与TCP，保护停与连接失败，独立代码/工作空间 | 601 |
| capture-raw-body-private.tar.gz | 沿capture_pointer补齐的CAMERA与BODY点云、采集manifest，含两腿与前一次ROS回归 | 12 |
| python-camera-curobo-dependencies.tar.gz | Python JAKA、EpicEye SDK/已安装模块、pinned cuRobo源码包 | 520 |
| original-tree-diff-untracked-private.tar.gz | 原ARES-R工作树HEAD、dirty/staged diff、untracked/ignored清单和小型未跟踪源码 | 7343 |
| additional-native-private.tar.gz | Python侧实际libjakaAPI及FK审计程序 | 2 |

六包合计231,695,184字节，全部归档SHA及内部文件SHA已核验。文件数是每包数量，包间有重复，不作为全局去重数量。原始SDK、模型、运行记录和点云不上传公共GitHub。

Mac私有目录的`ARCHIVE_INDEX.json`记录每包SHA/尺寸；各解包目录保留内部MANIFEST。`runtime-inventory.json`记录进程、Action ABI和关键现场源/二进制哈希；`delivery-summary.json`记录run_id与两腿plan/scene/native结果。每个完整运行目录的goal_binding.json、saved_pose_record.json和各腿telemetry/plan_handle将源版本、目标、场景与反馈连接起来。

## 比对与未覆盖项

P0增量相对原703份源码清单：552同SHA、1内容变化、499新增文件（包括生成产物；旧清单还有其他目录，不据此认定被删除）。原工作树没有reset/clean/切分支；不改同事dirty文件。ignored大型缓存内容没有全盘搬运，清单已保存。

已补齐原先只留scene指针、没有原始云文件的缺口。两个精确scene的原始采集目录和BODY转换产物都已获取，不用历史点云替代。

未复制完整Conda/venv、NVIDIA驱动和全部依赖wheel；只有环境freeze、pinned源码与SDK。重新安装Torch/CUDA/Warp等仍需匹配环境/可用安装源。Mac可做逻辑、ROS假后端设计和数据分析；真实GPU回放需Ubuntu+相容GPU。此次没有在另一台Ubuntu重跑，不宣称所有平台已可直接运行。

## 为ScanPick/ScanPlace的离线接手

资料足以继续：梳理现有脚本、定义Goal/Result、持物session合同、故障/取消/幂等测试、冻结点云与轨迹分析和GPU回放准备。资料不能替代新参数/工具/新对象的现场取放验收。

后续建议顺序：

1. 建立payload_session，明确Pick保持点、夹持验证和Place所需输入，禁止把旧“原位放回”复合脚本直接当ScanPick。
2. 将参数版本与README/catalog对齐；料盘DMP当前Y5_Z20_D20与旧D10描述冲突只登记，不在本轮改生产参数。
3. 增加统一RunBlock适配；保持旧ReturnCenter及新CenterRestore两个已验收接口不变。
4. 在无硬件网络的Ubuntu重放原始请求，最后返场做Pick/Place独立验收。
