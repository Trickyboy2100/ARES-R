# 烘干箱六泊位偏置坐标切换

## 坐标合同

六泊位共用人工指定的烘干箱角点参考原点。D 为 Epic 返回的检测物体坐标系，不是 CAMERA frame，也不能自动等同于 TCP frame。检测姿态与 TCP 期望姿态的关系仍由抓放任务定义。

正面朝向烘干箱时，约定 D +X = BODY -Y，D +Y = BODY -Z，D +Z = BODY +X：

```text
R_BODY_D = [[ 0,  0,  1],
            [-1,  0,  0],
            [ 0, -1,  0]]
delta_BODY = R_BODY_D * delta_D
delta_D = transpose(R_BODY_D) * delta_BODY
```

例如 D `[100,200,300]` mm 等价于 BODY `[300,-100,-200]` mm。矩阵只转换偏移向量，不凭空提供参考原点位置。实际泊位目标仍使用完整链 `T_BODY_TARGET = T_BODY_CORNER * T_CORNER_TARGET`。

RPY 表示相对检测参考姿态的额外旋转，不是绝对 TCP 姿态；零表示不额外旋转。旋转增量换基采用 `R_delta_BODY = R_BODY_D * R_delta_D * transpose(R_BODY_D)`，不能直接交换欧拉角。

## WebUI 操作

打开 `/operations` 的“六泊位”。一次仅显示一种偏置表达，点击“一键切换为 BODY / 检测坐标系”。切换同时转换六组已保存值及当前未保存输入，不写配置、不修改占用状态、不触发运动。输入 XYZ 单位 mm，RPY 单位度；保存时后端统一转为 DETECTION 表达，避免维护两套互相漂移的数据。

参考点名称可在烘干箱配置中记录。所有实测偏置必须相对同一个实际角点原点；更换实际原点后应重新测量，不可仅改名称复用旧数据。

有效且新鲜的绑定检测存在时，BODY 换算优先使用该检测实际旋转；否则显式提示采用上述正面朝向约定。无有效 anchor 时仍不能计算实际目标。BODY 保存和批量切换绑定 context revision，底盘、场景或检测发生变化后旧 context 被拒绝，刷新后重新核对。

## 实现与验证

- `src/ares_r/offset_frames.py`：唯一矩阵、完整旋转换基、fresh anchor 和 context digest。
- `operations.py`：规范化保存、只读批量转换；`POST /api/operations/offset-convert` 由 canonical backend 提供。
- `webui/operations.html`：单坐标表达、一键切换、草稿保留、参考点标注。
- `tests/test_offset_frames.py`：轴向、随机及奇异姿态往返、上下文过期、保存与 full-SE3 目标一致性。

现场隔离测试环境全量运行 612 tests，OK（1 skipped）。浏览器未保存示例 D→BODY→D 验证通过。未修改实际 TCP、相机标定、规划参数或泊位测量值；未执行机械臂、底盘、夹爪运动。

现场修改前备份：`worklog/preservation/2026-10-16-offset-frames/before-source.tgz`。测试日志：`worklog/runtime/offsets-tests-20261016.log`。
