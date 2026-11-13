# 烘干箱六泊位 ROS 功能库

十二个入口共用 `/ares_r/run_block` Action。编号为 `pick.dryer.tray.<slot>.v1` 和 `place.dryer.tray.<slot>.v1`。

| slot | 位置 |
| --- | --- |
| upper_left | 上层左 |
| upper_middle | 上层中 |
| upper_right | 上层右 |
| lower_left | 下层左 |
| lower_middle | 下层中 |
| lower_right | 下层右 |

`/ares_r/blocks/list` 返回各入口版本与发布状态。
`/ares_r/blocks/resolve_dryer_target` 使用 `ResolveDryerTarget` 服务，输入 block_id、observation_epoch、base_pose_revision，返回 binding_json。查询读取 canonical 主机的注册表，不触发检测或运动。调用前应通过现有场景服务完成检测及参考点绑定。

六个泊位几何来自 `worklog/runtime/operations/state.json` 的 `dryer.slots`。该文件也是现有 WebUI 的保存位置。任务动作参数来自 `config/ros_dryer_tasks.json`，模板位于封装源码 `profiles/templates/ros_dryer_tasks.json`。模板中的空值需录入，零偏置必须显式填写六个0。

计算采用 `T_BODY_TCP = T_BODY_参考点 × T_参考点_泊位 × T_泊位_TCP`。抓取与放置共享泊位几何，各自保存TCP接触偏置及接近、退出、夹爪参数。检测坐标系与TCP坐标系分别定义。

返回包含实际偏置、BODY变换、注册表版本、配置哈希、观测与底盘版本、占用状态。`T_body_tcp=null` 表示动作TCP偏置尚未配置。`execution_package_ready=false` 表示该结果仅用于目标准备。

当前十二入口已登记，目标解析及版本绑定可测试。逐泊位的运动执行适配和实机验收尚待完成，RunBlock执行保持未发布。原L03固定下层中间历史入口单独保留，其参数读取方式沿用原版本。

每个泊位分别记录抓取与放置验收。占用更新应绑定实际取放结果，目标查询不会修改占用状态。
