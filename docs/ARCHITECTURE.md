# Target architecture

```text
Task state machine
  ├── Base/navigation adapter
  ├── Epic Pro client and protocol parser
  ├── Frame/pose validation
  ├── Motion planner
  ├── JAKA trajectory executor
  ├── Gripper adapter
  └── Safety and recovery supervisor
```

建议状态：

```text
READY -> PICK_SCAN -> PLAN_PRE_GRASP -> APPROACH -> GRASP ->
VERIFY_GRASP -> RETREAT -> TRANSPORT -> PLACE_SCAN ->
PLAN_PRE_PLACE -> INSERT -> RELEASE -> VERIFY_RELEASE -> RETRACT -> READY
```

长距离运动应使用经过限位和碰撞检查的关节轨迹；抓取接近、抬升、放置插入和退出保留短距离受约束直线运动。
