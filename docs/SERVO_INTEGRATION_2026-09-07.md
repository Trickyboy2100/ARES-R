# cuRobo → Trajectory → JAKA servo 正式接口

## 职责边界

```text
静态 SceneSnapshot（米，URDF base_link；未来 Epic 转换接口）
                       ↓
固定起点 / 当前实际关节 → cuRobo plan_cspace
                       ↓
Trajectory JSON + 模型/场景/工具/参考点版本 + 数值/空间门槛
                       ↓
独立右臂 SDK 2.2.2 进程：servo_j(ABS, 10)，80 ms
                       ↓
同进程实际关节/TCP反馈 → JSONL 日志 → Terminal dashboard
```

- `demo_reference.py`：版本化起点；六关节弧度、控制器基坐标 TCP mm/rad、工具号/偏移、世界/模型/限位/FK 标定指纹。
- `demo_workflow.py`：复位规划 → 复位执行 → 到位核验 → 20 cm 规划 → 执行。已知且清理完整的 `TRACKING_ERROR` 允许一次 3×→2×重新规划；其他失败终止，不自动恢复或回程。
- `obstacle_demo*.py`：隔离 GPU 规划、时间放慢/80 ms 重采样、重新验证；不导入控制 SDK。
- `trajectory.py`：沿用已有统一文件契约。上层规划与下层执行通过文件交接，不在 GPU 进程中直接发送 servo。
- `native_demo.py`：SDK 环境隔离、起点/版本/限位门槛、互斥、启动/回收执行进程。旧 Python SDK 不替换。
- `servo_dashboard.py`：只消费执行日志，不连接机器人；空格、q、Esc、Ctrl+C 请求原生进程停止。SDK 停止调用仅由执行进程负责，不采用双线程同时调用 SDK。
- `scripts/jaka_right_demo.cpp`：固定右臂地址；新鲜实际反馈、工具、队列、跟踪误差、周期超时检查；失败 abort、关闭 servo、logout。无上电/自动使能/恢复程序。

## tmp 调试成果迁移审计

2026-09-07 读取 `/home/yikun/ARES-R/tmp`；原文件和轨迹均保持原样，不执行原脚本、不连接左臂。

| 原组件 | 正式接入方式 | 不直接迁移的行为 |
|---|---|---|
| `servo_left_driver.py` | Trajectory 文件交接、8 ms 整数周期、预检、按键停止、退出伺服原则；正式 native executor + dashboard | 默认左臂、自动使能、线程直接并发 abort、手工宣称 collision_checked |
| `record_waypoints.py` | `waypoints.py` 支持旧 J1..J6 命名、显式 rad/deg 字段，并核对两种单位一致性；固定起点记录改为 SDK 实际反馈 | 默认左臂连接、未检查返回码的数据读取 |
| `make_spline_traj.py` | 提取 centripetal Catmull-Rom 几何到正式 `waypoints.py`，补离线单测 | 不裁剪越界关节，不宣称避障通过，不作为 cuRobo 失败回退 |
| `make_traj.py` | 轨迹文件/起点/目标的分层思想沿用 | `--start` 文案称 rad 但又转 radians 的单位问题；匀速直连不是本轮规划器 |

源文件 SHA256：

```text
servo_left_driver.py bd4c970708a44f7397a9d1eca271e77e83fbcf406c7e3da0778a14d9dac61ad0
record_waypoints.py 1362fbd15477fe7138e07cd77b8b97744bd020b1765290b8d2b756e715e94e54
make_spline_traj.py 19fc18f3f4bc7fb17e3ef0b9e57c0abce203c106116bfe799b8022b0e90b4418
make_traj.py 74c84e26fb8ae6f5d500defed273bb6483cfe7c625dd4f7f4d0d2581fd338bad
```

正式 Terminal 离线入口：

```text
servo waypoints tmp/waypoints.json
servo spline tmp/waypoints.json logs/waypoints_geometry.json
```

仅读取旧记录，生成明确标记的 `offline_waypoint_geometry`。输出没有执行用时间序列、不能传入 native demo 执行。输出文件已存在则拒绝覆盖；超限拒绝而非裁剪。

## 避障输入扩展点

```text
curobo scene load config/planning_scene.example.json
```

当前支持版本化、静态、轴对齐 cuboid；`pose=[x,y,z,qw,qx,qy,qz]`，长度单位米，坐标 `urdf_base_link`，不是车体 world 或相机坐标。`cuboids` 为名称到 `{dims:[sx,sy,sz], pose:[x,y,z,1,0,0,0]}` 的映射。加载只对当前 Terminal 会话生效；规划请求冻结内容和摘要，执行前重新核验，变更后必须重规划。演示虚拟块同时加入 cuRobo 和独立距离校验。

Epic 点云尚未接入。未支持的数据源、点云字段、坐标系和旋转盒明确拒绝，不静默忽略。后续需要相机外参/时间戳/失效策略、点云滤波到碰撞几何、附着物建模及实时更新与执行中停止策略；现阶段不能宣称动态避障。

复位使用当前静态场景；未加载对象时相当于净空场景。为初始化 GPU 碰撞后端保留位于 URDF 坐标 `[10,10,10] m` 的远端虚拟盒，仅为实现占位，不代表物理障碍。复位也启用模型自碰撞检查、限位、速度/加速度和右侧工作区门槛；不沿演示轨迹盲目倒放。净空人工确认与物理急停条件仍是必要条件。

## SDK 符号错误

`is_in_servomoveEPi` 缺失可在 `LD_LIBRARY_PATH=/home/yikun/JAKA` 下用无效模式参数复现，发生于连接前。该目录为旧 SDK；2.2.2 符号存在于 `/home/yikun/JAKA/lib/libjakaAPI.so`。

修复采用子进程专用库路径、移除继承的 preload/audit、`LD_BIND_NOW=1`；编译加入固定 RPATH 和立即绑定，构建后执行不联网的加载检查。构建占用右臂互斥锁，执行期间禁止覆盖二进制。禁止全局改换共用账户的 SDK 环境。
