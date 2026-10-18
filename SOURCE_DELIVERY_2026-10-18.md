# ARES-R Mac source delivery for Ubuntu

Branch: `codex/roundtrip-source-delivery-20261018`.

This branch uploads the necessary October Mac source files that were absent or
older on GitHub. It is a **source delivery**, not a claim that the October
roundtrip has completed GPU replay or site commissioning. No robot was operated
to prepare this delivery. Production integration and golden first-pick remain
unchanged on their branches.

## Obtain on Ubuntu

In a fresh checkout (do not switch over a dirty research worktree):

```sh
git clone --branch codex/roundtrip-source-delivery-20261018 --single-branch \
  https://github.com/Trickyboy2100/ARES-R.git ARES-R-roundtrip-source
cd ARES-R-roundtrip-source
shasum -a 256 -c worklog/source-delivery/2026-10-18/SHA256SUMS
# On Ubuntu, sha256sum -c may be used instead of shasum -a 256 -c.
```

An existing clean repository can use `git fetch origin` followed by a new local
branch tracking `origin/codex/roundtrip-source-delivery-20261018`.

## Current source locations

| Component | Location |
|---|---|
| Frontend | `src/ares_r/webui/index.html`, `operations.html`, `roundtrip_panel.js` |
| Web server | `src/ares_r/webui/server.py` |
| Canonical backend | `src/ares_r/canonical_backend.py` |
| Launcher | `src/ares_r/demos/roundtrip_launcher.py` |
| 19-stage runner | `scripts/run_grasp_place_roundtrip.py` |
| Stage recipe | `src/ares_r/manipulation/roundtrip_demo.py` |
| Demo parameters | `demos/right_arm_grasp_place_roundtrip_v1/parameters.json` |
| Route / planner profiles | `config/grasp_place_base_route.json`, `config/planner_latency_profiles.json` |
| Native packaging/source | `src/ares_r/motion/native_execution_package.py`, `native_demo.py`, `scripts/jaka_right_demo.cpp` |
| Service templates | `deploy/systemd/ares-r-backend.service`, `ares-r-webui.service` |
| Tests | `tests/test_roundtrip_*.py` and related planner/operations/geometry tests |
| File provenance / hashes | `worklog/source-delivery/2026-10-18/SOURCE_MANIFEST.json`, `SHA256SUMS` |

## FAST version split — preserved, not silently merged

The canonical files retain the exact `ARES-R-offsets-20261016` bytes. Its worker
does **not** consume the single-pass solver policy. The operations worktree has
the single-pass FAST implementation, but lacks the offsets cuboid-capacity cache
fix. Do not overwrite one with the other without review and frozen GPU testing.

All differing/operations-only relevant files are preserved under:

`worklog/source-delivery/2026-10-18/operations-variants/`

Exact diffs are in `planner-diffs/`. Shared dependencies (`latency_solver.py`,
`cpu_distance.py`, `sphere_cuboid_cpu.cpp`) are present in canonical source. A
post-hoc latency-budget check is not cancellation. Neither variant establishes
which code the October16 site process actually loaded.

## Boundaries

- No raw workplace pointcloud/images, private run logs, credentials, vendor SDK
  binaries or cached native `.so` were added in this delivery.
- Station configs are preserved source snapshots, not current robot state.
  `.32` absolute interpreter/asset paths need explicit Ubuntu replay overrides.
- Exact pinned URDF/STL/spheres, site JAKA binary/SDK dependencies and original
  October16 frozen inputs are still required. They are **not** supplied by a
  README or by a source hash; missing inputs must stay INCOMPLETE.
- Recovery scripts are historical diagnostics, not formal task resume.
- Do not run execute/start/service-install commands to validate a source pull.
  First establish a hardware-network-isolated offline environment.
- No full physical or GPU pass is claimed. See the October18 gap/replay reports.

Golden files retain SHA256:

```text
e158482004601bbb1e562ee842fb590f27805813b7d7ee029ce5e59e41ea2bb0  scripts/run_first_pick_demo.py
25b78297558e755895d3a0202f0afe43147ac5625539c70bd7e790343b246056  demos/right_arm_epic_pick_lift_v1/demo.json
```
