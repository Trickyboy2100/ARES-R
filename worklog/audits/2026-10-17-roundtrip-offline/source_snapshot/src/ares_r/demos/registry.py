"""Filesystem-backed, fail-closed demo catalog and selection state."""

from __future__ import annotations

import json
import os
from pathlib import Path
import signal
from typing import Mapping


SCHEMA_VERSION = 1


def _atomic_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


class DemoRegistry:
    """Discover immutable demo definitions; runtime state stays outside them."""

    def __init__(self, root="demos", state_path="logs/demo_runtime.json"):
        self.root = Path(root)
        self.state_path = Path(state_path)

    def _definitions(self):
        values = {}
        if not self.root.exists():
            return values
        for path in sorted(self.root.glob("*/demo.json")):
            value = json.loads(path.read_text(encoding="utf-8"))
            if value.get("schema_version") != SCHEMA_VERSION:
                raise ValueError("unsupported demo schema in %s" % path)
            demo_id = value.get("demo_id")
            if not demo_id or demo_id in values or path.parent.name != demo_id:
                raise ValueError("invalid or duplicate demo_id in %s" % path)
            if value.get("execution", {}).get("entrypoint") is None:
                raise ValueError("demo %s has no execution entrypoint" % demo_id)
            values[demo_id] = dict(value, definition_path=str(path))
        return values

    def list(self):
        selected = self.status().get("selected_demo_id")
        return [{"demo_id": value["demo_id"], "name": value["name"],
                 "version": value["version"], "category": value["category"],
                 "commissioning_state": value["commissioning_state"],
                 "selected": value["demo_id"] == selected,
                 "description": value.get("description", "")}
                for value in self._definitions().values()]

    def inspect(self, demo_id):
        try:
            return self._definitions()[demo_id]
        except KeyError:
            raise ValueError("unknown demo %r" % demo_id)

    def status(self):
        if not self.state_path.exists():
            return {"schema_version": 1, "state": "NO_DEMO_SELECTED",
                    "selected_demo_id": None, "active_run_id": None}
        value = json.loads(self.state_path.read_text(encoding="utf-8"))
        selected = value.get("selected_demo_id")
        if selected is not None and selected not in self._definitions():
            return dict(value, state="INVALID_SELECTION",
                        invalid_reason="selected demo definition is missing")
        return value

    def select(self, demo_id):
        definition = self.inspect(demo_id)
        value = {"schema_version": 1, "state": "SELECTED",
                 "selected_demo_id": demo_id, "selected_version": definition["version"],
                 "active_run_id": None, "last_run": self.status().get("last_run")}
        _atomic_json(self.state_path, value)
        return dict(value, demo=definition)

    def selected(self, demo_id=None):
        chosen = demo_id or self.status().get("selected_demo_id")
        if not chosen:
            raise RuntimeError("no demo selected; use demo select DEMO_ID")
        return self.inspect(chosen)

    def prepare(self, demo_id=None):
        definition = self.selected(demo_id)
        execution = definition["execution"]
        value = {"schema_version": 1, "state": "READY_TO_PREPARE_FRESH_RUN",
                 "selected_demo_id": definition["demo_id"],
                 "selected_version": definition["version"], "active_run_id": None,
                 "prepare_command": execution["prepare_command"],
                 "run_command": execution["run_command"],
                 "stop_command": execution["stop_command"],
                 "authorization_phrase": execution["authorization_phrase"],
                 "freshness_policy": definition["freshness_policy"]}
        _atomic_json(self.state_path, value)
        return value

    def stop(self):
        value = self.status()
        active = self.state_path.with_name("demo_active_sender.json")
        stop_result = "NO_ACTIVE_SENDER"
        if active.exists():
            record = json.loads(active.read_text(encoding="utf-8"))
            pid = int(record.get("pid", 0)); token = str(record.get("expected_process_token", ""))
            commandline = Path("/proc/%d/cmdline" % pid)
            if pid > 1 and token and commandline.exists() and token.encode() in commandline.read_bytes():
                os.kill(pid, signal.SIGTERM); stop_result = "SIGTERM_SENT_TO_AUDITED_SENDER"
            else:
                stop_result = "STALE_OR_UNVERIFIED_SENDER_RECORD_NOT_SIGNALED"
        value.update({"state": "STOP_REQUESTED", "active_run_id": None,
                      "stop_result": stop_result})
        _atomic_json(self.state_path, value)
        return value
