# Skill-Handoff Research Smoke — ARES × ARES-R

**Branch:** `research/skill-handoff-smoke-20261012` (isolated from real robot production).
**Baseline:** ARES `main@b978cbd669b5a3f6bc0bd19defcbe5256692f145`; ARES-R integration `7120c3f3aad17330d0af6ada1e39c60bc58fe7fb`.
**Safety:** These scripts perform **NO hardware I/O**. Do not merge or execute physical tasks from this branch. Newer October site work may be uncommitted and is not included in this branch.

## Three candidates

- **A — downstream-conditioned terminal-state selection:** rank discrete grasp symmetry and Cartesian center IK/yaw choices given the *remaining task*, reuse cuRobo for free-space segments and hard collision/limit validation; try contextual success-ranker/bandit before masked Q-learning. Related: STAP (ICRA 2023), RAPS (NeurIPS 2021).
- **B — learned Bridge Option / termination matching:** train a goal-conditioned transition skill between predecessor terminal distribution and successor initiation region. Related: Adversarial Skill Chaining (CoRL 2021), Curriculum-guided skill learning (Robotics and Autonomous Systems 2025).
- **C — learned skill-outcome model + rolling optimization:** predict next predicates, time, probability and uncertainty and select termination, observation and prepare strategy under a bounded compute budget. Related: SkiMo (CoRL 2022), TAMPURA.

Start with **A**; keep the same typed scenario/candidate interface to permit B/C later. Qwen, VLA and WebUI are not prerequisites.

## Smoke-0 — evidence integrity (implemented)

On an exported 2026-10-12 frozen-planning archive:

```bash
PYTHONPATH=src:. python3 -m unittest tests.test_skill_handoff_research_smoke -v
PYTHONPATH=src:. python3 -m research.skill_handoff_smoke.audit_plans \
  --input /absolute/path/ARES-R_2026-10-12_Preland_Planning_Records \
  --output /tmp/ares_r_handoff_smoke0
PYTHONPATH=src:. python3 -m research.skill_handoff_smoke.headroom \
  --input /tmp/ares_r_handoff_smoke0/planner_records.jsonl \
  --output /tmp/ares_r_handoff_smoke0/headroom.json
```

`headroom` deliberately exits 3 until actual candidate-wise downstream results exist. The 2026-10-12 archived planning traces yielded **19** parsable request/result pairs (**8** planning SUCCESS, **11** planning FAILURE) but **0** verified downstream skill labels. This is a useful provenance smoke, **not** RL feasibility or task success evidence.

## Smoke-1 — real kinematics/collision problem-existence probe (not yet run)

Use existing code rather than building a fake physics oracle:

1. ARES pinned URDF and `core/kinematics.py` for robot/tool geometry.
2. ARES-R `RuntimeMultiIKBackend` and `TransferChainPlanner` (existing deterministic heuristic comparator).
3. Existing ARES-R `SceneAwareMotionService`, persistent cuRobo and **the same** collision, site soft joint limits, horizontal-orientation checks, and fresh/frozen scene contract.

Initial affordable probe: 6 low-cost contexts spanning at least 2 semantic destination layouts; for each context compare at least 4 terminal candidates (normal/flipped grasp × 2 plausible center yaw/IK branches). Prune with IK/endpoint/soft limits before any expensive cuRobo solve. At most one bounded FAST and one bounded FALLBACK per surviving *segment*. Identical frozen scenarios should be repeated under different planner seeds, with such attempts grouped rather than counted as independent scenarios. Never execute JAKA/AMR/gripper.

Output a JSONL table with: `context_id`, `task_family`, `scene/tool/config revision`, `candidate_id`, `heuristic_rank`, `next_skill`, `next_skill_preconditions`, `downstream_skill_success` (boolean only if actually verified; otherwise null), `failed_stage`, `failure_class`, `planner_calls`, `planner_wall_s`, `min_clearance`, and links to source request/result hashes.

**First question:** are there fully controlled cases in which at least two candidates for the *same* state are both valid predecessors but different in successor feasibility? Does the current heuristic miss the better one? If not, do NOT train RL for this task.

## Smoke-2 — learning and generalization (not yet run)

Once scientifically controlled downstream labels exist and Smoke-1 exposes an oracle-vs-heuristic gap:
- Start with a *supervised ranker* and a contextual bandit as null hypotheses. If there is only one decision per episode, claiming RL advantage would be unjustified.
- Build a 2–3 step semi-Markov option environment with decisions about grasp/center termination and later preparation/re-observation; test whether delayed reward and observations change the optimal earlier choice.
- Try masked Double DQN or MaskablePPO (sb3-contrib) only if sequential control warrants it.
- Compare: fixed policy, greedy per-skill, existing `transfer_chain.py` heuristic, equal-call-budget full-chain beam/DP, supervised ranker, RL. Keep held-out *scene/task families*, common planner budgets and multiple seeds.
- Metrics: verified next-skill initiation success (HSR), total task success, latency, number of cuRobo calls, soft-limit/collision rejection, calibration to held-out tasks and confidence intervals.

If a deterministic full-chain planner already matches the oracle with acceptable compute, report that honestly; stronger RL performance is not guaranteed.

## Important simulation caveat

ARES Isaac Sim `tray_grasp_cycle/demo.py` simplifies grasp with FixedJoint; it also documents a simulator-only single-frame target jump when cuRobo fails. Those cases CANNOT yield valid collision-constrained RL success labels. Any scientific Isaac benchmark must remove/flag that fallback and distinguish physical contact from kinematic attachment.
