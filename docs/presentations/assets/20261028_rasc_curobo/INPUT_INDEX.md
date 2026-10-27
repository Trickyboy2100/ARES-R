# 输入与来源审计

执行基线：工作单21cd158；算法基底6866106；实际GPU worker关节映射修复8fbd669。独立工作树，未切换/修改原RC1。

| 输入 | 匿名化定位 | SHA256 / 核验 |
|---|---|---|
| 同源CAMERA原始NPY | 20261010_114817_fecbdf64 | `a9031515bada1c3859bec842d145f44d8ce407ac9af3c8fea95478d7ea463b8f`，实际读文件核验 |
| BODY NPZ | 20261010_114819_091f37ab | `ec20097e0b365e4ca9c4aaa71d0a342c0e1b8a49049c4b4ef5198cfc97420555`；原始NPY经过固定TF，float32逐元素一致 |
| 配套场景 | SCENE_133c1fca71484bd2abea0cb3e0b6af8d | 同目录whole_robot_geometry、双臂FK audit、scene_report、snapshot |
| 标定 | 固定T_BODY_CAMERA | `sha256:ccb214ea13b7020528d98d7a532908427c25d61c3ce1d40bd0a833e61a7a4e6c`；没有重新估计外参 |
| 双臂capture q摘要 | whole_robot_geometry | `d2193186e840ad031aa2de3c94ee9cfb497034de44ba01315fca9f42ed0efdaa` |
| 工具版本 | 同帧几何快照 | `sha256:323e83dce64395aef6a23c80ab97734f7db9713592977af3890ebf53a76b6fa7` |
| 原历史transit规划request | Oct10 transit_plan | `5f0bc7c8a9ebf93d186cc5cbdd3348f9d037c5dc551753d71be4ceb9e2cfa741` |
| 原历史transit规划result | Oct10 transit_plan | `c6227c6427710caaab1bb330649c57a82f4d811edae56976bea3077b3ac88869` |
| 机器人URDF | ARES@b978cbd… | `65789fd396bc33251338141bbc6b6400be48a32e67b94a1541cba7c2aeae8228`，git对象取出并与请求asset_sha256一致 |
| cuRobo | pinned 8e734f3ced1df898990bcd92de40abce475907db | worker运行时核对整个源文件Git blob manifest |

原始点云、完整关节/设备记录及派生几何保留于忽略的私有运行目录，不提交。公开输出只有经过审查的渲染、标量、匿名摘要和源码。工具通过CLI接收受控数据根目录，禁止自动采集或现场下载。

原始输入是2026-10-10采集，不能称为9/21的7→167帧，不能称为10/21的401框/431采样实验。

关键状态边界：capture q用于原始点云自体过滤；历史transit request的规划q0与capture q不同（最大约177.75°），两种表示使用相同的规划q0与目标。该离线A/B是静态冻结世界表示消融，并不证明fresh ObservationEpoch到实机执行的状态绑定通过。原历史request缺attached revision元数据，本轮仅补充身份绑定；没有删除新世界的任何基元。

本地还有10/10 160941、172331两组真实原始NPY/BODY配套数据。本轮不将它们猜测为CLEAR/AVOID/BLOCK标签。9/21原始capture与10/21 tar不在已检查的工作区/本地素材目录；具体缺口见报告。
