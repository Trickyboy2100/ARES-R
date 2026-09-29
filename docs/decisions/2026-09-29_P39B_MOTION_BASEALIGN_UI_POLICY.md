# P3.9B Motion, Base-Alignment and UI Policy

Date: 2026-09-29
Status: implementation decision for the next physical vertical slice

## 1. Canonical integration baseline

At the time of this decision the integration branch is:

`6075295f77418a9a171a8ceef0d436e2c13ca461`

P3.9 runtime/low-code remains additive. The golden first-pick fallback remains unchanged.

## 2. Point-to-point arm motion policy

Every non-contact arm point-to-point motion in the TaskRuntime/Demo path MUST use the existing SceneAwareMotionService + cuRobo path with the current pointcloud obstacle pipeline.

Examples:

- current → pregrasp;
- lifted grasp state → center/stow pose;
- center/stow pose → preplace / above-place pose;
- normal retreat/reposition moves outside the contact window;
- named-pose moves used by a Task/Scheme.

Do not use direct JAKA MoveJ as a shortcut inside the TaskRuntime for these moves.

Exceptions:

- bounded grasp contact approach;
- bounded placement descent;
- initial vertical escape/lift that is explicitly part of the contact policy.

Those keep the current constrained contact semantics.

## 3. Central exclusion policy

The historical central exclusion is `|BODY Y| <= 0.07 m`.

That means:

- half-width = 7 cm on each side of BODY centerline;
- total forbidden band width = 14 cm.

Make it a versioned runtime/config switch.

Required config semantics:

`central_exclusion.enabled = false` for the current P3.9B demo.

Disabling this virtual band MUST NOT disable:

- real robot-link collision;
- right-arm vs left-arm collision;
- self collision;
- scene obstacle collision;
- controller collision/limit/E-stop protections.

The switch must propagate consistently through planner request generation, independent dense validation and SafetyKernel. No hard-coded `0.07` gate may remain active when the policy is disabled.

## 4. Manipulation-aware automatic base alignment

Add a reusable Skill:

`navigate.align_for_manipulation`

Purpose: move the AMR within a bounded translation window until the requested right-arm manipulation target becomes both reachable and cuRobo-plannable.

Per alignment episode, total allowed translation from the episode origin:

- BODY/AMR X (forward/back): `[-0.15, +0.15] m`;
- BODY/AMR Y (left/right): `[-0.40, +0.40] m`;
- yaw: `0 deg` in P3.9B.

Do not random-walk by applying the bounds repeatedly. The bounds apply to total displacement from the episode origin.

Recommended algorithm:

1. quick 5700 detection for the requested pick/place semantic target;
2. predict target BODY pose under candidate base translations;
3. score candidates with right-arm RuntimeGoalIK / joint margin / singularity and minimum base displacement;
4. move to the best bounded candidate;
5. truthful BaseMotionObserver SETTLED;
6. fresh atomic 5700+5000 ObservationEpoch;
7. attempt the required cuRobo free-space plan;
8. if the plan fails for reachability/scene reasons, perform a bounded closed-loop correction and retry;
9. stop after a small bounded number of corrections; never exceed the total X/Y envelope.

After the first successful physical run, store the successful relative offset as a PRIOR for the next run, not as unconditional truth. Every run still re-detects and revalidates.

## 5. Pick-side and place-side alignment

Use the same generic Skill twice:

- PICK alignment: target = `right_pick` / tray material pregrasp;
- PLACE alignment: target = `right_place_rightmost` / preplace above groove.

Place alignment occurs with the grasped object attached and the right arm first moved to the center/stow posture.

## 6. Center/stow pose

The user reports that another teammate already created a `center` posture for retracting the right arm toward the chest before lateral base motion.

The remote canonical repository currently does not expose a `center` named pose. Therefore P3.9B must search the effective `.32` workspace before inventing anything:

- tracked and untracked files;
- coworker dirty patch/preservation;
- Git history;
- config and scripts;
- terms `center`, `centre`, `chest`, `收起`, `胸前`, `stow`.

If found:

- preserve its original source and values;
- verify read-only FK/TCP semantics;
- verify the final gripper is level/horizontal as intended;
- promote it into the named-pose/TaskRuntime data model without changing the source pose.

If not found, STOP before physical center motion and request the exact teammate definition. Do not silently substitute `ready`.

Movement from post-lift to center uses cuRobo with the attached-object geometry and normal scene avoidance.

Use a level/horizontal transfer orientation policy (yaw may remain free) if compatible with the existing center definition.

## 7. New demo stop point

New demo ID:

`right_arm_autoalign_pick_center_preplace_v1`

Physical sequence:

1. auto-align base for PICK within the bounded X/Y window;
2. fresh pick ObservationEpoch;
3. cuRobo current → pregrasp with normal pointcloud avoidance;
4. contact approach + close + grasp verification;
5. bounded vertical initial lift;
6. activate coarse attached object;
7. cuRobo attached-object move to verified `center` posture, level/horizontal;
8. auto-align base for PLACE while arm remains at center;
9. fresh place ObservationEpoch;
10. cuRobo center → preplace / directly above rightmost placement target with attached object and pointcloud avoidance;
11. HOLD ABOVE PLACE.

The demo deliberately stops above the placement point.

It does NOT descend, release or retreat in this commissioning run.

## 8. WebUI/ART deployment

On `.32`, the canonical backend runtime and WebUI must be available automatically after boot.

Autostart MUST NOT cause robot motion.

Implement versioned service units/install scripts with:

- network-online dependency;
- restart-on-failure;
- explicit working directory/environment;
- journal logging;
- health/status check;
- backend starts before WebUI;
- no physical task execution on service startup.

If current ART is a client rather than a daemon, do not fake a second hardware owner. Start one canonical ARES-R backend service and make ART CLI and WebUI clients of the same backend/state.

## 9. Version synchronization

ART and WebUI must show the same runtime identity:

- ARES-R package/runtime version;
- short Git SHA;
- TaskRuntime version;
- active Scheme version;
- WebUI build/version.

Add a shared system-info endpoint/command. The UI header/footer and ART `version`/`system info` must be generated from the same backend values.

## 10. WebUI coordinate audit

BODY frame is:

`+X forward, +Y left, +Z up`.

The 3D view must be checked against known geometry:

- left arm base at BODY Y = +0.20 m;
- right arm base at BODY Y = -0.20 m.

In the default robot-forward/rear viewing preset, the left arm must appear on screen-left and the right arm on screen-right.

Add explicit axis labels and deterministic projection tests. Fix any mirrored-Y visualization without changing the underlying BODY/world data.

Recommended UI view presets:

- Robot Forward / Rear;
- Front;
- Top.

## 11. Low-code exposure

Expose the new base-alignment and center-transfer capabilities in ART/WebUI as Skills/Task nodes, not hard-coded demo-only buttons.

Required visible/editable nodes include:

- `navigate.align_for_manipulation`;
- `manipulation.move_free` target `center`;
- pick/place observation;
- pregrasp/preplace targets.

The new demo must appear in Demo Library and as a Task/Scheme in Task Studio.