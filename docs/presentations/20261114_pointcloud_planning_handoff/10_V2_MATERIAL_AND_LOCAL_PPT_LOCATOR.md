# V2 原始PPT和可用素材定位：**准确已知** vs **本机待定位**

> 特别说明：截至2026-11-14，没有证据可核实下列参考PPT在用户Mac上的绝对路径。**不得编造 /Users/xxx/... 文件地址**。仓库仅存可读文字引用/原有RASC图集；原始PPT二进制不在本交接分支。

## 1. Codex首先必须找的原始参考PPT（按优先级）

| source_id | 精确候选文件名（macOS可存在(1)重复下载后缀） | 作用 | 仓库是否有原PPTX | 文本/需求已在repo |
|---|---|---|---|---|
| PPT-TEMPLATE | 生料和水泥的水分细度检验操作目标识别与控制算法研发内部验收20261030V0.95 - 机械臂.pptx | **必须继承的原母版、主题、Logo、页面比例、固定组件** | NO | references/01_TEMPLATE_TEXT_REFERENCE.md |
| PPT-METHOD | 20261028-水分细度目标识别与场景自适应规划控制-2.pptx | 9页方法版算法含notes、已有清晰方法框图 | NO | references/02_METHOD_TEXT_REFERENCE.md |
| PPT-LARGE | 20261028-水分细度目标识别与场景自适应规划控制.pptx | 40页左右的大版与末尾真实素材页，后部图片是优先提取对象 | NO | references/03_LARGE_TEXT_REFERENCE.md |
| PPT-HALF | 点云场景重建与机械臂规划_研发过程与工作量汇报_14加2页.pptx | 被否定的16页视觉半成品，**仅保留内容** | NO | 02_DRAFT_14_PLUS_2.md |

附加可读材料：Recording 154(1).txt（原14:57录音，不整份公开入库），2026-10-27会议事实纪要PDF（内部讨论记录）；只保留相关需求摘要见07_RECORDING_REQUIREMENTS.md。仓库为public，入库前自行确认原PPT是否包含不宜公开的公司/专利/个人信息。

### Mac上如何获取真实绝对路径（需由本机Codex执行，不可猜）

先用Finder/Spotlight查找4个完整文件名，再在本机终端运行以下精确查询。下面只是一段**命令**，不是已经找到的路径：

```bash
mdfind -name "生料和水泥的水分细度检验操作目标识别与控制算法研发内部验收20261030V0.95 - 机械臂"
mdfind -name "20261028-水分细度目标识别与场景自适应规划控制-2"
mdfind -name "20261028-水分细度目标识别与场景自适应规划控制"
mdfind -name "点云场景重建与机械臂规划_研发过程与工作量汇报_14加2页"
```

如Spotlight不索引下载目录，可限制在以下用户授权的常规文件夹查找：~/Downloads、~/Documents、~/Desktop、~/Library/Mobile Documents/com~apple~CloudDocs/。**不要递归搜索整台电脑、邮件、隐藏目录或无关个人数据**。

找到后用python或shasum核对实际大小、SHA256、slide count；将私有绝对路径写入本机的忽略文件（如 .local/acceptance_source_paths.json），**不要提交Mac个人绝对路径到public GitHub**。PPT素材不在仓库的事实，不能靠推测同名文件已入库解决。

## 2. 仓库中目前**真实存在**的素材根目录（相对repo）

`docs/presentations/assets/20261028_rasc_curobo/`：
- `index.html`：总素材入口，**不应直接整图缩到PPT**。
- `ASSET_MANIFEST.json`：逐图源ID、图组、参数、哈希、是否含实际观测的登记。
- `README.md` / `STATUS.md` / `INPUT_INDEX.md`：可用于判断图是否属于CAMERA Oct10或GRASP Oct21。
- `panels/rasc6/`：总图集六阶段同源帧，但视觉相对复杂，优先做清晰局部裁剪。
- `panels/geometry_ab/old_boxes_zoom.png` / `new_primitives_zoom.png` / `error_occupied_space_slice.png`：Oct10 CAMERA 32→235的同源对照。
- `clarity_v2/03_old_cutaway.png`、`04_new_cutaway.png`、`section_old_new_pair.png`：局部剖切比较，图注必须注明是剖切显示，不表示删除真实占据。
- `panels/planning/planning_old.png` / `planning_new.png` / `route_overlay.png`：Oct10 OLD/NEW GPU都成功，不是9/21 CURRENT_BASE对照。
- `panels/performance/latency_module_before_after.png`：历史CPU三个模块对照，10/21数据。
- `panels/performance/cpu_backend_comparison.png` / `contact_query_comparison.png`：后续同输入等价检查，测试定义和前项不同。
- `panels/attachments/`：历史PLACE持物错误/修正及恢复耗时。
- `grasp_v3/index.html` 与 `grasp_v3/panels/rasc6/`：Oct21 GRASP同源观测，19→405，不等于Oct10 CAMERA 32→235。
- `panels/servo/`：两条真实ServoJ ABORT诊断曲线；**不能当成功实机轨迹**。

原有本地证据工具位于`tools/presentation_evidence/`，离线执行必须先阅读工具README和输入许可；不得自动访问实验室设备。

## 3. 更好的优先来源：旧周报与大PPT的原生高分辨率媒体

| 目标图 | 首选来源 | 后备来源 | 新PPT页 |
|---|---|---|---|
| 工位/设备真实整体 | 周报9/4–10/23、10/30机械臂验收PPT | 大PPT中真实工位照片 | 1/14 |
| 旧框误占据和局部多基元 | 周报9/18/9/24/10/23；大PPT靠后素材页 | repo clarity_v2 + geometry_ab | 4–6 |
| 9/21真实相同A/B三视图 | 9/24周报内对应图，方法稿第6页原嵌图片 | worklog/evidence/2026-09-21-p3-1-residual-support/current_base_avoid/clear_vs_avoid_three_views.png | 11 |
| 右臂TCP+实体夹爪 | 9/11/9/18周报JAKA界面/实物近景 | 大PPT的TCP校准图 | 7 |
| 真实P3.6/P3.7绕障 | 9/24周报后现场照片+对应录屏 | 场景执行证据目录中经验证视频/图 | 9/12 |
| PLACE持物过大 | 10/23周报 + 大PPT后部素材页 | repo panels/attachments | 10 |
| 新版原生运行工作台 | 10/16/10/23周报或验收稿 | repo panels/runtime（先判真伪/来源） | 1/14 |
| CPU模块时间 | 历史runlog数值重新制作原生表/条形图 | repo panels/performance | 13 |
| 14页实机全流程 | Golden Demo录像或10/23、10/30周报截取真实关键帧 | repo旧演示材料图片 | 14 |

**切忌**：周报有画面但未必属于同一组实验。旧PPT某页实际是“2026-10-23图示”+“9/21表”，必须保留这两个来源的区别。

## 4. 原PPT拆分与提取规则

1. 先按slide order渲染模板、方法稿、大稿全部页，形成contact sheets；单独登记大稿末尾有图却没有可提取文字的页面。
2. 读取`ppt/presentation.xml`的sldId对应关系；从`ppt/slides/_rels/slide*.xml.rels`取得媒体rel，再抽取`ppt/media`原始文件。
3. 不直接截取1024×768的整张PPT后强行放大；优先提取单张原始高清图片、SVG或可编辑原生形状。
4. 对原生形状流程图与公式，尽可能复用/组合源元素，而不是贴一张糊图。
5. 每个媒体生成一条metadata：source_ppt, slide_ordinal, object_id, rel_id, original_media_sha256, pixel_dim, crop, used_in_new_slide, dataset_id, evidence_level, note。
6. 若原PPT附带真实视频，应原样记录duration/FPS/文件名/是否快放；“视频时间”不可当现场运行时间。
7. 不在public repo上传未经确认的原件（可能含公司商标、协议、敏感场景、通讯地址）。如必须在Codex本机使用，原文件只需本地可读、无需public推送。

## 5. 原始图提取后要生成的审查产物

- `assets/source_ppts/contact_template.png`、`contact_method.png`、`contact_large.png`（仅当二进制可得时生成）；
- `assets/extracted/`按source_id/slide序组织的子图，优先PNG原嵌入文件而非屏幕截图；
- `source_media_index.csv`含原始文件、页码、对象ID、SHA、图片尺寸、应用页；
- `source_ppt_manifest.json`含Mac私有路径只保存在本地忽略文件，公开清单只写basename+SHA；
- 16页PPT备注和来源表一致。

**准确交接句**：三份原始PPT目前未在repo原样提交；已存在的是文字索引与独立研发图集。Mac路径未核实，请Codex本机按上面精确文件名定位。