# P3.9B center pose recovery

The teammate-created center/chest posture was recovered from the effective
`.32` worktree before P3.9B implementation. It was present as an uncommitted
change to `config/named_poses.json` and `docs/NAMED_POSES.md`, with supporting
files under `tmp/place_9.28/` and
`worklog/evidence/2026-09-28-place/center_exec_20260928T172814/`.

It is not the existing `ready` pose. The recovered right-arm target is:

```text
BODY TCP xyz = [0.3583093030168863, -0.0800000000, 1.0278356006116391] m
BODY TCP rpy = [pi/2, 0, pi] rad
right joints = [-4.16054218920497, 0.12380159547135215,
                -1.6410621564086367, -5.609400696253764,
                -1.1920778258720994, -2.656972108297568] rad
```

Read-only evidence records a 2026-09-28 supervised cuRobo/ServoJ execution,
138 samples over 10.96 seconds, and zero endpoint joint residual. Tool Y points
along BODY +Z and tool Z along BODY +Y, which is the recorded horizontal tray
orientation. P3.9B preserves the values unchanged and still requires a fresh
scene, attached-object geometry and a new cuRobo plan before any execution.

`CENTER_POSE_SOURCE_VERIFIED = YES`
