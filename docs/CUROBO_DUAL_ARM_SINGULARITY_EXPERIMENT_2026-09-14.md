# 双臂预抓取路径奇异性与 cuRobo 规划耗时实验

日期：2026-09-14  
状态：实机预抓取实验准备版，尚未发送运动  
范围：JAKA Mini2 左右臂；现场监督下逐条规划、检查并执行  

## 0. 第一次使用 ARES-R 必读

### 0.1 本次工作最后应得到什么

每条机械臂需要形成一组可复查的实验资料：

```text
实际起点 joints/TCP
        ↓
固定预抓取目标 joints/TCP
        ↓
3 种 cuRobo profile 的规划结果与耗时
        ↓
选中的轨迹预览
        ↓
一次现场确认
        ↓
单臂 ServoJ 实机执行日志和实际反馈
```

首次实验不追求自动抓取，不闭合夹爪，不移动底盘。目标只是让 TCP 从三个安全起点分别到达预抓取点，并查清哪些起点容易出现奇异、腕部翻转、限位或规划耗时突增。

### 0.2 ARES-R 在哪里

工控机地址和仓库目录：

```text
SSH:  yikun@172.28.172.210
仓库: /home/yikun/ARES-R
```

从另一台电脑登录：

```bash
ssh yikun@172.28.172.210
cd /home/yikun/ARES-R
pwd
git status --short --branch
```

`pwd` 应输出 `/home/yikun/ARES-R`。本实验开始时 `main` 应位于 `92a9c5749558dfa443dc9cb6a2a2f9963d6201aa`，并且只看到本文档这个未跟踪文件。发现其他修改时不得执行 `reset`、`checkout` 或删除文件，应先记录并确认修改来源。

### 0.3 禁止使用的旧入口

以下文件是历史原型或专项脚本，不是本实验入口：

```text
prototype/0_test.py
b5_move.py
b5_move_safe.py
b5_servo_move.py
curobo execute-micro
```

不得直接运行，不得复制其中的 ServoJ 调用做实验。所有实机操作从 `scripts/run_terminal.sh` 进入。

### 0.4 ART 是什么

ART 指 ARES-R Terminal。启动后会出现：

```text
ares-r>
```

只有看到这个提示符后才能输入 ART 命令。`jaka status right` 是 ART 命令，不是在普通 Bash 提示符中执行的 Linux 命令。

ART 有两种启动方式：

```bash
# 离线模式：不连接任何实机
cd /home/yikun/ARES-R
./scripts/run_terminal.sh

# 实机模式：连接相机、双臂和夹爪，但启动本身不会让机械臂运动
cd /home/yikun/ARES-R
ARES_R_HARDWARE_CONFIRM=YES ./scripts/run_terminal.sh --enable-hardware
```

本实验需要读取真实关节和 TCP，因此使用第二种。出现 `Using ... dope3.8 ...` 属于正常的串口依赖选择。

退出 ART：

```text
exit
```

命令正在运行时需要请求停止，可按 `Ctrl+C`。实机运动时物理急停优先于键盘停止。

### 0.5 建议打开两个 SSH 窗口

窗口 A 专门运行 ART，不在其中执行 Git 或修改配置。窗口 B 专门查看日志和文件：

```bash
cd /home/yikun/ARES-R
find logs -maxdepth 2 -type f -printf '%T@ %p\n' | sort -nr | head -20
```

不要同时启动两个硬件模式 ART。第二个控制进程可能与第一个争用控制器连接。

### 0.6 命令是否会运动

| 命令 | 是否连接实机 | 是否运动 | 用途 |
|---|---|---|---|
| `status` | 是 | 否 | 查看整体连接状态 |
| `jaka status left/right` | 是 | 否 | 查看控制器、限位、碰撞等状态 |
| `jaka joints left/right` | 是 | 否 | 读取六关节角 |
| `world view` | 是 | 否 | 读取双臂并显示 BODY 坐标三视图 |
| `curobo status` | 否/只查本机环境 | 否 | 查看 GPU、模型和 cuRobo 环境 |
| `curobo preview FILE` | 否 | 否 | 查看已保存轨迹 |
| `jaka plan ...` | 是 | 否 | 只预览关节目标 |
| `jaka move ...` | 是 | **是** | 受控 MoveJ，仅允许邻近目标 |
| `pose go ...` | 是 | **是** | 移动到已 commissioning 的命名姿态 |
| `curobo demo cycle20` | 是 | **是** | 历史右臂 20 cm Demo，不是预抓取实验 |

任何要求输入 `MOVE LEFT`、`MOVE RIGHT`、`RUN ...` 的命令都可能发送运动。看不懂提示时不要输入确认短语。

### 0.7 开始前现场检查

逐项口头确认并在实验记录中写明：

- 机器人底盘静止，实验期间不接受导航任务；
- 当前只测试一条臂，另一条臂停止且不进入测试区域；
- 测试臂、肘部、腕部、TCP 和线缆的预计扫掠区域无人员和物体；
- 夹爪空载，不抓持料盘或工具；
- 物理急停可立即触及；
- JAKA App 内机械臂状态正常，无未复位的限位、碰撞或保护停止；
- 控制器中启用的 Tool ID 与本次刚校准的 TCP 完全一致；
- 不存在另一个 ART、JAKA 调试脚本或同事程序正在控制同一条臂。

任一项不满足时只允许读取状态和离线规划。

### 0.8 第一次进入 ART 后照着输入

先不要运动，逐行输入：

```text
status
curobo status
jaka status left
jaka status right
jaka joints left
jaka joints right
world view
```

判断方法：

- `curobo status` 中 `planning_ready` 应为 `true`；
- JAKA 状态不应出现碰撞、关节限位、保护停止或连接失败；
- `jaka joints` 应返回六个有限数值，不能出现 `NaN`、空数组或持续不变化的假值；
- `world view` 应同时看到 L/R，两臂位置与现场目测方向一致；
- 状态异常时复制完整输出，不要反复重启或自动重试运动。

### 0.9 “当前 TCP 作为预抓取点”的记录办法

推荐使用 JAKA App 的拖拽/手动模式把单臂 TCP 摆到预抓取位置。此过程由 JAKA 控制器完成，不通过 ARES-R。到位后：

1. 退出拖拽模式并确保机械臂保持静止；
2. 在 JAKA App 截图保存 Tool ID 和 TCP 配置；
3. 在 ART 输入 `jaka joints SIDE`；
4. 输入 `world view`，记录 BODY TCP；
5. 输入 `note PREGRASP_SIDE captured，Tool ID=...，现场工装=...`；
6. 将六关节弧度值和 BODY TCP 六维值写入 case manifest；
7. 再读取一次，确认两次值一致后才作为 goal。

`SIDE` 必须替换成 `left` 或 `right`，不能原样输入。预抓取点是轨迹终点，不是抓取接触点，应与物体保留预定接近距离。

### 0.10 当前软件状态

已经可用：

- 双臂状态、关节和 world view 读取；
- 右臂历史 20 cm cuRobo 规划/执行链；
- 保存的规划 request 离线复放；
- cuRobo 分阶段时间戳和轨迹预览。

尚未可用：

- 任意左右臂预抓取 case 的统一 `plan` 命令；
- 左臂通用 cuRobo→ServoJ 执行器；
- 自动计算并显示整条轨迹雅可比奇异指标；
- 双臂同时运动。

因此本文后续出现的 `benchmark_pregrasp.py` 是紧接着需要实现的工具，不是当前已经存在的命令。工具完成前只能采集目标、生成实验 case、复放旧 request，不能用旧 Demo 指令代替真实预抓取轨迹。

## 1. 实验目的

建立可重复的数据集，比较左右臂从机器人身前不同起点到同一预抓取位姿时：

1. cuRobo 是否找到完整、无碰撞的关节空间路径；
2. 路径是否接近腕部、肘部或综合雅可比奇异区；
3. 不同 cuRobo profile 的成功率、规划耗时和路径质量；
4. 起点、IK 分支、工具 TCP 或配置变化是否导致结果突变。

本轮目标是尽快取得真实轨迹、控制器反馈和规划耗时，不把生产级自主运行认证作为实验前置条件。规划成功仍需现场确认后才能逐条执行。

## 2. 固定事实与坐标约定

- BODY 原点：双臂基座中心连线中点正下方的地面点。
- `+X`：车体前方/北；`+Y`：车体左方/西；`+Z`：向上。
- 左臂基座：`[0.0, +0.2, 1.2] m`；右臂基座：`[0.0, -0.2, 1.2] m`。
- 身体中心禁区厚度 14 cm：`|BODY Y| <= 0.07 m` 不允许 TCP、工具或机械臂扫掠体触碰。
- 每条记录至少包含控制器 Tool ID、TCP 六维值、起终点 joints、规划 profile 和日志路径；digest 等追溯字段由程序能取得多少就记录多少，不阻塞第一次实验。
- 左右臂分别执行。若另一条臂尚未进入碰撞模型，将其停在明确不进入测试臂扫掠空间的位置并保持静止，现场确认后可做监督实验。

## 3. 最重要的变量控制

同一个 TCP 点可以对应多个 IK 解，奇异性取决于整组关节构型，而不只取决于 TCP 位置。因此一个有效 case 必须冻结：

```text
case_id
arm
start_joint_rad[6]
start_body_tcp_m_rad[6]
goal_joint_rad[6]
goal_body_tcp_m_rad[6]
goal_ik_branch_id
other_arm_joint_rad[6]
tool_id + tcp_revision
scene_snapshot_id / scene_digest
robot_model_revision
planning_profile
random_seed
```

目标 TCP 六维姿态必须完全一致。只固定 XYZ、让 RPY 或 IK 分支漂移，不属于同一组对照实验。

## 4. 预抓取目标定义

先为实际工位各定义一个左右镜像的预抓取位姿，不在文档内猜测现场数值：

```text
PREGRASP_L = [X_t, +Y_t, Z_t, R_l, P_l, Yaw_l]
PREGRASP_R = [X_t, -Y_t, Z_t, R_r, P_r, Yaw_r]
```

要求：

- 均为 BODY 坐标，平移单位 m、旋转单位 rad；
- 夹爪姿态、预抓取距离和抓取轴由同一工装/目标定义；
- 使用控制器当前已校准 TCP 反算并保存 goal joints；
- 每臂选择一个固定 IK 分支作为主实验，其他 IK 分支另设 `branch_B/branch_C` case，不得混入重复测时；
- 目标不得进入中心禁区。额外 5 cm 是建议裕量，不再作为首次监督实验的硬阻断条件。

## 5. 身前起点集合

首次实机实验只采用三个起点，形成结果后再扩展。`outward` 对左臂为 `+Y`、对右臂为 `-Y`。

| ID | BODY 平移相对目标 | 目的 |
|---|---|---|
| S0 | 已验收的 `ready` 或当前规范中立位 | 基准 |
| S1 | `[-0.25 X, +0.10 outward, +0.10 Z] m` | 远距离斜向进入 |
| S4 | `[-0.15 X, +0.15 outward, +0.05 Z] m` | 外侧进入 |

S0、S1、S4 完成后再加入高位 S2、低位 S3 和靠中心 S5。所有起点保持与预抓取目标相同的 TCP RPY；优先采用与当前姿态连续的 IK 解，不要求首次实验穷举全部 IK 分支。

## 6. 奇异性指标

对 cuRobo 返回轨迹的每个插值点及每段至少 4 个 subsample 计算：

- `sigma_min_scaled`：缩放后 6×6 几何雅可比最小奇异值；
- `condition_number_scaled`：最大/最小奇异值；
- `manipulability_scaled`：`sqrt(det(J J^T))`；
- `abs_sin_j5`：腕部奇异的辅助指标，不能代替完整雅可比；
- 六关节最小软限位余量；
- 相邻点最大关节变化、速度、加速度；
- 最差样本 index、关节角和 BODY TCP。

平移雅可比和旋转雅可比量纲不同。比较条件数前使用固定特征长度 `L_ref = 0.5 m`：`J_scaled = [J_v / L_ref; J_w]`，并在所有 case 中保持一致。

第一轮仅把指标用于排序、提示和事后分析，不因尚未校准的数值阈值自动阻断轨迹：

| 等级 | 任一条件 |
|---|---|
| RED | `sigma_min_scaled < 0.02`，或 `condition_number > 200`，或 `abs(sin(J5)) < 0.05` |
| AMBER | `sigma_min_scaled < 0.05`，或 `condition_number > 100`，或 `abs(sin(J5)) < 0.10` |
| REVIEW | 指标正常但出现 IK 分支跳变、腕部翻转、软限位不足或大关节绕行 |

出现 RED 时暂停在执行确认点，由轨迹曲线、关节变化、控制器报警历史和现场姿态共同判断。不能仅用 `J5≈0` 判定所有奇异点。

## 7. cuRobo profile

首轮只使用仓库已经暴露且会完整写入 request/trajectory 的三种 profile：

| Profile | 变化 | 解释 |
|---|---|---|
| `current` | 8 IK seeds、8 TrajOpt seeds、5 attempts、graph attempt 1、CUDA Graph off | 基线 |
| `seeds4` | 4 IK seeds、4 TrajOpt seeds | 低成本对照 |
| `cuda-graph` | 基线 + CUDA Graph on | GPU 图优化对照 |

当前路径使用 `plan_cspace(goal_joint, start_joint)`，goal IK 已在规划前固定。因此 `num_ik_seeds` 对这一实验通常没有实际作用；`seeds4` 的主要变化来自 TrajOpt seeds。若要研究 IK seeds，必须另建 Pose-goal 实验，不得把 plan_cspace 结果解释为 IK seed 结果。

后续可增加 `fast`、`robust`、`graph-late` profile，但必须通过代码评审加入 `PROFILES`，禁止临时改 `config/system.json` 后忘记还原。自碰撞检查、工具代理球和分段验证不得为了提速关闭或减少。

## 8. 运行顺序

### 8.1 同步与版本留证

```bash
cd /home/yikun/ARES-R
git status --short --branch
git rev-parse HEAD
git rev-parse origin/main
sha256sum config/robot_world.json config/system.json config/jaka_mini2_motion.site.json
```

本次同步基线应为：

```text
main = 92a9c5749558dfa443dc9cb6a2a2f9963d6201aa
```

### 8.2 采集 TCP/关节状态

启动实机终端：

```bash
cd /home/yikun/ARES-R
ARES_R_HARDWARE_CONFIRM=YES ./scripts/run_terminal.sh --enable-hardware
```

逐项记录：

```text
status
jaka status left
jaka status right
jaka joints left
jaka joints right
world view
note 双臂奇异性实验基线：记录Tool ID、TCP revision、另一臂固定姿态
```

退出 ART 后，将完整事件日志路径填入实验 manifest。控制器 APP 中的 Tool ID/TCP 页面另行截图留证。TCP 改动后，旧 case 全部失效。

### 8.3 快速验证现有规划计时链

现有固定历史请求可用于确认环境和计时链路：

```bash
cd /home/yikun/ARES-R
/home/yikun/ares-r-curobo-venv/bin/python scripts/benchmark_curobo_planning.py \
  logs/curobo_obstacle_20260907_154635_1eb10b95/request.json --profile current
/home/yikun/ares-r-curobo-venv/bin/python scripts/benchmark_curobo_planning.py \
  logs/curobo_obstacle_20260907_154635_1eb10b95/request.json --profile seeds4
/home/yikun/ares-r-curobo-venv/bin/python scripts/benchmark_curobo_planning.py \
  logs/curobo_obstacle_20260907_154635_1eb10b95/request.json --profile cuda-graph
```

这三条命令只验证旧右臂 request 的复放能力，不能代表新预抓取实验。

### 8.4 实机预抓取所需的最小工具补齐

现有入口无法把任意双臂预抓取轨迹交给受监督 ServoJ。开始移动前只补一个最小工具，不等待完整生产框架：

1. 从控制器读取实际 start joints，并从 case manifest 读取预抓取 goal joints；
2. 支持 `arm=left/right`，使用各自 BODY→planning-base 变换；
3. 使用固定 start joints 和 goal joints；
4. 场景至少包含车体、当前工具代理和中心禁区；另一条臂由物理隔离保证，日志明确记录是否已建模；
5. 保存原始 cuRobo 轨迹，不追加 fallback 或终点修正；
6. 计算第 6 节奇异性指标；
7. 保存 profile、random seed、模型/工具/场景 digest 和完整阶段时间；
8. 规划和执行保持两个命令；`plan` 永不运动，`run` 要求逐条确认并显示 dashboard；
9. `run` 执行前重新读取 actual joints，与 trajectory 起点不一致时重新规划；
10. 一次只连接并控制选定的一条臂。

现有 `curobo plan-file` 每关节仅允许 0.5°，现有 obstacle worker 又只接受右臂 Demo request；二者均不可绕过限制用作本实验的任意双臂规划器。

最小工具完成后，推荐形成以下命令。下列命令是接口设计，当前版本执行前必须先用 `help` 确认已经出现；`help` 中没有时不得输入：

```text
# 只读取当前臂并保存为一个实验起点，不运动
pregrasp capture-start CASE_ID SIDE

# 只保存当前臂为预抓取目标，不运动
pregrasp capture-goal TARGET_ID SIDE

# 只规划，不运动
pregrasp plan CASE_ID PROFILE

# 查看关节、TCP、奇异性和时间曲线，不运动
pregrasp preview last

# 执行刚刚规划且尚未使用的轨迹；必须再次输入精确确认短语
pregrasp run last
```

计划输出目录建议为：

```text
logs/pregrasp_<date>_<case_id>_<run_id>/
├── case.json
├── request.json
├── planner.log
├── trajectory.json
├── trajectory.preview.html
├── singularity.json
├── native_execution.log
└── result.json
```

### 8.5 case manifest 示例

以下只是数据格式示例，所有 `REPLACE_*` 必须换成现场实测值。含占位符的文件应被程序拒绝：

```json
{
  "schema_version": 1,
  "case_id": "right_S0_to_pregrasp_A",
  "arm": "right",
  "start_joint_rad": ["REPLACE_6_VALUES"],
  "start_body_tcp_m_rad": ["REPLACE_6_VALUES"],
  "goal_joint_rad": ["REPLACE_6_VALUES"],
  "goal_body_tcp_m_rad": ["REPLACE_6_VALUES"],
  "goal_ik_branch_id": "controller_current_branch",
  "other_arm_joint_rad": ["REPLACE_6_VALUES"],
  "other_arm_physically_separated": true,
  "tool_id": "REPLACE_TOOL_ID",
  "tcp_revision": "2026-09-14-site",
  "scene_note": "empty supervised test workspace",
  "operator_note": "first pregrasp commissioning"
}
```

注意：六维 TCP 顺序为 `[x, y, z, roll, pitch, yaw]`，不是旋转向量；BODY 平移单位为 m、角度单位为 rad。控制器原始 TCP 常以 mm/rad 返回，写入 BODY manifest 前必须经过 ARES-R 坐标变换，不能直接把 mm 当 m。

### 8.6 首轮实机采样矩阵

不再要求 108 次离线运行。每条臂先执行：

```text
3 starts × 3 profiles × 1 plan = 9 plans
从每个 start 选择 1 条通过预览的轨迹实机执行 = 3 motions
```

右臂先完成 3 条，再按相同方法做左臂。首轮固定 `random_seed=123`。只有发现规划不稳定时才增加重复次数或随机种子。

首轮至少汇总：

- success / failure；
- orchestration wall、worker total、`plan_cspace` wall；
- cuRobo `total_time`、`solve_time`；
- 最小 `sigma_min_scaled`、最大 condition number；
- 最小碰撞净空、最小软限位余量；
- 路径关节长度、TCP 路径长度、点数；
- 失败阶段和完整错误消息。

## 9. 实机执行顺序

每次计划通过轨迹预览和现场确认后即可执行，不要求先完成整批离线评审：

1. 现场净空、物理急停、观察人员到位；
2. 另一条臂停在不进入测试区域的位置，不同时运行任务；
3. 从 S0 开始，再按 S1、S4 顺序；
4. 先低速运行一条已通过的轨迹，逐点比较 commanded/actual joints；
5. 监视跟踪误差、控制器奇异/限位报警、ServoJ deadline lag；
6. 出现控制器奇异/限位报警、明显腕部翻转、跟踪误差或现场干涉风险立即停止；
7. 每次移动后重新读取实际 joints/TCP，禁止假定终点已到达；
8. 首轮不做双臂同步运动。

当前通用 cuRobo 实机执行仍未验收，文档不提供绕过 ART 安全门禁的 ServoJ 命令。

### 9.1 单条轨迹的标准操作卡

每次只处理一个 case，顺序不得颠倒：

1. 确认选定臂和 case ID，例如 `right_S0_to_pregrasp_A`；
2. 读取实际 joints/TCP，确认与 case 起点相符；
3. 执行 `plan`，此时机械臂不应移动；
4. 记录 planning wall、solve time、成功/失败和输出目录；
5. 打开 preview，检查六关节曲线是否存在突跳、大绕行或腕部翻转；
6. 检查 TCP/连杆三视图是否越过中心禁区、车体或现场工装；
7. 比较三种 profile，选择路径正常且耗时可接受的一条，不单纯选择最快的一条；
8. 再次确认现场净空、另一臂静止、急停可用；
9. 执行 `run` 并输入屏幕显示的精确确认短语；
10. 全程观察 dashboard；异常时按急停，普通停止可按 `Ctrl+C`；
11. 到达后不要立刻运行下一条，先读取实际 joints/TCP 并记录终点误差；
12. 保存 result，再决定返回起点或进入下一个 case；返回也必须重新规划，不得把旧轨迹数组直接倒放。

### 9.2 dashboard 重点观察项

- `sample/current/total`：轨迹执行进度；
- planned/actual joints：计划与控制器反馈；
- tracking error：持续增大或超过门限立即停止；
- BODY TCP XYZ/RPY：确认方向和最终预抓取位姿；
- deadline lag/read-send time：判断 ServoJ 发送是否卡顿；
- collision/limit/protective stop：任一出现都停止；
- `servo_disabled=0`、`logout=0`、`target_reached`：执行正常收尾的必要日志。

终端回到 `ares-r>` 不等于轨迹一定成功，必须同时检查最终误差和收尾日志。

## 10. 结果表

| case | arm | start | goal branch | profile | seed | success | plan wall s | solve s | sigma min | condition max | clearance m | limit margin rad | result |
|---|---|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---|
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |

每个失败都保留 request、planner log 和失败摘要。失败不可被后一次成功覆盖；重试必须生成新的 run ID。

## 11. 常见问题和处理

| 现象 | 含义 | 处理 |
|---|---|---|
| SSH timeout | ZeroTier 或网络链路暂时不可达 | 等待数秒重连；不要因此重启机器人 |
| `planning_ready=false` | cuRobo Python、GPU 或模型不可用 | 保存完整 `curobo status`，停止规划 |
| `symbol lookup error ... is_in_servomove` | JAKA SDK 动态库版本混用 | 退出 ART，检查 SDK V2.2.2 隔离；禁止换成旧脚本继续 |
| `start mismatch` | 实际关节与轨迹起点不同 | 丢弃本次执行许可，从新鲜实际状态重新规划 |
| `scene stale` | 拍照、机械臂、底盘、标定或场景已变化 | 重新建立场景并重新规划 |
| cuRobo failed | 当前 profile 未找到路径 | 保留失败日志，尝试下一 profile；禁止直线插值替代 |
| controller limit/singularity alarm | 控制器拒绝当前构型或路径 | 停止，记录报警码和当时 joints/TCP，修改起点或 IK 分支 |
| 腕部突然翻转 | IK 分支或轨迹经过不良腕部构型 | 不执行或立即停止；固定另一 IK 分支重规划 |
| ART 看似卡住 | SDK 调用、规划子进程或网络反馈等待 | 先观察 dashboard/日志；需要停止时 `Ctrl+C`，不要同时开第二个控制进程 |
| 轨迹完成但 TCP 不准 | TCP、工具号、坐标变换或跟踪存在问题 | 保持机械臂静止，读取两次状态并核对 Tool ID；不要继续下一个 case |
| `collision_checked=false` | 完整现场碰撞模型尚未认证 | 只允许现场净空、空载、监督实验，不解释为自主避障认证 |

失败后禁止自动连续重试。先确认机械臂已经停止、Servo 模式已经退出、控制器连接正常，再从实际状态重新规划。

## 12. 当日交接与留痕

实验结束后在普通 Bash 窗口执行：

```bash
cd /home/yikun/ARES-R
./scripts/worklog add "双臂预抓取实验：填写完成的case和结果" \
  --author "填写姓名" --source manual \
  --files docs/CUROBO_DUAL_ARM_SINGULARITY_EXPERIMENT_2026-09-14.md \
  --tests "填写成功/失败数量和日志目录" \
  --next "填写下一步"
```

交接内容至少包含：

```text
测试日期和人员
仓库 commit
测试臂
Tool ID / TCP revision
预抓取目标 joints + BODY TCP
完成的 case IDs
各 profile 耗时
实机执行是否成功
控制器报警码
日志目录
机器人最终 joints/TCP
机器人是否仍使能
下一步
```

不得把 `logs/` 中的大型轨迹、点云或原始日志直接 `git add .`。需提交的摘要放入 `worklog/`，原始日志保留在工控机并记录路径。

## 13. 验收结论格式

每条臂分别给出，不允许用右臂结论替代左臂：

```text
TCP_REVISION_VERIFIED = true/false
ROBOT_MODEL_FK_VERIFIED = true/false
OTHER_ARM_COLLISION_MODELED = true/false
CENTER_FORBIDDEN_ZONE_MODELED = true/false
PLANNING_PROFILE_RECOMMENDED = <profile/none>
SINGULARITY_GATE_STATUS = PROVISIONAL/PASSED/FAILED
PLANNING_ONLY_DATASET_COMPLETE = true/false
REAL_EXECUTION_COMMISSIONED = true/false
```

任何依赖项为 false 时，最终状态不得写成“可用于自主抓取”。

## 14. 相关资料

- `docs/CUROBO_PLANNING_TIME_AUDIT_2026-09-08.md`
- `docs/CUROBO_DEMO.md`
- `docs/CUROBO_REAL_DEMO20.md`
- `docs/COMMISSIONING_PLAYBOOK.md`
- `docs/JAKA_DH_VALIDATION_2026-09-04.md`
- `config/robot_world.json`
- `config/system.json`
- `scripts/benchmark_curobo_planning.py`
