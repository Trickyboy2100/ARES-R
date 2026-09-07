import copy
import math
from dataclasses import replace
import unittest
from unittest.mock import patch

from ares_r.motion.trajectory import Trajectory
from ares_r.motion.curobo import ARM_NAMES
from ares_r.motion.native_demo import validate_demo20,execute
from ares_r import terminal


class Demo20Test(unittest.TestCase):
    def test_last_alias_requires_current_session_plan(self):
        from types import SimpleNamespace
        with self.assertRaises(RuntimeError):terminal._demo_path(SimpleNamespace(),"last")
        self.assertEqual(terminal._demo_path(SimpleNamespace(last_demo20_path="plan.json"),"last"),"plan.json")

    def setUp(self):
        self.trajectory=Trajectory(1,"curobo-v2-virtual-obstacle-demo","right",ARM_NAMES,.08,
            tuple(tuple([i*.0001]+[0.0]*5) for i in range(201)),False,"model","virtual","tool","none")
        self.raw={"demo":dict(tcp_path_m=[[i*.001,0,0] for i in range(201)],
            world_link_points_m=[[[0,-.2,1.2] for _ in range(8)] for _ in range(201)],
            simulation_collision_checked=True,min_model_clearance_m=.01,baseline_min_clearance_m=-.01)}

    def test_demo_gate_accepts_only_numeric_valid_separated_path(self):
        validate_demo20(self.raw,self.trajectory)
        self.assertFalse(self.trajectory.collision_checked)
        for key,value in (("min_model_clearance_m",0),("baseline_min_clearance_m",.1),
                          ("simulation_collision_checked",False)):
            raw=copy.deepcopy(self.raw);raw["demo"][key]=value
            with self.assertRaises(RuntimeError): validate_demo20(raw,self.trajectory)

    def test_crossing_left_and_nonfinite_geometry_blocked(self):
        for point in ([0,.1,1.2],[float("nan"),-.2,1.2]):
            raw=copy.deepcopy(self.raw);raw["demo"]["world_link_points_m"][100][5]=point
            with self.assertRaises(RuntimeError): validate_demo20(raw,self.trajectory)

    def test_no_confirmation_no_connection(self):
        with patch("ares_r.motion.native_demo.status_connections") as probe:
            with self.assertRaises(RuntimeError):execute({},"missing","demo20")
            probe.assert_not_called()

    def test_terminal_allowlist(self):
        self.assertTrue(terminal._allowed_in_hardware(["curobo","demo","plan20"]))
        self.assertTrue(terminal._allowed_in_hardware(["curobo","demo","run20","file"]))
        self.assertFalse(terminal._allowed_in_jaka_readonly(["curobo","demo","run20","file"]))

    def test_large_reposition_is_not_a_twenty_cm_demo(self):
        n=1201
        points=[]
        for i in range(n):
            t=i/(n-1);s=10*t**3-15*t**4+6*t**5
            points.append((math.radians(104)*s,0.,0.,0.,0.,0.))
        trajectory=replace(self.trajectory,points=tuple(points))
        raw=copy.deepcopy(self.raw)
        raw["demo"].update(tcp_path_m=[[i*.7/(n-1),0,0] for i in range(n)],
            world_link_points_m=[[[0,-.2,1.2] for _ in range(8)] for _ in range(n)])
        validate_demo20(raw,trajectory,reset=True)
        with self.assertRaises(RuntimeError):validate_demo20(raw,trajectory)
