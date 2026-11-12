"""Fail-closed TCP command front end for the demo console (demo-0 ready).

This module is a thin adapter over the existing console HTTP API
(`/api/demo-console/*`).  It deliberately does **not** duplicate planning or
execution logic and never invents the console's现场 confirmations: an external
client must send the same authorization phrase and observer flags the web
console requires, otherwise the request is rejected before any HTTP call.

Wire protocol
-------------
One UTF-8 command per line, one JSON reply per line (newline-delimited JSON).
A connection may carry several commands.  Plain-text shortcuts exist for
read-only operations::

    PING
    HELP
    STATUS
    STOP

``RUN`` and ``PLAN`` must be JSON because they need explicit safety fields::

    {"cmd":"run","demo":"demo-0",
     "authorization":"RUN demo-0-return-center",
     "onsite_observer_confirmed":true,
     "prepared_environment_confirmed":true,
     "request_id":"client-side-id"}

    {"cmd":"plan","demo":"demo-0","timeout_s":900}

``PLAN`` runs ``scripts/run_return_center_demo.py --prepare`` (cuRobo planning
only, no motion) and returns the last JSON line of that script.

Binding policy: a non-loopback address requires ``ARES_R_TCP_CONSOLE_TOKEN``
(or ``--token``); every request then has to carry the same value in its JSON
``token`` field.
"""

from __future__ import annotations

import ipaddress
import json
import os
import secrets
import socket
import socketserver
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[3]
DEMO0_ALIAS = 'demo-0-return-center'
SERVER_NAME = 'ares-r-demo-console-tcp/1'
MAX_LINE = 16 * 1024
DEFAULT_PLAN_TIMEOUT_S = 900.0
#: How long an idle client may keep a connection open without sending a command.
CLIENT_IDLE_TIMEOUT_S = 300.0

DEMO_SHORTHANDS = {
    'demo-0': DEMO0_ALIAS,
    'demo0': DEMO0_ALIAS,
    'demo-0-return-center': DEMO0_ALIAS,
    'return-center': DEMO0_ALIAS,
    'return_center': DEMO0_ALIAS,
    'right_arm_return_center_v1': DEMO0_ALIAS,
}
SAFETY_FIELDS = ('onsite_observer_confirmed', 'prepared_environment_confirmed',
                 'historical_recovery_acknowledged')
REQUIRED_CONFIRMATIONS = ('onsite_observer_confirmed', 'prepared_environment_confirmed')
HELP_COMMANDS = ('PING', 'HELP', 'STATUS', 'RUN <json>', 'PLAN <json>', 'STOP')


class CommandError(RuntimeError):
    """A request rejected locally, before (or instead of) touching the console."""

    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def normalize_demo(value):
    """Resolve the demo0 shorthands, keep other aliases verbatim."""
    if not isinstance(value, str) or not value.strip():
        raise CommandError('BAD_REQUEST', 'demo is required (use "demo-0")')
    text = value.strip()
    return DEMO_SHORTHANDS.get(text.lower(), text)


def require_token_for_bind(host, token):
    """Refuse an unauthenticated non-loopback bind instead of opening motion to LAN."""
    if token:
        return
    try:
        loopback = ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = host.strip().lower() in ('localhost', 'localhost.localdomain')
    if not loopback:
        raise SystemExit(
            'refusing to bind %r without a shared token: set '
            'ARES_R_TCP_CONSOLE_TOKEN (or --token) so remote clients cannot '
            'start physical motion unauthenticated' % host)


def http_api(base_url):
    """Return ``call(path, body=None, timeout=...)`` against the console API."""
    base = str(base_url).rstrip('/')

    def call(path, body=None, timeout=30):
        data = None if body is None else json.dumps(body).encode('utf-8')
        request = Request(base + path, data=data,
                          headers={'Content-Type': 'application/json'})
        try:
            with urlopen(request, timeout=timeout) as stream:
                raw = stream.read().decode('utf-8')
        except HTTPError as exc:
            detail = exc.read().decode('utf-8', 'replace')
            raise CommandError('CONSOLE_HTTP_%d' % exc.code,
                               '%s -> %s' % (path, detail[-800:])) from exc
        except (URLError, OSError) as exc:
            raise CommandError('CONSOLE_UNAVAILABLE',
                               '%s: %s (is the RC1 webui/backend running?)'
                               % (path, exc)) from exc
        try:
            return json.loads(raw) if raw else {}
        except ValueError as exc:
            raise CommandError('CONSOLE_INVALID_JSON',
                               '%s -> %r' % (path, raw[-400:])) from exc

    return call


class DemoConsoleTcp:
    """Command dispatcher shared by every TCP connection."""

    def __init__(self, api, root=ROOT, token=None, plan_runner=None):
        self.api = api
        self.root = Path(root)
        self.token = token or None
        self.plan_runner = plan_runner or self._run_prepare
        self._plan_lock = threading.Lock()

    # ------------------------------------------------------------ parsing
    def parse(self, raw):
        text = str(raw).strip()
        if not text:
            raise CommandError('BAD_REQUEST', 'empty command')
        if text.startswith('{'):
            try:
                value = json.loads(text)
            except ValueError as exc:
                raise CommandError('BAD_REQUEST', 'invalid JSON: %s' % exc) from exc
            if not isinstance(value, dict):
                raise CommandError('BAD_REQUEST', 'JSON command must be an object')
            command = str(value.get('cmd') or value.get('command') or '').strip().lower()
            if not command:
                raise CommandError('BAD_REQUEST', 'JSON command needs "cmd"')
            return command, value
        parts = text.split()
        command = parts[0].lower()
        request = {}
        if len(parts) > 1:
            request['demo'] = parts[1]
        return command, request

    def _check_token(self, request):
        if not self.token:
            return
        supplied = request.get('token')
        if not isinstance(supplied, str) or not secrets.compare_digest(
                supplied, self.token):
            raise CommandError('UNAUTHORIZED', 'missing or invalid token')
        return

    # ---------------------------------------------------------- dispatch
    def dispatch(self, raw):
        command = 'unknown'
        try:
            command, request = self.parse(raw)
            self._check_token(request)
            handler = {
                'ping': self._ping,
                'help': self._help,
                'status': self._status,
                'run': self._run,
                'plan': self._plan,
                'prepare': self._plan,
                'stop': self._stop,
            }.get(command)
            if handler is None:
                raise CommandError('UNKNOWN_COMMAND',
                                   'unknown command %r; try HELP' % command)
            value = handler(request)
            value.setdefault('ok', True)
            value.setdefault('cmd', command)
            return value
        except CommandError as exc:
            return dict(ok=False, cmd=command, code=exc.code, error=str(exc))
        except Exception as exc:  # pragma: no cover - defensive
            return dict(ok=False, cmd=command, code='INTERNAL',
                        error='%s: %s' % (type(exc).__name__, exc))

    # ----------------------------------------------------------- handlers
    def _ping(self, request):
        return dict(result='PONG', server=SERVER_NAME, now_unix=time.time())

    def _help(self, request):
        return dict(server=SERVER_NAME, commands=list(HELP_COMMANDS),
                    demo='demo-0 -> %s' % DEMO0_ALIAS,
                    note='RUN/PLAN require JSON with authorization and observer '
                         'confirmations; this server never adds them for you')

    def _status(self, request):
        console = self.api('/api/demo-console/status', timeout=30)
        return dict(console=console, last_run=self._last_run())

    def _last_run(self):
        path = (self.root / 'worklog/evidence/demo-runs'
                / 'right_arm_return_center_v1/last-run.json')
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return None

    def _start_body(self, request, alias):
        authorization = request.get('authorization')
        expected = 'RUN ' + alias
        if authorization != expected:
            raise CommandError(
                'NOT_AUTHORIZED',
                'authorization must be exactly %r' % expected)
        for name in REQUIRED_CONFIRMATIONS:
            if request.get(name) is not True:
                raise CommandError(
                    'NOT_CONFIRMED',
                    '%s must be true (现场确认不能由 TCP 服务代填)' % name)
        body = dict(alias=alias, authorization=authorization)
        for name in SAFETY_FIELDS:
            if name in request:
                body[name] = request[name]
        body['request_id'] = str(request.get('request_id')
                                 or uuid.uuid4().hex)
        return body

    def _run(self, request):
        alias = normalize_demo(request.get('demo'))
        body = self._start_body(request, alias)
        job = self.api('/api/demo-console/start', body, timeout=120)
        return dict(demo=alias, job=job)

    def _plan(self, request):
        alias = normalize_demo(request.get('demo'))
        if alias != DEMO0_ALIAS:
            raise CommandError('UNSUPPORTED_DEMO',
                               'PLAN is only implemented for demo-0 (%s)' % DEMO0_ALIAS)
        if not self._plan_lock.acquire(blocking=False):
            raise CommandError('BUSY', 'another PLAN is already running')
        try:
            console = self.api('/api/demo-console/status', timeout=30)
            if console.get('running'):
                raise CommandError('DEMO_BUSY',
                                   'console job is running; refusing a parallel plan')
            timeout_s = float(request.get('timeout_s') or DEFAULT_PLAN_TIMEOUT_S)
            value = self.plan_runner(timeout_s)
            value.setdefault('ok', True)
            value.setdefault('cmd', 'plan')
            value.setdefault('demo', alias)
            return value
        finally:
            self._plan_lock.release()

    def _stop(self, request):
        return dict(console=self.api('/api/demo-console/stop', {}, timeout=60))

    # ------------------------------------------------------------- PLAN
    def _run_prepare(self, timeout_s):
        """Run demo-0 planning only (no motion) and return its last JSON line."""
        script = self.root / 'scripts/run_return_center_demo.py'
        env = dict(os.environ, PYTHONPATH=str(self.root / 'src'))
        try:
            completed = subprocess.run(
                [sys.executable, str(script), '--prepare'],
                cwd=str(self.root), env=env, capture_output=True, text=True,
                timeout=timeout_s, check=False)
        except subprocess.TimeoutExpired as exc:
            raise CommandError('PLAN_TIMEOUT',
                               'demo-0 --prepare exceeded %.0f s' % timeout_s) from exc
        lines = [line for line in (completed.stdout or '').splitlines()
                 if line.lstrip().startswith('{')]
        result = None
        for line in reversed(lines):
            try:
                result = json.loads(line)
                break
            except ValueError:
                continue
        record = dict(physical_motion=False, returncode=completed.returncode,
                      result=result,
                      log_tail=(completed.stderr or completed.stdout or '')[-2500:])
        if completed.returncode != 0:
            raise CommandError('PLAN_FAILED', json.dumps(record, ensure_ascii=False))
        return record


class TcpServer(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, commands):
        self.commands = commands
        super().__init__(address, _Handler)


class _Handler(socketserver.StreamRequestHandler):
    timeout = CLIENT_IDLE_TIMEOUT_S

    def handle(self):
        while True:
            try:
                line = self.rfile.readline(MAX_LINE + 1)
            except (socket.timeout, TimeoutError):
                return
            except OSError:
                return
            if not line:
                return
            if len(line) > MAX_LINE:
                self._reply(dict(ok=False, cmd='unknown', code='LINE_TOO_LONG',
                                 error='command line exceeds %d bytes' % MAX_LINE))
                return
            text = line.decode('utf-8', 'replace').strip()
            if not text:
                continue
            try:
                self._reply(self.server.commands.dispatch(text))
            except (BrokenPipeError, ConnectionResetError):
                return

    def _reply(self, value):
        payload = json.dumps(value, ensure_ascii=False, default=str) + '\n'
        self.wfile.write(payload.encode('utf-8'))
        self.wfile.flush()


def serve(host, port, commands):
    """Blocking server loop; returns the bound server (useful for tests)."""
    return TcpServer((host, int(port)), commands)


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--host', default='127.0.0.1',
                        help='bind address (non-loopback requires a token)')
    parser.add_argument('--port', type=int, default=8790,
                        help='TCP port (default 8790)')
    parser.add_argument('--base-url', default=os.environ.get(
        'ARES_R_ROUNDTRIP_API_URL', 'http://127.0.0.1:8775'),
        help='demo console HTTP base URL (default: env or 127.0.0.1:8775)')
    parser.add_argument('--token', default=os.environ.get('ARES_R_TCP_CONSOLE_TOKEN'),
                        help='shared token required from remote clients')
    args = parser.parse_args(argv)

    require_token_for_bind(args.host, args.token)
    commands = DemoConsoleTcp(http_api(args.base_url), root=ROOT, token=args.token)
    server = serve(args.host, args.port, commands)
    print(json.dumps(dict(event='LISTENING', server=SERVER_NAME, host=args.host,
                          port=server.server_address[1], base_url=args.base_url,
                          token_required=bool(args.token)),
                     ensure_ascii=False), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
