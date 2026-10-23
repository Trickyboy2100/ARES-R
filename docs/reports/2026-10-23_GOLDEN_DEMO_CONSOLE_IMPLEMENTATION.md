# Golden Demo 控制台实现与无运动验收

日期：2026-10-23。

## 已实现

三个名称及 canonical ID 的映射见 `demos/catalog_aliases.json`。Golden作为验证类型；旧ID、golden runner、现场参数和已验收轨迹算法均保留。
新增独立 `/demo-console`，原场景页和操作台均有入口。准备文字、确认与一键自动准备/执行、统一停止、重复点击隔离、恢复不自动续跑均进入canonical backend。
提速版准备条件明确为当前验收站位或ID1可识别同一夹具内目标；不是固定历史坐标输入。

资源准备隔离新run，保留热planner；仅在manifest证明本目录planner死亡时隔离遗留socket并重新启动。
不会删除证据、清controller fault、杀他人GPU任务或重启共享相机。

两条逻辑工作线展示执行及并行准备/验证，不虚构OS线程或SkillRuntime调用。
监控显示真实资源曲线、关节/TCP、BODY点云和碰撞抽象、计划段和actual反馈。
关节折线使用同一 pinned URDF 与已验证 `T_controller_model`；无校正时明确报错，不采用错误identity校正。
运行时不额外打开JAKA采样会话，复用native actual和到位证据；左臂/底盘最近快照与过期年龄明确区分。

## 验证

- Mac新增23项单测通过；覆盖3种adapter（mock）、别名、权限、重复点击、占用、停止归属、恢复隔离、资源复用、场景缓存与反馈过期。
- 现场RC1相同Python环境：**838 tests，OK，1 skipped**，11.506秒。
- 浏览器实查3个入口、不同准备说明、默认禁止启动、CPU/RAM/GPU/显存曲线及左右臂实时关节/TCP折线显示。
- 新页面加载后backend状态IDLE，无实机自动启动。
- `run_pick_reset_demo.py` 的 `verify_pinned_inputs()` 在现场通过；正式Demo固定来源没有被本次改动改变。
- 原 first-pick 的Python、sender与template资产均存在；本轮未执行旧first-pick或历史取放。
- 只重载空闲隔离8775/8776，备份位于 `.32:/home/yikun/ARES-R-RC1-20261019/worklog/preservation/20261023-demo-console-before/`。

Mac全量测试中Linux `/proc` / 本机socket沙箱相关用例不能作为Linux回归结论；采用上述现场Linux全量测试结果。

## 边界

此次完成界面和adapter无运动验证，**没有点击真实启动按钮，也没有新增第三次实机闭环记录**。
原2次提速闭环的134.54/144.13秒为执行段历史值，不含本轮fresh准备时间，不承诺按钮到结束只需这些时间。
三维机械臂为关节折线，不是完整CAD网格。反馈显示约1.5秒刷新，不声称80ms控制频率的图形同步。
提速版完整显示已生成的各段轨迹；历史取放若缺少同格式产物，显示原阶段/日志，不伪造轨迹或实时读回。
软件停止不替代物理急停；legacy native停止归属不明进入RECOVERY_REQUIRED，不自动重试。

## 使用位置

- 现场：`http://172.28.172.210:8775/demo-console`。
- 本机当前SSH隧道：`http://127.0.0.1:8789/demo-console`（隧道在线时可用）。
- 使用说明：`docs/GOLDEN_DEMO_CONSOLE.md`。
- ART共享查询/停止：`demo console list`、`demo console status`、`demo console stop`。

未push；本轮不增加运动授权、不修改物理速度、碰撞或验证阈值。
