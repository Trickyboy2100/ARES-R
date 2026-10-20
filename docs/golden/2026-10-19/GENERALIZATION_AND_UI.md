# 下一开发分支：可解释、可分阶段、可泛化

本文件是实现工作单，不宣称功能已经完成。本golden分支冻结现场成功实现；优化在独立分支推进，每项通过真实回放后再合入候选版本。

## WebUI/ART共用模型解释

默认显示三视图+透视图；BODY +Y左、+X前、+Z上。点击任何碰撞体显示：类型、来源帧/时间、ID、原始点数、原始尺寸、inflation后尺寸、TCP/link6变换、revision、当前用于哪些检查。
固定图例：原始点灰、环境障碍红、持物紫、机器人蓝、夹爪青、目标绿。可单独隐藏“显示”，不改变实际碰撞开关。
故障直接显示碰撞pair和最近位置，附两者原始点与模型；不能只显示409。模型厚度、旧cluster包围盒、实际附着体组件分开显示。
顶部时间条：扫描/重建/IK/solve/验证/等待/执行；FAST/QUALITY和重试次数明确可见。失败恢复记录单独链接，不能覆盖原FAULT。
阶段卡：输入来源、输出、预计时长、真实时长、最后通过的检查；“仅预览”“从已验证checkpoint恢复”与“运行完整Demo”分开。

## 持物推断改进

现有问题已证明是源cluster混入支撑/物体后直接整体AABB；尚无证据证明唯一根因是拍照角度。新算法需记录检测时机、机器人姿态和遮挡程度。
抓前分离target/support，夹持后结合gripper读回、TCP邻域pre/post差分；抬起后在足够可见时验证随TCP运动的点集合。明确target ownership与世界障碍去重。
物体形状在object frame保存，随TCP刚性变换；不能每次BODY朝向改变就重新膨胀为宽大的BODY轴对齐盒。
优先复用已知物体类别模板和识别尺寸；未知物体可自动估计并提供不确定性/可视化确认。避免每换物体都要求人工输入尺寸。低置信度不把整个dock当payload。

## 站位和多泊位

保留原GRASP/PLACE注册表，新增语义alias SCALE_FRONT（称前站）→GRASP、DRYER_FRONT→PLACE；当前仅相对路线，不伪造SLAM绝对坐标。
路线双向显式存储，绑定站位revision、base yaw、载荷/机械臂包络。现有40/81/32与32/81/40作为已验证路线保留。
六泊位状态：UNKNOWN/EMPTY/RESERVED/OCCUPIED/ERROR；取放先reservation，传感确认后commit；失败释放或保留人工复核锁。UNKNOWN不自动当EMPTY。
五次连续任务使用同一transfer Skill和slot selector，不复制五段Python。反向任务显式指定source slot→scale reference、检测profile与取放局部偏置；不能简单反转旧joint path。

## 并行可行性

先做低耦合并行：证据写盘、UI更新、静态模型加载、下阶段配置准备。5700/5000是否能并行取决于同一相机设备仲裁，不能默认双线程就安全且更快。

底盘移动时收臂、抬升50mm后底盘后退均改变环境相对BODY的位置；当前静止BODY SceneSnapshot和独立arm/base executor不能直接支持。需要：

- 时间同步base轨迹与arm轨迹、WORLD↔BODY时变变换；
- whole-robot+payload联合扫掠验证，moving-base controller/observer；
- base/arm共同资源租约、统一停止、误差预算和可恢复状态；
- 50mm触发基于实际TCP和验证后的脱离接触条件，不用sleep或命令已发送代替。

分三步：离线联合回放→场地监督低速commissioning→正式并行profile。当前保持串行golden，thread_count=2不能作为并行运动验收。
优先估算收益：只可隐藏两任务较短者时长，扣除同步开销；返程收臂若任务根本不需要收臂，增加收臂并非提速。
