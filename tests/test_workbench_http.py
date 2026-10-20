import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import urlopen, Request
from urllib.error import HTTPError
from ares_r.demo_workbench import ReviewHandler


class ReviewHTTPTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), ReviewHandler)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()
        self.url = "http://127.0.0.1:%s" % self.server.server_port

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)

    def test_no_motion_endpoint(self):
        with self.assertRaises(HTTPError) as exc:
            urlopen(Request(self.url + "/api/operations/execute", data=b"{}"))
        self.assertEqual(exc.exception.code, 405)

    def test_web_and_cli_share_draft_contract(self):
        body = {"direction": "SCALE_TO_DRYER",
                "slots": ["lower_left", "lower_middle", "lower_right", "upper_left", "upper_middle"]}
        with urlopen(Request(self.url + "/api/workbench/draft", data=json.dumps(body).encode())) as reply:
            result = json.load(reply)
        self.assertEqual(len(result["transfers"]), 5)
        self.assertEqual(len(result["occupancy_blockers"]), 5)
        self.assertFalse(result["execution_enabled"])
        self.assertTrue(result["not_a_runtime_scheme"])

    def test_unknown_slot_is_rejected(self):
        with self.assertRaises(HTTPError) as exc:
            urlopen(Request(self.url + "/api/workbench/draft",
                            data=b'{"direction":"SCALE_TO_DRYER","slots":["made_up"]}'))
        self.assertEqual(exc.exception.code, 400)
