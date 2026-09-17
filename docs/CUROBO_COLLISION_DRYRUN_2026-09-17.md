# cuRobo collision dry-run gate（2026-09-17）

## 结果

BLOCK/FREE planning-only测试未运行。原因不是cuRobo不可用，而是上游Phase C没有得到唯一稳定的 `T_body_camera`，所以不存在合法BODY collision world、ObservationEpoch或SceneSnapshot。使用歧义外参构造BLOCK/FREE场景只能证明人工cuboid会影响planner，不能证明真实点云进入了碰撞世界。

对应机器状态：

```text
execution_allowed=false
planning_ready=false
curobo_block_test=NOT_RUN
curobo_free_test=NOT_RUN
```

工作单规定A–G全部成立后才能进入Phase H；因此左右臂 `current→up` cuRobo planning-only也没有生成。当前精确缺口为：

1. 唯一且可验收的 `T_body_camera`；
2. BODY ROI/self-filter/table separation结果；
3. 同一ObservationEpoch冻结的SceneSnapshot；
4. 左臂经过审计的controller↔cuRobo model校正和arm-parameterized worker；
5. 完整夹爪/tool/inactive-arm collision geometry。

本轮没有执行任何JAKA、夹爪或AMR运动API，`execution_enabled=false`保持不变。
