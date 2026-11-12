# 功能块01：CenterRestore ROS1 API

- Block ID：`utility.center_restore.right.v1`
- ROS包：`ares_r_center_restore`
- Action：`/ares_r/center_restore`
- 类型：`ares_r_center_restore/CenterRestoreAction`
- 旧`/ares_r/return_center` v0.2不改语义、不改MD5。

## Goal

| 字段 | 合同 |
|---|---|
| request_id | 必填唯一业务ID；同请求重发沿用，永久不自动重跑 |
| target_mode | CAPTURE_START或SAVED_POSE_REF，禁止隐式切换 |
| saved_pose_id | SAVED_POSE_REF必填，例如本次保存的right/front_right_high_axes_aligned |
| expected_saved_pose_sha | 保存记录文件原始字节SHA256，SAVED_POSE_REF必填；变更即拒绝 |
| onsite_observer_confirmed | 现场观察与急停条件确认 |
| prepared_environment_confirmed | 路径净空、控制器健康、底盘与左臂保持等确认 |
| empty_hand_confirmed | 空手/无负载确认；未知不运动 |

CAPTURE_START在运动前保存当前关节与BODY TCP、tool、基座/标定/模型绑定。SAVED_POSE_REF读取实际注册表和可核对的记录文件，SHA不匹配或同名来源不唯一即拒绝。两腿全程不移动底盘。

## Feedback / Result

Feedback：stage、phase、run_id、elapsed_s。

Result：success、terminal_state、return_to_saved_pose_verified、run_id、center_arrival_json、saved_arrival_json、evidence_uri、error_code。

两腿均确认后才SUCCEEDED。center确认后第二腿失败返回CENTER_ARRIVED_RESTORE_FAILED；未知执行回执返回UNCERTAIN，不自动重发。额外Goal返回BUSY，不抢占正在运行的Goal。保护停返回失败/恢复要求，禁止继续返程。

每个到位结果包含实际BODY TCP、误差、连续新鲜样本、控制器状态、native结果及Servo退出。保存姿态另核对六关节最大误差≤0.05°；TCP沿用3mm/3°合同。

## 同一canonical任务

内部使用8775 `/api/demo-console/start/status/stop`，新增别名`block-01-center-restore-right`。一项HTTP job与一项ROS Goal绑定，runner内部顺序执行两个fresh cuRobo腿。不会启动两个独立ReturnCenter任务。

取消经所属job发软件停止并确认，无法确认则RECOVERY_REQUIRED；停止/故障后不自动继续。任务记录在canonical根的`worklog/evidence/demo-console/<run_id>/block/`，每腿各有plan_handle、scene ID、native文件、真实到位结果。

## 本次已保存目标

ID：`right/front_right_high_axes_aligned`。
源记录SHA：`bbcd723fc83d1091b9065ed2636e6689e52987c9cfa8a8e3db5defac16a7499a`。
绑定目标内容revision：`46adb9b0d941eba8c9fe16af756a68609aa545a850e01c503069274a86305982`。

以上只标识本次记录，不能默认用于未来工位或修改后的工具。实际位姿/关节原文在私有交付记录中。

## 验收与使用

本次SAVED_POSE_REF真实两腿已通过；CAPTURE_START只有逻辑验证，尚未另做实机验收。正式客户端请通过actionlib发送Goal并等待Result，不直接向/goal话题连续重复发布。

操作示例（仅格式，执行前按真实记录填入）：

```python
import rospy, actionlib
from ares_r_center_restore.msg import CenterRestoreAction, CenterRestoreGoal
rospy.init_node('center_restore_client')
c = actionlib.SimpleActionClient('/ares_r/center_restore', CenterRestoreAction)
c.wait_for_server()
g = CenterRestoreGoal(request_id='new-business-id', target_mode='SAVED_POSE_REF',
    saved_pose_id='REGISTERED_POSE_ID', expected_saved_pose_sha='VERIFIED_SHA256',
    onsite_observer_confirmed=True, prepared_environment_confirmed=True,
    empty_hand_confirmed=True)
c.send_goal(g)
c.wait_for_result()
print(c.get_result())
```
