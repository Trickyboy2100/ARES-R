from __future__ import annotations

import json
from pathlib import Path
import threading
import time


class EventStream:
    """Crash-readable synchronous compact JSONL; monotonic time is authoritative."""
    def __init__(self, path, clock=time.monotonic):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.clock=clock;self._lock=threading.Lock();self._sequence=0
    def emit(self, event, **fields):
        with self._lock:
            self._sequence += 1
            row={"sequence":self._sequence,"event":event,"monotonic_s":self.clock(),**fields}
            with self.path.open("a",encoding="utf-8") as out:
                out.write(json.dumps(row,separators=(",",":"),sort_keys=True)+"\n");out.flush()
            return row
    def read(self):
        if not self.path.exists(): return []
        return [json.loads(x) for x in self.path.read_text().splitlines() if x.strip()]
