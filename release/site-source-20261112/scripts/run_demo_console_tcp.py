#!/usr/bin/env python3
"""TCP command port for the demo console (demo-0 = `right_arm_return_center_v1`).

Start it next to the running RC1 webui::

    PYTHONPATH=src .venv/bin/python scripts/run_demo_console_tcp.py

Then a client can use newline-delimited JSON on 127.0.0.1:8790::

    {"cmd":"ping"}
    {"cmd":"status"}
    {"cmd":"run","demo":"demo-0",
     "authorization":"RUN demo-0-return-center",
     "onsite_observer_confirmed":true,
     "prepared_environment_confirmed":true}

Motion is never started without the same authorization phrase and现场确认 the
web console requires; the TCP layer only forwards them.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from ares_r.demos.tcp_console import main

if __name__ == '__main__':
    raise SystemExit(main())
