"""An explicit process contract, independent of system.json mode."""
import os


def reject_physical_io():
    if os.environ.get('ARES_R_OFFLINE_REPLAY') == '1':
        raise RuntimeError('OFFLINE_PHYSICAL_EXECUTE_DENIED')
