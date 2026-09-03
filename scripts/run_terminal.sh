#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo_dir"
export PYTHONPATH="$repo_dir/src${PYTHONPATH:+:$PYTHONPATH}"
python_bin="${ARES_R_PYTHON:-python3}"
if [[ " $* " == *" --mode gripper-only "* ]] && ! "$python_bin" -c 'import serial' >/dev/null 2>&1; then
  server_python="/home/yikun/anaconda3/envs/dope3.8/bin/python"
  if [[ -x "$server_python" ]]; then
    python_bin="$server_python"
    echo "Using $python_bin for gripper serial support."
  else
    echo "gripper-only mode requires pyserial; set ARES_R_PYTHON to a compatible interpreter." >&2
    exit 2
  fi
fi
exec "$python_bin" -m ares_r.cli "$@"
