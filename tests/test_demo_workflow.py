import copy
import io
import json
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch

from ares_r.motion import demo_reference as reference
from ares_r.motion.native_demo import native_environment,SDK_LIBRARY
from ares_r.motion.scene import load_scene,scene_cuboids
from ares_r.motion.servo_dashboard import monitor,render
from ares_r.motion.waypoints import load_waypoints,catmull_rom
from ares_r.motion.demo_workflow import cycle,reset


class WorkflowTest(unittest.TestCase):
    def test_loader_isolates_legacy_sdk_without_global_mutation(self):
        with patch.dict(os.environ,{"LD_LIBRARY_PATH":"/old","LD_PRELOAD":"bad.so","LD_AUDIT":"bad.so"}):
            env=native_environment()
            self.assertEqual(env["LD_LIBRARY_PATH"],SDK_LIBRARY)
            self.assertEqual(env["LD_BIND_NOW"],"1")
            self.assertNotIn("LD_PRELOAD",env);self.assertNotIn("LD_AUDIT",env)
            self.assertEqual(os.environ["LD_LIBRARY_PATH"],"/old")

    def test_reference_requires_joints_not_just_tcp(self):
        live=dict(actual_rad=[0.]*6,tcp_mm_rad=[0.]*6)
        saved=dict(snapshot=copy.deepcopy(live))
        self.assertTrue(reference.at_reference(saved,live))
        live["actual_rad"][1]=.1
        self.assertFalse(reference.at_reference(saved,live))
        live["actual_rad"][1]=0;live["tcp_mm_rad"][0]=2
        self.assertFalse(reference.at_reference(saved,live))

    def test_unconfirmed_workflow_never_reads_robot(self):
        with patch("ares_r.motion.demo_workflow.run_demo") as plan:
            for call in (reset,cycle):
                with self.assertRaises(RuntimeError): call({})
            plan.assert_not_called()

    def test_reset_failure_blocks_outbound(self):
        with patch("ares_r.motion.demo_workflow.reset",side_effect=RuntimeError("blocked")),patch("ares_r.motion.demo_workflow.run_demo") as plan:
            with self.assertRaises(RuntimeError): cycle({},confirmed=True)
            plan.assert_not_called()

    def test_manual_stop_terminates_and_waits_for_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"log";path.write_text('{"event":"sample","index":0}\n')
            child=Mock();child.poll.return_value=None;child.wait.return_value=1
            with patch("ares_r.motion.servo_dashboard.stop_key",return_value=True),patch("sys.stdout",new_callable=io.StringIO):
                with self.assertRaises(RuntimeError):monitor(child,path,{"points":[[0]*6]*2},"reset")
            child.terminate.assert_called_once();child.wait.assert_called_once_with(timeout=10)

    def test_dashboard_exit_and_actual_units(self):
        event=dict(event="sample",index=1,actual_rad=[math.pi]*6,tcp_mm_rad=[10,20,30,0,0,0],tracking_error_deg=.05)
        text=render(event,10,2,"demo20")
        self.assertIn("180.000",text);self.assertIn("20.0%",text);self.assertIn("controller BASE",text)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"log";path.write_text(json.dumps(event)+"\n")
            child=Mock(returncode=0);child.poll.return_value=0
            with patch("sys.stdout",new_callable=io.StringIO):self.assertEqual(monitor(child,path,{"points":[[0]*6]*10},"demo20"),0)
            child.terminate.assert_not_called()

    def test_scene_refuses_unsupported_pointcloud_and_frame(self):
        data=load_scene({})
        self.assertEqual(scene_cuboids(data),{})
        for key,value in (("source","epic"),("frame","camera"),("pointcloud",[])):
            changed=dict(data);changed[key]=value
            with self.assertRaises(ValueError):scene_cuboids(changed)
        data["cuboids"]={"box":dict(dims=[.1,.1,.1],pose=[0,0,0,1,0,0,0])}
        self.assertIn("box",scene_cuboids(data))
        data["cuboids"]["box"]["dims"][0]=float("nan")
        with self.assertRaises(ValueError):scene_cuboids(data)

    def test_tmp_waypoint_units_and_spline_endpoints(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"w.json"
            data=dict(arm="left",joint_names=["J%d"%i for i in range(1,7)],waypoints_deg=[[0.]*6,[90.]*6])
            path.write_text(json.dumps(data));normal=load_waypoints(path)
            self.assertAlmostEqual(normal["waypoints_rad"][1][0],math.pi/2)
            data["waypoints_rad"]=[[0.]*6,[90.]*6];path.write_text(json.dumps(data))
            with self.assertRaises(ValueError):load_waypoints(path)
        a,b=[0.]*6,[1.]*6
        self.assertEqual(catmull_rom(a,a,b,b,0),a)
        self.assertEqual(catmull_rom(a,a,b,b,1),b)
