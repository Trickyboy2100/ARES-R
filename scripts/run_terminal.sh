#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo_dir"
export PYTHONPATH="$repo_dir/src${PYTHONPATH:+:$PYTHONPATH}"
python_bin="${ARES_R_PYTHON:-python3}"
exec "$python_bin" -m ares_r.cli "$@"
