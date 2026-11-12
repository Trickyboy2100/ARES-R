"""Cooperative read lease against the existing native RIGHT ServoJ lock.

Native senders and controlled SDK batches both own LOCK_EX. Status-page
loads never request this lease implicitly. No SDK or motion calls here.
"""
from contextlib import contextmanager
import fcntl,os
from pathlib import Path

LOCK_PATH=Path('/tmp/ares-r-right-servo.lock')

@contextmanager
def controller_read_lease(path=None):
    file=os.open(str(path or LOCK_PATH),os.O_CREAT|os.O_RDWR,0o600)
    try:
        try:fcntl.flock(file,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RuntimeError('SDK_READ_DEFERRED_NATIVE_OWNER_ACTIVE')
        yield
    finally:os.close(file)
