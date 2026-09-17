# 2026-09-14 下午预抓取实验帮助

> **无需担心程序恢复或回退：当前 ARES-R 改动、S0 数据、右臂预抓取执行器和测试结果均完整保留。下午不需要重做程序，也不需要执行 Git 回退。**
>
> **更新（下午现场已推进）：S1/S4 的 manifest 已建立、起点已实际捕获、三种 profile 均已规划完成；文档原先给出的 S1/S4 控制器坐标经核实不可达，已在第六、八节更正为实测可达值。执行侧的原生发送器包络已修复，`pregrasp run` 现对 S1/S4 均可用。**

状态：下午现场操作版  
仓库：`/home/yikun/ARES-R`  
范围：右臂 S1、S4 预抓取实验；左臂暂时只做规划和预览  

## 一、上午已经完成的内容

- `pregrasp capture-start`：读取并保存实际起点，不运动。
- `pregrasp capture-goal`：读取并保存预抓取目标，不运动。
- `pregrasp plan`：调用 cuRobo 进行规划，不运动。
- `pregrasp preview`：显示规划、几何和奇异性结果，不运动。
- `pregrasp run`：右臂受监督 ServoJ 执行，要求明确确认。
- `current / seeds4 / cuda-graph` 三种规划 profile 已接入。
- 右臂原生执行程序已重新编译，二进制包含 `pregrasp` 模式。
- 203 项单元测试通过，Python 编译检查通过。
- S0 三种 profile 均已成功生成轨迹和耗时记录。S0 已判定为**不可执行**（见第三节）。
- S1、S4 起点已实际捕获，两种 case 各三种 profile 均已规划完成，均为 0 RED。
- 当天未生成新的 `native_execution` 日志，新预抓取轨迹尚未实机执行。

### 下午新增：原生发送器包络修复

原生发送器的硬门限与站点配置**不同**，早期生成的文件会在操作员输入确认短语之后才被发送器拒绝：

| 门限 | 站点 `jaka_mini2_motion.site.json` | 发送器 `jaka_right_demo` | 谁更严 |
| --- | --- | --- | --- |
| 速度 | 0.10 rad/s | `rad(3.0)` = 0.05236 rad/s | 发送器 1.9 倍 |
| 加速度 | 0.2 rad/s² | 0.2 rad/s² | 相同 |
| **伺服跟随误差** | 无对应项 | `distance(实际, 上一拍目标) > 0.2°` | **发送器，最严** |
| 单关节行程 | — | 150°（`pregrasp`/`reset` 复用同一包络） | 发送器 |
| 时长 | — | 240 s | 发送器 |

现已改为逐关节取 `min(站点, 发送器, 跟随误差推算上限)`，并在写入文件前用与 C++ 完全一致的逐样本检查闭环确认。

### 跟随误差门限（2026-09-14 实机发现）

发送器还有第三道门：它中止于 `"tracking error"`——当实测关节与**上一拍目标**相差超过 0.2° 时。
这个残差正比于命令速度，因此它是一道比速度上限更紧的天花板，而速度/加速度校验看不到它。

实测比值（门值 / 峰值速度）跨越 0.038–0.114 s，取决于构型与正在运动的关节组合。
历史上记录在案的 3 次实机失败**全部**撞在这道门上：

| 运行 | 峰值速度 °/s | 门值 ° | 结果 |
| --- | --- | --- | --- |
| named_ready_160315 | 1.83 | 0.1992 | FAIL |
| obstacle_e4acbf28 | 1.86 | 0.1997 | FAIL |
| **2026-09-14 right_S1** | **1.73** | **0.1893** | **FAIL** |
| named_ready_160443 | 1.60 | 0.0907 | OK |
| obstacle_162238 | 2.39 | 0.1577 | OK |

现在取保守值 0.12 s 并把预算限制在 0.15°（发送器容许量的 75%），即速度上限 **1.25 °/s**。

当前改动全部仍在 `.32` 工控机工作区中。禁止执行：

```bash
git reset --hard
git checkout -- .
git clean -fd
git pull --rebase
```

## 二、S1/S4 卡点结论（已解决）

上午的矩阵失败原因是 `case manifest not found`。**该问题已排除**，当前状态：

```text
worklog/pregrasp/cases/right_S1/manifest.json   已建立
worklog/pregrasp/cases/right_S4/manifest.json   已建立
worklog/pregrasp/cases/right_S1/start.json      已捕获
worklog/pregrasp/cases/right_S4/start.json      已捕获
```

### 更需要留意的一点：文档原先的 S1/S4 坐标不可达

本文档早先给出的"S1 建议 BODY 起点"与"S4 建议 BODY 起点"，即相对预抓取终点
`[-0.25, -0.10, +0.10]` 与 `[-0.15, -0.15, +0.05]`，经全局 IK 复核**不可达**：
在保持 TCP 姿态不变的条件下沿 −X 后退，会让肘部折叠超出 J3 的 ±130° 限位。
用 300 个随机种子加目标种子求解，得到 S1 姿态误差 38.47°、S4 姿态误差 7.89°，
均卡在 J2/J3 的 ±121.4° 软限位上，其中 S1 的偏差肉眼可见。

纯 −X 后退超过约 100 mm 就开始不可行（误差 9.67°），所以该偏差不是数值噪声。

现在第六、八节已替换为**已在实机上实际到达并捕获**的坐标。§6/§8 的采集动作已完成，
不要再重复执行 `capture-start`（脚本采用禁止覆盖策略，会报 `already exists`）。

因此不需要修改 cuRobo 参数。**剩余顺序**为：

```text
复核已捕获的 S1/S4 与规划结果
→ 选择明确轨迹目录
→ preview 确认
→ 右臂受监督实机执行
→ 记录终点与控制器状态
```

## 三、S0 暂停执行

S0 起终点跨越两个明显奇异区域：

```text
J3: +90.48° → -51.02°
J5: +13.67° →  -9.91°
```

S0 轨迹统计（`current` profile，881 个采样）：

```text
RED samples              426 / 881
min sigma_min_scaled     0.00000965
max condition number     234713
worst J5                 -0.0085°
```

按路径分段看，RED 集中在**中段**——正是 J3/J5 同时逼近 0° 的区间：

| 路径段 | min_sigma_min | max_cond | min abs(sin J5) | RED | AMBER |
| --- | --- | --- | --- | --- | --- |
| 起点段 0–25% | 0.047564 | 47.07 | 0.18747 | 0 | 36 |
| **中段 25–75%** | **0.000010** | **234713** | **0.00015** | **401** | 199 |
| 接近终点 75–100% | 0.017243 | 124.54 | 0.12215 | 25 | 276 |

作为对照，S1/S4 在同一分段口径下**没有任何 RED**：

| 路径段 | S1 min_sigma / max_cond | S4 min_sigma / max_cond | S1 RED | S4 RED |
| --- | --- | --- | --- | --- | --- |
| 起点段 0–25% | 0.215055 / 10.06 | 0.194006 / 11.11 | 0 | 0 |
| 中段 25–75% | 0.051287 / 39.32 | 0.050322 / 40.17 | 0 | 0 |
| 接近终点 75–100% | 0.032782 / 63.04 | 0.032782 / 63.04 | 0 | 0 |

三个 profile 的几何路径几乎相同。CUDA Graph 和 seed 数量只影响耗时或搜索方式，不能消除固定起终点导致的 J3/J5 过零问题。

**禁止执行 `pregrasp run last`**：`last` 按修改时间取最新目录，历史上曾指向上午成功生成的 S0 轨迹。任何情况下都请传入经过检查的**明确目录**。

## 四、下午开始前检查

### 4.1 检查是否已有 ART

在普通 Bash 窗口执行：

```bash
pgrep -af "python.*ares_r.cli"
```

若存在 `python3 -m ares_r.cli --enable-hardware`，表示硬件 ART 已启动。不要再启动第二个硬件 ART。

若不存在 ART，执行：

```bash
cd /home/yikun/ARES-R
ARES_R_HARDWARE_CONFIRM=YES ./scripts/run_terminal.sh --enable-hardware
```

进入后应看到：

```text
ares-r>
```

### 4.2 读取状态，不运动

在 `ares-r>` 后逐行输入：

```text
status
curobo status
jaka status right
jaka joints right
world view
```

注意：以下写法无效，不要输入：

```text
jaka status left|right
```

左右臂状态必须分开执行：

```text
jaka status left
jaka status right
```

### 4.3 现场条件

- 底盘保持静止。
- 右臂夹爪保持空载。
- 左臂停在右臂扫掠区域之外并保持静止。
- 右臂、肘部、腕部、TCP 和线缆扫掠区域保持净空。
- 物理急停保持可触及。
- JAKA App 不显示碰撞、限位或保护停止。
- 当前 Tool ID 保持为上午记录的 `2`。
- TCP 数据保持为上午记录版本；若 TCP 发生变化，所有旧轨迹失效并重新采集。

## 五、创建 S1/S4 manifest（已完成）

`right_S1` 与 `right_S4` 的 `manifest.json` 均已建立，内容与下方列出的完全一致（已逐字核对）。
以下步骤保留作为参考与重建依据，**无需重做**。

在第二个普通 Bash 窗口执行，不要在 `ares-r>` 中执行：

```bash
cd /home/yikun/ARES-R

mkdir -p worklog/pregrasp/cases/right_S1
mkdir -p worklog/pregrasp/cases/right_S4

cp -n worklog/pregrasp/cases/right_S0/manifest.json \
  worklog/pregrasp/cases/right_S1/manifest.json

cp -n worklog/pregrasp/cases/right_S0/manifest.json \
  worklog/pregrasp/cases/right_S4/manifest.json
```

`cp -n` 不覆盖已有文件。随后编辑：

```bash
nano worklog/pregrasp/cases/right_S1/manifest.json
```

S1 文件内容应为：

```json
{
  "schema_version": 1,
  "case_id": "right_S1",
  "arm": "right",
  "goal_target_id": "PREGRASP_R",
  "goal_ik_branch_id": "controller_current_branch",
  "other_arm_physically_separated": true,
  "tool_id": 2,
  "tcp_revision": "2026-09-14-site",
  "scene_note": "empty supervised test workspace",
  "operator_note": "right S1 pregrasp commissioning"
}
```

保存 nano：`Ctrl+O`，按 Enter，再按 `Ctrl+X`。

编辑 S4：

```bash
nano worklog/pregrasp/cases/right_S4/manifest.json
```

S4 文件内容应为：

```json
{
  "schema_version": 1,
  "case_id": "right_S4",
  "arm": "right",
  "goal_target_id": "PREGRASP_R",
  "goal_ik_branch_id": "controller_current_branch",
  "other_arm_physically_separated": true,
  "tool_id": 2,
  "tcp_revision": "2026-09-14-site",
  "scene_note": "empty supervised test workspace",
  "operator_note": "right S4 pregrasp commissioning"
}
```

检查文件：

```bash
python3 -m json.tool worklog/pregrasp/cases/right_S1/manifest.json
python3 -m json.tool worklog/pregrasp/cases/right_S4/manifest.json
```

无报错即表示 JSON 格式正确。

## 六、S1 目标位置与采集（已完成）

上午保存的右臂预抓取点：

```text
PREGRASP_R BODY [m, rad]
[0.699681, -0.192624, 1.068202,
 1.645747,  0.025409, 1.519975]
```

同一个点的控制器读数（以下 S1/S4 的参考姿态以此为准）：

```text
控制器 TCP 平移: [499.965, -489.534, -131.798] mm
控制器 rpy     : [1.645747, 0.025409, 0.734576] rad
```

### S1 起点（已实测到达并捕获）

本节数值已经过实机验证：机械臂实际运动到了下列位置，并已执行
`pregrasp capture-start right_S1 right`。**不要重复捕获**（会报 `already exists`）。

BODY 增量相对预抓取终点：

```text
[-0.075, -0.150, +0.100] m
```

对应 BODY 绝对坐标：

```text
[0.624557, -0.342938, 1.168276,
 1.645583,  0.025523, 1.519101]
```

右臂控制器 TCP 平移目标/实测：

```text
目标参考: [340.866, -542.567, -31.798] mm
实际实测: [340.556, -542.701, -31.724] mm
```

控制器 TCP 旋转实际值：

```text
[1.645583, 0.025523, 0.733703] rad
```

使用 JAKA App 低速笛卡尔点动接近以上控制器 TCP。BODY 坐标不能直接填入控制器坐标。移动期间保持当前肘部和腕部 IK 分支，尽量使 J3、J5 与预抓取终点保持同号并远离 0°。

**为什么不是文档早先写的 `[252.478, -383.468, -31.798]`**：那个点对应 BODY 增量
`[-0.25, -0.10, +0.10]`，在保持 TCP 姿态的前提下不可达（J3 撞软限位，IK 姿态误差 38.47°）。
如果 JAKA App 里"移动不过去"，就是这个原因，不是操作问题。

停止点动并确认机械臂静止后，在 ART 输入：

```text
jaka joints right
world view
pregrasp capture-start right_S1 right
```

**此步已完成。** 实际输出曾为：

```text
Start captured; no motion was sent:
/home/yikun/ARES-R/worklog/pregrasp/cases/right_S1/start.json
```

若日后需要重建（例如重新摆位后旧的 `start.json` 已失效），脚本会报
`already exists`。届时不要强行覆盖，先归档：

```bash
cd /home/yikun/ARES-R
mv worklog/pregrasp/cases/right_S1/start.json \
   worklog/pregrasp/cases/right_S1/start.invalid-$(date +%Y%m%d-%H%M%S).json
```

然后重新执行 `pregrasp capture-start right_S1 right`。

检查起点不等于终点：

```bash
python3 - <<'PY'
import json
from pathlib import Path
s=json.loads(Path('worklog/pregrasp/cases/right_S1/start.json').read_text())
g=json.loads(Path('worklog/pregrasp/targets/PREGRASP_R.json').read_text())
print('start deg:', s['joint_position_deg'])
print('goal  deg:', g['joint_position_deg'])
print('max joint difference deg:', max(abs(a-b) for a,b in zip(s['joint_position_deg'],g['joint_position_deg'])))
PY
```

`max joint difference deg` 必须明显大于 0。

## 七、S1 规划与检查（已完成）

本节已执行完毕，三种 profile 均生成轨迹：

```text
pregrasp plan right_S1 current
pregrasp plan right_S1 seeds4
pregrasp plan right_S1 cuda-graph
```

产物目录（可直接用于 `preview` 与 `run`）：

```text
current     logs/pregrasp_20260914_right_S1_20260914_160702_6bfaaf2c
seeds4      logs/pregrasp_20260914_right_S1_20260914_160736_bcf8448f
cuda-graph  logs/pregrasp_20260914_right_S1_20260914_160740_b26ea939
```

结果：

| profile | RED | AMBER | OK | min_sigma_min | max_cond | 软限位余量 | 模型净空 | 中心面余量 | plan_cspace |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| current | 0 | 215 | 666 | 0.032782 | 63.04 | 0.2606 rad | 0.09285 m | 0.09852 m | 2242.9 ms |
| seeds4 | 0 | 215 | 666 | 0.032782 | 63.04 | 0.2606 rad | 0.09285 m | 0.09852 m | 2318.2 ms |
| cuda-graph | 0 | 215 | 666 | 0.032782 | 63.04 | 0.2606 rad | 0.09285 m | 0.09852 m | 1825.6 ms |

三个 profile 的奇异性与几何指标**完全一致**，只有耗时不同。这是预期的：起终点固定时，
seed 数量与 CUDA Graph 只改变搜索方式，不改变最优几何路径。

### 判断项逐条结论

1. `case_id = right_S1` ✓
2. 起点与刚采集的 S1 一致，终点与 PREGRASP_R 一致 ✓
3. **J3、J5 均未跨过 0°** ✓

   ```text
   J3  -106.473° → -51.015°   （全为负）
   J5   -52.452° →  -9.909°   （全为负）
   ```

4. **无绕行、无折返、无腕部翻转** ✓ 关节空间总变程 301.2° 等于净变程 301.2°
   （绕行比 1.00，即每个关节单调）。作为对照，S0 也是 1.00，但它的 J3/J5 跨零。
5. 净空与余量均为正且充裕 ✓ 中心面余量 0.09852 m、模型净空 0.09285 m。
6. 无 RED ✓，无需调整起点或 IK 分支。

### 一个需要注意的指标口径问题

全路径汇总的 `min_sigma_min` / `max_cond` / `min_abs_sin_j5` **由共同终点决定**，不能用来区分 S1 与 S4：
三者的最差样本都在 idx 836 / 881，其关节向量与 PREGRASP_R 终点仅差 `1.68e-07 rad`，
即就是终点构型本身（终点比较接近腕部奇异：J5 仅 −9.909°，`|sin J5| = 0.172`，
按 §6 属 AMBER 级，未到 RED）。

因为 S1/S4 共用同一个预抓取终点，所以两者的汇总指标必然相同（均为 0 RED / 215-220 AMBER / 0.032782 / 63.04）。
**真正能区分两条路径的是起点段与中段**（见第三节对照表），以及 AMBER 数量
（S1 = 215，S4 = 220，差额全部来自接近终点段）。

基线几何合理，并且已完成另外两个 profile。

只比较规划耗时不能代替轨迹检查。优先选择路径连续、奇异样本少且净空正常的轨迹。

## 八、S4 目标位置与采集（已完成）

### S4 起点（已实测到达并捕获）

同样已经实机验证并已执行 `pregrasp capture-start right_S4 right`。
**不要重复捕获**。

BODY 增量相对预抓取终点：

```text
[-0.050, -0.200, +0.050] m
```

对应 BODY 绝对坐标：

```text
[0.649683, -0.392630, 1.118212,
 1.645710,  0.025381, 1.519950]
```

右臂控制器 TCP 平移目标/实测：

```text
目标参考: [323.188, -595.600, -81.798] mm
实际实测: [323.185, -595.605, -81.788] mm
```

控制器 TCP 旋转实际值（与 S1 接近，各分量差异 < 0.001 rad）：

```text
[1.645710, 0.025381, 0.734552] rad
```

**为什么不是文档早先写的 `[287.833, -489.534, -81.798]`**：那个点对应 BODY 增量
`[-0.15, -0.15, +0.05]`，同样不可达（IK 姿态误差 7.89°）。

### S4 规划（已完成）

规划已完成：

```text
pregrasp plan right_S4 current
pregrasp plan right_S4 seeds4
pregrasp plan right_S4 cuda-graph
```

产物目录：

```text
current     logs/pregrasp_20260914_right_S4_20260914_162500_a8faa24d
seeds4      logs/pregrasp_20260914_right_S4_20260914_162505_4255cfed
cuda-graph  logs/pregrasp_20260914_right_S4_20260914_162456_8114d42c
```

结果（三种 profile 指标一致）：

| profile | RED | AMBER | OK | min_sigma_min | max_cond | 软限位余量 | 模型净空 | 中心面余量 | plan_cspace |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| current | 0 | 220 | 661 | 0.032782 | 63.04 | 0.3558 rad | 0.09285 m | 0.10960 m | 2272.0 ms |
| seeds4 | 0 | 220 | 661 | 0.032782 | 63.04 | 0.3558 rad | 0.09285 m | 0.10960 m | 2277.8 ms |
| cuda-graph | 0 | 220 | 661 | 0.032782 | 63.04 | 0.3558 rad | 0.09285 m | 0.10960 m | 1802.1 ms |

判断项：`case_id = right_S4` ✓；**J3（−92.034° → −51.015°）、J5（−52.002° → −9.909°）均未跨过 0°** ✓；
关节空间绕行比 1.00（完全单调，无折返）✓；无 RED ✓。

S4 相对 S1 的可见差异：软限位余量更大（0.3558 vs 0.2606 rad）
且中心面余量更大（0.10960 vs 0.09852 m），即 S4 起点离限位与中央禁区都更远；
但起点段奇异性略差（0.194006 vs 0.215055）。两者都是健康路径。

## 九、实机执行

当前只允许右臂进入 `pregrasp run`。左臂轨迹保持 planning-only。

执行前再次确认：

- case ID 正确；
- 实际起点没有变化；
- Tool ID 仍为 2；
- 夹爪空载；
- 左臂静止并物理隔离；
- 右臂完整扫掠区域净空；
- 急停可触及；
- preview 不存在明显腕部翻转或 J3/J5 过零。

不要使用：

```text
pregrasp run last
```

使用经过检查的明确目录（以下六个均可，推荐先用 `current`）：

```text
right_S1 current     /home/yikun/ARES-R/logs/pregrasp_20260914_right_S1_20260914_160702_6bfaaf2c
right_S1 seeds4      /home/yikun/ARES-R/logs/pregrasp_20260914_right_S1_20260914_160736_bcf8448f
right_S1 cuda-graph  /home/yikun/ARES-R/logs/pregrasp_20260914_right_S1_20260914_160740_b26ea939
right_S4 current     /home/yikun/ARES-R/logs/pregrasp_20260914_right_S4_20260914_162500_a8faa24d
right_S4 seeds4      /home/yikun/ARES-R/logs/pregrasp_20260914_right_S4_20260914_162505_4255cfed
right_S4 cuda-graph  /home/yikun/ARES-R/logs/pregrasp_20260914_right_S4_20260914_162456_8114d42c
```

例如执行 S1 的基线 profile：

```text
pregrasp run /home/yikun/ARES-R/logs/pregrasp_20260914_right_S1_20260914_160702_6bfaaf2c
```

### 执行前预计的时长与门限

`pregrasp run` 会在写入原生文件前使用**站点上限、发送器上限与跟随误差推算上限中更严者**重新参数化时间轴：

| 项目 | right_S1 | right_S4 |
| --- | --- | --- |
| 原生采样点数 | 1480 | 1448 |
| 采样周期 | 80 ms（发送器硬要求） | 80 ms |
| **预计执行时长** | **约 118.3 s** | **约 115.8 s** |
| peakV / 生效上限 | 0.02181 / 0.02182 rad/s（1.25 °/s） | 0.02181 / 0.02182 rad/s |
| peakA / 上限 | 0.0092 / 0.2 rad/s² | 0.0085 / 0.2 rad/s² |
| 预测跟随门值 / 0.2° | 0.1500（余量 25%） | 0.1499（余量 25%） |
| 单关节最大行程 | 98.6° / 150° | 96.3° / 150° |

**现场请按约 2 分钟预留时间**，并确认控制器不会因此触发看门狗或超时。
先前按 3.0 °/s 速度上限算出约 49 s，那个版本会被发送器的跟随误差门在运动中途中止（2026-09-14 已实际发生）。

这两个文件已经用真实二进制（`/home/yikun/ares-r-curobo-assets/jaka_right_demo`）直接验证过：
利用 `load()` 在 `login_in()` **之前**执行、失败即退出的特性，把轨迹复制一份并在尾部
多追加一个 token，发送器返回 `trailing data`——说明头部、时间戳、元数据、关节限位、行程、
速度、加速度、端点加速度**全部通过**，且全程 `try to connect` 计数为 0（未接触控制器）。
负对照（把点抽稀 6 倍）返回 `velocity/acceleration cap`，证明校验不是空转。

屏幕应要求输入：

```text
RUN PREGRASP right_S1
```

确认 case ID 后再输入。执行期间观察：

- planned/actual joints；
- tracking error；
- BODY TCP；
- deadline lag；
- collision/limit/protective stop；
- ServoJ 退出状态。

异常时使用物理急停；普通中止可按 `Ctrl+C`。禁止同时启动另一个控制程序。

结束后立即读取：

```text
jaka joints right
world view
```

检查原生日志是否同时包含：

```text
target_reached
servo_disabled code=0
logout code=0
```

未同时出现时不得判定执行成功。

## 十、下午最短任务清单

```text
[x] 确认没有第二个硬件 ART
[x] 创建并检查 right_S1/manifest.json
[x] 创建并检查 right_S4/manifest.json
[x] 移动到真实 S1（已更正为可达坐标）
[x] capture-start right_S1 right
[x] plan right_S1 current / seeds4 / cuda-graph
[x] 确认 S1 的 J3、J5 不跨零且绕行比为 1.00
[x] 移动到真实 S4（已更正为可达坐标）
[x] capture-start right_S4 right
[x] plan right_S4 current / seeds4 / cuda-graph
[x] 确认 S4 的 J3、J5 不跨零且绕行比为 1.00
[x] 修复原生发送器速度/加速度包络不匹配
[x] 用真实二进制验证 S1/S4 轨迹文件可通过发送器门限
[x] 修复伺服跟随误差门限未建模（2026-09-14 首次执行中途中止的根因）
[x] 重启 ART 以恢复被释放的右臂（失败后右臂会变为 DISABLED）
[ ] 选择一条明确目录进行首次右臂受监督执行（约 2 分钟）
[ ] 执行期间监控 tracking error / deadline lag / BODY TCP
[ ] 读取终点 joints/TCP
[ ] 核实 native 日志同时包含 target_reached / servo_disabled code=0 / logout code=0
[ ] 保存日志路径和控制器报警情况
```

## 十一、常见报错

### `case manifest not found`

原因：对应 case 目录缺少 `manifest.json`。按照第五节创建，不需要修改 cuRobo。

### `already exists`

原因：捕获文件采用禁止覆盖策略。按照第六节先归档旧文件，再重新捕获。

### `start and goal are identical`

原因：机械臂未离开预抓取终点就执行了 `capture-start`。移动到真实 S1/S4 后重新捕获。

### `start mismatch`

原因：实际机械臂已经偏离轨迹起点。禁止继续确认，从当前实际姿态重新捕获并规划。

### `planning failed`

保留 planner log，先检查起终点、模型碰撞、中心禁区、软限位和奇异构型。禁止用直线插值或 MoveJ 替代失败的 cuRobo 路径。

### 大量 RED

先检查 J3、J5 是否跨过 0°。若存在跨零，改变起点或选择与终点同一侧的 IK 分支。CUDA Graph 不解决构型奇异问题。

### `tracking error`

**这是运动过程中发生的中止**（不是 `load()` 阶段），发送器已停止伺服并退出，机械臂停在原地——
`abort` / `servo_disabled` / `logout` 仍会返回 code 0，所以日志看起来"正常结束"，但**不会**出现 `target_reached`。

原因：实测关节与**上一拍目标**相差超过 0.2°。这个残差正比于命令速度，
所以文件级的速度/加速度校验**看不到**它。2026-09-14 right_S1 就是这样在
第 100 拍（约 8 s、1.73 °/s）中止的，机械臂只走了 3.9°。

处置：**不要重试同一条轨迹**。确认包络是否已包含跟随误差上限（现在已包含，速度上限 1.25 °/s）。
若在新版本下仍出现，说明该构型的跟随比值超出保守值 0.12 s，需要重新拍摄标定而不是继续降速试。

### `servo_j` / 控制器报警

若控制器面板出现报警，先按急停、记录报警码，再重启 ART。不要在同一会话里继续执行第二条轨迹。

### `symbol lookup error`

表示 JAKA SDK 动态库混用。退出 ART 并记录完整错误，不运行旧脚本继续。

### `velocity/acceleration cap` 或 `excursion cap` 或 `duration cap`

发送器在 `load()` 阶段拒绝了轨迹。这是**规划/发送器包络不匹配**，不是机械臂故障，也不会造成运动——
`load()` 在连接控制器之前执行。可能原因：站点速度上限（0.10 rad/s）比发送器（0.05236 rad/s）宽，
如果旧版本生成了原生文件就会超出。现在已改为取二者更严者并在写文件前闭环校验；
若仍出现，说明包络或上限被改过，需要重新检查幂等常数而不是直接实机重试。

### `cannot fit this path inside the native sender velocity/acceleration envelope`

路径在允许时长（240 s）内无法降到发送器速度/加速度以下。属于预期的**规划侧**拒绝，
发生在操作员输入确认短语之前。需要缩短行程或改变起点，不要直接重试。

### `right status port occupied` / `right lock occupied`

右臂已有另一个读取者。检查 `pgrep -af "python.*ares_r.cli"`，确认只有一个硬件 ART。
另注意：现在 ARES-R 自身的控制连接（如 `exclusive_right` 关闭 SDK 后残留的半关闭套接字）
不会再被误认为竞争读取者，此类报错若出现则是真的有第二个进程。

## 十二、收尾记录

记录以下内容：

```text
S1 实际起点 joints/TCP
S4 实际起点 joints/TCP
PREGRASP_R joints/TCP
三种 profile 的规划时间
RED/AMBER/OK 数量
最小模型净空
最小中心面余量
实机执行目录
native_execution 日志
终点误差
控制器报警码
机器人最终姿态
```

保留所有失败目录和日志。禁止使用后一次成功覆盖前一次失败。
