# 2026-10-12 Preland real-aligned evidence

This directory is the Git-managed index for the 2026-10-10 through 2026-10-12
Center/Transit/Preland field-planning records. It is intended to let a research
host bind planner requests, SceneSnapshots, calibration revisions, and the
three real point-cloud epochs without changing production configuration.

## Public-repository boundary

`Trickyboy2100/ARES-R` is a public repository. The full archive contains field
point clouds, local network identifiers, controller paths, and physical scene
state. Therefore the following binary payloads are deliberately **not** stored
in Git or Git LFS:

- `raw_camera_captures/*/pointcloud_camera_mm.npy`
- `body_cloud_artifacts/*/body_cloud.npz`
- `scenes/*/scene/clean_residual.npz`
- `ARES-R_2026-10-12_Preland_Planning_Records_REAL_ALIGNED.tar.gz`

This public branch contains only the archive index, complete member hash lists,
controlled-binary manifest, and verification utility. Frozen planner requests,
SceneSnapshots, collision worlds, live robot state, site configuration, local
network identifiers, absolute field paths, and point-cloud binaries remain in
the controlled archive. No password, token, private key, or API credential was
found by the pre-publication scan.

## Full controlled archive

- file: `ARES-R_2026-10-12_Preland_Planning_Records_REAL_ALIGNED.tar.gz`
- bytes: `114867535`
- SHA256: `69c10d90cdcc5483c70409404bb80bb50bf9ee00700d677ecbe9b138b49c8964`
- top-level directory after extraction:
  `ARES-R_2026-10-12_Preland_Planning_Records/`

Run `./verify_archive.sh /path/to/ARES-R_2026-10-12_Preland_Planning_Records_REAL_ALIGNED.tar.gz`
on the Ubuntu research host. Verification is successful only when the archive
hash, gzip/tar integrity, and every entry in
`real_aligned_sources/SHA256SUMS.txt` pass.

## Three time-bound real datasets

| case | SceneSnapshot | CAMERA capture | BODY artifact | CAMERA SHA256 |
|---|---|---|---|---|
| split Center→Transit→Preland | `SCENE_133c1fca71484bd2abea0cb3e0b6af8d` | `20261010_114817_fecbdf64` | `20261010_114819_091f37ab` | `a9031515bada1c3859bec842d145f44d8ce407ac9af3c8fea95478d7ea463b8f` |
| one-shot, complete but yaw-free | `SCENE_79c016c8062b433684c6d4793f9a0c01` | `20261010_160941_3b7f44c4` | `20261010_160943_b01df85d` | `717fed60133d63c6a321b73ffd6da78e9b894e97958993b3154384f44c0e6352` |
| final forward yaw, 70 mm preland | `SCENE_61f1f6d4c63541068396069319124185` | `20261010_172331_6d8ec0af` | `20261010_172333_96562cc8` | `09dd21de9542b566bee79097aef079d4cddf83c190cedea8cd2da4908a4d3fa9` |

All three BODY manifests bind the same commissioned transform revision
`sha256:ccb214ea13b7020528d98d7a532908427c25d61c3ce1d40bd0a833e61a7a4e6c`
and validation revision
`sha256:23e44f93cb0b498792e8069628448f53813eed0b38a4951fb1b5e034764b7e11`.
CAMERA coordinates are millimetres; BODY coordinates are metres. The actual
per-epoch BODY manifest is authoritative over stale top-level configuration.

## Reproduction order

1. Obtain the controlled archive from the delivery location recorded in
   `DELIVERY_MANIFEST.json`.
2. Run `verify_archive.sh` before using any file.
3. Read `real_aligned_sources/README_REAL_ALIGNED.md` and each capture/BODY
   manifest.
4. Bind each planner request to its listed SceneSnapshot and point-cloud epoch.
5. Treat `config_snapshot/site_config_20261014/` only as a selected 2026-10-14
   reference snapshot. It is not a byte-for-byte 2026-10-10 configuration
   freeze and must not overwrite a production installation.
6. Preserve the documented `system.json` versus stale
   `pointcloud_pipeline.site.json` calibration-status conflict; use the
   transform revision embedded in each BODY manifest.

`SOURCE_RECORDS_SHA256SUMS.txt` and `REAL_ALIGNED_SOURCE_SHA256SUMS.txt` refer
to the complete controlled archive and therefore name files intentionally not
published in Git. `PUBLIC_INDEX_SHA256SUMS.txt` verifies only this public index.

The complete records are not available from this public branch alone. This is
intentional: reproduction requires the controlled archive plus a successful
run of `verify_archive.sh`.


