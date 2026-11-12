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
            max_retries=3,max_relative_translation_m=1,max_relative_rotation_deg=180.0,
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
        with self.assertRaises(ValueError):self.base.move_relative(0,0,181)
        with patch("ares_r.adapters.amr_http.urlopen",return_value=_Response({"ok":True})) as open_:
            self.base.move_relative(.1,-.2,-30)
            request=open_.call_args.args[0]
            body=json.loads(request.data)
            self.assertEqual(request.method,"POST")
            self.assertEqual(request.full_url,
                "http://192.168.99.30:11375/openapi/control/move/relative")
            # Compatibility payload commissioned on the R300 v0.3.18
            # controller.  Do not silently rename or rescale these fields.
            # ``orientation`` stays in DEGREES: rescaling it to radians is the
            # defect fixed on 2026-09-21; see the rotation commissioning record.
            self.assertEqual(body,{"x":.1,"y":-.2,"orientation":-30.0,
                "maxLinearspeed":.2,"maxAngularspeed":.2,
                "collisiondetection":1,"timeout":30.0})

    def test_rotation_is_degrees_and_forwarded_without_conversion(self):
        # Measured on 2026-09-21: ``orientation`` is degrees, so a degree value
        # must reach the wire untouched.
        with patch("ares_r.adapters.amr_http.urlopen",return_value=_Response({"status":3})) as open_:
            self.base.move_relative(0,0,-30)
            self.assertEqual(json.loads(open_.call_args.args[0].data)["orientation"],-30.0)

    def test_rotation_envelope_is_expressed_in_degrees(self):
        with patch("ares_r.adapters.amr_http.urlopen",return_value=_Response({"status":3})):
            self.base.move_relative(0,0,180.0)
        for degrees in (-180.0001,180.0001):
            with self.assertRaises(ValueError):self.base.move_relative(0,0,degrees)

    def test_lateral_sign_is_forwarded_without_axis_remapping(self):
        with patch("ares_r.adapters.amr_http.urlopen",return_value=_Response({"status":3})) as open_:
            self.base.move_relative(0,-.6,0)
            body=json.loads(open_.call_args.args[0].data)
            self.assertEqual(body["x"],0.0)
            self.assertEqual(body["y"],-.6)
            self.assertEqual(body["orientation"],0.0)

    def test_named_navigation_requires_explicit_config(self):
        with self.assertRaises(RuntimeError):self.base.navigate("pick_station")
        self.config["positions"]={"pick_station":{"id":"7","posName":"PICK","retries":1}}
        with patch("ares_r.adapters.amr_http.urlopen",return_value=_Response({"ok":True})):
            self.base.navigate("pick_station")
            self.assertEqual(self.base.station(),"PICK")


if __name__=="__main__":unittest.main()
