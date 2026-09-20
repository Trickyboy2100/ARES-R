# ARES-R whole dual-arm collision asset audit — 2026-09-20

## Scope and safety

This audit is P2 only. It used saved read-only JAKA diagnostics and a stationary Pixel Pro BODY cloud. No AMR, arm, or gripper motion API was called. The production camera transform was consumed unchanged.

## Selected asset chain

- Pinned source: `Trickyboy2100/ARES@b978cbd669b5a3f6bc0bd19defcbe5256692f145`.
- Arm: pinned `jaka_minicobo_gripper.urdf` plus `Link0.STL` through `Link6.STL`.
- Gripper: pinned EG2-4C2 meshes, joints, mimic relations, and fixed identity mount `link6 -> 4C2_baselink`.
- BODY mounts: `config/robot_world.json`; left `[0,+0.2,1.2] m`, right `[0,-0.2,1.2] m`.
- Live tool/TCP metadata: left tool 3 and right tool 2 from the saved JAKA diagnostics.

The original meshes and kinematic chain remain authoritative. Collision OBBs are generated mechanically from their mesh bounds; no generic arm or gripper proxy replaces them.

## Classification

| Asset | Classification | Evidence / decision |
|---|---|---|
| Mini2 joint chain and Link0–Link6 origin/axis | `VALIDATED_AFTER_SITE_CHECK` | 17 controller-FK samples per arm. Current left/right maximum translation disagreements are 1.299 mm / 1.014 mm and orientation disagreements are 0.000329° / 0.000208°. |
| Arm Link0–Link6 STL geometry | `VALIDATED_AFTER_SITE_CHECK` | Pinned ARES meshes, immutable SHA-256 manifest, exact URDF link transforms, and BODY cloud overlay. |
| Legacy ARES cuRobo spheres | `MISSING_BLOCKER` | `base_link` and every EG2-4C2 link have empty lists; Link6 has only two 2 mm spheres; several link spheres follow incompatible/insufficient extents. These spheres are not selected for P2 production geometry. |
| Mesh-derived per-link collision OBBs | `VALIDATED_AFTER_SITE_CHECK` | Generated from each pinned Link STL and transformed by the same canonical FK used by overlay, filtering and collision checks. |
| EG2-4C2 mesh and `link6` mounting | `VALIDATED_AFTER_SITE_CHECK` | Pinned mesh/URDF chain; identity fixed base mounting; overlay places the envelope beyond Link6 on the TCP side. |
| Gripper opening state | `CONSERVATIVE_PROXY` | No trusted live opening angle entered this snapshot. The union of every gripper mesh at 0, 0.41 and 0.82 rad produces a conservative full-opening envelope. |
| JAKA tool/TCP | `VALIDATED_AFTER_SITE_CHECK` | Read-only controller diagnostics: left tool 3 `[1.949,-33.966,80.2] mm`; right tool 2 `[27.946,-2.365,81.402] mm`; marker is enclosed by the gripper envelope. |
| BODY left/right base transforms | `VALIDATED_AFTER_SITE_CHECK` | Previously commissioned BODY convention and current base-frame overlay. |
| AGV/chassis | `CONSERVATIVE_PROXY` | Conservative BODY OBB pending measured CAD. It may remove only robot-owned near-body points and is not used to claim dimensional validation. |
| 14 cm central exclusion | `VALIDATED_EXISTING_MODEL` | BODY `|Y| <= 0.070 m` constraint. It participates in planning-world output but has `filter_owned=false`, because it is not physical robot material. |

## Canonical backend and revision policy

`src/ares_r/perception/robot_collision.py` is the one BODY geometry backend for:

1. overlay;
2. self-filter;
3. inactive-arm obstacle export;
4. offline mutual-arm collision tests.

Every snapshot binds geometry, live joint and tool revisions. The inactive-arm obstacle revision includes the inactive joint vector, tool revision and canonical box payload; changing the inactive state therefore changes the scene revision.

## Site overlay conclusion

The visible right-arm returns plausibly coincide with the orange Link0–Link6 geometry and magenta gripper envelope. Left-arm returns are sparse/occluded in this fixed camera snapshot, while its base side, FK chain and gripper direction remain independently checked by controller FK and the BODY model. Both base origins are at the configured left/right locations. The central slab is visualization/planning geometry only.

Evidence and immutable asset hashes are in `worklog/evidence/2026-09-20-p2-collision-model/` and `worklog/generated/robot_collision_model_manifest.json`.
