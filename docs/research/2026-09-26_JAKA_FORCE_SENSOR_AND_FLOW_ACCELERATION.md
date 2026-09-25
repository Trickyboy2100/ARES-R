# Research Note — JAKA force sensor + full-flow acceleration after first successful real pick

Date: 2026-09-26
Status: engineering research / implementation preparation

## 0. Current field milestone

The first real right-arm pick succeeded in one attempt.

Recorded field result from the operator/Codex session:

~~~text
CURRENT→50 mm pregrasp: SUCCESS
max tracking error: 0.591 deg

contact approach: SUCCESS
max tracking error: 0.036 deg

gripper close:
stable readback 45/1000
final 44/1000

15 cm local pointcloud grasp verification:
removed voxels = 538
removed fraction = 47.4%
PASS

BODY +Z 100 mm lift:
SUCCESS
max tracking error = 0.045 deg

target_reached on all three motion segments
ServoJ disabled normally
no fault
left arm stationary
AMR stationary
final state = lifted HOLD
~~~

The flow was functionally excellent but operationally slow (~5 minutes end-to-end for the staged pick checkpoint).

The engineering priority is now:

~~~text
preserve successful semantics
→ reduce orchestration/scan/planning latency
→ use force sensing as fast contact/grasp feedback
→ extend HOLD to complete transfer + place
~~~

## 1. Likely JAKA force sensor model

Exact installed model is NOT yet verified from the physical label or JAKA App sensor configuration.

JAKA currently sells the End Effector 6-Axis Force Sensor Assembly VI series:

| Model | Force range | Torque range | Overload | Accuracy | Supply | IP | Temperature |
|---|---:|---:|---:|---:|---:|---|---|
| JK-SE-VI-200 | Fx/Fy/Fz 200 N | Mx/My/Mz 8 Nm | 300% FS | 0.5% FS | 12 V | IP64 | 5–80°C |
| JK-SE-VI-400 | Fx/Fy/Fz 400 N | Mx/My/Mz 12 Nm | 300% FS | 0.5% FS | 12 V | IP64 | 5–80°C |
| JK-SE-VI-H | Fx/Fy 800 N, Fz 1000 N | Mx/My/Mz 40 Nm | 400% FS | 0.5% FS | 12 V | IP64 | 5–80°C |

Official JAKA product brochure recommends:

~~~text
JK-SE-VI-200  → robots <= 5 kg payload
JK-SE-VI-400  → 7–12 kg
JK-SE-VI-H    → >12 kg
~~~

JAKA Mini2 payload is 2 kg.

Therefore the strongest current hypothesis is:

~~~text
INSTALLED_FORCE_SENSOR_CANDIDATE = JK-SE-VI-200
CONFIDENCE = medium/high based on robot class + appearance, NOT yet verified
~~~

Do not write this model into production config until read from JAKA App/controller configuration or physical label.

Official references:

- https://www.jaka.com/en/productDetails/End_Effector_6-Axis_Force_Sensor_Assembly
- https://www.jaka.com/profile/upload/2025/11/05/20251105171610A003.pdf
- https://www.jaka.com/en/productDetails/JAKA_Mini2
- https://www.jaka.com/profile/upload/2026/02/28/20260228141133A022.pdf

## 2. The 145 mm vs 184 mm TCP discrepancy is now plausibly explained

Field measurements:

~~~text
manual force-sensor/tool-side flange → physical grasp center ≈145 mm
controller TCP Z ≈184 mm
difference ≈39 mm
~~~

The JAKA JK-SE VI mounting drawing for VI-200/400/H shows a round sensor body and includes an axial dimension of about 31.5 mm. The same drawing shows about 75 mm outside diameter and a 50 mm flange bolt circle.

Therefore a very plausible explanation is:

~~~text
the manual measurement started at the FORCE SENSOR TOOL-SIDE FLANGE
instead of the ROBOT WRIST FLANGE

robot flange
→ force sensor (~31.5 mm axial stack)
→ adapter/gripper
→ grasp center
~~~

31.5 mm sensor thickness plus adapter/interface stack or measurement uncertainty is of the same order as the observed ~39 mm discrepancy.

This is still a hypothesis until the exact installed sensor/adapter dimensions are verified.

Engineering implication:

- do not reinterpret the controller TCP from the old 145 mm tape measurement;
- add the force sensor + adapter stack explicitly to the tool-chain drawing/model;
- later measure robot-flange → sensor-tool-flange → gripper-base → grasp-center separately.

## 3. Force sensor data available from JAKA

Official JAKA SDK force-control guide shows that RobotStatus includes force information:

~~~text
status.torq_sensor_monitor_data.actTorque[0..5]
~~~

The guide demonstrates reading Z-direction force inside an 8 ms Servo loop using get_robot_status().

Relevant SDK APIs include:

~~~text
get_robot_status(...)
set_torque_sensor_mode(...)
set_ft_ctrl_frame(...)
set_compliant_type(...)
disable_force_control(...)
set_torque_sensor_filter(...)
set_torsenosr_brand(...)
set_torque_sensor_soft_limit(...)
set_torq_sensor_tool_payload(...)
start_torq_sensor_payload_identify(...)
~~~

For the FIRST integration, ARES-R should be read/monitor-only:

~~~text
FORCE_MONITOR_V1
~~~

Do NOT turn on constant-force compliance or tool dragging yet.

JAKA Modbus/bus documentation also exposes six sensor channels (Fx/Fy/Fz/Mx/My/Mz). The App provides real-time force curves.

Official references:

- https://www.jaka.com/docs/downloads/SDK/SDK-FT.pdf
- https://www.jaka.com/docs/cobo/330/3.0/EN/guide/10.Busaddress.html
- https://www.jaka.com/docs/cobo/330/3.0/EN/guide/9.Settings.html

## 4. Coordinate interpretation — important correction

The user's intuition is partly correct:

- current right_pick approach axis is tool +z;
- that tool +z has been verified to point approximately along BODY +X during the horizontal pick;
- therefore a force component along tool +z is a very useful CONTACT/INSERTION signal.

But:

~~~text
tool Fz is NOT the weight direction during this horizontal grasp.
~~~

Gravity is BODY/world -Z.

For weight/grasp verification use the full 3D force vector:

~~~text
F_body = R_body_force * F_sensor
F_vertical = dot(F_body, BODY_Z)
estimated_mass ≈ |ΔF_vertical| / g
~~~

or configure/read the force-control frame in the world/tool frame only after the frame semantics are audited.

Never assume raw sensor Fz is gravity merely because the variable is named Fz.

## 5. Zeroing, drift and filtering

JAKA documentation explicitly recommends zeroing before force-control use.

Important published behavior:

- after correct zeroing, zero drift can still be about 0.5% full scale, roughly 1–2 N for typical sensors;
- a no-load deviation within 20 N or 2 Nm can occur before rezeroing and does not by itself mean hardware failure;
- JAKA recommends 20–60 Hz smoothing for common force-control scenarios;
- force sensor safety limits can stop the robot if configured and enabled;
- sensor limits are ineffective until the sensor has been zeroed.

For our use:

~~~text
do not zero while holding the object if object weight must be measured.
~~~

Recommended cycle:

1. empty gripper, no external contact;
2. zero sensor;
3. record 0.5–1.0 s baseline wrench;
4. approach/grasp;
5. lift;
6. compare force against the empty baseline;
7. only after grasp verification consider updating payload compensation.

## 6. FORCE_GUARDED_CONTACT_V1 — strongest immediate opportunity

The successful CONTACT_BYPASS_V1 was a good demo decision: pointcloud collision for the active tool was ignored only in the short contact window while arm links/controller protections remained active.

The force sensor can convert this from blind-but-bounded to touch-aware-and-bounded:

~~~text
PREGRASP
→ force baseline
→ CONTACT_BYPASS_V1
→ straight approach

monitor:
  axial approach force
  lateral force norm
  torque norm / off-axis torque

if force rises unexpectedly:
  motion_abort
  HOLD
~~~

This should be implemented as FORCE_GUARDED_CONTACT_V1, not full force compliance.

Why this is valuable:

- catches actual contact missed by pointcloud;
- lets us keep the simple bypass instead of rebuilding millimetre-level contact collision geometry now;
- can support faster approach than the current ultra-conservative execution;
- detects oblique/jammed contact using lateral force/torque, not only axial force.

Thresholds must be calibrated from real empty-motion data; do not hard-code one universal Newton value.

## 7. Force-based grasp verification — likely faster than post-grasp pointcloud

Current successful verification required:

~~~text
gripper readback
+ 15 cm local Pixel Pro scene delta
~~~

It worked, but it costs capture/processing time and the grasp itself can occlude the vision target.

A faster V1 can use:

~~~text
gripper readback
+ lift force signature
~~~

### Recommended logic

At empty-gripper baseline:

~~~text
F_vertical_empty = averaged BODY vertical wrench
~~~

After close and during the first lift:

- do not decide immediately while the object is still supported by the tray;
- after 10–30 mm lift, the object should transfer its weight to the wrist;
- after motion settles briefly, calculate a stable vertical-force plateau.

Then:

~~~text
ΔF_vertical = F_vertical_loaded - F_vertical_empty

if stable ΔF_vertical is consistent with a carried object:
    GRASP_FORCE_CONFIRMED
elif ambiguous:
    FALLBACK_TO_POINTCLOUD_VERIFY
else:
    GRASP_FAILED / STOP
~~~

Because a VI-200 has 0.5% FS accuracy (~1 N at 200 N full scale) and practical drift can be ~1–2 N, force-only verification is excellent for objects whose weight signal is several Newtons; it may be weak for very light objects.

The actual tray/material mass must therefore be measured once before choosing the acceptance band.

## 8. Force-based lift and transfer monitoring

### 8.1 Slip/drop detection

Track the vertical force plateau.

A sudden return toward the empty baseline can indicate object slipped/dropped or grip released unexpectedly.

### 8.2 Snag/contact detection

Unexpected lateral force or torque while transferring can indicate payload catches an obstacle or unmodeled contact.

This gives a physical feedback layer that pointcloud-only planning cannot provide.

### 8.3 Payload/mass estimation

After a stable HOLD:

~~~text
m_est = ΔF_vertical / 9.80665
~~~

This can provide a grasp-confidence feature, approximate carried mass, payload-compensation input later, and a sanity check against expected material category.

Do not update controller payload compensation before measuring the added load, or the weight signal may be removed by compensation.

## 9. Force-assisted placement

This is the second high-value application.

Current geometric plan:

~~~text
preplace
→ vertical descend
→ stop at detected target +5 mm
~~~

Future fast/accurate V1.5:

~~~text
preplace
→ vertical descend under FORCE_GUARDED_CONTACT
→ detect real support/contact force rise
→ stop
→ release
~~~

This can compensate for small 5700 Z error, tray/groove height tolerance, base localization drift and pointcloud support-surface error.

Start with force as a monitor/termination guard, not constant-force compliance.

## 10. Why not replace vision with force

Force and vision solve different problems.

Keep vision for target pose, obstacle geometry, free-space planning, attached-object geometry and large scene changes.

Use force for contact onset, grasp/load confirmation, slip/drop detection, placement contact and physical anomaly detection.

Recommended fused hierarchy:

~~~text
VISION = where can I move?
FORCE  = what am I touching / carrying right now?
~~~

## 11. Full-flow acceleration — lessons from the first successful pick

### What worked

1. atomic target/scene provenance removed ambiguity between 5700 and pointcloud;
2. base positioning placed the target in the right-arm workspace;
3. 50 mm pregrasp gave a reliable free-space staging point;
4. only terminal grasp orientation was constrained; free-space cuRobo was allowed to reorient;
5. CONTACT_BYPASS_V1 avoided false contact blocks from over-conservative pointcloud/tool geometry;
6. gripper 40% before approach gave good physical geometry;
7. the first actual grasp was accurate in one attempt;
8. short vertical lift was an excellent checkpoint before attempting transfer;
9. all ServoJ stages stopped cleanly and tracking errors were small.

### What made it slow

The ~5 min was not a single slow motion problem. It included:

- multiple Python/service/orchestration boundaries;
- repeated fresh capture / scene construction;
- separate planning/package/preflight stages;
- post-grasp Pixel Pro verification;
- stage-by-stage AI/operator orchestration;
- conservative contact/lift timing;
- evidence generation occurring synchronously.

### Highest-value acceleration actions

#### A. Make Scheme execution native, not conversational

Once P3.8C is validated, the robot should run the Scheme state machine itself. Human/AI should not manually launch each internal script.

#### B. Keep services persistent

Keep alive Pixel Pro capture worker, persistent cuRobo planner, force monitor, JAKA telemetry reader and WebUI/ART backend.

#### C. Scan by lifecycle, not by every micro-motion

Full scene scan is required after AMR/base motion, before a new free-space plan, or after a major unexpected scene change.

Do not require a full pointcloud scan between every short contact/lift step.

#### D. Replace post-grasp pointcloud verify with force-first verify

Use force + gripper readback as primary. Use pointcloud only when force confidence is ambiguous or as periodic evidence.

This is likely the biggest immediate sensing-time win.

#### E. Stage-specific speed profiles

Use faster commissioned free-space speed and a separate contact speed profile with force guard.

The successful contact/lift tracking errors were far below the pregrasp tracking error, suggesting room to tune those segments based on real data.

#### F. Asynchronous evidence writing

Motion/force monitoring should write compact real-time logs. Heavy visualization and report generation should happen after the stage, not block the next command.

## 12. Proposed target flow

Near-term full customer demo:

~~~text
AMR to pickup
→ settle observer
→ atomic 5700 + fast scene
→ cuRobo pregrasp
→ force baseline
→ FORCE_GUARDED_CONTACT approach
→ close
→ 20–30 mm lift
→ force grasp verification
→ continue lift to 100 mm
→ coarse attached object
→ full scene-aware move to z=1.20 / visibility-clear
→ AMR to placement
→ settle
→ atomic right_place_rightmost + fresh scene
→ cuRobo preplace
→ force-guarded vertical place
→ release
→ force release verification
→ retreat
→ result verify
~~~

## 13. Practical development order

~~~text
D0 preserve/push successful first-pick evidence
D1 identify/read force sensor
D2 record force baselines and coordinate semantics
D3 add FORCE_GUARDED_CONTACT monitor-only
D4 add force-based grasp verification with pointcloud fallback
D5 run pick→100 mm lift again, faster
D6 extend attached transfer + base move + place
D7 add force-guarded placement/release
D8 optimize end-to-end Scheme timing
~~~

## 14. Exact sensor identification action

When next physically available, capture ONE of:

1. JAKA App → Force Control Configuration → Associated Sensor List showing sensor model;
2. photo of force sensor label/nameplate;
3. controller/exported configuration containing sensor model.

Until then:

~~~text
likely model = JK-SE-VI-200
production model identity = UNVERIFIED
~~~