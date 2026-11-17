"""Short operator-facing explanations, with full diagnostics kept in evidence."""
import re


def failure_summary(job):
    error = str(job.get("error") or (job.get("result") or {}).get("error_code")
                or job.get('failure_reason') or (job.get('execution_result') or {}).get('reason') or "")
    if not error:
        return None
    result = job.get("result") or {}
    code, title, action = "TASK_FAILED", "任务未完成", "展开技术详情，核对失败阶段和原始日志。"
    phase = job.get("phase") or job.get("stage") or "UNKNOWN"
    controller = re.search(r"errcode=(\d+)", error)
    if 'MIRROR_TCP_ARRIVAL' in error:
        code, title = 'MIRROR_TCP_ARRIVAL_FAILED', 'TCP镜像到位回读未通过'
        phase = 'TCP_ARRIVAL_VERIFICATION'
        action = '展开查看TCP实际位置、朝向及目标误差；不会自动修正或续跑。'
    elif 'MIRROR_SOURCE_TOOL_CHANGED' in error or 'MIRROR_DESTINATION_TOOL_CHANGED' in error:
        code, title = 'MIRROR_TOOL_CHANGED', '镜像任务绑定的工具标定已变化'
        phase = 'TOOL_REVISION'
        action = '确认活动工具及标定后重新读取并求解。'
    elif 'actual telemetry connection closed' in error:
        code, title = 'MIRROR_SOURCE_FEEDBACK_LOST', '镜像参考臂反馈连接中断'
        phase = 'SOURCE_ARM_MONITOR'
        action = '检查控制器反馈连接；任务已退出，不会自动续跑。'
    elif "'NoneType' object has no attribute 'update'" in error:
        code, title = 'MIRROR_STATE_ASSEMBLY_FAILED', '镜像状态数据装配失败'
        phase = 'STATE_PREPARATION'
        action = '旧SDK返回空状态；需使用成功的native实际状态重新建立任务。'
    elif 'START_STATE_CHANGED' in error:
        code, title = 'START_STATE_CHANGED', '执行前实际关节与计划起点不一致'
        action = '查看 actual/expected 关节差值，重新读取并求解。'
    elif 'MIRROR_SOURCE_ARM_MOVED' in error:
        code, title = 'MIRROR_SOURCE_ARM_MOVED', '镜像参考臂发生变化'
        action = '确认参考臂静止后重新发起镜像。'
    elif 'MIRROR_MUTUAL_COLLISION' in error or 'MIRROR_SELF_COLLISION' in error:
        code, title = 'MIRROR_ROBOT_COLLISION', '镜像路径的机器人几何检查未通过'
        action = '展开详情核对具体连杆对。'
    elif 'MIRROR_PATH_COLLISION' in error:
        code, title = 'MIRROR_PATH_COLLISION', '镜像路径与场景障碍重叠'
        action = '查看具体连杆和障碍物，核对场景与模型。'
    elif "READONLY_NATIVE_SNAPSHOT_FAILED" in error or 'MIRROR_NATIVE_SNAPSHOT_FAILED' in error or controller:
        code = "CONTROLLER_STATE_READ_FAILED"
        title = "控制器状态读取未通过"
        phase = "CONTROLLER_PRECHECK"
        action = "核对控制器当前报警，以及 SDK 与 native sender 的状态回读。"
        if controller:
            code = "JAKA_" + controller.group(1)
            title += " · JAKA " + controller.group(1)
    elif "planner socket" in error or "FAST_PLANNER_NOT_READY" in error:
        code, title = "PLANNER_SERVICE_UNAVAILABLE", "规划服务未就绪"
        action = "检查 planner 服务及其 socket 配置。"
    elif "SCAN_FAILED" in error or "live scene build failed" in error:
        code, title = "SCENE_SCAN_FAILED", "场景扫描失败"
        action = "检查相机连接和本次扫描日志。"
    elif "INVALID_START_COLLISION" in error:
        code, title = "START_COLLISION", "规划模型检测到起点碰撞"
        action = "查看模型与点云叠加，核对碰撞对象和当前关节状态。"
    elif "timeout" in error.lower() or "timed out" in error.lower() or "DEADLINE" in error:
        code, title = "TASK_TIMEOUT", "当前阶段超时"
        action = "检查该阶段的服务状态和耗时记录。"
    elif "IK" in error and ("FAIL" in error or "failed" in error):
        code, title = "IK_FAILED", "目标位姿求解失败"
        action = "核对目标坐标系、TCP 和关节分支。"
    markers = result.get("dispatch_markers")
    return {"code": code, "title": title, "phase": phase, "action": action,
            "motion_dispatched": bool(markers) if isinstance(markers, list) else None,
            "log_path": job.get("log"), "evidence_path": job.get("output"),
            "details": error}
