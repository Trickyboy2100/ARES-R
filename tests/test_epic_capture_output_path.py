import json
from pathlib import Path
import unittest
from unittest.mock import patch
from ares_r.epic_pointcloud import _fast_capture


class CaptureOutputPathTests(unittest.TestCase):
    def test_worker_receives_caller_absolute_path(self):
        sent=[]
        class Client:
            def settimeout(self, value):pass
            def connect(self, value):pass
            def sendall(self, value):sent.append(json.loads(value))
            def recv(self, size):
                if getattr(self,'done',False):return b''
                self.done=True;return b'{"ok":true}'
            def close(self):pass
        with patch('ares_r.epic_pointcloud.socket.socket',return_value=Client()):
            manifest=_fast_capture({'epic_pointcloud':{'endpoint':'example:5000'}},Path('logs/test-captures'))
        self.assertTrue(Path(sent[0]['output']).is_absolute())
        self.assertEqual(Path(sent[0]['output']).parent,(Path.cwd()/'logs/test-captures').resolve())
        self.assertEqual(manifest,Path(sent[0]['output'])/'manifest.json')
