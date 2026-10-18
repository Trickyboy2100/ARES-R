#!/usr/bin/env bash
# Network/serial isolation inherited by Python, SDKs and subprocesses.
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
args=(--die-with-parent --new-session --unshare-net --unshare-ipc
      --ro-bind / / --dev /dev --proc /proc --tmpfs /tmp
      --bind "$root" "$root" --chdir "$root"
      --setenv ARES_R_OFFLINE_REPLAY 1 --setenv CUDA_VISIBLE_DEVICES 0
      --setenv PYTHONPATH "$root/src"
      --setenv XDG_CACHE_HOME "$root/worklog/runtime/cache"
      --setenv ARES_R_CUROBO_CACHE "$root/worklog/runtime/cache/curobo"
      --setenv WARP_CACHE_PATH "$root/worklog/runtime/cache/warp"
      --setenv NUMBA_CACHE_DIR "$root/worklog/runtime/cache/numba"
      --setenv MPLCONFIGDIR "$root/worklog/runtime/cache/matplotlib"
      --setenv CUDA_CACHE_PATH "$root/worklog/runtime/cache/cuda")
if [[ "${1:-}" == --gpu ]]; then
    shift
    for device in /dev/nvidia0 /dev/nvidiactl /dev/nvidia-uvm /dev/nvidia-uvm-tools; do
        [[ ! -e "$device" ]] || args+=(--dev-bind "$device" "$device")
    done
fi
[[ $# -gt 0 ]] || { echo 'usage: offline_sandbox.sh [--gpu] COMMAND ...' >&2; exit 2; }
exec bwrap "${args[@]}" -- "$@"
