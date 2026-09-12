# ARES-R Skill Catalog

Status: S0 taxonomy. IDs are proposed contracts, not implementations. Initial maturity is `SPECIFIED` unless explicitly promoted by later evidence.

## Taxonomy rules

A skill is the smallest stable semantic intent that has independently meaningful preconditions, verification and effects. A planner stage is smaller; a protocol is larger. Device names belong in Resource/Affordance data unless interaction semantics genuinely differ. Parameters use resource IDs and typed SI quantities; coordinates are internal resolved data.

Failure families used below:

- `INPUT`: invalid schema/unit/resource/type;
- `RESOURCE`: absent, occupied, incompatible, busy or state unknown;
- `OBSERVATION`: unavailable, stale, low confidence or calibration mismatch;
- `PLAN`: unreachable, collision, constraint, no strategy;
- `EXECUTION`: provider unavailable, rejected, tracking or device fault;
- `VERIFICATION`: intended effect not observed or ambiguous;
- `SAFETY`: invariant, interlock, zone or approval failure;
- `TIMEOUT/CANCELLED/INTERNAL`.

Maturity targets mean the highest plausible near-term target, not current status: `MV` = MOCK_VERIFIED, `SV` = SIM_VERIFIED, `RD` = REAL_DRYRUN, `RC` = REAL_COMMISSIONED.

## L0 — Hardware primitives (internal only)

| ID | Parameters | Resources/capability | Preconditions → effects | Failures | Target |
|---|---|---|---|---|---|
| `hw.arm.read_state` | arm | arm/read | connected → observation only | EXECUTION, TIMEOUT | RC |
| `hw.arm.execute_joint_trajectory` | trajectory, lease | arm/trajectory | valid lease/start → physical joints changed, snapshot stale | PLAN, EXECUTION, SAFETY | RC |
| `hw.arm.servo_joint` | internal stream, lease | arm/servo | commissioned stream → physical joints changed | EXECUTION, SAFETY | RC |
| `hw.gripper.command` | side, setpoint/force limits | gripper/command | healthy gripper → gripper state changed | EXECUTION, VERIFICATION | RC |
| `hw.base.navigate` | internal route, lease | base/navigation | localized/clear → base pose changed, environment invalid | PLAN, EXECUTION, SAFETY | RC |
| `hw.base.stop` | lease | base/stop | base controlled → stopped evidence | EXECUTION | RC |
| `hw.camera.capture` | profile | camera/capture | calibrated/available → raw observation artifact | OBSERVATION, EXECUTION | RC |
| `hw.device.command` | validated provider command | device-specific | interlocks true → device state candidate | EXECUTION, SAFETY | RC |

L0 is never exported to LLM/function calling. Existing ARES-R adapters remain the future implementation boundary.

## L1 — Robot basic skills

| ID | Parameters | Resources | Preconditions → verified effects | Failures | Target |
|---|---|---|---|---|---|
| `observe.capture_scene` ★ | station?, profile | camera, observation zone | robot stationary, calibration valid → committed ObservationEpoch/EnvironmentRevision | OBSERVATION, RESOURCE | RC |
| `observe.detect_resource` ★ | resource/query, confidence | camera, scene | current observation available → detection bound to epoch | OBSERVATION, VERIFICATION | RC |
| `observe.verify_predicate` ★ | predicate, method, threshold | sensor/resources | observable predicate → TRUE/FALSE/UNKNOWN evidence | OBSERVATION, VERIFICATION | RC |
| `navigate.go_to_station` ★ | station, tolerance | base, route/zone | localized, station dock free → base at docking pose; scene invalidated | RESOURCE, PLAN, EXECUTION, SAFETY | RC |
| `navigate.align_station` | station, tolerance | base, station zone | near station, fiducial/geometry visible → aligned base_station | OBSERVATION, EXECUTION | RC |
| `manipulation.approach` | resource/affordance, arm, standoff | arm, zone, scene | fresh scene, reachable → TCP at preinteraction state | PLAN, EXECUTION, SAFETY | SV |
| `manipulation.retreat` | arm, direction/distance policy | arm, zone | controlled object/tool state known → safe clearance verified | PLAN, EXECUTION | SV |
| `manipulation.grasp` ★ | object, arm?, grasp policy | object, arm, gripper, zone | object localized/free/compatible → grasp verified and object attached | RESOURCE, PLAN, EXECUTION, VERIFICATION | RC |
| `manipulation.release` ★ | object, destination | object, gripper, destination | object attached and destination valid → release verified, detached | RESOURCE, EXECUTION, VERIFICATION | RC |
| `robot.stow` | arm=left/right/both | arm(s), zones | no incompatible payload → stowed predicate | PLAN, EXECUTION, SAFETY | RC |

## L2 — Generic manipulation and device interaction

| ID | Typed parameters | Required resources/preconditions | Verified effects | Failure families | Target |
|---|---|---|---|---|---|
| `manipulation.pick` ★ | object:ResourceRef, arm?:enum, grasp?:policy | object located/free; scene fresh; gripper compatible; locks | attached(object, arm); former occupancy empty | RESOURCE, OBSERVATION, PLAN, EXECUTION, VERIFICATION, SAFETY | RC |
| `manipulation.place` ★ | object, destination:Holder/Slot, pose_policy | object attached; destination compatible/free/localized | located_at(object,destination); detached; occupied | RESOURCE, PLAN, EXECUTION, VERIFICATION | RC |
| `manipulation.transfer_object` ★ | object, destination, source? | source relation valid, destination free | composed pick/place with lineage preserved | all except INPUT as appropriate | RC |
| `manipulation.regrasp` | object, from_arm, to_arm/fixture | stable intermediate support or safe handover | new attachment/grasp orientation verified | RESOURCE, PLAN, VERIFICATION, SAFETY | SV |
| `manipulation.handover` | object, giver, receiver, handover_zone | dual-arm capable, zone exclusive | attachment atomically transfers | PLAN, EXECUTION, VERIFICATION, SAFETY | SV |
| `manipulation.insert` | object, port, depth/force policy | compatible affordance/alignment/force sensing | seated(object,port) | RESOURCE, PLAN, EXECUTION, VERIFICATION | SV |
| `manipulation.extract` | object, holder/port, extraction policy | graspable/not interlocked | object removed and attached/placed | RESOURCE, EXECUTION, VERIFICATION | SV |
| `manipulation.push` | resource, direction, distance/target predicate | push affordance and clear sweep | target predicate true | PLAN, EXECUTION, VERIFICATION | SV |
| `manipulation.pull` | resource, target predicate | pull affordance/grasp | target predicate true | PLAN, EXECUTION, VERIFICATION | SV |
| `manipulation.press` ★ | control, actuation policy | press affordance, device safe | control/device predicate transition | RESOURCE, EXECUTION, VERIFICATION, SAFETY | RC |
| `manipulation.turn` ★ | control, target value/delta, policy | rotary affordance/limits | knob/valve setting verified | RESOURCE, EXECUTION, VERIFICATION | RC |
| `manipulation.open_door` | door, target_fraction | openable affordance, device interlocks, sweep clear | door_state OPEN/angle threshold | RESOURCE, PLAN, EXECUTION, VERIFICATION, SAFETY | SV |
| `manipulation.close_door` | door | close affordance/sweep clear | door_state CLOSED/interlock evidence | same | SV |
| `manipulation.open_drawer` | drawer, target_fraction | sliding affordance/sweep clear | drawer OPEN/extension threshold | same | SV |
| `manipulation.close_drawer` | drawer | sliding affordance/sweep clear | drawer CLOSED | same | SV |
| `manipulation.pour` | source, destination, amount?, rate?, residue policy | source held, destination stable, content known | transferred quantity estimate; content relations updated | RESOURCE, PLAN, EXECUTION, VERIFICATION, SAFETY | SV |
| `manipulation.shake` | container, pattern, duration | sealed container, payload limits | agitation cycle evidence; location unchanged | RESOURCE, PLAN, EXECUTION, SAFETY | SV |
| `manipulation.scoop` | source, destination/tool, amount? | scoop tool/solid accessible | quantity candidate transferred | RESOURCE, PLAN, VERIFICATION | SV |
| `manipulation.spray` | dispenser, target, dose/passes | compatible fluid/target, protected zone | application evidence/consumable decrement | RESOURCE, EXECUTION, SAFETY | MV |
| `manipulation.wipe` | target_surface, tool, pattern, passes | tool mounted/wetness compatible | coverage evidence; cleanliness candidate | RESOURCE, PLAN, VERIFICATION | SV |
| `device.load` ★ | device, payload, slot/port | door/open/interlock state; slot compatible/free | loaded_in(payload,slot), occupied | RESOURCE, PLAN, EXECUTION, VERIFICATION, SAFETY | RC |
| `device.unload` | device, payload/slot, destination | cycle complete, safe state | payload removed and relocated | RESOURCE, EXECUTION, VERIFICATION | RC |
| `device.start` ★ | device, program/settings | payload/config/interlocks valid; operator policy | device RUNNING with run_id | INPUT, RESOURCE, EXECUTION, VERIFICATION, SAFETY | RC |
| `device.stop` | device, stop_mode | device controllable | device STOPPED/SAFE | EXECUTION, VERIFICATION, SAFETY | RC |
| `tool.acquire` | tool, arm | tool free/compatible/localized | tool attached; tool revision changes | RESOURCE, PLAN, VERIFICATION | SV |
| `tool.return` | tool, holder | tool attached; holder free | tool seated/available; detached | RESOURCE, PLAN, VERIFICATION | SV |
| `tool.change` | from_tool?, to_tool, arm | tool changer available | requested tool attached and revision updated | RESOURCE, EXECUTION, VERIFICATION | SV |

`transfer_object` is retained as a recoverable L2 composition, not collapsed into a single opaque arm motion. `grasp`/`release` remain L1 building blocks; normal planners should expose `pick`/`place`, not these lower-level mechanics.

## L3 — Laboratory semantic skills

| ID | Typed parameters | Required resources/preconditions | Verified effects | Failure families | Target |
|---|---|---|---|---|---|
| `lab.weigh` | sample/container, balance, tare?, stability, units | balance ready/calibrated; pan available; container compatible | Measurement with uncertainty/provenance; sample identity preserved | RESOURCE, EXECUTION, VERIFICATION | RC |
| `lab.dose_solid` | source, destination, mass, tolerance, tool? | material/containers compatible; balance/feeder available | mass transferred within tolerance, inventory adjusted | RESOURCE, EXECUTION, VERIFICATION, SAFETY | RC |
| `lab.transfer_solid` | sample, from, to, amount?, method | identity/content/location known | content relation and amount estimate updated | RESOURCE, VERIFICATION, SAFETY | RC |
| `lab.transfer_liquid` | liquid/sample, from, to, volume/amount, rate? | compatibility, capacity, liquid handler/tool | volume transferred, inventories/lineage updated | RESOURCE, EXECUTION, VERIFICATION, SAFETY | RC |
| `lab.mix` | container, method, duration/intensity | sealed/stable/compatible | mixed predicate plus process record | RESOURCE, EXECUTION, SAFETY | SV |
| `lab.stir` | vessel, speed, duration, temperature? | stir capability, vessel compatible | stir run record; final device state known | RESOURCE, EXECUTION, VERIFICATION | RC |
| `lab.grind` | sample, device/tool, endpoint | grinder compatible/loaded | particle-size endpoint evidence | RESOURCE, EXECUTION, VERIFICATION, SAFETY | MV |
| `lab.sieve` | sample, sieve, size, duration | sieve/tool clean/compatible | fractions and lineage created | RESOURCE, VERIFICATION | MV |
| `lab.heat` | vessel/sample, device, target_temp, duration/ramp | thermal compatibility, sensor/interlocks | temperature profile and final state recorded | RESOURCE, EXECUTION, VERIFICATION, SAFETY | RC |
| `lab.cool` | vessel/sample, target_temp, duration/ramp | cooling capability/compatibility | temperature profile recorded | same | RC |
| `lab.dry` | sample, device/method, endpoint/duration | safe volatility/device capability | dry endpoint evidence; mass/state update | RESOURCE, EXECUTION, VERIFICATION, SAFETY | MV |
| `lab.filter` | mixture, filter, filtrate_destination, residue_destination? | compatible filter/capacity | filtrate/residue resources and lineage | RESOURCE, EXECUTION, VERIFICATION | MV |
| `lab.centrifuge` | samples, device, speed/rcf, duration, temp? | rotor compatibility, balanced loading, lid/interlocks | cycle record and separated-state candidate | INPUT, RESOURCE, EXECUTION, VERIFICATION, SAFETY | RC |
| `lab.measure` ★ | subject, instrument, method, settings | instrument calibrated/ready; subject correctly loaded | immutable Measurement + artifact/provenance | RESOURCE, EXECUTION, VERIFICATION | RC |
| `lab.clean` | target, method, agent?, cycles?, acceptance | cleaning resources compatible; waste capacity | cleanliness predicate/evidence; consumables/waste updated | RESOURCE, EXECUTION, VERIFICATION, SAFETY | RC |
| `lab.rinse` | target, solvent, volume, cycles | compatibility/waste route | rinse record and contamination state update | RESOURCE, SAFETY | RC |
| `lab.decant` | source, destination, phase, amount? | settled phases/pose compatible | phase transfer and lineage | RESOURCE, VERIFICATION | SV |
| `lab.dispense` | source, destination, quantity, tolerance | calibrated dispenser, capacity | quantity delivered within tolerance | RESOURCE, EXECUTION, VERIFICATION | RC |
| `lab.label` | resource, label data/method | identity verified, labeler available | label relation/artifact verified | RESOURCE, VERIFICATION | RC |
| `lab.scan_id` | resource/query, scanner | code visible/scanner ready | identity observation bound to resource | OBSERVATION, VERIFICATION | RC |
| `lab.seal` | container, seal/method | compatible clean rim/material | sealed predicate/leak evidence | RESOURCE, EXECUTION, VERIFICATION | RC |
| `lab.unseal` | container, method | safe pressure/content, tool available | open predicate, seal consumed | RESOURCE, SAFETY, VERIFICATION | RC |
| `lab.incubate` | sample/container, device, temperature, duration | compatible device/slot | incubation profile/run record | RESOURCE, EXECUTION, VERIFICATION | RC |

XDL-inspired operations such as separate, crystallize, precipitate, evaporate, irradiate and purge belong in future domain packs once the applicable devices, hazards and acceptance predicates are defined. They are not Tier-A because premature generic contracts would hide chemistry-specific safety.

## L4 — Protocol/composite tasks

L4 is declarative orchestration, not a new actuator abstraction. Proposed IDs include:

- `protocol.pick_inspect_place`: observe → pick → lift/observe → place → verify;
- `protocol.weigh_sample`: identify → tare → transfer/load → measure → unload/return;
- `protocol.prepare_solution`: weigh/dose → transfer liquid → mix → label;
- `protocol.device_run`: load → close/interlock → start → monitor → unload;
- `protocol.sample_workup`: cool → filter/centrifuge → transfer → dry;
- `protocol.clean_station`: inventory waste/consumables → clean/rinse → inspect → restore tools.

Protocol nodes reference skill invocations, conditions, bounded retry/fallback, compensation, approvals and dataflow. They do not contain joint trajectories or raw device commands.

## Tier-A: first 14 implementation contracts

The first tranche intentionally closes one useful offline-to-real spine: observe, resolve, move, manipulate, operate a device, measure and clean.

| # | Skill | Why Tier-A | Initial / near-term target |
|---:|---|---|---|
| 1 | `observe.capture_scene` | makes WorldModel the mandatory perception path | SPECIFIED → MV → RD |
| 2 | `observe.detect_resource` | binds semantic target evidence to observation epoch | SPECIFIED → MV → RD |
| 3 | `observe.verify_predicate` | common independent verification primitive | SPECIFIED → MV → RD |
| 4 | `navigate.go_to_station` | mobile workspace transition and scene invalidation | SPECIFIED → MV → RD |
| 5 | `manipulation.grasp` | verified attachment boundary | SPECIFIED → MV → SV |
| 6 | `manipulation.release` | verified detach boundary | SPECIFIED → MV → SV |
| 7 | `manipulation.pick` | core snapshot-bound manipulation composition | SPECIFIED → MV → SV |
| 8 | `manipulation.place` | core symbolic destination manipulation | SPECIFIED → MV → SV |
| 9 | `manipulation.transfer_object` | recoverable pick/place between resources | SPECIFIED → MV → SV |
| 10 | `manipulation.press` | generic device control affordance | SPECIFIED → MV → SV |
| 11 | `manipulation.turn` | generic knob/valve affordance | SPECIFIED → MV → SV |
| 12 | `device.load` | connects mobile manipulation with instrument slots | SPECIFIED → MV → SV |
| 13 | `device.start` | bounded semantic device invocation, never raw command | SPECIFIED → MV → RD |
| 14 | `lab.measure` | produces the central laboratory output with provenance | SPECIFIED → MV → RD |

### Tier-A executability audit

Each line explicitly defines `precondition → plan → execute → verify → effect/failure`:

1. **capture_scene:** calibrated camera + stationary robot → reserve observation zone/build capture plan → capture/ingest → validate hash, epoch coherence and quality → commit EnvironmentRevision; otherwise `OBSERVATION_*` and no environment claim.
2. **detect_resource:** fresh epoch + resolvable query → choose detector/profile → infer → verify confidence/provenance/epoch → detection relation; otherwise `TARGET_NOT_FOUND/LOW_CONFIDENCE`.
3. **verify_predicate:** predicate has verifier → select independent evidence → observe → evaluate TRUE/FALSE/UNKNOWN → evidence record, never guessed state.
4. **go_to_station:** localized base + free dock/route → plan and lock route/dock → navigate → verify station tolerance/alignment → base_station update and environment invalidation; otherwise nav/safety failure.
5. **grasp:** localized compatible free object → choose grasp/arm and plan against snapshot → approach/close/lift-test → verify retention → attach and occupancy update; otherwise retreat/reobserve and no attachment.
6. **release:** attached object + valid support/destination → plan release/retreat → open/retreat → verify support and non-attachment → detach/location candidate; unknown result invalidates geometry.
7. **pick:** object free + active scene → compose observe/approach/grasp/retreat with locks → execute under lease → verify grasp and clearance → attached object; bounded alternative grasp or failure.
8. **place:** attached object + free compatible destination → compute placement/approach/retreat → execute → verify object in destination and stable → detach/occupancy/location transaction; else UNKNOWN and reobserve.
9. **transfer_object:** valid source/destination → build recoverable pick/place plan → execute subskills → verify final location/identity → atomic semantic location transition with full subresults.
10. **press:** safe device + press affordance → plan contact/force/retreat → press → verify control/device predicate → device-state transition; no blind repeat for non-idempotent controls.
11. **turn:** rotary affordance and limits known → plan grasp/rotation → turn within force/angle bounds → verify setting → control-value transition; jam/limit is terminal unless policy says retreat.
12. **device.load:** safe/open device + compatible free slot + held/located payload → compose open/pick/insert → execute → verify seated identity/interlock → loaded/occupied transaction.
13. **device.start:** loaded/configured/interlocked device → compile approved program → provider start → verify run ID and RUNNING state → run record; command acknowledgement alone is insufficient.
14. **measure:** calibrated ready instrument + correctly located subject → configure/acquire plan → run device → validate quality/stability/artifact → immutable Measurement with uncertainty, units, calibration and subject lineage.

## Self-audit

### A. Completeness

Covered: mobile navigation/docking; scene observation/detection; dual-arm grasp/place/regrasp/handover; articulated fixtures; container/tool/sample handling; loading and device control; solid/liquid transfer; thermal/mixing/separation; measurement; identification/sealing; cleaning and waste/consumables effects. Domain-specific hazardous chemistry remains explicitly deferred rather than silently omitted.

### B. Abstraction

- No furnace/cabinet/microwave-specific door skills: generic door/drawer/control skills consume affordances.
- L0 raw actuator calls are internal only.
- Pick, place and device operations remain independently recoverable; L4 protocols are not giant opaque skills.
- `transfer_object` is a composition with subresults, not duplicated mechanics.

### C. Executability

All 14 Tier-A skills above have an explicit precondition, plan, execution, verification, effect and failure route. Each effect is evidence-gated; `UNKNOWN` prevents false commits. Every motion-bearing plan is SceneSnapshot/ExecutionLease-bound and every semantic update is workspace-revision-bound.
