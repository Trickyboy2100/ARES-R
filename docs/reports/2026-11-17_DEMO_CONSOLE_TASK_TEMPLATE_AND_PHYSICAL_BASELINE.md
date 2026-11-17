# Demo Console任务与5700模板：以现场原生Demo为基线

2026-11-17，读取现场RC1分派源码、11份参数、10个Demo证据目录的近期JSON记录和最近80个Console运行目录。仅只读梳理，未扫描相机、未执行运动、未修改生产分派或ROS发布门。采集范围有界，未找到证据不等于历史从未执行过。

## 统一判断原则

1. 现场原生Demo及同事最近实机结果是业务基线，ROS只是后续适配层。不能因为旧ROS registry的physical_start_enabled=false，就否认legacy Demo的真实成功。
2. 分别登记：任务类型、实际5700命令、参数版本、单段成功/完整成功、当前版本绑定、ROS封装/联调/交付；不能用一个Golden/Candidate标签代替所有维度。
3. 已完成的真实运行应保留为可复用基线。缺运行时参数hash时，补证据归属或复用当时参数快照；不擅自把所有历史工作重新判为未验收，也不把旧成功泛化到任意新偏置。
4. 文件mtime不是完整绑定证据；本轮已取当前参数SHA，但补取各运行参数快照/mtime的网络连接失败，因此不把当前文件SHA冒充历史运行SHA。
5. Console直接启动既有脚本/API，不会因为卡片带ROS标签就自动经过ROS Action。ROS demo00/01卡片和ROS客户端复用执行器，但实际调用路径应单独标明。

## 当前任务总表

| Console alias | 任务 | 5700实际配置 | 当前几何（BODY） | 实机证据结论 |
|---|---|---|---|---|
| demo-0-return-center | 辅助：回center | 无5700；只做场景采集 | — | 2026-11-17 09:22 AT_CENTER |
| demo-4-main-siftgrasp-dmpplace | 复合：筛网取→转场→DMP放 | 意图 ID6→ID2；当前Console分派有缺口 | 放置偏置[-20,-445,+100]mm，下降60mm | 未找到本组合完整成功；现有Console可能误走料盘roundtrip |
| demo-5-main-dmpplace | 放：筛网→除尘收料机 | ID2；320,2,2,1,1,0 | 预放[-23,-410,+100]mm；下降60mm；退出40mm | 2026-11-09 PLACE_CENTER_COMPLETE |
| demo-6-liaopan-placetoDMP | 放：料盘→除尘收料机 | ID2；320,2,2,1,1,0 | 当前预放[0,+5,+20]mm；下降20mm；退出40mm | 2026-11-09 PLACE_CENTER_COMPLETE；不能用该旧结果冻结当前V7几何 |
| demo-2-liaopan-placeto-hongganxiang | 放：料盘→烘干箱下层中 | ID3；320,2,3,1,1,0 | 当前预放[+70,-315,+303]mm；下降30mm；退出40mm | 2026-11-11 PLACE_CENTER_COMPLETE |
| demo-1-liaopan-placeto-cheng | 放：料盘→称/程工位（现场名称待统一） | ID9；320,2,9,1,1,0 | 预放[0,0,+60]mm；下降60mm；退出40mm | 2026-11-13只见PLANNED_ONLY，不能算完整实机成功 |
| demo-3-branch-sift-graspreset | 取后原位放回：筛网 | ID6；320,2,6,1,1,0 | 按shaiwang params/source_parameters；抬升230mm | 2026-11-06 PICK_LIFT_REPLACE_RESET_COMPLETE，116.15秒执行 |
| demo-1-main-grasphold | 取：料盘并持稳 | ID1；320,2,1,1,1,0 | 旧first_pick执行包；抬升100mm | 保留历史Golden；本轮有限近期目录未找到新完整结果 |
| demo-2-main-graspplace | 复合：料盘取→转场→烘干箱放→返回 | 取ID1；放ID3 | 读取roundtrip参数、站位/路线及泊位偏置；当前下降50mm | 历史接续完成保留；当前参数下近期完整成功证据不足 |
| demo-2-branch-grasprptspdup | 取后原位放回：料盘提速版 | ID1；320,2,1,1,1,0 | 当前运行使用roundtrip parameters，与source_parameters快照对应；抬升230mm | 11-13最近实机停在RESET_CENTER；不是新的完整成功 |
| demo-7-shaiwang-placeto-cheng | 放：筛网→秤 | ID8；320,2,8,1,1,0 | 预放[0,0,+100]mm；下降100mm；退出40mm | 2026-11-13 PLACE_CENTER_COMPLETE；应更新过时的待验收文案 |

偏置为相对检测返回点的BODY平移，单位mm；是读取到的生效参数，不是本轮修改。上述5700 ID为程序实际请求的抓取配置编号，不等于已独立验收厂家UI内名称。无模板任务不应为了统一而强行触发5700。

## 现场已证明的放置结果

以下4项均有result=PLACE_CENTER_COMPLETE、place=PLACED_AND_RELEASED、center=AT_CENTER；不能继续笼统写“完全没有实机验证”。这仍不自动构成其新ROS wrapper的端到端实机验收。

- `right_arm_dmp_place_v1`：`worklog/evidence/demo-runs/right_arm_dmp_place_v1/run_1794204348793064700/result.json`。
- `right_arm_liaopan_dmp_place_v1`：`worklog/evidence/demo-runs/right_arm_liaopan_dmp_place_v1/run_1794216841515922914/result.json`。
- `right_arm_liaopan_hongganxiang_place`：`worklog/evidence/demo-runs/right_arm_liaopan_hongganxiang_place/run_1794383252441911735/result.json`。
- `right_arm_shaiwang_cheng_place_v1`：`worklog/evidence/demo-runs/right_arm_shaiwang_cheng_place_v1/run_1794554796221507249/result.json`。

料盘ID9只找到PLANNED_ONLY；料盘ID1提速原位抓放最近记录为RESET_CENTER故障。早期成功和近期失败应并列，不用最新失败抹掉历史，也不把到预放置点/规划成功当完整放置成功。

## 5700字段的实际含义与覆盖顺序

- 放置检测函数：`scripts/run_dmp_place_demo.py:1475 detect_place_target()`。
- `1483`取system.json中的profile作为模板；`1484–1489`覆盖space_id / object_id / camera_id并重新构造`320,space,config,camera,1,0`。
- 因此阶段名称epic_profile=right_pick并不意味着执行取料；参数epic_grasp_config_id=2/8才决定最终ID2/8。业务取放由执行器动作及末状态决定，不能从profile名字判断。
- 当前这些右臂命令均space=2、camera=1。ID1=当前料盘抓取请求，ID6=筛网抓取请求，ID2=两种DMP放置请求，ID3=料盘烘干箱参考点请求，ID8=筛网秤放置，ID9=料盘称/程放置。共享ID2对不同对象的适用性只以对应实机与当前模板配置为准。
- 曾用过的ID4/ID7不应从聊天历史直接写回当前Demo；当前程序并未使用它们作为这些卡片的生效配置。

## 必须处理的Console逻辑问题

### 未识别strategy误入另一个任务

现场`src/ares_r/demos/console.py:177 _run()`显式处理pick_reset / return_center / sift_pick_reset / dmp_place / first_pick，剩余情况进入通用else，调用料盘roundtrip_start。当前目录含strategy=sift_dmp_roundtrip，但所读base Console没有对应分支。它可能触发ID1→ID3的料盘全链，而不是标题所说ID6→ID2筛网全链。

这是源码分派缺陷；本轮未通过实机尝试验证，也未修改正式运行链。应改成明确的`elif strategy == 'roundtrip'`与未知strategy拒绝，再单独对接筛网全链；不能凭卡片标题标成已正确接线。现场overlay可扩展其他策略，如ROS Demo02，但不能假设它修复了这个base分支。

### 卡片文字和当前参数不一致

- ID2料盘DMP当前V7为预放z+20mm、下降20mm，标题仍含10mm。
- ID8筛网秤放置已有11-13完整成功，卡片仍保留初次失败和“修复后未复跑”的旧结论。
- 筛网原位抓放真实执行目录是right_arm_shaiwang_pick_reset_v1，卡片demo_id为right_arm_sift_pick_lift_replace_reset_v1；审计必须沿wrapper委派追踪，不能按目录名相似度判断没有记录。
- Golden和validation_level互相矛盾，例如料盘提速版仍为GOLDEN而当前参数注记待重验。应显示“历史Golden＋当前参数/最近运行结果”，避免一个标签覆盖事实。

### 放置偏置不是全部实时读Console泊位表

现有共用Place脚本直接读取各Demo parameters.json的preplace_offset_body_m；本轮源码中没有berth_reference或operations/state.json的引用。烘干箱当前[70,-315,303]mm来自参数中的BODY预放置偏置；berth_reference是说明性来源，不能据其存在宣称每轮都会读取新的泊位注册表。改变WebUI槽位偏置不保证自动影响这个legacy Demo。

### last-run覆盖最近成功证据

last-run.json可能被后一次PLANNED_ONLY覆盖，不能只看last-run判断“从未成功”；应分别维护last_attempt / last_full_physical_success / accepted_parameter_revision。本轮没有重写历史索引。

## ROS封装的批判性复用

- 保留已认可的ReturnCenter/CenterRestore Action及ABI，复用现有任务所有权、反馈、取消和结果回读。
- BusinessConsole的旧23项registry不是现场业务验收权威。P01/P02的ScanPick以持物结束，不能直接把“抓起再放回”的成功Demo当成它的ROS完整验收；但应直接复用已经成功的抓取/抬升执行段，不再复制一套规划算法。
- L01/L02/L03/L04对应legacy放置已存在不同程度实机证据；先用实际脚本与当时参数纠正旧wrapper，不能反过来用旧wrapper参数覆盖现场成功参数。L04本地适配有回放，现场Business registry仍落后。
- 原生Place启动时已持物，而新ROS ScanPlace引入payload_session；这属于接口合同差异，需要明确接入，不能让旧成功Demo突然因缺新字段失效。
- 本轮读取目录已变为13项，多出独立ROS Demo02候选，当前另有开发工作；不因它出现在目录就推断已完成双臂实机或Delivered。未修改该模块。

## 建议的Console卡片字段

名称 / 取、放、原位抓放、复合、辅助 / 对象 / 来源与目的工位 / 5700空间、配置ID、相机 / 末状态 / 底盘是否移动 / 参数版本 / 最近完整实机成功及证据 / 当前版本绑定 / ROS可调用性 / ROS交付状态。

按任务筛选与按ROS交付筛选分开。后续先校正metadata和未知strategy分派，再用既有实机执行器做薄ROS适配；本轮不创建新任务或新运动方案。

## 归档

- 结构化矩阵：`worklog/evidence/2026-11-17-demo-console-task-audit/demo-task-matrix.json`。
- 完整只读源码/参数/结果快照（Mac私有）：`/Users/andyee/Documents/ChatGPT/local/site-private-demo-console-truth-20261117`。
- 当前参数SHA、revision和证据路径均在矩阵中。未push。
