# 右臂原位抓取—230mm抬升—放回复位

正式版本：1.0.0。Demo ID：`right_arm_pick_lift_replace_reset_v1`。

已完成两次无中断实机验收：热态134.54秒、RC1 planner冷态144.13秒。执行时间不包含事前扫描/规划准备。冷态测试仅重启独立planner，确认worker为空、runtime_count=0；未重启工控机、backend或共享相机，不宣称整机断电冷启动通过。

## 流程与范围

当前固定夹具和100mm宽料盘；右臂从验收center开始。左臂保持，底盘不动。

fresh ID1 + Pixel Pro → fresh scene → cuRobo到55mm预抓取 → 40%开度接近 → 闭爪 → 连续BODY+Z抬升230mm → 场景与新鲜滚动夹爪反馈验证 → 反向下降放回原位 → 松爪 → 反向退出 → 回本次初始center。

并行仅用于下一段Native准备、只读底盘观察及扫描/夹爪反馈，不包含底盘与机械臂同时运动。仍保留controller、tracking、scene/state绑定和到位检查。遇到fault不自动继续，不自动下降/松爪。

这不是跨站取放，不使用ID3或六泊位。`source_parameters.json`为现场继承配置快照，含旧roundtrip的PLACE等未使用字段；真实阶段由本Demo入口及后端定义，不能按那些旧字段推断本流程会移动底盘。

## 运行

仅在 `.32:/home/yikun/ARES-R-RC1-20261019`，使用既有 `.venv`。ID1通信服务、Pixel Pro、独立canonical backend/WebUI和planner必须已启动。相机标定、工具、持物模型和现场夹具应与验收一致，现场监督与物理急停可用。

只准备，不运动：

```bash
cd /home/yikun/ARES-R-RC1-20261019
PYTHONPATH=src .venv/bin/python scripts/run_pick_reset_demo.py --prepare
```

新鲜准备后自动执行整轮（明确监督授权）：

```bash
PYTHONPATH=src .venv/bin/python scripts/run_pick_reset_demo.py --execute \
  --authorization 'RIGHT PICK RESET TIMING' --onsite-observer-confirmed
```

该入口是薄客户端，调用已验收的准备/打包工具和canonical `start` API，不复制机械臂执行算法。已准备候选可追加`--prepared <该Demo自己的run目录>`，超过原300秒新鲜度或已使用则拒绝，必须重新prepare。不能复用本目录中的验收轨迹。

停止：

```bash
PYTHONPATH=src .venv/bin/python scripts/run_pick_reset_demo.py --stop
```

等价于现有WebUI停止按钮/canonical `/api/operations/stop`；不能替代物理急停。开机、刷新页面、选择Demo或prepare均不会自动运动。

## ART和WebUI

共用DemoRegistry，ART `demo list` / `demo select right_arm_pick_lift_replace_reset_v1` / `demo prepare` 可查看版本和命令；WebUI的Demo目录显示同一新条目。当前不新增或声称已有该Demo的专属一键运行按钮，实机运行使用上述正式入口。

## 配置和证据

- `demo.json`：阶段、范围、正式入口和freshness合同。
- `source_parameters.json`：与验收一致的现场参数快照；不覆盖其他Demo。
- `pinned_inputs.json`：后端脚本及现场配置哈希；复现入口发现改变会要求明确版本审核，不影响独立实验入口。
- `evidence.json`：热态/冷态成功记录、pointcloud/package/native hashes及耗时。
- 新运行写入 `worklog/evidence/demo-runs/right_arm_pick_lift_replace_reset_v1/<run>/`。

本机/现场其他配置可能不同，不能为让校验通过而盲目覆盖生产配置。URDF、SDK、native sender、camera worker及既有初始化/几何模板仍为现场依赖；该定义不等于完整跨机器安装包。原始点云继续保留现场/private归档，不直接公开推送。

原golden `right_arm_epic_pick_lift_v1`、`scripts/run_first_pick_demo.py`及跨站roundtrip均不替换、不迁移。
