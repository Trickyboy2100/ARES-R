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
