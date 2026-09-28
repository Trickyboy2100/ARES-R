from __future__ import annotations

import json
from pathlib import Path
import queue
import threading


class AsyncEvidenceWriter:
    def __init__(self, root, max_queue=64):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.queue=queue.Queue(maxsize=max_queue);self.errors=[];self._closed=False
        self._thread=threading.Thread(target=self._worker,name="ares-evidence",daemon=True);self._thread.start()
    def submit_json(self, relative_path, value, block=False):
        if self._closed: raise RuntimeError("evidence writer closed")
        try:self.queue.put((str(relative_path),value),block=block,timeout=.1 if block else 0)
        except queue.Full: raise RuntimeError("EVIDENCE_BACKPRESSURE")
    def _worker(self):
        while True:
            item=self.queue.get()
            try:
                if item is None:return
                relative,value=item;path=self.root/relative;path.parent.mkdir(parents=True,exist_ok=True)
                tmp=path.with_suffix(path.suffix+".tmp")
                tmp.write_text(json.dumps(value,indent=2,sort_keys=True)+"\n",encoding="utf-8");tmp.replace(path)
            except Exception as exc:self.errors.append("%s: %s"%(type(exc).__name__,exc))
            finally:self.queue.task_done()
    def flush(self):
        self.queue.join()
        if self.errors: raise RuntimeError("EVIDENCE_WRITE_FAILED: "+self.errors[-1])
    def close(self):
        if self._closed:return
        self.flush();self._closed=True;self.queue.put(None);self._thread.join(timeout=2)
