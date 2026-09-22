# 2026-09-22 Right-arm A/B CLEAR supervised demo

Status: **B→A→B completed on hardware**. Each leg used a fresh Pixel Pro capture,
fresh dual-arm read-only state, fresh SceneSnapshot and a new cuRobo direct
start→goal plan. No explicit waypoint was supplied. The BODY-forward,
horizontal-TCP orientation constraint remained active. No AMR, left-arm or
gripper motion was commanded.

| Leg | Snapshot | Geometric trajectory hash | Dense modeled clearance | Native duration | Peak measured tracking error | Result |
| --- | --- | --- | --- | --- | --- | --- |
| B→A | `SCENE_98d599344e4045368742648268a74b35` | `sha256:56c26833e858a656765f2362e97b8de924045c6b5fcdf2537d15e768acdec098` | 33.06 mm | 25.98 s | 0.3524° | `target_reached`, servo disabled, logout |
| A→B | `SCENE_61d65a9f7713420c95cd9dc9f180fb84` | `sha256:85754af252c56a57e52cde28288b0978a446aeacbba54a61f44015cca2c1324f` | 31.84 mm | 25.96 s | 0.3210° | `target_reached`, servo disabled, logout |

The right supervised sender hard tracking-abort threshold was set to 0.5°;
other native modes retained 0.2°. The A/B sender ceiling was 0.070 rad/s,
with 0.10 rad/s² acceleration ceiling and 80 ms samples. Both legs had an
offline predicted tracking error of about 0.480°. This was a scoped trial,
not a general commissioning of that speed profile.

At B, four repeatable point-cloud components near the tool lay 20–40 mm
outside the pinned gripper box. For this demo, only gripper-owned points used
a 40 mm sensor margin; other robot boxes and environment obstacles retained
their prior rules. The A/B planner and independent validator both used a
conservative demo-only tool envelope enclosing the pinned gripper and these
observed points. The 30 mm modeled clearance acceptance applied to these
two fresh plans. `TOOL_TCP_PHYSICAL_SEMANTICS_UNRESOLVED=YES` remains in force;
this trial does not validate the physical TCP or a production tool model.

Evidence root: `worklog/evidence/2026-09-22-p3-3a-clear-fastlane/`.
The leg-specific directories are `art_scan_20260922T092335Z`,
`supervised_b_to_a_gate05_20260922T0926Z`, `art_scan_20260922T092633Z`,
and `supervised_a_to_b_gate05_20260922T0928Z`. Native logs contain every
80 ms feedback sample and the abort/servo-off/logout events. After completion,
the active-sender manifest was absent and the right controller reported
`inpos=1`, `queue=0`, `active_queue=0` at B. The robot was not commanded again.

Verification: `PYTHONPATH=src python3 -m unittest discover -s tests -q`:
430 tests, OK, one skipped. No GitHub push was performed.
