# GRASP → 取料 → PLACE 放料 → GRASP

版本：0.2.0-review。状态：代码与Mock回放已准备，**不等于完整实机commissioning通过**。`review_approved=false`，本轮不执行任何设备动作。旧 `right_arm_epic_pick_lift_v1` / `scripts/run_first_pick_demo.py` 保持原样，继续作为golden fallback。

## 审核流程

1. 从当前GRASP站开始。新拍Pixel Pro、5700 `320,2,1,1,1,0`（右臂space2/config1），绑定fresh observation、双臂状态、标定及工具版本。
2. persistent cuRobo FAST规划到预抓取点。预抓取距离沿用现场成功参数 **55mm**；无显式恢复waypoint、无MoveJ fallback、无Codex逐段指令。
3. 右夹爪40%（raw400），沿检测接近轴固定姿态接触、闭合raw0。Link1–6、左臂、自碰撞及控制器保护保留；仅使用原CONTACT_BYPASS_V1的限定接触语义。
4. 延迟读回0.25/0.75/1.5秒，并做TCP附近15cm scene delta；失败即停止，不抬起、不启动底盘。
5. 最初100mm竖直抬升沿用成功contact escape，附加独立dense水平验证，误差不得超过3°。抬升native速度上限由旧0.05改为 **0.20rad/s**、加速度0.20rad/s²；这属于新阶段速度应用，尚未实测验收，不能写成已commission。
6. contact bypass到100mm后失效，启用原coarse attached-object模型；fresh scene、cuRobo完整避障继续上移130mm，到抓取点之上**累计230mm**的HOLD。不能把230mm全部放进contact bypass。持物段硬水平≤3°，优先/当前版本要求物理夹爪朝BODY +X，yaw0。该yaw指TCP局部+Z接近轴的BODY方位，不是控制器RPY yaw必须数值0。
7. 保持持物HOLD，底盘0.10m/s执行：X−0.30m → Y−0.75m → X+0.30m。每段true completion、fresh完成marker、稳定停住；不旋转，左臂不动。
8. PLACE停稳后新匹配5700 config3，从六泊位注册表读取**下层中间**最新DETECTION偏置。完整SE3组合后，在BODY +Z额外加40mm作为preland。显示新标记、fresh点云，再用cuRobo FAST、attached模型、硬水平/yaw0规划并执行到该点。
9. 不再下降，右夹爪打开40%（raw400），解除attached状态并使场景失效。**TCP高于泊位40mm，不等于物体底面仅落下40mm**，实际接触/落差取决于夹持变换；该释放方式需现场审核，不宣称力控放置或落座验证。
10. 根据最新override，**取消收臂**：底盘X−0.30m → Y+0.75m → X+0.30m返回GRASP，每段停稳。双臂保持释放后的姿态，不规划center，不执行任何返回阶段机械臂运动。现场净空须包含保持该姿态时的完整扫掠范围。

本版本为19阶段，不读取center目标，也不拿ready替代。原center配置未修改。

## 参数与速度

完整参数：`parameters.json`。总抬升是相对抓取点+230mm，不是BODY绝对高度230mm。自由空间/抬升速度上限0.20rad/s，接触接近仍0.05rad/s，tracking stop保持1.5°。native打包仍须满足site和sender的最严格限制，不能通过写参数跳过限制；实际时长取决于time dilation，不承诺恒定笛卡尔速度。

FAST采用现有4IK/2trajopt、CUDA graph、一次solve/持久planner，期限**4.0秒**。本Demo的每段规划最多**3次总请求**：FAST → QUALITY → QUALITY，成功立即结束重试。QUALITY使用站点已有8/8配置及 `config/system.json:curobo.timeout_s`（当前240秒上限，不代表每次必等240秒）；不是4秒FAST的质量设置。不会重复每请求丢弃结果的warmup solve。

每次重试重新获取当前状态/场景，pick重新捕获完整epoch；非接触移动强制fresh scan。仅solver/规划失败可重试，碰撞保护不放松；执行包/硬验证失败、控制器fault、抓取验证失败、STOP不进入自动运动重试。三次都失败就停，不能用旧scene或旧trajectory续跑。全局FAST profile本身仍禁止隐式fallback；此次显式fallback只属于本Demo编排，不影响其他motion mode。

期望间隙沿用已配置0mm；硬碰撞与cuRobo避障保持开启。未知持物自体点、支撑结构或dock引起碰撞时停止，不删除环境来强行过门。

## 命令

在 `/home/yikun/ARES-R`：

```bash
python3 scripts/run_grasp_place_roundtrip.py --prepare
python3 scripts/run_grasp_place_roundtrip.py --replay
```

prepare只检查参数、资产和生成审核包；replay仅Mock顺序/故障测试。均不拍照、不连接控制器、不运动，不可将通过解释为实机全链规划已通过。

完整流程审核通过之后，才能把versioned参数中的 `review_approved` 改为true；再在有现场观察/急停的TTY运行：

```bash
python3 scripts/run_grasp_place_roundtrip.py --execute \
  --authorization 'RIGHT GRASP PLACE ROUNDTRIP' --onsite-observer-confirmed
```

停止：

```bash
python3 scripts/run_grasp_place_roundtrip.py --stop
```

Ctrl+C、ART/WebUI STOP也会触发停止锁存；native段收到SIGTERM后由既有sender执行abort/servo disable。以上均不能代替物理急停。STOP后不自动恢复，不自动补走剩余底盘段，不自动松夹爪。现场检查后另行决定恢复；不能简单清除锁存后接续旧scene/轨迹。

ART/WebUI Demo Library可发现新demo，Select/Prepare显示同一套参数和脚本命令；不会让网页自动物理运行，也不改变旧demo。

### WebUI一键入口（2026-10-16追加）

三维主页和 `/operations` 顶部新增“完整抓放 Demo · 实机”。确认现场监控、物理急停、伸臂底盘扫掠净空与释放方式后勾选复选框，再点击“一键开始完整抓放（实机）”。不再需要逐段输入命令。

启动通过canonical backend，冻结本次参数、路线、下层中间泊位偏置及授权记录，只在该次隔离参数副本中设置review批准；原 `parameters.json` 的 `review_approved=false` 不变，CLI默认不因此获得永久执行权。运行状态/当前stage/计时/日志由同一后端返回，拒绝重复启动，拒绝其他客户端在该流程中插入机械臂或底盘动作。Stop仍可调用。页面关闭后后台脚本继续运行，须显式STOP；重启不会自动创建或恢复物理任务。

API：`GET /api/demo/roundtrip/status`、`POST /api/demo/roundtrip/start`、`POST /api/demo/roundtrip/stop`。start必须携带现场确认、精确授权及当前contract digest。授权测试使用Mock进程，不实际运行机器人；现场无授权负向请求已确认拒绝，`running=false`。

## 复用的接口与调用

| 阶段 | 既有接口 |
|---|---|
| pick epoch | capture_manipulation_observation.py / ManipulationObservationTransaction |
| pregrasp目标、IK seed | prepare_authorized_first_pick.py（模板仅作模型/seed，scene来自fresh epoch） |
| 规划与重试 | plan_with_retries → persistent cuRobo，FAST4s→QUALITY→QUALITY，最多3次总请求 |
| contact/100mm lift | build_first_pick_execution_package.py / CONTACT_BYPASS_V1 |
| native重定时 | package_native_preview + validate-supervised-path，保留原几何 |
| 首抓执行 | 已校验v6_pick supervised_path，逐段fresh start/base/tool/left-arm检查 |
| 抓取验证 | verify_authorized_first_pick.py，local scene delta AND delayed readback |
| 剩余130mm/放置 | /api/motion/plan → SceneAwareMotion → /api/operations/execute |
| 全程水平 | tcp_orientation.validate_level_path，dense samples，3°hard |
| 底盘 | canonical /api/operations/base-move + BaseMotionObserver + fresh completed marker |
| 放置偏置 | EpicClient配置3 + robot_world固定base→BODY + slot DETECTION offset |
| 取消 | 新Demo stop.request + canonical operations_stop，未修改golden runner |

新stage编排在 `src/ares_r/manipulation/roundtrip_demo.py`；真实adapter在 `scripts/run_grasp_place_roundtrip.py`。运行日志、时间戳、轨迹hash、验证结果保存在 `worklog/evidence/demo-runs/right_arm_grasp_place_roundtrip_v1/<run>/`；状态隔离到 `worklog/runtime/right_arm_grasp_place_roundtrip_v1/`。

## 仍需实机验收的内容

- FAST与QUALITY fallback是否能完成当前fresh场景的pick/持物/放置目标；本轮未实际解这些新链路。
- 提速到0.20rad/s的接触后100mm lift跟踪表现；不冒充旧速度commission证据。
- 附着物与fresh扫描的一致性、230mm HOLD的底盘全扫掠净空、40mm上方释放的实际落座。
- 两站SLAM闭环误差上轮约96.5mm/5.84°；路线完成不等于精确回到物理起点，下一轮必须fresh ID1，不可复用旧抓取坐标。
