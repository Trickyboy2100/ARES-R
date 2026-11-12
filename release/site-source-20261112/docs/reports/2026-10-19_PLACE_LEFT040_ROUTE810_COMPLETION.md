# PLACE +Y40mm and 81cm lateral-route retry

Independent runtime `/home/yikun/ARES-R-RC1-20261019`. User explicitly requested BODY-left40mm, new PLACE, outbound40/81/32cm and return32/81/40cm, then retry placement.

Completed physically:

1. PLACE left40mm, yaw command0; completion log72649/queue11328, settled. New PLACE observed map379 pose `[-0.9810510278,-0.3035790026,-113.56199646deg]`; confidence raw25.87. SLAM remains a noisy observation, not precision truth.
2. Fresh ID3 plus registered lower-middle offset. New preland BODY `[0.7586878503,-0.0363775024,1.2097934645]` m.
3. FAST cuRobo succeeded first attempt; scan/detection/planning total26.477s. Plan `PLAN_f4be267535fa4362bd673076164e8ac4`; hash `sha256:8e13a45832cee89acbeb4625fddd4c8e10809f6d70043ea46c4a1abda8568971`. Modeled minimum gap2.2298mm, no collision-disable or point deletion. Exact previewed trajectory physically reached preland.
4. First descent attempt stopped BEFORE dispatch due a software `KeyError: errcode` for inactive-left `MINIMAL_READONLY_COLLISION_STATE`. Fixed formal `validate_place_dispatch_state`: full active-right controller health remains mandatory; left minimal scope requires unchanged finite joints/tool and rejects known faults, but does not claim full left-controller health. Four regression tests added. 768 total tests, one skipped, remaining passed.
5. Recovery confirmed preland arrival and absence of prior descent dispatch receipt. No preland movement repeated. Formal `Live.place_descend(.05)` acquired a new attached scene, validated local-contact descent and retimed native path, physically descended50mm, confirmed target and servo disable. Stage wall26.951s including scan/checks/native/settle.
6. Gripper raw400; release readback confirmed. Detached object, then physically returned by BODY back32cm, left81cm, forward40cm. Stage walls18.671/23.175/16.171s. No arm stow.

Final physical outcome: `PLACED_RELEASED_RETURNED_GRASP`. Right gripper is open; arm remains in post-placement posture. This is successful recovery completion, NOT an uninterrupted full-cycle commissioning claim. Original canonical fault/checkpoint history remains preserved.

Configuration/source changes: `config/grasp_place_base_route.json` V5; Demo parameters V15 netPLACE `[-0.08,-0.81,0]`; `src/ares_r/manipulation/roundtrip_demo.py` version contract supports V5 and preserves V4/85cm replay; WebUI roundtrip description updated; formal descent state-field compatibility fixed in `scripts/run_grasp_place_roundtrip.py` and `src/ares_r/manipulation/live_roundtrip_contract.py`.

Site evidence:

- `worklog/evidence/base-routes/20261019-place-left040/`
- `worklog/evidence/20261019-new-place-left040-preland/`
- `worklog/evidence/operations-single/20261019-new-place810-finish/` (preland success and pre-dispatch field error)
- `worklog/evidence/operations-single/20261019-new-place810-after-preland/` (successful descent, release, return)
- `worklog/evidence/20261019-place810-state-field-tests.log`

No push requested or performed. Original production checkout and golden first-pick unchanged.
