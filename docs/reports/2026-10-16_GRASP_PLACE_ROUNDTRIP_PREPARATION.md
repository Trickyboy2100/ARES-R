# 完整往返抓放 Demo 准备记录

日期：2026-10-16，Asia/Shanghai。仅实现/测试/注册，不进行设备运动。

- Demo：`right_arm_grasp_place_roundtrip_v1`，版本0.1.0-review。
- 全部参数与调用说明：`demos/right_arm_grasp_place_roundtrip_v1/parameters.json`、同目录README。
- 脚本：`scripts/run_grasp_place_roundtrip.py`；20阶段编排：`src/ares_r/manipulation/roundtrip_demo.py`。
- 全量隔离测试：623 tests，OK，1 skipped。日志 `worklog/runtime/roundtrip-full-tests-20261016.log`。
- 新增9项回归通过，覆盖往返顺序、230mm分解、禁止扩大contact bypass、禁止并发/QUALITY fallback、stage fault立即停止。
- Mock全链回放通过；真实adapter未执行、未将回放当成实机验收。
- `--prepare`：依赖资产齐全，FAST期限匹配4秒。审核包包含参数/路线digest和golden fallback文件哈希；`execution_allowed=false`。
- ART/WebUI `/api/demos` 已发现新demo，但未自动选中或运行。后台/WebUI服务active。
- FAST配置仅将2秒改为4秒并更新revision；已有seed/graph/distance backend不变。硬碰撞/跟踪/site/native限制保留。
- STOP新增仅在新Demo active记录存在时写其停止锁存；原有停止流程保留。
- 同事dirty改动未reset/revert，覆盖前逐文件哈希一致并保全到 `worklog/preservation/2026-10-16-roundtrip-demo/`。

Golden fallback未改变：

```text
scripts/run_first_pick_demo.py
e158482004601bbb1e562ee842fb590f27805813b7d7ee029ce5e59e41ea2bb0
demos/right_arm_epic_pick_lift_v1/demo.json
25b78297558e755895d3a0202f0afe43147ac5625539c70bd7e790343b246056
```

## 审核前不能宣称的状态

`FULL_PHYSICAL_CYCLE_COMMISSIONED=NO`。
`FRESH_FAST_4S_FULL_CHAIN_VALIDATED=NO`。
`CONTACT_LIFT_0_20_STAGE_COMMISSIONED=NO`。
`CONCURRENT_BASE_ARM_RETURN_READY=NO`。
`EXECUTION_REVIEW_APPROVED=NO`。

当前串行返回实现：后撤0.30m→停稳→fresh scene水平cuRobo收臂→左移0.75m→前移0.30m。与边移动边收臂的请求不同，须明确审核同意。持物230mm HOLD的底盘扫掠净空、4cm上方释放的实际落差与40%开度也需现场审核。全链每个新目标仍必须fresh scan/plan/validate，4秒超时即停止，不借用旧轨迹。

## 后续operator override：V2（当前有效）

以上V1时序作为历史保留，当前参数revision为 `RIGHT_GRASP_PLACE_ROUNDTRIP_2026_10_16_V2_NO_STOW_RETRY3`，Demo版本0.2.0-review。

- 已接受4cm上方直接释放，取消所有返回收臂动作；返回只执行X−0.30m→Y+0.75m→X+0.30m，各段停稳，右臂保持释放后姿态。
- 当前为19阶段，不读取center、不规划center、不执行stow。
- 每段最多3次总规划请求：FAST（4秒）→QUALITY→QUALITY，成功立即结束。QUALITY使用当前site配置上限240秒；不修改其他motion mode的隐式fallback策略。
- 每次规划重试fresh state/scene，pick重新获得atomic epoch。仅规划失败重试，不重复夹爪或已执行运动。三次都失败、controller fault、执行失败、STOP或抓取验证失败时停。
- 新增12项测试通过；完整隔离回归626 tests，OK，1 skipped。日志 `worklog/runtime/roundtrip-full-tests-v2-20261016.log`。
- V2 prepare与19阶段Mock replay通过；新策略在ART/WebUI目录可见。
- 本轮仍未实机运动，`review_approved=false`，真实全链commissioning结论保持未完成。旧golden fallback未修改。
