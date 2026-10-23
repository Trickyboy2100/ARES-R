# 冷启动复演与正式Demo登记

日期：2026-10-23。

## 结果

冷planner复演一次成功，完整完成抓取、连续230mm抬升、验证、原路下降放回、释放、退出和回center，无fault、无人工续接。物体已放回，右臂已回初始center，底盘未移动。

新正式Demo：`right_arm_pick_lift_replace_reset_v1`，版本`1.0.0`。验收仅覆盖当前固定夹具场景的右臂原位抓取复位，不覆盖跨站转场、六泊位、任意物体或整机断电启动。原golden与roundtrip不替换。

## 冷启动到底重启了什么

使用已有 `restart_rc1_planner.py`，确认旧RC1 planner空闲且PID/命令行归属一致后正常stop/start，不强杀其他任务。重启后、prepare前实际读到：

```json
{"state":"READY","worker_pid":null,"runtime_count":0,"prewarmed":false,"pid":14827}
```

因此这是planner进程、CUDA/运行时缓存为空的复演。backend、WebUI和共享相机服务仍在运行，工控机没有重启；不能称整机或相机SDK冷启动验收。

## 冷态与前一热态成功记录

| 项目 | 热态r7 | planner冷态r8 |
| --- | ---: | ---: |
| 资源初始化，与观察并行 | 0.452s | 13.358s |
| 观察事务与场景 | 15.789s | 16.539s |
| 首次正式规划请求 | 3.010s | 8.339s |
| 几何准备关键路径总量 | 28.811s | 34.677s |
| 初始4份Native打包，各段相加 | 3.442s | 3.808s |
| 启动前准备量模型 | 32.254s | 38.485s |
| 实机执行启动到回center | **134.536s** | **144.135s** |

准备量模型不包含独立调用间隙，不是WebUI点击到运动的测量。初始化13.36秒与观察16.54秒重叠，不能再次相加。冷态准备与执行量模型约182.62秒，并非统一入口端到端实测。

冷态预抓取及反向回center的Native计划各32.64秒，热态各27.76秒；两次fresh扫描和求解轨迹不同，所以执行多约9.6秒主要对应路径差异，不能归因于“CUDA冷启动让ServoJ变慢”。该差异也说明轨迹长度/耗时稳定性仍值得后续profile重复测试，不宣称全局最快方案。

## 冷态实际阶段时间

| 阶段 | 秒 |
| --- | ---: |
| 夹爪runtime预检 | 0.101 |
| 夹爪40% | 1.261 |
| 预抓取 | 35.280 |
| 后台Native ready等待/检查 | 0.00591 |
| 接近55mm | 13.120 |
| 闭爪 | 0.407 |
| 抬升前验证 | 2.005 |
| 连续230mm抬升 | 15.429 |
| 抬升后验证 | 8.164 |
| 原路下降 | 15.429 |
| 释放 | 1.259 |
| 退出 | 13.223 |
| 回center | 35.278 |

所有5项抬升后gate为true。最终BODY TCP位置：`[0.354851751,-0.077535294,1.021138842] m`。六份Native采样hash及pointcloud/package/result hashes已写入Demo的`evidence.json`。

## 正式化内容

- 独立目录 `demos/right_arm_pick_lift_replace_reset_v1/`：定义、说明、参数来源快照、验收源码/现场配置指纹、冷/热成功证据。
- 正式入口 `scripts/run_pick_reset_demo.py` 是薄客户端：调用已实测准备/打包工具与canonical后台，不复制机械臂算法，不替换旧runner。
- `--execute` 无既有候选时会fresh prepare，然后启动一次完整循环并监控；不是从历史验收轨迹直接重放。
- 支持 `--prepare`（不运动）、`--execute`（监督授权）、`--stop`。
- 新运行目录隔离为 `worklog/evidence/demo-runs/right_arm_pick_lift_replace_reset_v1/<run>/`。
- 通过现有DemoRegistry进入ART/WebUI共用目录；没有实现或声称新增专属WebUI一键实机按钮。
- 为保证此正式版可复现，入口核对已验收脚本和现场配置指纹。变化要求新版本审核，仅限本Demo入口，不增加其他实验链路的全局限制。

ART可用 `demo select right_arm_pick_lift_replace_reset_v1`、`demo prepare` 查看正式命令。完整运行/停止命令位于新Demo README。

## 入口验证与测试边界

正式薄客户端的授权、配置漂移、已有准备工具及canonical API转发做了单元测试；现场另实际执行了一次新正式命名空间的 `--prepare`，结果 `PREPARED`、`physical_motion=false`，观察16.23秒、热请求2.97秒、几何准备29.16秒，首批Native约3.51秒。

该prepare候选不是第三次物理运行，不自动执行，也不可在过期后复用。物理验收记录是r7/r8对同一canonical执行后端的两次成功调用，不虚称薄客户端又做了第三次全程动作。

全量测试：**815项，0失败，1项跳过，11.568秒**。本机实验/正式入口相关19项测试通过。新目录与正式入口已部署到独立RC1；原golden源码、生产配置、速度/跟踪/控制器保护未修改。不自动push。

现场r8证据：`/home/yikun/ARES-R-RC1-20261019/worklog/evidence/20261023-pick-reset-r8-cold/`。

正式prepare证据：`/home/yikun/ARES-R-RC1-20261019/worklog/evidence/demo-runs/right_arm_pick_lift_replace_reset_v1/run_1792739593986859307/`。

冷态/正式prepare与定义快照已拉回本机private目录：`/Users/andyee/Documents/ChatGPT/local/site-private-20261023/20261023-pick-reset-cold-formal-checkpoint.tar.gz`。SHA256两端一致：`fd2fb9f569e621c372d47f818a5bd8d36a597c991f9f351afef11a0e452d45d1`。该包明确排除PLY/NPZ/NPY/图片，不宣称完整原始点云归档。
