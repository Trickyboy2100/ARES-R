# TCP镜像准备与center待确认

## 已验证关节点镜像

现场任务 `mirror-1794881091879073722` 返回SUCCEEDED、target_reached=true，原生运动8.208秒，最终关节误差0.00278°，六个关节点最大镜像误差0.3064mm。此前失败与v1.1修复单独保留，不把此次成功扩展为TCP镜像已验收。

## TCP匹配

只读发现镜像后左TCP BODY位置约[0.429616,0.411076,1.617969]m，右TCP约[0.437159,-0.383267,1.607323]m。左tool2与右tool3的原始标定不同，原仅关节点模式不能保证TCP镜像。

v1.2-tcp新增默认match_tcp=true，旧模式可通过页面取消勾选或接口match_tcp=false使用。目标p=S*p_source，R=S*R_source*S，其中S=diag(1,-1,1)，使TCP X/Z作BODY反射而Y反向，保持合法右手旋转。使用活动工具实际数据，不更改工具标定。TCP优先，连杆仅尽量保持镜像；本例最大关节点偏离严格镜像约17.1mm，不能称为所有关节点严格对称。

TCP到位要求原生关节到位证明及真实TCP回读，两者都通过才成功。当前容差3mm/1°；到位缺少TCP、工具ID/标定变化、源臂反馈异常都不能标为成功。状态和原始日志保留TCP位置及朝向误差。

72项相关离线测试通过，真实厂商头文件语法检查、现场Linux native编译与参数烟测通过。当前fresh scene下81点路径通过，到native发送边界停止，尚未执行TCP镜像实机运动。模型预测0.0381mm/0.00444°，与物理到位误差区分。

## 现场入口

operations和Demo Console的双向按钮均保留，新增“同时镜像TCP位置和朝向”，默认开启。版本2026.11.17-onsite-ready-mirror-v1.2-tcp。当前左臂修正关节增量约[+2.20,-2.73,+3.87,+2.34,+2.76,-31.59]°，速度仍0.08rad/s。点击时重新读取与求解。

备份：`worklog/preservation/mirror-tcp-v1.2-20261117T103032/`
预检查：`worklog/evidence/2026-11-17-mirror-tcp/preflight-1794882694890106952/`
本地代码增量：`site-ready-20261117/mirror-tcp-v1_2.tar.gz`

## center请求

新增要求为规范center、TCP轴精确对齐BODY、目标BODY Y=0。现有center仅右臂有BODY目标，左臂为历史关节快照。已请求确认更新右臂、左臂或两臂，以及未完成消息“并且”的补充。未改center配置，未执行center运动，也未将未验收新目标标为commissioned。后续应保留旧center与证据、统一各入口读取同一目标，避免WebUI常量与ROS配置不一致。
