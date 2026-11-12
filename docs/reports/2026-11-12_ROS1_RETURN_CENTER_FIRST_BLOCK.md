# ROS1首个功能块：右臂回center

## 验收

首个ROS Action已通过实际控制链执行回center。现场观察成功；ARES实时读数 BODY TCP=[0.357633091,-0.078075393,1.027582145]m，相对center位置误差2.05563mm，控制器errcode=0、in_position=true。完成164个native采样，计划运动13.04秒。

必须同时保留原始软件结果：该运行的console状态为FAULT，原因是到位SETTLING阶段工具偏置漏读导致的误报，不是整条运动没有执行。没有将历史FAULT改写成SUCCEEDED。它是首次物理任务完成记录，尚不是修复后全链SUCCEEDED验收。

## 实现

`ros1/ares_r_demo_bridge`提供`/ares_r/return_center` Action，复用canonical HTTP8775 Demo后端。Goal携带请求ID和现场确认；Feedback提供阶段、run_id和耗时；Result包含成功与错误。取消仅转发所属后端任务，等待停止结果。请求超时不自动重发。

新增包是适配层，部署环境需已有`/api/demo-console/start/status/stop`和`right_arm_return_center_v1`；本提交不声称提供完整现场RC1快照。原Golden入口与同事dirty代码未纳入本次提交。

## 修复

1. SDK登录稳定等待200ms→1000ms；非零控制器错误仍停止，未清错、未跳过保护。初始化错误的确切根因未完全复现。
2. 到位`final=read(robot)`没有加载tool数据，却比较`final.tool`与起始真实tool。修复为`read(robot,true)`，保留原变化检测。

修复源代码：`native/jaka_right_scene_aware_status_v1.cpp`。现场编译到RC1私有native目录，原共享v5未覆盖。现场绑定scene_aware_execution.SENDER与native_execution_package.AUDITED_SITE_SENDER_SHA256均已更新；不提交机器二进制及机器绑定修改。重新构建后必须按构建结果重新审计SHA，不能把另一机器的二进制直接当作一致。

现场构建命令：

```bash
g++ -std=c++11 native/jaka_right_scene_aware_status_v1.cpp \
  -I"/home/yikun/ws/SDK v2.2.2/04 Linux/c&c++/inc_of_c++" \
  -L/home/yikun/JAKA/lib -Wl,-rpath,/home/yikun/JAKA/lib \
  -ljakaAPI -pthread -o native/jaka_right_scene_aware_status_v1
```

## 验证与状态

ROS catkin编译通过；真实ROS通信+模拟后端5/5通过（缺确认、占用、成功、失败、取消）；native相关离线回归19/19通过；初始化修复后3次snapshot通过。SETTLING修复编译通过、19项回归通过，但修复后的完整实机运动尚未重跑。

ROS测试使用隔离master127.0.0.1:11321，无开机自动运动。本提交不含token、原始点云或照片。

## 后续v0.2回归已闭环

2026-11-12T13:55:45+0800，从轴对正右前高位经ROS到center正式返回SUCCEEDED，ARRIVED_CONFIRMED，三次新鲜到位回读全部通过。位置2.05056mm、姿态0.002935°，Servo退出确认。原首次FAULT证据保留；本次为修复后的独立新运行，详见2026-11-12_OFFLINE_HANDOFF.md。
