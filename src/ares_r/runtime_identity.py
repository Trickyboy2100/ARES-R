"""One runtime identity shared by the canonical backend, ART and WebUI."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import time

from . import __version__


TASK_RUNTIME_VERSION = "1.1.0-p39b"
WEBUI_BUILD_VERSION = "2026.09.29-p39b"


def git_sha(root="."):
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(root), text=True,
            stderr=subprocess.DEVNULL, timeout=2).strip()
    except Exception:
        return "UNKNOWN"


def runtime_identity(root=".", *, started_monotonic=None, active_scheme=None):
    root=Path(root);sha=git_sha(root)
    central={"enabled":True,"half_width_m":.07,"revision":"LEGACY_DEFAULT"}
    path=root/"config/scene_aware_motion.json"
    if path.exists():central.update(json.loads(path.read_text()).get("central_exclusion",{}))
    return {
        "ares_r_version":__version__,"git_sha":sha,"git_sha_short":sha[:8],
        "task_runtime_version":TASK_RUNTIME_VERSION,
        "webui_build_version":WEBUI_BUILD_VERSION,
        "active_scheme":active_scheme,"central_exclusion":central,
        "backend_health":"READY",
        "backend_uptime_s":(None if started_monotonic is None else
                            max(0.0,time.monotonic()-started_monotonic)),
    }
