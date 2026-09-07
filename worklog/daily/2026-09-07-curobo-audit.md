# 2026-09-07 cuRobo 接入审计

Source: manual

- 完成右臂单独只读诊断、现场 GPU/Python 依赖检查、原 ARES 规划实现和 JAKA SDK 接口初审。
- 左臂正在实际运动，未向任一机械臂发送运动、servo 使能或停止指令，未改动共享环境及现场测试脚本。
- 记录 `servo_j(tgt, 1)` 的模式歧义、旧规划末尾未验证修正段、时间参数化与双臂互锁缺口。
- 加固轨迹文件及数值检查，47 项离线单元测试通过。
- GPU cuRobo 规划、现场碰撞模型核验和右臂实机轨迹验证仍待完成。
- 详细说明：`docs/CUROBO_AUDIT_2026-09-07.md`。

## cuRobo Demo 开发

- 现场已确认左右臂工作区域隔离、观察和物理急停条件。右臂运动授权限于小幅、低速验证。
- 增加 `--devices right-arm` 连接范围，排除左臂、相机和夹爪；仍只有离线/使能实机两种模式。
- 增加 `curobo status / plan / plan-file / preview`，GPU 规划器与 SDK 进程隔离。
- 固定 cuRobo 提交，418 个上游代码/配置文件通过 Git blob SHA 校验；专用 Python 3.11 环境与模型目录位于仓库外，未修改现有测试环境。
- 原 ARES URDF 与右臂 14 组 SDK FK 对比，固定基座校正后最大位置误差 1.3153 mm、姿态误差 0.0001704°；未认证碰撞模型。
- 未登录回环对象参数检查与本机 ELF/头文件审计确认：现场 `servo_j` 只接收两参数，`servo_j_extend` 包装 C 接口 `(handle, joint_pos, move_mode, step_num)`，`ABS=0`。不使用在线三参数 `servo_j` 假设。
- 专用 J6 微动执行器已添加隔离单元测试，尚未接入 Terminal 执行命令；57 项离线测试通过。GPU 规划和实机验证仍待完成。
