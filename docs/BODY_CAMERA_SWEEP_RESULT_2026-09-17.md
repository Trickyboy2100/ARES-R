# BODY-camera translation sweep result — 2026-09-17

## Safety and scope

- Calibration hardware scope enabled only the Pixel Pro and AMR adapter.
- Both arms and both grippers remained disabled.
- AMR rotation was never requested; translation speed was limited to `0.05 m/s`.
- The AMR was explicitly stopped after the final observation.

## Captures

Calibration run:

```text
logs/calibration/body_camera/20260917_163644_0dd5978e
```

| Frame | Commanded BODY displacement | Observed result |
| --- | ---: | --- |
| origin | `(0, 0) m` | reference |
| `sweep_xplus` | `(+0.09, 0) m` | translation observed |
| `sweep_xminus` | return to `(0, 0) m` | return observed |
| `sweep_yminus` | `(0, -0.09) m` | translation **not** observed |

No `+Y` return was sent after the ineffective `-Y` request, because the cloud
showed that the robot was already at the origin. This avoided movement to the
left of the initial pose.

## Registration metrics

| Pair against origin | Estimated translation norm | Rotation drift | Fitness | RMSE |
| --- | ---: | ---: | ---: | ---: |
| `sweep_xplus` | `0.08934 m` | `0.463 deg` | `0.7204` | `9.26 mm` |
| `sweep_xminus` | `0.00355 m` | `0.105 deg` | `0.8648` | `5.66 mm` |
| `sweep_yminus` | `0.00357 m` | `0.107 deg` | `0.8645` | `5.55 mm` |

The forward translation scale was `0.9914`. Return-to-origin consistency
passed with a horizontal residual of `3.52 mm`.

The valid forward sample gives a single-axis yaw estimate of `-72.91 deg`.
The table-edge prior branch is `-79.56 deg`, producing a disagreement of about
`6.64 deg`. A second valid, non-collinear translation is required before yaw
can pass the `2 deg` commissioning gate.

The AMR endpoint returned `status=3` for both the effective `+X` request and
the ineffective `-Y` request. It is therefore not a trustworthy proof of
physical displacement. The point-cloud validator now rejects a commanded
translation whose observed scale is below `0.5`, so the ineffective lateral
sample cannot contaminate the yaw estimate.

## Current transform state

- roll/pitch source: table support plane
- z source: `TABLE_HEIGHT_0.750`; camera BODY z prior `1.56957 m`
- yaw source: table-edge prior plus incomplete one-axis sweep
- tx/ty source: missing
- state: `UNCOMMISSIONED`
- `BODY_SCENE_ALLOWED`: `NO`

Still required:

1. Commission or otherwise verify a second non-collinear AMR translation.
2. Measure Pixel Pro optical-center `x/y` relative to BODY origin, including
   reference points and estimated uncertainty.
3. Run fixed-rotation/fixed-z, tx/ty-only refinement and overlay validation.

Free 6DoF ICP remains prohibited. Production SceneSnapshot generation and
production CLEAR/AVOID/BLOCK planning are not started while the transform is
uncommissioned.

```text
READY_FOR_SUPERVISED_CLEAR = NO
READY_FOR_SUPERVISED_AVOID = NO
```

