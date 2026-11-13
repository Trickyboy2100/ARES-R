# ARES-R ROS1 取放功能块

统一接口为 `/ares_r/run_block`。封装共登记 11 项能力，包含原姿态往返、5项抓取及5项放置，其中称上两个放置功能为可选项。

| 功能 | 封装状态 |
|---|---|
| U01 姿态往返 | 沿用已认可的 `/ares_r/center_restore` |
| P01 称上筛网抓取 | 原 HOLD 执行器适配，结束于持物确认 |
| P02 称上料盘抓取 | 加速版原入口增加 HOLD 结束选项，230mm 抬升后保持 |
| L01/L02/L03 除尘收料机及烘干箱放置 | 复用原 Place 执行器，校验释放、退出和回 center |
| P03/P04/P05 新工位抓取 | 共用接口已注册，工位参数待绑定 |
| L04/L05 称上放置 | 参数模板已提供，需求与工位数据待确认 |

新取放块的实机 Start 当前保持未发布状态。候选代码已接入 canonical 任务所有权、持物会话、工具/几何绑定、ROS反馈、取消和结果回报。现场运动验收记录单独登记。

## 主要接口

- `/ares_r/blocks/list` 查询功能、参数版本和验收状态。
- `/ares_r/blocks/prepare` 提交静止扫描与规划准备任务。
- `/ares_r/blocks/preparation_status` 根据 run_id 查询准备结果。
- `/ares_r/run_block` 运行已发布的取放功能，提供阶段反馈及最终结果。

同一 request_id 保持幂等。取消按 run_id 发送到 canonical；实际停止尚未确认时返回 UNCERTAIN。ScanPick 返回 payload_session_id，ScanPlace 用该 session 核对原抓取证据、新鲜夹爪读数、工具定义和持物几何。释放确认后立即记录 RELEASED_CONFIRMED，后续退出失败会保留该状态。

## 代码入口

| 文件 | 功能 |
|---|---|
| `block_registry.json` | 11项能力、5份生效参数SHA和验收状态 |
| `blocks/console.py`、`blocks/backend.py` | canonical 同一任务所有者与精确run_id状态/停止 |
| `blocks/action_transport.py` | ROS→canonical 调用、反馈、取消及终态核对 |
| `run_canonical_block.py` | ScanPick/ScanPlace 执行器委派 |
| `blocks/live_payload.py` | 原SDK只读工具数据、延迟夹爪反馈及原生包绑定 |
| `blocks/place_runtime.py` | 持物几何进入规划、释放状态持久化、退出后回center |
| `blocks/tray_hold.py`、`patches/` | SHA锁定的独立料盘HOLD候选补丁 |
| `profiles/templates/` | 缺失工位参数模板 |
| `ros/ares_r_manipulation_blocks/` | ROS源码、Action、Service、客户端及launch |
| `ONSITE_ROS_BASELINE.md` | 已认可的现场ROS自启动链 |

## 部署

候选目录为 `/home/yikun/ARES-R-ROS-BUSINESS-20261113`。后端使用 `run_backend_overlay.py`，`ARES_R_SITE_ROOT` 指向实际RC1运行目录；接口节点使用 `canonical.launch` 并指向该后端。候选版仅在维护窗口进行服务切换。

运动发布记录位于实际运行目录 `config/ros_business_release.json`，与功能块版本、参数SHA和验收证据绑定。未绑定工位参数或未发布的块可查询及进行适用的准备检查。首次现场验收采用显式授权且绑定唯一request_id的测试记录，验收前无需伪造已通过的运行ID；测试授权不会自动将功能块标为已发布。

## 测试

```bash
python3 -m unittest discover -s release/ros1-business-blocks/tests -q
```

测试环境需要NumPy。现场Noetic编译及隔离ROS模拟通信已通过，详细结果见 `evidence/`。接口测试使用模拟执行边界，新的实机取放验收尚未进行。
