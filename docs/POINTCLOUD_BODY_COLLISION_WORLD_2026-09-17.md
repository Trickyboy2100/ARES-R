# BODY-frame collision world结果（2026-09-17）

## 状态

```text
CAMERA multi-plane      PASS
LEVEL candidate         PASS
vendor cam2Base         NOT FOUND
automatic BODY pose     INCONCLUSIVE
BODY overlay gate       FAIL (global ambiguity)
BODY ROI                NOT RUN
robot/tool self-filter  NOT RUN
known table geometry    NOT COMPILED
unknown BODY AABB       NOT GENERATED
SceneSnapshot           NOT FROZEN
```

这是工作单要求的fail-closed结果。虽然生成了诊断overlay，矩阵存在多解，因此不得继续用其中任一解删除机器人或桌面点；否则可能把真实障碍误删。

没有self-filter前后点数，也没有BODY residual cluster/AABB数量。此前camera-frame的28–31个AABB仍只属于算法实验，未升级为BODY障碍。

机器可读状态为 `worklog/generated/body_collision_world.json`。外部可视证据：

```text
/home/yikun/ARES-R_AUDIT_20260917/body_registration/support_planes/
/home/yikun/ARES-R_AUDIT_20260917/body_registration/auto_registration_v2/
/home/yikun/ARES-R_AUDIT_20260917/body_registration/auto_registration_robot_roi/
```

下一次获得可追溯外参后，严格恢复 `BODY transform → ROI → 双臂/tool self-filter → support slab → residual cluster/AABB`，并重新生成全部06–10图。现有诊断矩阵不得作为该流程输入。
