# Transfer-chain atomic Skill implementation checkpoint

Date: 2026-09-29

Branch: `feat/e2e-v0-integration-20260917`

Physical execution: prohibited in this checkpoint

## Outcome

`manipulation.plan_transfer_chain` is now the canonical planning-only capability for selecting the two-finger grasp symmetry and compatible IK branches across:

`pregrasp → grasp → lift → center → rear-preplace → preplace`

The former `audit_symmetric_grasp_full_chain.py` and `plan_symmetric_first_pick.py` remain diagnostic prototypes only. The commissioned Scheme does not depend on them.

## Contract

- Input is bound to one fresh `ObservationEpoch` and `SceneSnapshot`.
- Grasp candidates are `NORMAL` and `FLIPPED_180`, where the latter is a 180° rotation about the tool approach axis.
- Every stage uses bounded deterministic multi-IK; no unbounded cuRobo brute force is permitted.
- `center` constrains only BODY TCP position plus a level-tool manifold. BODY yaw is enumerated and selected; historical center joints are numerical seeds only.
- Dynamic programming scores joint continuity, maximum per-stage change, Jacobian minimum singular value and joint-limit margin.
- At most three complete chains per symmetry may survive; the commissioned Scheme requests two.
- Only surviving chains reach the persistent cuRobo validator. Each segment is limited to `FAST → FALLBACK`, at most two solves.
- Hard level-orientation post-validation is mandatory. Collision-free paths that tilt or flip the tool fail.
- AMR motion is an explicit rebind boundary. `center→rear-preplace` and `rear-preplace→preplace` remain pending until the base settles and a fresh place-side scene is available.
- A successful invocation writes immutable `transfer_chain_selection.json` with an artifact digest.

## Runtime and UI integration

- Skill Registry exposes `manipulation.plan_transfer_chain` with schema-driven parameters for the Task Studio form.
- `RealCapabilityProvider` delegates the capability to an injected canonical `TransferChainSkillService`.
- TaskRuntime replay supplies the same output bindings consumed by downstream nodes.
- `right_arm_autoalign_pick_center_preplace_v1` now contains an explicit `plan_transfer_chain` node.
- The Scheme uses the selected pregrasp and selected center IK; it represents rear-preplace as a generic BODY offset `[-0.15, 0, 0]`.
- A fresh Pixel Pro scene is required after reaching rear-preplace before the final preplace move.

Task Studio validation result:

```text
valid=true
node_count=18
dag_digest=sha256:6ecc5f9d7a6b2b1051cba28703dd8ded8b77b8f10e1063bf3166fe4eeefb039c
```

TaskRuntime frozen replay result:

```text
status=SUCCEEDED
nodes=18
selected_grasp_symmetry_id=FLIPPED_180
```

## Test evidence

```text
567 tests run
OK (skipped=1)
```

Dedicated tests cover bounded DP selection, scene-rebind markers, hard-orientation rejection and immutable artifact refusal.

## Current live blocker

Three new `right_pick` observation attempts returned:

```text
000,3020
Epic error 3020: 未检测出结果
```

No new observation transaction was committed, so no production `transfer_chain_selection.json` may be created from the current scene. Historical evidence was used only for kinematic design checks and was not presented as a fresh live pass.

## Readiness

```text
WHOLE_CHAIN_BRANCH_SELECTED=NO (awaiting fresh right_pick observation)
SELECTED_BRANCH_PREGRASP_CUROBO_PASS=NO (not run against a new committed scene)
SELECTED_BRANCH_LIFT_TO_CENTER_CUROBO_PASS=NO (not run against a new committed scene)
HARD_LEVEL_ORIENTATION_VALIDATOR_PASS=YES (implementation and rejection tests)
TASK_RUNTIME_AUTONOMOUS_BRANCH_SELECTION_READY=YES (schema, DAG and replay)
SUPERVISED_PHYSICAL_RUNNER_CHANGE_ALLOWED=NO
```

The next permitted action is a fresh successful `right_pick` observation followed by one planning-only invocation of `manipulation.plan_transfer_chain`. Physical execution remains blocked until all five production artifact flags are `YES`.
