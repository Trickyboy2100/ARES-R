# 返场前 Mac / .32 / GitHub 三方代码与真实证据缺口

日期：2026-10-18，Asia/Shanghai。

## 范围与结论

本轮遵循 PRESITE 工作单的首轮边界：**inventory / custody only**。没有实现运行链路修复，没有运动、重新采集、修改现场文件，也没有公开上传私有点云/配置/凭据。

读取工作单来源：GitHub `planning/20261018-roundtrip-delivery-dash` 的 PRESITE_MAC_UBUNTU_EVIDENCE_REPLAY 和 ROUNDTRIP_DELIVERY_DASH；同时读取10月17日故障报告、逐阶段参考、FAST版本差异补充和返场计划。规划分支不是运行基线。

结论：Mac 上已找回本轮所需的 WebUI/backend/19阶段 Demo/参数/路线/打包器/测试/服务定义；**它们分散在不同 dirty 副本，不是一个已验证的可部署 release**。10月16日三次实机原始 run、持物点云和原生反馈未找到；.32 本轮 SSH 超时。Ubuntu 尚未可登录，不能声称真实 GPU replay 已通过。

## 1. GitHub 现状与逐文件比较

本轮通过 GitHub API 重新核实：

| 分支 | HEAD | blob文件路径数 | 无法解析字节SHA256的blob |
|---|---|---:|---:|
| feat/e2e-v0-integration-20260917 | `7120c3f3aad17330d0af6ada1e39c60bc58fe7fb` | 1548 | 0 |
| codex/audit-roundtrip-20261017 | `b2b44528ee1df0d0aeed657754bcfcdae3cbc2be` | 1624 | 0 |

比较方法不是把 Git SHA1 当作 SHA256：读取 API tree blob ID，获取本地 Git object 中相同 blob 的完整字节，计算 SHA256；若 object 不在本地库，则以本地文件计算 Git blob ID 证明与远端 blob 完全相同后计算 SHA256。逐本地路径与两份远端树比较，另外记录远端存在、本地不存在的路径。Git LFS pointer如有，只代表pointer，不冒称大文件本体。

完整结果保存在私有归档的 `INTEGRATION_FILE_COMPARISON.json`、`AUDIT_FILE_COMPARISON.json`、`remote/*_sha256.json`。两份分支均逐文件覆盖；不表示 integration 已包含这些最新运行代码。

## 2. Mac 工作树盘点

搜索 Documents/ChatGPT/local、Downloads 下 ARES-R Git副本，并核查 Desktop、.codex/worktrees；PSSD本轮未挂载。共发现12个既有 ARES-R repository。父目录 local/.git 为 unborn 仓库，不是 ARES运行树。新增RC工作树是本轮输出，不混入输入盘点。

| 副本 | HEAD短SHA | tracked modified | untracked | ignored |
|---|---|---:|---:|---:|
| local/ARES-R-offsets-20261016 | 9ff45177fdf9 | 13 | 373 | 795 |
| local/ARES-R-operations-20261015 | b3ab33125c71 | 10 | 29 | 458 |
| local/ARES-R-data-archive-20261012 | 7120c3f3aad1 | 0 | 0 | 0 |
| local/ARES-R-data-archive-sparse-20261012 | 30f21c7b945c | 0 | 0 | 0 |
| Downloads/ARES-R | da779767482f | 0 | 35 | 8888 |
| Downloads/ARES-R_CALIB | 7d2cde2be3f9 | 4 | 5 | 7 |
| Downloads/ARES-R_BODY_WORK | 020d7ceb4405 | 0 | 13 | 1 |
| Downloads/ARES-R-p39b-dev | 34b2ed8ff239 | 0 | 0 | 47 |
| Downloads/ARES-R_DEMO_WORK | 31c423e8e363 | 1 | 10 | 89 |
| Downloads/ARES-R-p36 | 131a47bbdeb2 | 0 | 9 | 146 |
| Downloads/ARES-R_INTEGRATION_WORK | b9673bc173b5 | 10 | 22 | 104 |
| Downloads/ARES-R-body-camera | d202baa61fa5 | 0 | 0 | 4 |

共23309个文件/符号链接记录：12236 tracked unchanged、38 tracked modified、496 untracked、10539 ignored。计数包含重复副本、生成文件和历史资料，不是23309份最新代码。

另外核查Git worktree注册表中的10个 `/private/tmp/ares-r-p*` 历史工作树路径，全部已不存在；只记录，不执行prune。可达Git refs随bundle保全，不声称能恢复那些已删除工作树中从未提交的文件。

逐文件保留 relative path、SHA256、size、mtime_ns、mode、Git分类、root HEAD/branch；不追踪符号链接目标，不读用户SSH密钥。`.git`历史用bundle保全，dirty/index另存binary patch，文件本体按source/data/dependencies_generated分别归档，不将私有原始数据放进代码分支。

### 保全例外，不能隐瞒

- offsets有41个 ` 2.py` 重复文件是 iCloud非驻留占位，列出名称和大小但未取得字节，不猜哈希。不涉及此次关键运行模块的正规文件名。
- sparse archive是partial/promisor clone，创建完整history bundle时需要远端未落地object，因本机Git DNS不可用而失败。其现有198个文件本体均已归档，Git历史完整性仍单列缺口，不把它当代码丢失或用户删除。
- 该partial clone当前已落地的 `.git` 元数据/objects另存 `partial-git-metadata.tar.gz`，保全现有对象，但仍不声称具备缺失的promisor对象。
- 首次保全读取占位文件时被有界中断，未完成归档保留于 `incomplete-attempt-1`，不可用于恢复；使用最终 `bundles/` 和验证报告。
- 其他同事dirty不根据文件名猜作者，不合并、不reset/revert、不清理untracked/ignored。

## 3. 最新运行文件具体来源

完整38项文件×工作树×远端的 SHA256 matrix 位于私有 `CRITICAL_RUNTIME_FILE_MATRIX.json`。下列为重点：

| 组件 | Mac完整文件来源 | integration | audit |
|---|---|---|---|
| WebUI index/operations/server | offsets，operations有不同版本 | 旧index/server，无operations | 部分server源码快照，非完整前端 |
| canonical backend | offsets；operations不同 | 旧版 | offsets源码快照 |
| roundtrip_panel.js / launcher / roundtrip_demo.py | offsets | 无 | 有源码快照 |
| run_grasp_place_roundtrip.py | offsets | 无 | 有源码快照 |
| Demo demo.json / parameters.json | offsets | 无 | 无 |
| grasp_place_base_route.json | offsets | 无 | 无 |
| planner_latency_profiles.json | 两份存在且不同 | 无 | 无 |
| production_scene_worker.py | 两份功能不同 | 更旧 | offsets源码快照 |
| latency_solver / cpu_distance | 两份存在 | 无 | 只有latency_solver源码快照 |
| native_execution_package.py | 两份相同 | 较旧 | 源码快照 |
| native_demo.py / jaka_right_demo.cpp | 两份相同 | 有 | 有源码快照 |
| roundtrip测试 | offsets | 无 | 无 |
| deploy/systemd backend/webui | 两份相同 | 有模板 | 模板继承于audit根，而非现场安装状态 |
| native v5/v6_pick实际二进制 / JAKA SDK | 未找到所需现场文件 | 无现场有效文件 | 只有历史hash/源码 |
| 实际pinned URDF/STL/spheres | 配置中有路径与hash，盘点未找到本体 | 未得到生产资产本体 | hash不能替代资产 |

`operations.js`独立文件不存在不等于前端缺失：主要逻辑在 `operations.html` 内联。必须核查完整页面及依赖，不能机械要求一个并不存在的文件名。

找到的版本：

- route revision：`GRASP_PLACE_BODY_ROUTE_2026_10_16_V2_GRASP_LEFT100MM`；文件SHA256 `02521117b731b1d7f85598cfef92e2e074bc47154328a9b78424311ff193ba16`。
- parameters revision：`RIGHT_GRASP_PLACE_ROUNDTRIP_2026_10_16_V2_NO_STOW_RETRY3`；SHA256 `75dbf1832405762a83eb1f0c79de2931b740342dc568cf4485cac09593ebbb61`；55mm contact、230mm总抬升、无stow、FAST/QUALITY/QUALITY。
- Mac存在更早10月16日准备文档仍写750mm和收臂，与上述后续参数不同，不能把旧文字文档当最终effective配置。
- systemd模板的相同hash不证明现场installed unit、ExecStart环境和loaded module相同。

## 4. 两份FAST的准确差别

| 项目 | offsets | operations |
|---|---|---|
| worker SHA256 | `6a706b15843f1211fa9117a339d03b4e8a1996567d36e813aecac78314978329` | `3afcc99a04217a385cc6999f9065d2d4ac06eca7fe747b8644c3b6e2683d5012` |
| solver_policy验证与single-pass | 未接入 | 接入 |
| max_goal_candidates消费 | 未接入 | 接入 |
| FAST native CPU distance/跳过baseline诊断 | 未接入该选择 | 接入 |
| cuboid容量分桶+容量进入runtime key | 有 | 没有；不能整文件替换丢掉这个修复 |
| result deadline检查 | 无此末尾合同 | 结果生成后检查，**不等于主动取消** |
| runtime缓存容量/VRAM上限 | 未闭合 | 未闭合 |
| 服务端任务中断/取消ack | 未闭合 | 未闭合 |

两份latency_solver本体相同：`e853aac0c60ac86595541ed84229f6d176c5d540746446ec77a93db9f73bae72`。worker仍包含warmup与benchmark_runs循环，不能只看到single-pass函数名就宣称每个请求始终只solve一次。需要effective request和GPU测量。

五个planner模块的完整unified diff保存在私有 `diffs/`。本轮不盲合并、不选择“日期更新的版本”；最终选择需冻结真实输入并验证。现场10月16日实际加载哪份仍未知。

## 5. 三方证据缺失矩阵

状态严格采用：**完整文件 / 仅源码快照 / 仅哈希 / 完全缺失**。聊天数值另作旁证，不提升为完整文件；.32列的缺失指“本轮未取得”，不是宣称服务器上不存在。

| 资料 | Mac | GitHub | .32本轮取得 |
|---|---|---|---|
| 最新WebUI/backend/launcher/主脚本 | 完整文件（版本分裂） | 部分仅源码快照 | 完全缺失 |
| 最终Demo参数/85cm路线 | 完整文件 | 完全缺失 | 完全缺失 |
| 三次web_1792140369955017446 / 1460049419632 / 2393480633163 | 完全缺失 | 完全缺失；只有聊天数值账本 | 完全缺失 |
| pick原始观测/原始CAMERA/BODY点云 | 完全缺失（10/16） | 完全缺失（10/16） | 完全缺失 |
| post-close / post-LIFT100持物场景 | 完全缺失 | 完全缺失 | 完全缺失 |
| 100mm confirmed_lift原生文件/反馈 | 完全缺失；有恢复脚本不是运行数据 | 仅恢复脚本源码快照 | 完全缺失 |
| 最终130mm三个PLAN目录请求/结果/世界 | 完全缺失 | 完全缺失；只有数值摘要 | 完全缺失 |
| 37/37/37原始采样时间戳 | 完全缺失；聊天值不能重造采样时刻 | 完全缺失 | 完全缺失 |
| 115.04s contact native输入/反馈、72s lift反馈 | 完全缺失（实际run） | 仅源码快照/聊天数值 | 完全缺失 |
| AMR Oct16独立测试JSON/路线定义 | 部分完整文件（非持物全链） | 最新路线缺失 | 完全缺失 |
| Oct16 installed service / loaded worker / SDK / sender | 部分模板完整，实际binary仅历史hash | 仅模板/历史hash | 完全缺失 |
| Oct12三组preland真实数据 | 完整本地既有归档 | 既有清单/资料，不替代Oct16 | 本轮未取得 |

Mac路径全量搜索的4个confirmed_lift匹配全部是恢复脚本/pycache/审计副本，**没有实际confirmed_lift运行目录**。两个本地 `RETURNED_GRASP` JSON是先前Mock循环，不能证明实机19阶段完成。

## 6. 存储、恢复与下一步

私有目录：`/Users/andyee/Documents/ChatGPT/local/presite-20261018-private/`，权限0700。

- `SOURCE_CUSTODY_MANIFEST.json`、`MAC_WORKTREE_DIFF_REPORT.md`、`UNRESOLVED_FILE_ORIGINS.md`。
- `bundles/`：source / data / dependencies_generated分开；`git/`：bundle、index/worktree patch。
- `PRIVATE_ARCHIVE_SHA256SUMS`：归档字节hash；`CUSTODY_VERIFICATION.json`：逐tar成员重读SHA256结果及Git bundle验证。
- `SITE_EVIDENCE_MANIFEST.json`、`GPU_ACCESS_PROBES.json`、`OCT16_RAW_PATH_SEARCH.json`。

原始证据、站点配置、SDK二进制不自动push公共仓库。本轮只在独立RC分支保存报告和离线保全工具；它还不是可运行release。原两份dirty工作树不改，golden文件不改。

下一轮前置：恢复一个可信Ubuntu GPU SSH入口；.32可达时只读收集上述精确run及依赖链，然后才开始同输入失败复现与P1–P6小提交修复。
