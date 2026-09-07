#!/usr/bin/env python3
"""Run the ARES-R Terminal's read-only JAKA baseline command."""

import os
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parent.parent
env = dict(os.environ)
env["PYTHONPATH"] = str(root / "src") + (":" + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
env["ARES_R_HARDWARE_CONFIRM"] = "YES"
commands = "jaka baseline\nquit\n"
subprocess.run(
    [env.get("ARES_R_PYTHON", "python3"), "-m", "ares_r.cli", "--enable-hardware"],
    cwd=str(root), env=env, input=commands, text=True, check=True,
)
