# 2026-11-16 WebUI 与 ROS Demo01 回归

## 结果

ROS Action `/ares_r/center_restore` 实机返回 `SUCCEEDED / CENTER_RESTORE_COMPLETED`。运行 ID 为 `81a9ce0bb0594a87a9fb55d74163a84b`，总耗时 77.86 秒。右臂最终停在已保存右前高位。

| 运动段 | Native 实际执行 | TCP 位置误差 | TCP 姿态误差 |
|---|---:|---:|---:|
| 当前位姿 → center | 16.115 s | 2.046 mm | 0.00559° |
| center → 右前高位 | 14.655 s | 0.043 mm | 0.00890° |

目标 ID 为 `right/front_right_high_axes_aligned`，原始记录 SHA256 为 `bbcd723fc83d1091b9065ed2636e6689e52987c9cfa8a8e3db5defac16a7499a`。两段 arrival 均通过，第二段最大关节误差约 0.00002°。

## 本轮修复

- LIVE 扫描不调用桌面识别，也不添加历史桌面几何。其 manifest 中 `table_validation.status=NOT_REQUESTED`。显式标定验收仍可调用原参考桌面检查。
- 主页面与 Console 点云层共用完整 BODY 点云产物解析，规划清理残余为空时仍能显示原始观测。规划障碍继续来自原 scene pipeline。
- Console 顶部新增明确的 ROS Demo01 入口，绑定交付 manifest 的目标 ID 和 SHA。网页与 ROS 共用原 CenterRestoreConsole 和 run_block 执行器。`demo-0-return-center` 仍表示仅回 center 的历史辅助功能。
- backend 显式配置 RC1 planner socket，新增用户级 `ares-r-planner.service`。原地址错误由缺失 `ARES_R_PLANNER_SOCKET` 引起。
- ROS 自启脚本改由单个 `roslaunch -p 11321` 管理 master 和 Action 节点。删除后台 roscore 加固定 sleep 的竞态。
- 失败主提示展示简短原因、阶段和建议，完整错误与日志路径保存在展开的技术详情。`motion_dispatched` 只在任务有明确 dispatch markers 证据时填写。

## 首次失败记录

运行 `26ab8f7896e544c79cebbf5a950273ca` 在发送运动前返回 `READONLY_NATIVE_SNAPSHOT_FAILED`，native 报 JAKA `3182721 / 0x309081 SCB error`。随后独立 SDK 回读 errcode=0，native 复读也正常。该错误本轮未稳定复现，不能据此认定根因已消除。本轮保留原状态检查，并以新请求重新测试。

## 验证与证据

点云回归 5 项、双页面原始点云回归 1 项、失败提示回归 3 项通过。JavaScript 语法检查通过。ROS 两段实机验证通过。浏览器工具超时，页面视觉复核由人工刷新确认。

现场成功记录位于 `/home/yikun/ARES-R-RC1-20261019/worklog/evidence/demo-console/81a9ce0bb0594a87a9fb55d74163a84b/`，含 ROS 绑定、独立规划、两段真实反馈及到位结果。首次失败目录同级，ID 如上。

Mac 证据包位于 `/Users/andyee/Documents/ChatGPT/local/site-ui-unify-20261116/ros-test/ros-demo01-success-records.tar.gz`，SHA256 为 `ad39e73b7abd8b7b146f1174d785c3a3ea4c7f030c25df24433c47bb0084966d`，已与现场归档核对一致。证据包保存两次任务记录，原始点云继续保存在现场相应 capture manifest 指向的位置。

代码及现场服务配置已保存在本地工作树。本轮未 push。
