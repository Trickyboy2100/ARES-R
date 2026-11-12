# ROS1取放功能块：离线检查点

日期：2026-11-13。依据planning/20261112-13-ros1-business-blocks工作单。
本轮未连接机器人、未运动、未修改现场源码或Golden。不是新增取放功能块的实机交付报告。

## 已完成及边界

1. 在独立分支保存离线准备代码。基于fd2467c后的现有a471e9f、7d709ea继续推进；未reset。现有Quickstart的未提交修改和DS_Store不纳入本次提交。
2. 6个私有包逐包重新计算SHA256，全部一致；共231,695,184字节，tar全部可读。客户源码7/7文件SHA正确；既有Action MD5记录604285c770a2394b3024a6fb532f8380，跨机通信仍未验收。本轮没有重新证明所有内部文件哈希和异地第二份备份；此前内部核验记录保留。
3. 11项注册表（8必需取放、2可选、1辅助）。5个已有Demo参数文件与私有P0当前源码逐文件SHA一致，不把根目录旧配置当现场权威。
4. 新RunBlock Action定义及不运动的ROS节点。没有新增JAKA控制器、ROS Master、规划器或部署服务。
5. 离线阶段合同/回放、持久幂等语义测试。Pick末端必须HELD_CONFIRMED+session；没有自动下降/释放/center。Place释放确认之后才能退出，退出后才允许可选center；取消未确认停止时不报STOPPED。所有结果明确不构成物理成功。

## 有效配置与状态

完整来源、revision及文件SHA在release/ros1-business-blocks/block_registry.json。

|编号|功能|当前状态|
|---|---|---|
|U01|center→保存姿态|原Action已验收，限定目标/工具/空手；新RunBlock不代理它|
|P01|称上筛网抓取持稳|参数已锁定；独立HOLD执行适配及实机重验待做|
|P02|称上料盘抓取持稳|参数已锁定；当前工具3/零补偿/速度下需重验|
|P03–P05|DMP筛网/料盘、烘干箱料盘抓取|无现场独立profile，PLAN_ONLY；不猜检测ID/偏置|
|L01|DMP筛网放置|CANDIDATE，历史983092风险未关闭|
|L02|DMP料盘放置|有效V7_Y5_Z20_D20；旧D10说明不作为新合同|
|L03|烘干箱料盘放置|CANDIDATE，新偏置/水平分支/接触下降须重验|
|L04–L05|称上筛网/料盘放置|需求待确认，禁用|

L02当前实际值：BODY预放置偏置[0,+0.005,+0.020]m，下降0.020m；required_tool_id=3，required_site_max_velocity_rad_s=0.2。既有放置脚本开头还留有“直放不下降”的历史说明，不能替代parameters.json。本轮不改生产脚本/参数。

## 尚未完成，禁止混淆

- **没有新增可实际调用并完成取放的ROS功能块**；新增的是离线合同与参数准备。22项测试是纯Python，不是ROS模拟Action测试，也不是真实点云/cuRobo回放。
- 现有scripts/run_task_pick_reset_timing.py在VERIFY_AFTER_LIFT_PARALLEL后立即LOWER230。单独ScanPick不能通过直接运行该脚本实现。还需在canonical已有任务所有权下提取HOLD结束入口及持久payload_session，不能靠脚本名称包装或提前杀进程实现。
- Place合同阶段已经定义，但未将run_dmp_place_demo.py的真实release/readback/retreat证据接到RunBlock；不宣称Place提取完成。
- Mac未安装ROS/catkin；新Action未编译、MD5未生成、真实Action反馈/取消/BUSY/重启测试未运行。拒绝节点不是最终机器人执行桥。
- 离线ReplayJobs仅验证事务语义；正式运行须复用canonical全局锁，不能拿该SQLite当第二套硬件任务锁。
- 五份文件SHA锁定不等于全部运行依赖闭包已绑定；tool、SDK/native、scene、碰撞策略和payload版本仍须在最终prepare时由canonical校验。

## 下一步：只推进一条主线

先实现P01/P02共享的canonical Pick-HOLD适配（原Golden入口保持原行为）→接RunBlock→Ubuntu/Noetic真实Action测试→现场独立Pick验收。之后再接Place；不同时扩展新工位、WebUI、速度或规划算法。

三个现场验收按顺序执行：

1. **跨机器ROS**：先验证业务机解析、Master及双向TCPROS，错误Goal无运动拒绝，再按现场批准测试U01；收到反馈和最终结果，不依赖SSH。
2. **独立ScanPick**：仅在canonical适配、ROS测试均完成后，择P01/P02之一；fresh检测→预抓取→接触→夹持→抬升→HOLD，记录实际TCP/夹爪/工具、session；不得自动放回。
3. **独立ScanPlace**：仅在放置适配完成后，使用同一session；fresh检测→预放置→下降→释放确认→退出→可选center，完整保存结果。控制器受理不等于实际运动。

尚未完成的代码步骤不能直接交给现场同事用当前拒绝节点做运动。原Demo01可继续使用。

## 验证

- 新离线Python合同测试：22/22通过。
- 原CenterRestore Python测试：17/17通过（正确PYTHONPATH下）。
- 既有ROS消息、Golden源码、生产参数未修改。
- 公共提交不含私有归档、点云、厂家SDK、客户nodeapp或凭据。
