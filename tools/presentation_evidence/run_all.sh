#!/usr/bin/env bash
# No production service, capture, SSH, robot SDK or device entry point.
set -euo pipefail
[[ $# == 3 ]] || { echo 'usage: run_all.sh RECORDS_DIRECTORY PINNED_ARES_GIT_REPO PYTHON'; exit 2; }
records="$(realpath "$1")";ares_source="$(realpath "$2")";python="$(realpath "$3")"
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)";cd "$root"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2
private="${ARES_EVIDENCE_PRIVATE:-worklog/runtime/presentation_evidence}"
output="${ARES_EVIDENCE_OUTPUT:-docs/presentations/assets/20261028_rasc_curobo}"
mkdir -p "$private" "$output/runlogs"
export MPLCONFIGDIR="$root/worklog/runtime/cache/matplotlib"
scripts/offline_sandbox.sh --gpu "$python" tools/presentation_evidence/check_isolation.py "$output/runlogs/isolation.json"
scripts/offline_sandbox.sh --gpu "$python" tools/presentation_evidence/collect_environment.py "$output/runlogs/environment.json"
"$python" tools/presentation_evidence/prepare_model.py --ares-repo "$ares_source" --output "$private/model"
scripts/offline_sandbox.sh "$python" tools/presentation_evidence/replay_rasc.py --source "$records/real_aligned_sources" --private-output "$private" --output "$output" --repeats 5 > "$private/rasc.log" 2>&1
scripts/offline_sandbox.sh --gpu "$python" tools/presentation_evidence/compute_comparisons.py --records "$records" --private "$private" --assets "$output" --robot-yaml "$private/model/robot.yml" --urdf "$private/model/jaka_minicobo_gripper.urdf" --gpu > "$private/comparisons.log" 2>&1
scripts/offline_sandbox.sh "$python" tools/presentation_evidence/prepare_ui.py --private "$private" --output "$output" > "$private/ui_prepare.log" 2>&1
"${ARES_NODE:-node}" tools/presentation_evidence/capture_ui.cjs "$private" "$output/panels/runtime" > "$private/ui_browser.log" 2>&1
"$python" tools/presentation_evidence/render_assets.py --private "$private" --output "$output" > "$private/render.log" 2>&1
"$python" tools/presentation_evidence/extra_figures.py --private "$private" --output "$output" > "$private/extra.log" 2>&1
scripts/offline_sandbox.sh "$python" tools/presentation_evidence/run_regressions.py --output "$output/runlogs"
"$python" tools/presentation_evidence/write_reports.py --private "$private" --output "$output"
"$python" tools/presentation_evidence/finalize_bundle.py --private "$private" --output "$output"
"$python" tools/presentation_evidence/verify_bundle.py --output "$output"
printf 'Offline evidence gallery: %s/index.html\n' "$output"
