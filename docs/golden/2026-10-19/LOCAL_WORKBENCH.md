# 本地候选工作区：2026-10-20

分支 `codex/golden-offline-workbench-20261020`；只在本地提交，不push、不部署、不运动。
Golden保全锚点仍为 `f97ab4c`。此前保全的源码manifest描述该锚点，不用于把后续候选改动误报为原件损坏。

## 可实际使用

```bash
PYTHONPATH=src python -m ares_r.demo_workbench serve --port 8788
```

打开 `http://127.0.0.1:8788/workbench`。仅监听本机；无设备控制接口。已有正式WebUI也新增 `/workbench` 和导航链接，但本轮没有部署到 .32。
ART输入 `golden review` 可读取同一数据；不需要连接设备。也可：

```bash
PYTHONPATH=src python -m ares_r.demo_workbench status
PYTHONPATH=src python -m ares_r.demo_workbench timings --events /path/to/events.json
PYTHONPATH=src python -m ares_r.demo_workbench draft --direction SCALE_TO_DRYER --slots lower_left lower_middle lower_right upper_left upper_middle
PYTHONPATH=src python -m ares_r.demo_workbench draft --direction DRYER_TO_SCALE --slots lower_middle
```

页面包括：中文20阶段参数、复刻缺口、偏置来源、三视图/透视图模型查看器、两站注册表的只读语义映射、五次/反向任务草稿、实际接续时序。
草稿由同一个Python函数生成，可下载JSON。它是任务意图，**还不是已接入执行器的Scheme**，不会假装已验证任意五个泊位。
每次补料/称台清空作为显式前置条件；不能因为写了循环就假设现场料盘会自动出现或消失。

模型查看器可导入本地 `attachment.json` 或同frame的标准boxes/points JSON。当前缺少最终完整BODY scene，默认展示历史尺寸示意而非伪造现场。附件只有T_link6_object时明确标注LINK6；不要将其误称BODY三视图。导入数据仅在浏览器内解析。

## 已完成的最小性能修正

`persistent_planner_service.runtime_key` 以前把attached_object_collision整份记录纳入CUDA构建键。仅source_observation_id/point ownership变化，即使link6碰撞包络相同，也可能触发worker重建。
现使用经过完整revision验证的attached_to+link6_aabb作为持物构建部分。每次worker仍验证完整request/scene/attachment revision，改变尺寸、工具、机器人、profile仍重建。没有修改执行scene binding或cache轨迹复用规则。
结果新增 `planner_job.runtime_cache_hit/runtime_cache_reason/runtime_construction_key`。
这项修正在候选分支，CPU行为已测试；GPU提速尚未测量，不能声称已达到2秒。

## Ubuntu拿到数据后可直接运行

已有 `scripts/run_offline_gpu_replay.py` 是9月proxy/指定GPU验收，不能拿它证明10月真实场景已复现。新增 `scripts/benchmark_golden_frozen.py` 专门对哈希绑定的真实请求做对照。

填写 `ubuntu-benchmark.template.json` 的cases及所有资产依赖；原始文件不改，路径适配必须输出派生请求和新hash并保留来源。先验证：

```bash
python scripts/benchmark_golden_frozen.py --manifest /path/to/actual-manifest.json
bash scripts/offline_sandbox.sh --gpu python scripts/benchmark_golden_frozen.py --manifest /path/to/actual-manifest.json --gpu --output worklog/runtime/benchmark-unique --warm-runs 20
```

默认只比较FAST25/FAST50；QUALITY需显式 `--profiles QUALITY`，建议先 `--warm-runs 3`，其240秒预算可能昂贵。每个profile复用自有worker；冷运行和真正runtime_cache_hit热运行分开，不把超时后重建误算成热运行。记录所有失败/trajectory hash/独立检查与耗时。脚本未在GPU实跑，当前空模板会明确拒绝。

## 尚待完成，不能包装成已经可用

1. .32最终实际执行的request/scene/native/原始点云/运行注册表仍缺失；旧RC1压缩包截断。
2. 成功的160×100主段＋20mm夹持后段策略已新增正式可选入口：`prepare_task_payload` → package builder `--payload-policy` → roundtrip `payload_model_policy`。默认参数不启用，旧golden语义不变；候选开关见payload-candidate.patch.json。仍需缺失的真实数据完成全链回放后才可启用；通用payload分割必须另用真实点云验证。
3. 六泊位除历史lower_middle外仍需各自标定与取放姿态；反向从泊位抓回称台不能照搬ID3放置姿态。
4. 五次转移、反向转移需接入现有OperationsRegistry的reservation/complete和TaskRuntime，而非仅保存草稿。
5. 底盘+机械臂并行尚未commission。先做异步证据写盘/静态准备；联合运动需要动态BODY变换与共同扫掠验证。不能用“开两个线程”替代。

## 并行与工期优先级

优先保证串行黄金任务可无临时脚本接续地重复，再改善可见性和实际慢点。后台写盘/静态缓存是低耦合项；5700与5000共享相机，需要设备级仲裁。运动中fresh scene不能仍绑定静止底盘旧快照。
“升到50mm就后退”需实际TCP位移和脱离接触事件；“底盘移动同时收臂”需联动轨迹和统一停止。其潜在节省上限是两段较短耗时，不能直接把两段耗时相减后当作已验证收益。
