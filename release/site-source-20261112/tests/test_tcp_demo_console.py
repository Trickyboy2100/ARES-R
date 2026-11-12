import importlib.util, json, socket, threading, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'tcp_console', ROOT / 'src/ares_r/demos/tcp_console.py')
tcp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tcp)

RUN = dict(cmd='run', demo='demo-0',
           authorization='RUN demo-0-return-center',
           onsite_observer_confirmed=True,
           prepared_environment_confirmed=True)


class FakeApi:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.calls = []

    def __call__(self, path, body=None, timeout=30):
        self.calls.append((path, body, timeout))
        return self.responses.get(path, {})


def client(api, token=None, plan_runner=None):
    return tcp.DemoConsoleTcp(api, root=ROOT, token=token, plan_runner=plan_runner)


class ProtocolTests(unittest.TestCase):
    def test_plain_ping(self):
        value = client(FakeApi()).dispatch('PING')
        self.assertTrue(value['ok'])
        self.assertEqual(value['result'], 'PONG')

    def test_unknown_command(self):
        value = client(FakeApi()).dispatch('MOVE EVERYTHING')
        self.assertFalse(value['ok'])
        self.assertEqual(value['code'], 'UNKNOWN_COMMAND')
        self.assertIn('HELP', value['error'])

    def test_invalid_json(self):
        value = client(FakeApi()).dispatch('{"cmd":')
        self.assertFalse(value['ok'])
        self.assertEqual(value['code'], 'BAD_REQUEST')

    def test_status_returns_console_and_last_run(self):
        api = FakeApi({'/api/demo-console/status': {'state': 'IDLE'}})
        value = client(api).dispatch('{"cmd":"status"}')
        self.assertTrue(value['ok'])
        self.assertEqual(value['console'], {'state': 'IDLE'})
        self.assertIn('last_run', value)
        self.assertEqual(api.calls[0][0], '/api/demo-console/status')

    def test_stop_uses_the_console_stop_endpoint(self):
        api = FakeApi({'/api/demo-console/stop': {'state': 'STOPPED'}})
        value = client(api).dispatch('STOP')
        self.assertTrue(value['ok'])
        self.assertEqual(api.calls, [('/api/demo-console/stop', {}, 60)])


class SafetyGateTests(unittest.TestCase):
    def test_run_without_confirmations_is_rejected_before_http(self):
        api = FakeApi()
        body = dict(RUN, onsite_observer_confirmed=False)
        value = client(api).dispatch(json.dumps(body))
        self.assertFalse(value['ok'])
        self.assertEqual(value['code'], 'NOT_CONFIRMED')
        self.assertEqual(api.calls, [])

    def test_run_without_authorization_phrase_is_rejected(self):
        api = FakeApi()
        body = dict(RUN)
        body.pop('authorization')
        value = client(api).dispatch(json.dumps(body))
        self.assertFalse(value['ok'])
        self.assertEqual(value['code'], 'NOT_AUTHORIZED')
        self.assertEqual(api.calls, [])

    def test_plain_text_run_can_never_start_motion(self):
        api = FakeApi()
        value = client(api).dispatch('RUN demo-0')
        self.assertFalse(value['ok'])
        self.assertEqual(value['code'], 'NOT_AUTHORIZED')
        self.assertEqual(api.calls, [])

    def test_run_forwards_only_whitelisted_fields(self):
        api = FakeApi({'/api/demo-console/start': {'run_id': 'R'}})
        body = dict(RUN, token='nope', evil=True, request_id='req-1')
        value = client(api).dispatch(json.dumps(body))
        self.assertTrue(value['ok'])
        path, forwarded, _ = api.calls[0]
        self.assertEqual(path, '/api/demo-console/start')
        self.assertEqual(set(forwarded), {'alias', 'authorization', 'request_id',
                                          'onsite_observer_confirmed',
                                          'prepared_environment_confirmed'})
        self.assertEqual(forwarded['alias'], tcp.DEMO0_ALIAS)
        self.assertEqual(forwarded['request_id'], 'req-1')
        self.assertEqual(value['job'], {'run_id': 'R'})

    def test_request_id_is_generated_when_missing(self):
        api = FakeApi({'/api/demo-console/start': {}})
        client(api).dispatch(json.dumps(RUN))
        self.assertTrue(api.calls[0][1]['request_id'])

    def test_token_is_required_for_remote_clients(self):
        api = FakeApi()
        value = client(api, token='s3cret').dispatch('PING')
        self.assertFalse(value['ok'])
        self.assertEqual(value['code'], 'UNAUTHORIZED')
        accepted = client(api, token='s3cret').dispatch(
            json.dumps({'cmd': 'ping', 'token': 's3cret'}))
        self.assertTrue(accepted['ok'])

    def test_non_loopback_bind_requires_a_token(self):
        with self.assertRaises(SystemExit):
            tcp.require_token_for_bind('0.0.0.0', None)
        tcp.require_token_for_bind('0.0.0.0', 'token')
        tcp.require_token_for_bind('127.0.0.1', None)
        tcp.require_token_for_bind('localhost', None)


class PlanTests(unittest.TestCase):
    def test_plan_only_supports_demo0(self):
        api = FakeApi()
        value = client(api).dispatch(json.dumps(dict(cmd='plan', demo='demo-3')))
        self.assertFalse(value['ok'])
        self.assertEqual(value['code'], 'UNSUPPORTED_DEMO')
        self.assertEqual(api.calls, [])

    def test_plan_refuses_while_the_console_job_is_running(self):
        api = FakeApi({'/api/demo-console/status': {'running': True}})
        value = client(api, plan_runner=lambda timeout: {'ran': True}).dispatch(
            json.dumps(dict(cmd='plan', demo='demo-0')))
        self.assertFalse(value['ok'])
        self.assertEqual(value['code'], 'DEMO_BUSY')

    def test_plan_returns_runner_result(self):
        api = FakeApi({'/api/demo-console/status': {'running': False}})
        seen = []
        value = client(api, plan_runner=lambda timeout: seen.append(timeout) or
                       {'result': {'result': 'PREPARED'}}).dispatch(
            json.dumps(dict(cmd='plan', demo='demo0', timeout_s=42)))
        self.assertTrue(value['ok'])
        self.assertEqual(seen, [42.0])
        self.assertEqual(value['result'], {'result': 'PREPARED'})
        self.assertEqual(value['demo'], tcp.DEMO0_ALIAS)


class SocketTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeApi()
        self.server = tcp.TcpServer(('127.0.0.1', 0), client(self.api))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.address = self.server.server_address

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def test_multiple_commands_on_one_connection(self):
        with socket.create_connection(self.address, timeout=5) as stream:
            stream.sendall(b'PING\n{"cmd":"help"}\n')
            reader = stream.makefile('rb')
            first = json.loads(reader.readline())
            second = json.loads(reader.readline())
        self.assertEqual(first['result'], 'PONG')
        self.assertTrue(second['ok'])
        self.assertIn('RUN <json>', second['commands'])

    def test_oversized_line_is_refused(self):
        with socket.create_connection(self.address, timeout=5) as stream:
            stream.sendall(b'X' * (tcp.MAX_LINE + 10) + b'\n')
            reader = stream.makefile('rb')
            value = json.loads(reader.readline())
        self.assertFalse(value['ok'])
        self.assertEqual(value['code'], 'LINE_TOO_LONG')


if __name__ == '__main__':
    unittest.main()
