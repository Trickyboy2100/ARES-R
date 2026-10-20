# PLACE recovery physically completed — 2026-10-19

Result: **PLACED_RELEASED_RETURNED_GRASP**.

Operator approval: “确认，开始”, following the successful 160×100 mm exposed-payload planning preview. The prior full Demo fault remains preserved; this is a successful **recovery**, not an uninterrupted full-cycle commissioning result.

| Stage | Result | Observed stage wall time |
|---|---|---:|
| Fresh scene and cuRobo candidate refresh | PASS, first FAST attempt | 15.03 s |
| Move current→preland | ARRIVED | 22.04 s |
| Continuous BODY Z−50 mm descent | ARRIVED | 26.85 s |
| Gripper release raw400 | Readback confirmed | 1.26 s |
| Detach payload | PASS | 0.10 s |
| Base back320 mm | Completion/settle confirmed | 16.77 s |
| Base left810 mm | Completion/settle confirmed | 23.28 s |
| Base forward400 mm | Completion/settle confirmed | 18.27 s |

Observed event span: **125.34 seconds**, including stage transitions and validation. This is not the duration of the entire original pick→place Demo.

No pick or lift was repeated. No arm stow was performed. Arm remains in its post-release posture. Controller protections, physical speed ceilings, pointcloud obstacles and original fault records were retained.

End read-only right-arm state: errcode0, in_position=true, protective_stop=false, emergency_stop=false, on_soft_limit=false, tool1. Right BODY TCP XYZ approximately `[0.760520214,-0.015813167,1.164065877]` m. The existing Demo-local −10° orientation compensation was retained.

Release command/readback confirmation is recorded; no force-controlled insertion or independent visual certification of final tray seating is claimed. Base completion is command-route/settle evidence, not precision SLAM station certification.

## Selected physical execution

The preview candidate was refreshed before execution because of its age. Fresh target remained within the approved3mm tolerance. A new SceneSnapshot, validated path and native execution package were generated, rather than extending the old expiry or bypassing a stale lease.

Executed plan: `PLAN_fef112e7a5a04b368f26eda1794344ad`.

Executed trajectory: `sha256:8f02bae69c6b1216e64678082ebd7c9ac01826957c12ac6093299b449abfe44a`.

Source fault run: `af491998a03e4ecaaa524a3504583889`.

Model scope: this recovery uses the explicitly approved exposed160mm/width100mm/original-height attachment, with rear20mm included in the common collision enclosure. It does not prove generic object segmentation is fixed. The original historical package and golden first-pick demo were not rewritten, and default future Demo payload generation has not yet been migrated to this recovery-specific model.

## Evidence

Server: `/home/yikun/ARES-R-RC1-20261019/worklog/evidence/operations-single/20261019-v17-approved-place160-return/`.

Local: this directory contains `REPORT.json`, `events.json`, `after.json`, `PLACE_DESCENT50.json`, and `RELEASE.json`.

The original WebUI Demo may still show its historical MOVE_PRELAND fault: the recovery did not overwrite that record to fabricate an uninterrupted success. The recovery REPORT above is authoritative for the successfully completed remaining stages.
