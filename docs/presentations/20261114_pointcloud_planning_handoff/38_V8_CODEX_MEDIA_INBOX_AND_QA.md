# V8 Codex实施令＋视频素材投递规范＋交付质检

这是**可直接交给本机Codex执行的工作令**，无需再请用户逐页解释。务必先读34→35→36→37，再执行本文件。

## 1. 先解决文件定位，明确只需用户提供少量真人实拍

在本地ACES-R/ARES-R仓库根目录建立未纳入版本控制的私人素材区：

\`\`\`bash
cd "$(git rev-parse --show-toplevel)"
mkdir -p .local/acceptance_v8/{source_ppts,source_notes,user_media,charts,render,review}
printf '\\n.local/acceptance_v8/\\n' >> .git/info/exclude
\`\`\`

**绝对不要把原视频、未公开现场图、录音、用户原PPT、公司真实信息数据或机器IP/账号导出文件提交到公共GitHub。** 仅审核后将本任务书和适合公开的算法证据摘要推送。

Codex寻找原件：
1. **首选本次任务包里的** \`source_ppts/ARES-R_V7.1.pptx\` 和 \`source_notes/week12-1.md\`、\`week12-2.md\`、\`week12-3.md\`；若没有再在授权的用户Downloads/Documents查找；
2. 当前repo V7阶段资料位于\`docs/presentations/20261114_pointcloud_planning_handoff/29–33\`；这不是V7.1完整母件，**不能用Markdown重画一个新模板**；
3. 找到原始20261028大PPT则优先从zip/OOXML媒体提取；找不到则使用V7.1已嵌入真图和repo\`docs/presentations/assets/20261028_rasc_curobo/\`。
4. 最新Week12源本地工作树可能在\`ARES-R-ros1-return-center-20261112\`，位置由用户授权或已挂载文件提供；不能自动SSH现场\`.32\`机器人来补图或执行运动。
5. 远端参考\`codex/ros1-business-blocks-offline-20261113\` HEAD \`edba1bb139\`，\`codex/aa0f0-b-v15-performance-20261119\` HEAD \`f5fc8c15ba\`；后续本机未推送证据要审计，不得说远端已全部包含。

## 2. 用户真正需要手动提供的媒体：4项优先，其他可选

把文件放到\`<ARES-R根目录>/.local/acceptance_v8/user_media/\`。**不用重命名视频内部内容，只需要按下列文件名存一份副本**。可以MP4/MOV；如果原视频带声音请保留，但PPT中默认静音播放，除非用户授权。

| 优先级 | 文件名 | 该视频须包含的内容 | V8使用页 |
|---|---|---|---|
| **必备优先** | \`V8_SITE_01_WORKCELLS_OVERVIEW.mp4\` | 新现场各工位相对位置、机器人/天平/烘干箱/专机，镜头稳定 | 01、17 |
| **必备优先** | \`V8_BLOCK_01_AA0F0_FETCH_HOLD.mp4\` | 天平料盘ID1抓取、抬升、持稳；尽量能看到最终成功/末态 | 21 |
| **必备优先** | \`V8_BLOCK_02_AA0P0_PLACE_CENTER.mp4\` | 天平料盘从持物开始、让位/预放置、下降、松爪、退出、回center | 22 |
| **必备优先** | \`V8_BLOCK_03_AC0F0-02_SIEVE_CYCLE_ID10.mp4\` | 筛网新ID10抓取、230mm抬升、原位放回、复位完整流程 | 23 |
| 可选 | \`V8_BLOCK_04_DEMO02_ROS_DUAL_CENTER.mp4\` | 双臂ROS Demo02真实两段运动，尽量同镜头看双臂 | 24 |
| 可选 | \`V8_SITE_02_DRYER_SIX_BERTHS.mp4\` | 烘干箱六泊位以及机械臂与箱口相对位置，无需逐位执行 | 17、19 |
| 可选 | \`V8_UI_01_CAPABILITY_WALL.png\` | 8765功能墙大卡、原生/ROS、交付/开发切换状态 | 18、19 |
| 可选 | \`V8_UI_02_BLOCK_RUNNING.png\` | AA0F0或AA0P0运行监控页面，能看见阶段和结果；屏蔽隐私 | 21、22 |
| 可选 | \`V8_UI_03_TCP3_ID10.png\` | TCP3或Epic ID10检测实际界面/参数截图（不是新编的） | 20 |

**如果视频内容是其他日期/版本**，在旁边提供\`V8_MEDIA_NOTES.csv\`注明\`filename,recorded_date,block_id,run_id,source_stage,notes\`；没有run ID可以留空，Codex须标“现场演示画面（与某次日志非一一对应）”，不能贴同一时刻假时间码。

**这4个优先视频不是制作任务书的前置条件**。Codex先用已有原始run和历史真图做19旧页的图表及本周16–25的状态图；视频到位后再按正确源覆盖预留的媒体位置。若缺少视频，PPT保留清楚的\`[现场视频待插入：文件名]\`编辑占位（不要假造视频画面）。

### 用户最低工作量
只要拷贝这4个视频即可。**不需要用户重新生成点云、cuRobo路径、控制曲线、DBSCAN实验表或手写网页截图**；这些都由Codex在本机真实数据与repo代码中提取/重绘。功能墙截图Codex优先从本地离线UI/已有截图提取，无权连接实时设备时使用用户可选PNG。

## 3. 本地源输入保全

Codex执行：
- 复制母件到受控私有目录，生成SHA256和基础统计（19页，BBMG母版，形状、notes、媒体rel）；
- 复制周总结只作为“摘要线索”，原始run仍是结果主依据；
- 在已授权本地工作树完成\`git status -sb\`、\`git log -12 --oneline\`、\`git branch\`，**不执行修改生产分支或stash/reset任何现有工作**；
- 建立\`EVIDENCE_PRIORITY.md\`明确原始run（终态/时间/控制器读回）> 同运行原始日志 > 已提交技术报告 > 周总结 > 陈述性描述；
- 不允许为了打开页面自动运行生产后端、发JAKA/Epic/AMR命令。不允许改限位、模型安全边界来制造“成功”。

## 4. 优先从本地真实程序与数据生成的图

**可自动完成的内容（不要推给用户）：**
1. V7.1的历史同源点云/建模结果，真正裁剪可视ROI和坐标一致对照；见35号FIG-02—07；
2. P3.3\P3.4\P3.8E的真实JSON图表，见35号FIG-09—16；
3. 11/16–20 demo Console / ROS /功能块原始\`run_id\`→阶段→时间/结果CSV，按36号实测证据生成验收矩阵；
4. 最新功能墙\`src/ares_r/webui/demo_console.html\`＋\`demo_wall.js\`及\`docs/demo-handbook/catalog.json\`：如果无本地离线可显示版本就从已有UI原图/上次周报提取，不能私自连接现场系统；
5. \`AA0F0-B V1.4\`、\`AA0P0 V1.2\`、\`AC0F0-02\`源事件图；没有现场视频时先做真实阶段状态条；
6. \`V1.5\`和ROS Demo02并行模型：真实commit/阶段日志，只有同源事件才画Gantt；
7. 单次冻结GPU首请求10.302s vs同场景热请求3.805–3.901s图，明确solve子时间和任务边界；
8. 新TCP3/ID10适配的真实运行截图或代码差异（若仅有错误文本，画规范故障表不模拟网页）。

来源目录：
\`docs/presentations/assets/20261028_rasc_curobo/\`、
\`docs/reports/\`、
\`docs/integration/\`、
\`docs/function-validation/records/\`、
\`docs/demo-handbook/\`、
\`worklog/evidence/\`、
\`release/ros1-business-blocks/\`。
所有截图与表格应附源码版本/录入日期/原run。

## 5. 视频提取/投影方式

- Codex使用\`ffprobe\`提取视频长宽/帧率/真实时长，先建立\`video_inventory.csv\`；
- 在实际动作阶段边界选关键帧（每条4–6帧），不要机械等间隔抽样；可用ffmpeg视频帧与PPT原生阶段条；
- 截图尽可能保留完整机械臂、夹爪、目标工位；放大细节时保留一张全景作参照；
- 可放一个视频占位缩略图和本地相对文件名供用户后续嵌入；如果直接嵌入，检查PPT链接是否断开、文件大小和离线播放；
- 同一视频可复用于不同技术页作局部，但不能算多次独立试验；
- 没有可匹配run的照片，标明“现场实拍示意”，不制作假同步多机位；
- 视频不替代真日志：实际成功/耗时一定从源run取。

## 6. Codex执行顺序（有依赖但不因缺个别材料停工）

### Phase A：现状审计
- 解包V7.1，逐页记录原形状/公式/notes/照片，复现19页预览；
- 对照35号FIG，按任务阶段决定哪些数值和图要重画；
- 找到每张源图真实输入，建立\`figure_source_contract.csv\`；
- 根据36号处理week12-1/2/3与本地run冲突，输出\`week12_status_reconciliation.csv\`。

### Phase B：先做可核验图表，再摆PPT
- 对25项FIG逐一输出单独PNG/SVG、数据CSV、绘图脚本、可编辑图表；
- 先检查图像本身是否能看清差异、状态、阈值和单位，再放进模板；
- 对缺原始数据的图有界回退：可画历史表/控制器回执而不补伪曲线；
- 从历史图截取可见局部，不用整页截图；
- 特别优先旧V7.1页11、12、13、19：**原件这些页图片数0，必须真正做对照图。**

### Phase C：增量编辑V8结构
按37号25页严格执行，V7.1 → V8映射明确：
\`01→01,02→02,...,07→07,08+09→08,10→09,11→10,12→11,13→12,14→13,15+16→14,17+18→15,19→16,新页17–25\`。
只编辑内容、图片和组合元素位置，保留原BBMG模板、Logo、红线、页脚及黑体/Arial；不能为了填字把字号逐页缩小。标题不用疑问句。模板中的原生边框、线条可复制、重新组合，但禁止外来重做的整张系统框图替代模板。
每页图表必须能够让领导判断指标“改善/受限/权衡/未验收”。

### Phase D：QA至少两轮
**技术QA**：
- 每个值的source SHA和数据合同、单位、好坏方向、同源可比性正确；
- 历史planning-only与现场物理、旧/新TCP/ID、原生/ROS、源版本/正式别名区分；
- 强制抽查V8页03、05、06、07、09、10、11、12、16、19、21–25；
- 识别\`30目录\`≠\`30验证\`、\`ROS已部署\`≠\`ROS实机\`、\`HOLD后拆分\`≠\`新入口独立实机\`；
- 遗留故障如ID8 BrokenPipe不准删去；
- 不把不同任务用时算速度提升，不把旧工具预热失配22.986s当matched baseline；
- 用户录音与旧V7任务书要求充分体现工程调试、参数试验和现场工作量。

**视觉QA**：
- 实际渲染PPT和PDF生成第一页到最后一页的PNG与contact sheet；
- 在普通100%和缩略25%两档检查图例、坐标、文字及视觉对比，至少两轮；
- 将页面所有正文文字遮住做“只看图5秒测试”，仍能看出哪个方案更好/是否未达标；
- 每页阶段定位条能看出属于哪个任务环节；
- 本周至少3个实拍流程能用真实关键帧讲完整动作，功能墙状态可看清；
- 各自输出\`technical_review_round1.md\`、\`visual_review_round1.md\`、\`revisions.md\`、\`technical_review_round2.md\`、\`visual_review_round2.md\`。

## 7. 交付目录（本地私有、不自动push原始二进制）

\`\`\`text
output/acceptance_v8/
  ARES-R_甲方研发工作量汇报_V8_量化对照与现场功能块.pptx
  ARES-R_甲方研发工作量汇报_V8_量化对照与现场功能块.pdf
  preview/slide-01.png ... slide-25.png
  preview/contact_sheet.png
  figures/<25位编号的子图>.png|.svg
  figures/data/*.csv
  figures/scripts/*.py
  video_keyframes/<video_name>/
  source_manifest.csv
  evidence_registry.csv
  week12_status_reconciliation.csv
  slide_claims_and_source.csv
  video_inventory.csv
  speaker_notes.md
  qa/
    technical_review_round1.md
    visual_review_round1.md
    revisions.md
    technical_review_round2.md
    visual_review_round2.md
    customer_requirement_checklist.md
    missing_assets_and_fallbacks.md
\`\`\`

## 8. 对Codex的正式复制指令

> 同步并切换到ARES-R分支 \`docs/acceptance-v8-visual-site-functions-20261122\`，从同目录34号任务书开始，按34→35→36→37→38阅读。使用用户提供的\`ARES-R_V7.1.pptx\`为母件，不覆盖它，制作25页V8研发工作量PPT。第一项修改要在真实图和可编辑数值表里直接看清“同源对照、谁好谁坏、改善多少、处在任务哪个环节”，不能靠增加文字；第二项修改要用11/16–20现场原始run、版本和功能控制台资产，新增多工位适配、功能块定义与独立取/放/筛网/ROS验证的9页。本地找不到某份现场视频时，先按本任务书保留明确命名的占位并完成其他图表，不自行编造画面或历史数字。除用户主动投递的4条优先视频外，大多数历史图表、网页、任务日志和源代码应由你在本机已有repo及归档数据中自己提取处理。保留BBMG模板和黑体/Arial，完成技术与视觉两轮QA，交付PPTX/PDF/25页预览、每图生成代码/数据、speaker notes及来源台账。不连接真实机器人、不更改运动安全限制、不向公开GitHub上传私有原始文件。
