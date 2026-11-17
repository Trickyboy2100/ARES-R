# 2026-11-17 开发成果保存检查点

分支 `codex/ros1-business-blocks-offline-20261113`。GitHub核对基线 `cb50698c46bd91edef04bebc06ef46c37f6deba2`，本地此前已有14项后续提交，本次与近期未提交成果一起正常快进推送。

## 范围

- Console布局、标签、故障说明和受控恢复，WebUI服务与兼容端口部署。
- 左右姿态、镜像工具及Native、SLAM共享配置、现场车体模型策略与相关回归。
- 独立ROS Demo02双臂姿态往返、准备阶段并行、源码包、实机结果摘要。完整ROS实机通过，Delivered=false。
- ROS Demo00/01文档、模板与取放实机盘点、功能手册及A/R编号体系。
- 之前已提交的ROS业务封装、六泊位目标解析、Demo01提速与Turbo试验随分支一起保存。

现场配置包括关闭未测量车体proxy、共享SLAM容差以及0.20rad/s自由空间请求默认值。这些是已有现场改动的保全；各任务物理验收范围仍按各自证据登记。当前全量测试未通过，此检查点用于开发保全和后续修复。

## 测试

- 新增及直接相关测试64项，54项通过、10项跳过。跳过项目按日志保留。
- Demo02独立测试11项通过。
- 全量937项，918项通过、12项跳过、1项失败、6项错误。已经在允许本机测试socket的环境重跑。
- 功能手册编号、网页路由、搜索/分页、桌面及窄屏验证已记录。根据最新实机摘要更新双臂Demo02状态。

## 全量测试待处理

| 项目 | 当前结果 |
|---|---|
| A/B loop两项 | macOS无Linux `/proc/<pid>/stat` |
| 诊断绘图导入 | 当前Mac测试venv缺matplotlib |
| Console目录数量 | 旧测试预期4项，当前为5项 |
| DemoRegistry别名 | demo-0-return-center在当前静态registry测试中未解析 |
| 筛网Golden校验 | named_poses变更与旧冻结hash不一致；需按版本关系处理 |
| center快捷入口 | 旧测试构造的Dispatcher缺operations属性 |

保留这些失败，未通过改冻结哈希或放宽断言掩盖问题。原始测试日志在 `worklog/evidence/2026-11-17-push-checkpoint/`。

## 发布包与资料

Demo02 SOURCE_SHA256按当前源码重新生成，包含新增测试和当前验收状态。原始实机压缩包site-run.tar.gz、site-logs.tar.gz留在本机，Git仅保存摘要、大小和SHA256索引。测试临时PLAN目录、.DS_Store和缓存留在本地，不进入提交。

本次任务为Git保全；现场程序与其他工作树不自动切换到该提交。
