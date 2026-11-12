"""Shared ART/WebUI status surface for manipulation Schemes."""

from __future__ import annotations

import json
from pathlib import Path

from .task_parameters import load_task_parameters
from .tray_to_groove_scheme import RECOVERY_GRAPH, SCHEME_ID, SCHEME_VERSION


class SchemeBackend:
    def __init__(self, root="worklog/evidence/2026-09-24-p3-8b"):
        self.root = Path(root)
        self.state_path = self.root / "scheme_status.json"

    def list(self):
        return [{"scheme_id": SCHEME_ID, "version": SCHEME_VERSION,
                 "execution_state": "PLANNING_ONLY", "task_run_locked": True}]

    def inspect(self, scheme_id):
        if scheme_id != SCHEME_ID:
            raise ValueError("unknown Scheme %r" % scheme_id)
        parameters = load_task_parameters()
        return {"scheme_id": SCHEME_ID, "version": SCHEME_VERSION,
                "parameters_revision": parameters["revision"],
                "demo_scope": parameters["demo_scope"],
                "recovery_graph": RECOVERY_GRAPH, "task_run_locked": True}

    def status(self):
        if not self.state_path.exists():
            return {"scheme_id": SCHEME_ID, "state": "NOT_PLANNED",
                    "task_run_locked": True}
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def preview(self):
        status = self.status()
        package = self.root / "scheme_execution_package.json"
        if not package.exists():
            return status
        return json.loads(package.read_text(encoding="utf-8"))

    def stop(self):
        self.root.mkdir(parents=True, exist_ok=True)
        value = {"scheme_id": SCHEME_ID, "state": "STOPPED",
                 "reason": "OPERATOR_STOP", "task_run_locked": True}
        temporary = self.state_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.state_path)
        return value
