# SIFT抓取/专机放置站位登记与返回记录

本轮只做DMP站位登记、ID7只读检测、底盘返回SIFT站附近。没有执行机械臂/夹爪动作，没有开始完整SIFT取放。
Golden `demo-3-branch-sift-graspreset`、其冻结参数和SIFT站位快照未修改。

## 站位

两站保存在 `config/manipulation_stations.json`，地图379、UUID `daed22ba-a4fa-11f1-8205-bca8a6793fdd`。

|站位|SLAM X m|SLAM Y m|yaw deg|用途|
|---|---:|---:|---:|---|
|SIFT-BLC-GRSP|0.202325|0.753431|−4.836330|已验证筛网前半程的抓取站，原记录保持|
|DMP|−0.997630|0.637518|169.662003|新专机放置站，当前临时登记|

这是SLAM观测，不是毫米级物理测量。DMP登记confidence原值38.83；静止期间观测可漂移数厘米/数度。
AMR地图实际位置列表只有既有其他点，没有SIFT/DMP，故未冒用其他posId或宣称命名导航已commission。

## ID7检测

首次5700 connection refused；现场启动后 `320,2,7,1,1,0` 检测成功，2.222秒。
原始响应：

```text
320,0,1,1,1,2,7,0,0,0,0,0,446.01093,-435.41791,-73.69666,90.69647,177.36096,47.56673
```

沿现有right-arm-base→BODY链计算的位置 `[0.623264310,−0.192509604,1.126303340]m`，仅供后续放置接口核对。
没有应用旧烘干机泊位偏置或筛网抓取目标平移，也没有生成放置执行轨迹。
ID7参数只在检测进程内覆盖，config/system.json未改。复用了右臂ID3 parser的单位/手眼解释，原始meta内继承的COMMISSIONED并不代表新ID7放置语义已验收；注册表明确标记DETECTION_ONLY_CANDIDATE_NO_MOTION。

证据：`worklog/evidence/sift-dmp-station/1793261415137810318/`。

## 实际返回

现场已确认直达通道和约175°转向扫掠净空、可持续观察。使用既有canonical `base_move`、0.1m/s、collisiondetection=1，逐段等待BaseMotionObserver停稳；每次移动使旧scene/trajectory失效。机械臂和夹爪不动。

|阶段|BODY请求|墙钟秒|
|---|---|---:|
|平移1|X−0.730662m、Y−0.169214m、yaw0|20.246|
|平移2|X−0.345362m、Y−0.132122m、yaw0|12.668|
|恢复朝向|yaw−177.253337°，原地|37.357|

命令平移长度总计1.119772m，三阶段含停稳累计70.271秒。
结束SLAM `[0.155239,0.781594,−5.580490°]`，相对登记SIFT位置误差54.866mm、朝向误差−0.744160°，confidence原值49.13。
证据：`worklog/evidence/sift-dmp-station/return_1793261833805771182/`。

返回后两次ID6只读检测分别2.523/1.647秒，均 `000,3020`。因此状态是 **RETURNED_NEAR_SIFT_VISUAL_ALIGNMENT_PENDING**，不是抓取就绪，也不是精确站位导航验收成功。
不能复用旧抓取轨迹或自动启动Golden；下一步先确认原夹具中筛网及相机视野，重新识别/对位后再fresh规划。
本轮不再发送运动命令，未修改Golden冻结SIFT站位来掩盖回程差异。
