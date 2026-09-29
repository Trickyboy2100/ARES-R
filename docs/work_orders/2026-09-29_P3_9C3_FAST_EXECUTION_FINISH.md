# P3.9C3 — Fast execution finish: stop re-planning validated work

Date: 2026-09-29
Priority: EXECUTE THE FULL DEMO NOW

## Current facts

The current fresh chain has already passed the important planning gate:

- selected branch: `FLIPPED_180`;
- fresh `current→pregrasp` cuRobo trajectory exists and passed dense collision;
- full-chain selector has a valid lift IK / branch;
- current Task policy has `central_exclusion.enabled=false`;
- remaining failures are integration leftovers in packaging/contact-lift code, not a need for more global search.

## Hard steering

STOP all new branch sweeps, top-k expansion, beam expansion, repeated full-chain planning and architecture work.

Do NOT restart NORMAL/FLIPPED comparison unless the fresh physical state invalidates the selected branch.

Do NOT add new waypoints.

Do NOT change the validated pick target or center Cartesian target.

## Only fix these integration leftovers

1. Contact-bypass packaging must read the canonical central-exclusion policy. For this demo it is OFF. Remove any stale hard-coded `central_exclusion=true` in packagers/validators.

2. The initial BODY +Z lift must consume the valid lift IK / seed selected by `manipulation.plan_transfer_chain` when the local single-seed IK fails. Preserve the same straight +Z / fixed-orientation lift semantics.

3. Build the first-pick execution package directly from the already validated fresh `FLIPPED_180 current→pregrasp` trajectory and current fresh ObservationEpoch. Do not re-run the expensive full-chain search.

4. Run exactly one native preflight for pregrasp/contact/lift. If it passes, execute immediately.

## Physical sequence after the package passes

Execute without conversational pauses:

```text
validated current→pregrasp
→ gripper 40%
→ contact bypass approach
→ close
→ grasp verification
→ BODY +Z 100 mm lift
→ attach
→ cuRobo lift→center using the selected FLIPPED branch
→ base return to PLACE using the station contract
→ fresh place ObservationEpoch
→ same FLIPPED branch rebind
→ cuRobo center→rear-preplace (BODY X-0.15 m from preplace)
→ cuRobo rear-preplace→preplace
→ HOLD_ABOVE_PLACE
```

Do not descend or release.

## Station contract

Use the current commissioned station relation for this run:

- current/PLACE station as defined in `config/manipulation_stations.json`;
- PICK/PLACE inverse transform from that same config;
- do not re-search stations unless fresh evidence says the configured station cannot see/reach the target.

## Stop conditions

Stop only for:

- controller/device fault;
- fresh observation invalid;
- hard collision/dense validation failure;
- selected branch becomes invalid after scene rebind;
- grasp verification failure;
- explicit operator stop.

Do not stop for preferred-clearance misses, stale legacy central-exclusion gates, or a local IK seed failure when the frozen transfer-chain Skill already provides a valid semantic branch/IK seed.

## Acceptance

```text
PICK_EXECUTION_PACKAGE_READY = YES
PICK_GRASP_LIFT = PASS
LIFT_TO_CENTER_CUROBO = PASS
PLACE_SCENE_FRESH = YES
CENTER_TO_REAR_PREPLACE_CUROBO = PASS
REAR_PREPLACE_TO_PREPLACE_CUROBO = PASS
HOLD_ABOVE_PLACE = YES
AUTONOMOUS_SCHEME_NO_CODEX_WAYPOINT_ASSIST = YES
```

After success, preserve evidence, run tests, commit the integration fixes, and push normally.