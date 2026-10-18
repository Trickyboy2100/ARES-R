# Mac worktree custody / diff report

2026-10-18. Source custody only; not a runnable release or deployed build.

| Worktree | HEAD | tracked modified | untracked | ignored | nonresident |
|---|---|---:|---:|---:|---:|
| local-ARES-R-offsets-20261016 | `9ff45177fdf9` | 13 | 373 | 795 | 41 |
| local-ARES-R-operations-20261015 | `b3ab33125c71` | 10 | 29 | 458 | 0 |
| local-ARES-R-data-archive-20261012 | `7120c3f3aad1` | 0 | 0 | 0 | 0 |
| local-ARES-R-data-archive-sparse-20261012 | `30f21c7b945c` | 0 | 0 | 0 | 0 |
| downloads-ARES-R | `da779767482f` | 0 | 35 | 8888 | 0 |
| downloads-ARES-R_CALIB | `7d2cde2be3f9` | 4 | 5 | 7 | 0 |
| downloads-ARES-R_BODY_WORK | `020d7ceb4405` | 0 | 13 | 1 | 0 |
| downloads-ARES-R-p39b-dev | `34b2ed8ff239` | 0 | 0 | 47 | 0 |
| downloads-ARES-R_DEMO_WORK | `31c423e8e363` | 1 | 10 | 89 | 0 |
| downloads-ARES-R-p36 | `131a47bbdeb2` | 0 | 9 | 146 | 0 |
| downloads-ARES-R_INTEGRATION_WORK | `b9673bc173b5` | 10 | 22 | 104 | 0 |
| downloads-ARES-R-body-camera | `d202baa61fa5` | 0 | 0 | 4 | 0 |

## Remote byte SHA256 coverage

- integration `7120c3f3aad17330d0af6ada1e39c60bc58fe7fb`: 1548 paths; 0 unresolved blobs.
- audit `b2b44528ee1df0d0aeed657754bcfcdae3cbc2be`: 1624 paths; 0 unresolved blobs.

## Critical runtime bytes

Full hashes and all worktrees: private CRITICAL_RUNTIME_FILE_MATRIX.json.

| Path | offsets | operations | GitHub integration | audit snapshot |
|---|---|---|---|---|
| `src/ares_r/webui/index.html` | `7925ed4e660c` | `fa57398c3640` | `2a79fa2a3fb8` | MISSING |
| `src/ares_r/webui/operations.html` | `afa3e1f03a21` | `38c0dd764b8c` | MISSING | MISSING |
| `src/ares_r/webui/operations.js` | MISSING | MISSING | MISSING | MISSING |
| `src/ares_r/webui/roundtrip_panel.js` | `4900805ea90c` | MISSING | MISSING | `4900805ea90c` |
| `src/ares_r/webui/server.py` | `b498a28fb8f1` | `f7c4a01c26a9` | `c1758c0748fb` | `b498a28fb8f1` |
| `src/ares_r/canonical_backend.py` | `b8de12cd066b` | `6a7d5af5d20f` | `a306867e93a1` | `b8de12cd066b` |
| `src/ares_r/demos/roundtrip_launcher.py` | `c0ee6367b4b4` | MISSING | MISSING | `c0ee6367b4b4` |
| `src/ares_r/manipulation/roundtrip_demo.py` | `5cd716932b54` | MISSING | MISSING | `5cd716932b54` |
| `scripts/run_grasp_place_roundtrip.py` | `682eb9a40beb` | MISSING | MISSING | `682eb9a40beb` |
| `scripts/build_first_pick_execution_package.py` | `e08e2097f4a7` | `e08e2097f4a7` | `ac396de120fe` | `e08e2097f4a7` |
| `scripts/prepare_authorized_first_pick.py` | `80e35ab8aad9` | `80e35ab8aad9` | `ff1965812431` | `80e35ab8aad9` |
| `scripts/verify_authorized_first_pick.py` | `c1a43f85704a` | `c1a43f85704a` | `c1a43f85704a` | `c1a43f85704a` |
| `scripts/resume_confirmed_grasp_lift.py` | `d9df5d207516` | MISSING | MISSING | `d9df5d207516` |
| `scripts/finish_confirmed_lift_hold.py` | `afe36af29eae` | MISSING | MISSING | `afe36af29eae` |
| `config/grasp_place_base_route.json` | `02521117b731` | MISSING | MISSING | MISSING |
| `config/planner_latency_profiles.json` | `ab33125d2352` | `138798ba356b` | MISSING | MISSING |
| `demos/right_arm_grasp_place_roundtrip_v1/demo.json` | `e49196bbb2b8` | MISSING | MISSING | MISSING |
| `demos/right_arm_grasp_place_roundtrip_v1/parameters.json` | `75dbf1832405` | MISSING | MISSING | MISSING |
| `src/ares_r/motion/production_scene_worker.py` | `6a706b15843f` | `3afcc99a0421` | `3fe91cdaddea` | `6a706b15843f` |
| `src/ares_r/motion/latency_solver.py` | `e853aac0c60a` | `e853aac0c60a` | MISSING | `e853aac0c60a` |
| `src/ares_r/motion/cpu_distance.py` | `199f8a656024` | `199f8a656024` | MISSING | MISSING |
| `src/ares_r/motion/native_execution_package.py` | `e42bff026233` | `e42bff026233` | `a90c51467326` | `e42bff026233` |
| `src/ares_r/motion/native_demo.py` | `38c150448e25` | `38c150448e25` | `38c150448e25` | `38c150448e25` |
| `src/ares_r/motion/planner_service_client.py` | `67762e8faa23` | `67762e8faa23` | `c1698f164093` | `67762e8faa23` |
| `src/ares_r/motion/persistent_planner_service.py` | `37a5243fb836` | `37a5243fb836` | `f9524e1ca62d` | `37a5243fb836` |
| `scripts/jaka_right_demo.cpp` | `d6ce1fd49867` | `d6ce1fd49867` | `d6ce1fd49867` | `d6ce1fd49867` |
| `tests/test_roundtrip_demo.py` | `7d9e182f9542` | MISSING | MISSING | MISSING |
| `tests/test_roundtrip_launcher.py` | `7ed7ed211894` | MISSING | MISSING | MISSING |
| `tests/test_latency_solver.py` | `9d866440aae5` | `223725222c0f` | MISSING | MISSING |
| `deploy/systemd/ares-r-backend.service` | `acb96ebe50b9` | `acb96ebe50b9` | `acb96ebe50b9` | MISSING |
| `deploy/systemd/ares-r-webui.service` | `f967a6102a1f` | `f967a6102a1f` | `f967a6102a1f` | MISSING |
| `scripts/run_first_pick_demo.py` | `e15848200460` | `e15848200460` | `e15848200460` | `e15848200460` |
| `demos/right_arm_epic_pick_lift_v1/demo.json` | `25b78297558e` | `25b78297558e` | `25b78297558e` | MISSING |
| `pyproject.toml` | `fa43f6ffd1e0` | `fa43f6ffd1e0` | `fa43f6ffd1e0` | MISSING |
| `config/system.json` | `e653cc2ac2b8` | `e653cc2ac2b8` | `e653cc2ac2b8` | MISSING |
| `config/robot_collision_model.json` | `ced234301012` | `ced234301012` | `ced234301012` | MISSING |
| `config/jaka_tools.site.json` | `9a591433d131` | `9a591433d131` | `9a591433d131` | MISSING |
| `config/jaka_mini2_motion.site.json` | `93da191f2376` | `93da191f2376` | `8aaafcb02220` | MISSING |

## Exact FAST differences

- offsets worker keeps cuboid_capacity buckets in runtime cache key; operations does not.
- operations parses solver_policy, uses solve_single_pass, caps goal candidates, uses native CPU distance and skips FAST baseline diagnostics.
- operations latency_contract is evaluated after solve; this is not active cancellation.
- both still contain warmup and benchmark_runs loops; effective request values must be verified.
- no source was selected or merged in this custody phase; neither filename nor HEAD proves site-loaded bytes.
- exact patches for five planner modules are retained privately, with both full source archives.

## Custody boundaries

Private tar archives are partitioned into source / data / dependencies_generated. Git bundles and both index/worktree patches preserve committed and dirty histories. Nonresident placeholders are inventoried but bytes are not claimed. No owner attribution is inferred from dirty status. No production sources edited, no motion, no public raw uploads.
Search scope: 12 repositories discovered beneath Documents/ChatGPT/local and Downloads; no PSSD mounted and no .codex/worktrees Git checkout found. Parent local/.git is unborn, not an ARES runtime repository. Newly created RC checkout is an output, not an input.
Sparse archive checkout may have skip-worktree entries absent on disk; git bundle preserves committed objects. tracked_missing does not by itself mean user deletion.
