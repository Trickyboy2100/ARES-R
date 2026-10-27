#!/usr/bin/env bash
# Offline GRASP evidence only. Does not call capture, SDK, sender or production services.
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
workspace="$(cd -- "$root/../.." && pwd)"
cd "$root"
python="${ARES_EVIDENCE_PYTHON:-$workspace/repos/ARES-R/.venv/bin/python}"
private="$root/worklog/runtime/grasp_v3"
out="$root/docs/presentations/assets/20261028_rasc_curobo/grasp_v3"
model="$private/model"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2
git fetch origin codex/data-grasp-20261021-public
"$python" tools/presentation_evidence/fetch_grasp_v3.py --output "$private/source"
"$python" tools/presentation_evidence/prepare_model.py --ares-repo "$workspace/repos/ARES" --output "$model"
scripts/offline_sandbox.sh "$python" tools/presentation_evidence/replay_rasc.py --grasp-oct21 --source "$private/source/unpacked" --private-output "$private/replay" --output "$out" --repeats 3
scripts/offline_sandbox.sh "$python" tools/presentation_evidence/compute_comparisons.py --grasp-oct21 --records "$private/source/unpacked/worklog/evidence/20261021-center-grasp-planner-study" --assets "$out" --private "$private/replay" --robot-yaml "$model/robot.yml" --urdf "$model/jaka_minicobo_gripper.urdf" --gpu-only
scripts/offline_sandbox.sh --gpu "$python" tools/presentation_evidence/replay_grasp_gpu.py --study "$private/source/unpacked/worklog/evidence/20261021-center-grasp-planner-study" --private "$private/replay" --output "$out" --model "$model"
scripts/offline_sandbox.sh "$python" tools/presentation_evidence/render_grasp_v3.py --source "$private/source/unpacked" --private "$private/replay" --output "$out"
scripts/offline_sandbox.sh "$python" tools/presentation_evidence/finalize_grasp_v3.py --source "$private/source/unpacked" --private "$private/replay" --output "$out" --model "$model"
printf '%s\n' "Open $out/index.html"
