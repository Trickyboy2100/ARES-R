#!/usr/bin/env python3
"""Demo02 dual-arm client; independent from Demo01."""
import argparse,json,uuid
import rospy,actionlib
from ares_r_dual_center_restore.msg import CenterRestoreAction,CenterRestoreGoal


def main():
    parser=argparse.ArgumentParser(description='双臂扫描 → 各自center → 各自保存姿态')
    parser.add_argument('--execute',action='store_true',help='确认空手、净空、现场监督与急停后启动实机')
    parser.add_argument('--target-mode',choices=['CAPTURE_START','SAVED_POSE_REF'],default='CAPTURE_START')
    parser.add_argument('--saved-pose-id',default='')
    parser.add_argument('--saved-pose-sha',default='')
    args=parser.parse_args(rospy.myargv()[1:])
    if args.target_mode=='SAVED_POSE_REF' and not (args.saved_pose_id and args.saved_pose_sha):parser.error('paired saved pose ID and SHA required')
    if not args.execute:
        print('未启动运动。现场准备完成后加 --execute。');return 0
    rospy.init_node('center_restore_client',anonymous=True,disable_signals=True)
    c=actionlib.SimpleActionClient('/ares_r/dual_center_restore',CenterRestoreAction)
    if not c.wait_for_server(rospy.Duration(10)):
        print('ROS功能块未连接，请检查master/节点。');return 1
    goal=CenterRestoreGoal(request_id='client-'+uuid.uuid4().hex,target_mode=args.target_mode,
        saved_pose_id=args.saved_pose_id,expected_saved_pose_sha=args.saved_pose_sha,
        onsite_observer_confirmed=True,prepared_environment_confirmed=True,empty_hand_confirmed=True)
    last=[None]
    def feedback(v):
        text={('center_leg','PRECHECK'):'读取状态、扫描并规划到center',
              ('center_leg','EXECUTE'):'运动至center并确认到位',
              ('restore_leg','PRECHECK'):'重新扫描并规划到双臂保存姿态',
              ('restore_leg','EXECUTE'):'运动至双臂保存姿态并确认到位'}.get((v.stage,v.phase),v.stage)
        if text!=last[0]:print('%s（%.1f秒）'%(text,v.elapsed_s),flush=True);last[0]=text
    c.send_goal(goal,feedback_cb=feedback)
    try:
        if not c.wait_for_result(rospy.Duration(1500)):
            c.cancel_goal();print('等待超时，已请求停止；请核对后端实际停止状态。');return 1
    except KeyboardInterrupt:
        c.cancel_goal();print('已请求停止，等待实际停止结果……',flush=True)
        if not c.wait_for_result(rospy.Duration(30)):
            print('停止尚未确认，请现场核查。');return 1
    result=c.get_result()
    print(json.dumps(dict(success=result.success,state=result.terminal_state,
        restored=result.return_to_saved_pose_verified,run_id=result.run_id,error=result.error_code),ensure_ascii=False))
    return 0 if result.success else 1


if __name__=='__main__':raise SystemExit(main())
