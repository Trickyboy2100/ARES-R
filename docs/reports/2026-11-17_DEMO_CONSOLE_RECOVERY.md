# Demo Console 任务故障复位

新增 POST /api/demo-console/recover，body: {"confirmation":"RESET_FAILED_DEMO"}。前端按钮“复位任务故障”。

运行任务不可复位；失败任务须确认子进程退出、取得左右servo独占锁、真实SDK健康回读通过后，归档恢复证据并释放任务占用。历史失败结果不改写，不删日志、不自动运动、不自动续跑。控制器本身仍有错误时拒绝恢复；本版不发送clear_error、collision_recover、resume、enable。按钮明确是任务故障复位，不宣称消除控制器物理异常。

现场验证：2026-11-17接口返回RESET_READY，证据worklog/evidence/demo-recovery/faad043ce6be4032874d06489692f28a.json。

新增3项测试通过。既有test_demo_console 25项中3项失败：旧目录项数量固定4（现5）、旧alias无对应定义、历史SIFT Golden named_poses哈希与已更新center不一致；这些不应通过删除历史约束来掩盖，未改写Golden验收证据。

随后启动ROS Demo02重测9d03773d66a1431a847cf33b6bc22645，完整结果待回收。
