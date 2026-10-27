# 离线研发证据复现

本工具不采集相机、不导入执行SDK、不连接生产backend；CPU/GPU实验通过`offline_sandbox.sh`隔离网络和串口，GPU只映射本地0号。浏览器截屏用原HTML/JS及本地route fixture，所有外部请求拒绝。禁止将该脚本替换成现场任务入口。

输入由有权限的本地受控盘提供：

- `RECORDS_DIRECTORY`：`ARES-R_2026-10-12_Preland_Planning_Records`，含real_aligned_sources与transit10.10；点云/几何/manifest不随本包公开。
- `PINNED_ARES_GIT_REPO`：具备b978cbd669b5a3f6bc0bd19defcbe5256692f145 Git对象的ARES仓库；无需联网。直接取Git对象，不读取同仓未提交资产。
- `PYTHON`：Torch2.5.1+cu121、numpy2.4.6、scipy1.17.1、open3d0.19.0、matplotlib、PyYAML、Pillow；cuRobo pinned8e734f…及完整ARES_R_SOURCE_MANIFEST。cuRobo与Warp使用已有健康CUDA环境。
- Chromium与Playwright；设置`ARES_NODE`、`ARES_PLAYWRIGHT`（模块目录）和可选`CHROME_BIN`。不捆绑下载浏览器/字体。
- bwrap、c++编译器。系统NotoSansCJK-Regular.ttc、DejaVuSans；只引用本机字体，不分发字体。

```bash
export ARES_PLAYWRIGHT=/controlled/runtime/node_modules/playwright
export ARES_NODE=/controlled/runtime/bin/node
./tools/presentation_evidence/run_all.sh "$RECORDS_DIRECTORY" "$PINNED_ARES_GIT_REPO" "$PYTHON"
```

相同输出根会重新生成本轮派生素材；原输入和Golden不被修改。默认私有目录`worklog/runtime/presentation_evidence`已忽略，不提交。`ARES_EVIDENCE_OUTPUT`可指定新输出目录；`ARES_EVIDENCE_PRIVATE`需留在工作树可写且忽略的目录中（sandbox仅将工作树映射可写）。

分组重跑：

1. `prepare_model.py`提取pinned URDF/YAML并明确记录非commissioned运行配置；保留六轴限制，将非规划finger锁定为0，几何由冻结request给出。不要复制preview配置当现场资产。
2. `replay_rasc.py`运行六阶段，1冷/5热；同源OLD/NEW统一7mm且不删除微小基元。源mask开销边界见报告。
3. `compute_comparisons.py`重测CPU后端/索引并运行真实GPU A/B。`--gpu-only`跳过已完成CPU；`--reuse-completed`仅在核对相同scene/start/runtime目标与worker SHA后复用GPU收据（实际原始request SHA仍须审查），禁止用旧报告代替新scene。
4. `prepare_ui.py`在断网namespace内运行真实TaskStudio+ReplayProvider注入失败；`capture_ui.cjs`只截实际页面，route所有网络请求。
5. `render_assets.py`绘制主panel；`extra_figures.py`做参数扫、GPU轨迹/净空、真实恢复时间；`write_reports.py`生成审计。报告描述这份固定数据集，重跑库版本变化时务必核对所有历史叙述与新数值。
6. `finalize_bundle.py`加独立UI图注、manifest、图库与总览，保留原屏像素，公开资料做路径/IP泄漏检查。`verify_bundle.py`校验全部hash、全点保留、公平安全摘要与负结果标签。

测试使用仓库unittest，无需安装pytest。原有几何/CPU/index/TaskStudio/workbench25项与新增named-joint映射5项已运行。所有本轮日志位于私有运行目录；公开摘要与SHA在runlogs。

本轮没有正常完成的完整ServoJ原trace、原9/21 scan、原10/21 study tar或授权现场视频。对应图位BLOCKED；工具不会填假数、模拟actual q或在缺数据时自动连接现场。
