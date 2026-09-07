# 右臂反馈验证证据

- `raw_with_newline.json`：原始 10004 读取，78 帧后断连。
- `raw_without_newline.json`：无换行请求对照，79 帧后断连。
- `raw_keepalive.json`：开启本地 TCP keepalive 对照，76 帧后断连。
- `sdk222_feedback_20260907_140418.log.gz`：配套 SDK V2.2.2 C++ 公开接口，600 秒、7501 帧只读测试。末尾 `READ_ONLY_SDK_SOAK_PASSED`，最大查询耗时 0.018510144 s，`LOGOUT rc=0`。

原始通道对照均在无其他本机状态客户端的条件下进行。新 SDK 测试只查询右臂，不包含运动或程序恢复；`program_paused=1` 保持记录。通过读取测试不等于完成实机轨迹执行或证明绝对数据新鲜度。
