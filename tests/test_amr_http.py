import json
import unittest
from unittest.mock import patch

from ares_r.adapters.amr_http import AmrHttpBase


class _Response:
    status=200
    def __init__(self,data): self.data=json.dumps(data).encode()
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def read(self): return self.data


class AmrHttpTest(unittest.TestCase):
    def setUp(self):
        self.config=dict(base_url="http://192.168.99.30:11375/openapi",request_timeout_s=1,
            max_retries=3,max_relative_translation_m=1,max_relative_rotation_rad=3.14,
            default_linear_speed_mps=.2,max_linear_speed_mps=.5,
            default_angular_speed_radps=.2,max_angular_speed_radps=.3,
            default_motion_timeout_s=30,max_motion_timeout_s=120,positions={})
        self.base=AmrHttpBase(self.config)

    def test_read_only_battery_and_state(self):
        self.assertIn("not checked",self.base.state().detail)
        with patch("ares_r.adapters.amr_http.urlopen",return_value=_Response({"rate":98,"charge":0})) as open_:
            self.assertEqual(self.base.battery()["rate"],98)
            self.assertTrue(self.base.state().ready)
            self.assertEqual(open_.call_args.args[0].method,"GET")

    def test_position_move_sends_query_and_json(self):
        with patch("ares_r.adapters.amr_http.urlopen",return_value=_Response({"ok":True})) as open_:
            self.base.move_position("42","pick",2)
            request=open_.call_args.args[0]
            self.assertIn("id=42",request.full_url)
            self.assertEqual(json.loads(request.data),{"id":"42","posName":"pick","retries":2})

    def test_relative_move_enforces_envelope_and_collision_detection(self):
        with self.assertRaises(ValueError):self.base.move_relative(1,1,0)
        with self.assertRaises(ValueError):self.base.move_relative(.1,0,0,linear_mps=.6)
        with patch("ares_r.adapters.amr_http.urlopen",return_value=_Response({"ok":True})) as open_:
            self.base.move_relative(.1,-.2,.3)
            body=json.loads(open_.call_args.args[0].data)
            self.assertEqual(body["collisiondetection"],1)
            self.assertEqual(body["orientation"],.3)

    def test_named_navigation_requires_explicit_config(self):
        with self.assertRaises(RuntimeError):self.base.navigate("pick_station")
        self.config["positions"]={"pick_station":{"id":"7","posName":"PICK","retries":1}}
        with patch("ares_r.adapters.amr_http.urlopen",return_value=_Response({"ok":True})):
            self.base.navigate("pick_station")
            self.assertEqual(self.base.station(),"PICK")


if __name__=="__main__":unittest.main()
