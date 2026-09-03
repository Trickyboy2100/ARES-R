"""Append-only JSONL event log for debugging and replay."""

import json
from pathlib import Path
from typing import Any, Dict
import time


class EventLog:
    def __init__(self, directory: str) -> None:
        root = Path(directory)
        root.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        self.path = root / ("session-%s.jsonl" % stamp)

    def write(self, event: str, **data: Any) -> None:
        record: Dict[str, Any] = {"timestamp": time.time(), "event": event}
        record.update(data)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
