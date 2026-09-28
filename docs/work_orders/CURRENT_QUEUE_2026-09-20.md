# CURRENT QUEUE — 2026-09-28

## Current customer-facing priority

Functional correctness is no longer the main problem.

The first real pick succeeded. The next customer-visible problem is:

~~~text
cycle time
continuity
few visible pauses
automatic task progression
~~~

Do NOT start another broad manipulation redesign.

Do NOT immediately implement the force/speed/pipeline ideas one by one without first measuring the full critical path.

## Active now

### P3.8E — Full-cycle throughput / continuity audit

Execute:

~~~text
docs/work_orders/2026-09-28_P3_8E_FULL_CYCLE_THROUGHPUT_AUDIT.md
~~~

This round is AUDIT ONLY.

Required focus:

~~~text
real timing waterfall
critical-path DAG
parallelizable stages
persistent services
5700 || 5000 concurrency
scene lifecycle / redundant scans
persistent cuRobo + fast/fallback planner profile
motion continuity / ServoJ segmentation / blending options
stage-specific speed limits
force-feedback acceleration opportunity
AMR settle latency
gripper latency
synchronous evidence/logging overhead
WebUI/ART critical-path interference
event-driven pipelined Scheme runner
quantified top-10 optimization backlog
~~~

Hardware motion is forbidden in P3.8E.

## Current integration state to verify

When this queue entry was written, integration HEAD was observed as:

~~~text
e470fd46e8d77ba4e24394401d5dadcd4e50ab1b
feat(terminal): prepare selected demo from ART
~~~

Codex must verify current remote/local HEAD before using it.

## Existing implementation direction is paused, not cancelled

These remain valid but are NOT to be implemented during P3.8E:

~~~text
FORCE_MONITOR_V1
FORCE_GUARDED_CONTACT_V1
FORCE_GRASP_VERIFY_V1
native Scheme runner
stage-specific speed profiles
persistent pipeline improvements
full HOLD→place completion
~~~

Use P3.8E to decide the order and expected cycle-time impact.

## Required outputs

Create:

~~~text
docs/reports/2026-09-28_P3_8E_FULL_CYCLE_THROUGHPUT_AUDIT_REPORT.md
docs/roadmaps/2026-09-28_TRAY_TO_GROOVE_CYCLE_TIME_OPTIMIZATION_ROADMAP.md
~~~

The report must distinguish:

~~~text
MEASURED
REPLAY_BENCHMARKED
ESTIMATED
UNKNOWN
~~~

for all timing claims.

## Audit success condition

P3.8E is complete only when it provides:

~~~text
one measured current pick waterfall
one full-task critical-path model
one pipelined DAG
one low-risk Phase-1 acceleration plan
one Phase-2 continuity/pipelining plan
one optional Phase-3 streaming-scene plan
top-10 optimizations ranked by seconds saved / visible continuity / risk
quantitative cycle-time targets
~~~

## After P3.8E

Do not automatically resume the old P3.8D order.

Return to ChatGPT with the audit report.

ChatGPT/user will select the implementation phase, expected to start with the highest ROI low-risk changes.

## Git policy

Audit may create report/roadmap/instrumentation-only local changes if needed.
No force-push.
Do not execute hardware motion.
Stop with a local commit and report it.