# CURRENT QUEUE — 2026-09-20

Master roadmap:

~~~text
docs/roadmaps/2026-09-20_BODY_POINTCLOUD_DUAL_ARM_AVOIDANCE_ROADMAP.md
~~~

## Completed and pushed

### P0 — BODY-camera calibration

Completed. Production T_body_camera is COMMISSIONED.

### P1 — BODY pointcloud + viewer

Pushed to integration branch:

~~~text
c5ed44515cbe4d5e298f74117f4ac02bbccb3f20
feat(perception): add canonical BODY cloud viewer
~~~

Result:

~~~text
BODY_POINTCLOUD_READY_FOR_SELF_FILTER = YES
BODY_CLOUD_VIEWER_READY = YES
LIVE_VIEWER_PROTOTYPE_READY = YES
~~~

## Active now

### P1.5 — .32 Git branch realignment before P2

Execute first:

~~~text
docs/work_orders/2026-09-20_P1_5_DOT32_GIT_REALIGN.md
~~~

Reason:

~~~text
GitHub official integration HEAD = c5ed445
.32 local integration HEAD       = 2efbdb4

patch contents are equivalent,
but commit histories diverged.
~~~

P2 must NOT start until .32 official integration branch points to the exact same canonical commit as GitHub and the worktree is clean/preserved.

Exit gates:

~~~text
DOT32_INTEGRATION_ALIGNED_WITH_GITHUB = YES
WORKTREE_CLEAN_FOR_P2 = YES
~~~

## Next after P1.5

### P2 — whole dual-arm collision model + self-filter

~~~text
docs/work_orders/2026-09-20_P2_WHOLE_DUAL_ARM_COLLISION_MODEL.md
~~~

Order inside P2:

~~~text
asset audit
→ whole-robot collision overlay on raw BODY cloud
→ self-filter with SAME geometry
→ inactive-arm obstacle representation
→ offline regression
→ P3 go/no-go
~~~

Do not start P3 inside P2.

## Recorded next

### P3
~~~text
docs/work_orders/2026-09-20_P3_PRODUCTION_POINTCLOUD_CUROBO_DEMO.md
~~~

### P4
~~~text
docs/work_orders/2026-09-20_P4_WEBUI_TERMINAL_FRONTEND.md
~~~

### P5
~~~text
docs/work_orders/2026-09-20_P5_POINTCLOUD_THROUGHPUT_WATCHDOG.md
~~~

## Stage push policy

From P2 onward:

1. finish one phase;
2. run tests;
3. create a local commit on feat/e2e-v0-integration-20260917;
4. STOP and report;
5. DO NOT push automatically;
6. user returns to ChatGPT;
7. push only after explicit review instruction.

No force-push. No blanket reset/revert.

## User action rule

If physical user input is required, ask exactly one action:

~~~text
USER ACTION N
目的：
你现在做：
完成后回复：
安全边界：
~~~

## Current motion boundary

P1.5 and P2 require no AMR, arm, or gripper motion.
