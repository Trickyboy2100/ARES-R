# 最小缺口与现场分镜

1. 正常完整ServoJ成对反馈：取9/24 live_pick_authorized对应pregrasp/contact/lift的native_supervised.jsonl、native轨迹、sample dt、monotonic+wall anchor、控制器错误、settling/arrived和hash。画三段正常曲线，不补采危险动作只为画图。
2. 9/21六阶段原帧：current_base_avoid/capture_pointer指向20260921_161451_830b7857 manifest + CAMERA源；BODY TF、同帧双臂q、geometry、tool与SHA。没有这些不能复现7→167/9992锚点。
3. 10/21完整study：f0e6d87e825b6f653d4154e4a1c1c31445ac2b32efc15da9d05a85f98c5188d8；cloud tar 206e2fdef8886750ca7545ee9b23596c85a9252a45a949ed54d4cca60e3bbd60（已与源报告逐字核对，归档名20261021-study-clouds.tar.gz）。需要frozen-pregrasp-only-request、pick-epoch、431采样result、旧新性能原JSON及原site runtime YAML。原路径与完整依赖清单见源报告；本轮未取得这些归档。
4. 10/19空间持物/PLACE：缺before.json bd954fef…、fresh-ID3 98d2e1d…、preland proof58f19d…、native-audit4090d29…、descent轨迹c7e5ee…及planner包86c29cd…，完整哈希在golden/prepared-artifact-gaps.json。现有尺寸/事件只能支持尺寸示意与恢复时序，place_clearance_case不伪造。
5. LOCAL_PPT_WITH_DRAGGING_DEMO_NOT_FOUND：已检查本地可读PPT媒体索引，找到三类PPT、均无嵌入视频；需要负责人指明含3D点云/包络框拖拽演示的周进度PPT。原视频许可未核准前只在本地提取，禁止公开上传。
6. 正常完整物理filmstrip：8帧 detect/pregrasp/contact/grasp/lift/transfer/place/return，保留PLACE旧故障与修正后接续标识；需要原视频授权、时间戳与run对应关系。不得拼接旧动作+新模板声称泛化成功。
7. 现场底盘固定路线/no-stow扫掠、筛网/新专机跨对象任务、精确落座、10GB视觉与规划共驻均未由本包认证。现场需带对象几何/站位、TF/tool、q/AMR实际里程、run_id、GPU峰值整卡采样和abort日志验证；本轮没有现场连接。
