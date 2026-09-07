# 右臂实机 Demo 证据

- `curobo_20260907_144944_e85f735d/`：先行 J6 +0.2° 微动，41 点，完整到位并退出伺服。
- `curobo_obstacle_20260907_150324_bdf2224b/`：通过 ARES-R Terminal 执行的 20 cm Demo，513 点；`trajectory.preview.html` 为规划三视图与曲线回放。
- `request.json` 保留新鲜实际起点、TCP/工具偏移、模型变换与虚拟障碍参数；`trajectory.json` 保留真实 cuRobo 路径和验证数据。
- `native_execution_*.log.gz` 保留实际关节/TCP 反馈和退出结果。完整执行日志含 `target_reached`、`servo_disabled code=0`、`logout code=0`。

20 cm 结果：规划行程 193.868551 mm，实际 TCP 采样折线行程 194.319126 mm，实际起终点直线距离 159.648731 mm，最大跟踪误差 0.050748°，最终最大关节误差 0.001373°。实际 TCP 球代理采样对虚拟障碍最小间隙 8.841771 mm；不代表完整实机碰撞模型认证。

历史轨迹禁止直接当作当前起点再次执行；重新运行 `curobo demo plan20`。
