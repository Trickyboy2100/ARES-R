# 抓取功能与参数

## 共同流程

在指定工位静止 → 读取当前关节、TCP、工具与夹爪 → Epic匹配和新场景 → 检测坐标变换及任务偏置 → 预抓取规划 → 预开夹爪 → 接近目标 → 闭爪 → 延时回读和抓取验证 → 指定脱离/抬升 → 持稳结束。

新独立 Fetch 的末状态定义为 HOLD_CONFIRMED。原位抓放测试分支在持稳后继续下降、释放、退出和回center。提取独立 Fetch 时明确终止点，保留原先已验证的接近、闭合和抬升执行段。

自由空间复用现有 SceneAwareMotion/cuRobo；接触段沿用对应成功版本的动作和范围。每个新工位独立绑定目标、工具、物体、接触方向及退出通道。

## A0 料盘天平抓取 · AA0F0 / RA0F0

- 检测使用 space2 / config1 / camera1，`320,2,1,1,1,0`。
- 历史 `right_arm_epic_pick_lift_v1` 经 `scripts/run_first_pick_demo.py` 执行，抬升100mm后HOLD，归档为 AA0F0-03。
- 230mm原位抓放复用 `scripts/run_pick_reset_demo.py`，归档为 AA0F0-02。当前来源是 roundtrip 参数及 source_parameters 快照。
- 独立 AA0F0 选择经过绑定的 HOLD profile；100mm/230mm与面向下层烘干箱的交接高度分别登记，目录名称本身不改变既有执行高度。
- 近期当前参数版本为 `RIGHT_GRASP_PLACE_ROUNDTRIP_2026_11_09_V23_SITE020_NOCOMP_TOOL3_QSEEDS4_ANCHOR_ROLLED_BACK_SKIPFAST`。
- 11月13日原位抓放最新运行停在 RESET_CENTER。历史Golden仍保全，独立抓取段可按原始结果逐段复用，整体最新成功须另记。

## C0 筛网天平抓取 · AC0F0 / RC0F0

- 检测使用 space2 / config6 / camera1，`320,2,6,1,1,0`。
- Console旧别名 `demo-3-branch-sift-graspreset`；wrapper `scripts/run_sift_pick_reset_demo.py` 最终使用 `right_arm_shaiwang_pick_reset_v1`。
- 完整测试分支为抓取→抬升230mm→原位下降230mm→松爪→退出→全局center。
- 11月6日执行116.15s，结果 `PICK_LIFT_REPLACE_RESET_COMPLETE`。独立HOLD入口复用到抬升验证为止的步骤。
- 当前V12参数中目标平移偏置为[0,0,0]，姿态补偿为0；旧聊天里的−10°和毫米补偿不能直接重加。控制器工具已由现场重新定义，读取绑定工具版本。
- 夹爪延迟回读时刻[1.2,2.0,3.0]s；中心到位容差3mm/3°；任务水平容差4.5°。这些是该版本读数，其他Demo独立配置。
- 持物沿用 `DEMO_EXPOSED160_WIDTH100_REAR20_RETAINED_V2`。现场曾授权特定小突出物接触豁免；它属于该场景版本，迁移新工位时必须显式处理其适用范围。

## D1 / D2 专机抓取

| 功能 | 原生 / ROS | 可复用部分 | 新增绑定 |
|---|---|---|---|
| 取筛网 | AD1F0 / RD1F0 | C0筛网夹持、延时验证、持物记录 | 专机取料模板、接近方向、槽内脱离距离、持稳姿态 |
| 取料盘 | AD2F0 / RD2F0 | A0料盘抓取链 | 专机取料模板、对象姿态、脱离通道、持稳姿态 |

当前放置模板ID2只证明相关放置检测链可用。抓取ID与抓取姿态尚待读取或配置，不依据放置ID直接猜测。执行步骤为新鲜取料检测→预抓取→进入→闭合验证→脱离专机→持稳，槽内脱离轴以现场工装定义为准。

## 烘干箱六项抓取

| 原生 / ROS | 泊位 | 工位 | 待绑定的接触与脱离 |
|---|---|---|---|
| AB1F1 / RB1F1 | 上左 | B1 | 该槽取料TCP、进入深度、脱槽路径 |
| AB2F2 / RB2F2 | 上中 | B2 | 该槽取料TCP、进入深度、脱槽路径 |
| AB3F3 / RB3F3 | 上右 | B3 | 该槽取料TCP、进入深度、脱槽路径 |
| AB1F4 / RB1F4 | 下左 | B1 | 下层上方隔板净空、脱槽路径 |
| AB2F5 / RB2F5 | 下中 | B2 | 下层上方隔板净空、脱槽路径 |
| AB3F6 / RB3F6 | 下右 | B3 | 下层上方隔板净空、脱槽路径 |

共同步骤为检测烘干箱参考→解析指定泊位抓取TCP→前方预抓取→槽内接近→闭合验证→沿工装允许方向退出→到持稳位。槽内直接上抬230mm不能作为通用默认动作。各槽保留独立 `grasp_offset / approach_axis / approach_distance / withdraw_axis / withdraw_distance / hold_profile`。

当前六槽已有注册定义及目标解析接口，抓取模板、六份抓取偏置、物理脱离参数和逐槽验收仍需完成。放置目标与抓取TCP使用独立语义变换。

## 抓取输出与转移

Fetch输出应包含 object类型、payload_session、工具与夹持变换版本、实际末态TCP/关节、hold_profile、验证结果和证据路径。转场时使用明确的持物姿态与底盘路线，下一次Place根据当前物体和新检测建立目标。

参数原始路径、SHA和成功记录见[证据索引](08-evidence.md)。
