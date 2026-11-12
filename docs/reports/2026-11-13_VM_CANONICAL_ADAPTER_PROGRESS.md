# 专用VM与canonical取放适配进展

## 环境

宿主机32GB/16逻辑CPU。Parallels Ubuntu22.04已配置8vCPU/12GB、multi-user.target无桌面启动；空闲实际内存约10GB。通过Parallels guest tools root执行，不需要共享sudo密码，也未增加NOPASSWD用户。恢复桌面可执行`sudo systemctl set-default graphical.target`，按需`sudo systemctl start display-manager`。

构建使用Ubuntu仓库ROS1（catkin/actionlib）、NumPy。此前Docker已安装，Docker Hub网络仍阻塞；没有把Ubuntu22.04包装成现场Ubuntu20.04/Noetic同构环境。无CUDA/cuRobo性能结论。代码测试目录为`/root/ares-offline-20261113`；没有连接机器人或GPU研究机。

## 本轮代码成果

1. 找回原有独立SIFT HOLD执行器`run_sift_lift_hold.py`和`prepare_sift_lift_hold.py`，锁定源文件SHA。此前检查pick-reset脚本后断言“必须重新提取”并不完整，实际应优先复用这两个入口。
2. 确认原HOLD入口调用`settle_segment(live,target,stage,event)`，但当前helper要求第五参数tool_id。这是实际签名错误；新适配层在私有导入模块上绑定native包工具ID，源文件不变。测试复现缺参TypeError并验证修正；VM实际导入两份原始模块并核对签名通过。
3. 增加抓取终态检查：必须有HOLD完成、持物验证PASS、三个Native段到位/Servo退出、实际关节/控制器健康回读。不能仅看子进程退出码。
4. Place复用原stage_place函数，增加release.json读数、retreat-check.json实际方向/距离及配置核验。只有退出成立后才调用原stage_center。原PLACED_AND_RELEASED字符串不能证明已退出，因为原函数允许关闭退出配置。
5. 增加受控子进程入口草案，默认物理commissioning门关闭。所有旧Action、Golden、生产源码和参数不改。没有发布可直接运动的新功能块。

## 验证

Mac新44项、旧17项Python测试通过。VM真实模块导入通过（无main/Live/SDK调用）。之前已通过的新5项、旧7项ROS通信测试继续保留，它们仍是合成执行适配器；不能将其计为本轮真实canonical运动测试。

## 剩余事项

仍需离线完成：正式canonical console所有权插件与ROS连接、真实payload session新鲜绑定、跨Goal持久交接与永久幂等、P02独立HOLD，以及冻结实际取放失败证据回放。当前Place子进程分支明确拒绝未发布的新鲜持物绑定适配，不能当作完成版使用。

实机层面仍需：当前工具/速度/偏置下的独立ScanPick、ScanPlace、取消，以及业务电脑跨机ROS通信验收。3080设备才适合真实cuRobo GPU规划回放；本VM用于接口和集成。

## 本轮ROS持久生命周期增量

新节点现在将OFFLINE请求账本、终态结果和payload session存入显式状态目录。终态Goal重发返回原run_id/原结果；启动时未结束请求标为UNCERTAIN，不自动重派。不同请求BUSY不抢占，异常/停止保留结果。每个线程单独打开SQLite连接，避免跨线程连接异常。

合成模式需同时设置`~offline_replay=true`和进程环境`ARES_R_OFFLINE_REPLAY=1`，防止残留ROS参数意外把普通节点切成合成成功路径。物理路径仍拒绝。

最终VM真实ROS验证新增4项全部通过：终态重复请求、节点重启后同run_id不重派、Pick→Place跨Goal持物session交接、Place重复请求不重复释放；原本新5项反馈/失败/取消/BUSY测试重新通过。它们共9项都是合成执行器，不是新取放实机验收。此前旧CenterRestore的7项回归保留。

未实现：正式canonical console全局owner接入及真实持物新鲜绑定、P02独立HOLD、真实取放冻结失败证据的完整链路回放。ROS离线幂等已落实，不再只是Python语义测试；生产接口仍不可启动。
