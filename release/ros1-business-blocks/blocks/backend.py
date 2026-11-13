"""Add business RPCs to the canonical backend and its existing task owner."""
import re
from .console import BusinessConsole
from ares_r.canonical_backend import CanonicalBackend
from ares_r.demos.console import read


class BusinessBackend(CanonicalBackend):
    def _console(self):
        if not hasattr(self, '_demo_console'):
            self._demo_console = BusinessConsole(self)
        return self._demo_console

    def call(self, method, args=(), kwargs=None):
        if method not in ('business_status', 'business_stop'):
            return super().call(method, args, kwargs)
        if len(args) != 1 or kwargs:
            raise ValueError('ONE_RUN_ID_REQUIRED')
        run_id = args[0]
        if not isinstance(run_id, str) or re.fullmatch('[0-9a-f]{32}', run_id) is None:
            raise ValueError('INVALID_RUN_ID')
        console = self._console()
        with console.lock:
            if console.job.get('run_id') != run_id:
                if method == 'business_stop':
                    raise ValueError('STOP_OWNER_CHANGED')
                saved = read(self.root / 'worklog/runtime/business-prepare-jobs' / (run_id + '.json'))
                if not saved:
                    raise ValueError('UNKNOWN_BUSINESS_RUN')
                return saved
            if method == 'business_stop' and console.active():
                console.request_stop()
                self.operations_stop()
            return console.status()
