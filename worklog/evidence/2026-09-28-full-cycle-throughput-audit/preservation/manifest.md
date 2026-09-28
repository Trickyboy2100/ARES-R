# P3.8E preservation manifest

Captured: 2026-09-28, before P3.8E audit changes.

```text
branch = feat/e2e-v0-integration-20260917
dot32_HEAD = e470fd46e8d77ba4e24394401d5dadcd4e50ab1b
GitHub_canonical_HEAD = e470fd46e8d77ba4e24394401d5dadcd4e50ab1b
dot32_origin_tracking_HEAD = d7c9428bf1b66b796eebe701bfbb846e4fba9621 (STALE; not canonical)
baseline_tests = 517 OK, skipped=1, 5.251 s
```

## Canonical

- `e470fd46e`: Demo Library, selected-demo ART/WebUI interface and preserved first-pick flow.
- Successful first-pick evidence under `worklog/evidence/2026-09-24-p3-8b1a/live_pick_authorized_20260924T175237/`.

## Preserved unrelated local work

The following tracked changes existed before P3.8E and were neither edited nor staged by the audit:

```text
M src/ares_r/motion/grasp.py
M tests/test_grasp.py
```

The worktree also contained many untracked historical evidence directories plus:

```text
docs/COMMAND_REFERENCE.md
docs/assets/ares_r_pick_place_storyboard.png
docs/assets/ares_r_pick_place_workflow.gif
docs/work_orders/2026-09-21_RIGHT_ARM_TRAY_TO_GROOVE_PICK_PLACE_ORDER.md
```

Classification:

| Class | Content | Action |
|---|---|---|
| `KEEP_CODE` | tracked `grasp.py` / `test_grasp.py` changes | preserved, excluded from audit commit |
| `KEEP_EVIDENCE_SMALL` | first-pick manifests/JSON/JSONL | read only |
| `KEEP_LOCAL_LARGE` | historical pointcloud/NPZ/PLY/evidence trees | preserved, excluded |
| `GENERATED_REPRODUCIBLE` | P3.8E replay benchmark JSON | audit commit only |
| `TEMPORARY_REVIEW_REQUIRED` | untracked docs/assets above | preserved, excluded |

No reset, revert, clean, deletion or force operation was performed.
