# P1.5 — Realign .32 integration branch with GitHub before P2

## 0. Why this phase exists

P1 is correctly pushed to GitHub as:

~~~text
c5ed44515cbe4d5e298f74117f4ac02bbccb3f20
feat(perception): add canonical BODY cloud viewer
~~~

But the .32 worktree still points to an equivalent-but-divergent local history:

~~~text
.32 local:
74e09c8  P0-A equivalent
02a03f23 P0-B equivalent
2efbdb4  P1 equivalent

GitHub:
7ca1e1a  P0-A
4313a819 P0-B
c5ed445  P1
~~~

Patch contents are equivalent, but the commit graphs differ. P2 must not start on top of the divergent .32 branch, otherwise every future push will need another replay.

## 1. Goal

Before P2:

~~~text
preserve .32 current history and local-only files
→ classify untracked/dirty files
→ import GitHub c5ed445 into .32 by trusted relay
→ move the official .32 integration branch pointer onto exactly c5ed445
→ keep preservation refs/artifacts
→ run full tests
→ leave a clean single-line official branch
~~~

No robotics code changes in P1.5.

## 2. Do NOT do

- no force-push;
- no blanket reset before preservation;
- no deletion of untracked files before classification;
- no cherry-pick of equivalent P0/P1 commits onto c5ed445;
- no robot/camera/base motion;
- no P2 implementation until branch alignment is complete.

## 3. Preserve the current .32 state

Create a dated preservation branch from the current local HEAD, e.g.:

~~~text
preserve/site-20260920-pre-p2-realign
~~~

This branch protects the local commit chain.

Important: a branch does NOT preserve untracked files.

Also create a repo-local preservation package under:

~~~text
worklog/preservation/2026-09-20-pre-p2-realign/
~~~

Record:

- current branch/HEAD;
- git log graph;
- git status --porcelain;
- tracked diff patch if any;
- list of untracked files with byte sizes and SHA256 where practical;
- classification manifest.

For untracked files classify into:

~~~text
KEEP_CODE
KEEP_EVIDENCE_SMALL
KEEP_LOCAL_LARGE
GENERATED_REPRODUCIBLE
TEMPORARY_REVIEW_REQUIRED
~~~

Known examples requiring classification include:

~~~text
scripts/plan_right_grasp.py
scripts/probe_epic_grasp_points.py
worklog/evidence/2026-09-20-epic-grasp-probe/
worklog/generated/right_curobo_geometry.json
worklog/generated/right_live_state.json
worklog/pregrasp/
~~~

Do not delete these automatically.

Small source/tests/docs/evidence that are clearly valuable may be committed on the preservation branch only after review. Large pointcloud/log/generated files remain local with manifest + hashes.

## 4. Import the GitHub canonical branch into .32

Because .32 currently has no GitHub SSH identity, use the already proven trusted relay workflow.

The trusted machine with GitHub credentials should obtain:

~~~text
origin/feat/e2e-v0-integration-20260917
= c5ed44515cbe4d5e298f74117f4ac02bbccb3f20
~~~

Transfer that commit/ref to .32 via Git bundle / SCP or equivalent Git-native transport.

On .32 create/update a remote-tracking-style ref, for example:

~~~text
refs/remotes/github-relay/feat/e2e-v0-integration-20260917
~~~

Verify exact SHA is c5ed445 before changing the official branch.

## 5. Repoint the official .32 integration branch safely

After preservation is complete and worktree is clean:

1. checkout the preservation branch;
2. move the official branch ref:

~~~text
feat/e2e-v0-integration-20260917
→ c5ed44515cbe4d5e298f74117f4ac02bbccb3f20
~~~

3. checkout feat/e2e-v0-integration-20260917;
4. verify HEAD exact match with the imported canonical ref.

Prefer updating the branch ref while checked out on the preservation branch rather than using a destructive reset on an unpreserved worktree.

## 6. Upstream / sync policy

Two acceptable modes:

### Mode A — relay mode (preferred for now)

Do not place a personal GitHub private key in the shared yikun account.

Document:

~~~text
.32 is execution/test host
trusted workstation is GitHub relay
~~~

Maintain a helper/documented procedure to refresh the local github-relay ref via bundle.

In this mode, do NOT claim normal git pull will work.

### Mode B — repository-scoped deploy key

Only if the team deliberately wants direct .32 GitHub access, configure a repository-scoped deploy key with the minimum necessary permission.

Then configure:

~~~text
branch.feat/e2e-v0-integration-20260917.remote = origin
branch.feat/e2e-v0-integration-20260917.merge = refs/heads/feat/e2e-v0-integration-20260917
pull.ff = only
~~~

Do not create or install credentials during P1.5 unless explicitly requested.

## 7. Verification

After realignment run:

~~~text
PYTHONPATH=src python3 -m unittest discover -s tests -q
~~~

Expected baseline is at least the pushed P1 suite (395 tests).

Also verify:

~~~text
git status --short --branch
git rev-parse HEAD
git log --oneline --decorate --graph -12
~~~

Official branch must be clean before P2.

## 8. Exit report

Report:

1. preservation branch name and SHA;
2. preservation manifest path;
3. untracked-file classification summary;
4. official .32 branch HEAD;
5. GitHub canonical HEAD;
6. whether exact SHAs match;
7. test result;
8. chosen future sync mode (relay/deploy-key);
9. any local-only artifacts intentionally retained.

Exit target:

~~~text
DOT32_INTEGRATION_ALIGNED_WITH_GITHUB = YES
WORKTREE_CLEAN_FOR_P2 = YES
~~~

No push is required in P1.5 unless a preservation documentation change itself is intentionally added to GitHub after review.
