# ARES-R Demo Library

每个可演示任务占用一个稳定目录：

```text
demos/<demo_id>/
├── demo.json          机器可读定义、版本、阶段、freshness 和执行入口
├── README.md          现场操作说明
└── evidence.json      已完成 commissioning 的小型证据索引
```

运行时生成的点云、轨迹和日志不得写进这里，而写入
`worklog/evidence/demo-runs/<demo_id>/<run_id>/`。`demo.json` 是流程定义，
不是可复用旧轨迹；所有标记为 `fresh` 的数据必须在每次运行重新生成。

ART 与 WebUI 共用 `ares_r.demos.DemoRegistry`，因此选择状态、版本和执行入口一致。

2026-10-23 新增正式 `right_arm_pick_lift_replace_reset_v1`（1.0.0）：固定夹具下右臂抓取、连续230mm抬升、原路放回并回center，已完成热态及planner冷态无中断验收。范围不含底盘转场、六泊位或整机断电启动；详情及运行/停止命令见该目录README。原 `right_arm_epic_pick_lift_v1` golden不变。
