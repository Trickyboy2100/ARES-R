from __future__ import annotations

from contextlib import contextmanager
import threading
import time


class ResourceLockManager:
    def __init__(self): self._locks={};self._guard=threading.Lock()
    def _lock(self,name):
        with self._guard:return self._locks.setdefault(name,threading.Lock())
    @contextmanager
    def acquire(self,names,timeout_s=10.0):
        held=[];deadline=time.monotonic()+timeout_s
        try:
            for name in sorted(set(names)):
                lock=self._lock(name)
                if not lock.acquire(timeout=max(0,deadline-time.monotonic())):
                    raise TimeoutError("RESOURCE_BUSY:%s"%name)
                held.append(lock)
            yield
        finally:
            for lock in reversed(held):lock.release()
