import json
import math
import struct
from pathlib import Path
import tempfile
import unittest

from ares_r.atom_obstacles import convert_file,load_atom_obstacles,to_arm_scene
from ares_r.epic_pointcloud import inspect_ply,planning_assessment


class EpicPointcloudTest(unittest.TestCase):
    def _ply(self,path,points):
        header=("ply\nformat binary_little_endian 1.0\n"
            "obj_info num_cols 2\nobj_info num_rows 2\n"
            "element vertex %d\nproperty float x\nproperty float y\nproperty float z\n"
            "property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n"%len(points))
        with path.open("wb") as stream:
            stream.write(header.encode("ascii"))
            for xyz in points: stream.write(struct.pack("<fffBBB",*xyz,1,2,3))

    def test_binary_ply_is_audited_in_explicit_mm_and_m(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"cloud.ply"
            self._ply(path,[(100,200,1000),(0,0,0),(float("nan"),1,2),(200,300,2000)])
            stats=inspect_ply(path)
            self.assertEqual(stats["vertex_count"],4)
            self.assertEqual(stats["valid_point_count"],2)
            self.assertEqual(stats["valid_ratio"],.5)
            self.assertEqual(stats["source_coordinate_unit"],"mm")
            self.assertEqual(stats["xyz_min_m"],[.1,.2,1.0])
            report=planning_assessment(stats,{"epic_pointcloud":{"minimum_valid_ratio":.5,"T_body_camera":None}})
            self.assertTrue(report["quality_gate_passed"])
            self.assertFalse(report["current_planning_ready"])
            self.assertIn("T_body_camera is not commissioned",report["blockers"])

    def test_truncated_payload_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"cloud.ply";self._ply(path,[(100,0,1000)])
            path.write_bytes(path.read_bytes()[:-1])
            with self.assertRaises(ValueError): inspect_ply(path)

    def test_atom_body_aabb_becomes_conservative_arm_base_aabb(self):
        data=dict(schema_version=1,source="epic_atom",capture_time="now",frame="body",
            calibration_revision="cal-1",obstacles=[dict(id="box",type="aabb",
                center_m=[1,.2,1.4],dims_m=[.4,.2,.1],inflation_m=.01,confidence=.9)])
        world={"arms":{"right":{"base_xyz_m":[0,-.2,1.2],"base_rpy_rad":[0,0,math.pi/4]}}}
        scene=to_arm_scene(data,world,"right")
        self.assertEqual(scene["source"],"epic_atom")
        self.assertEqual(scene["arm"],"right")
        self.assertAlmostEqual(scene["cuboids"]["box"]["dims"][0],math.sqrt(.5)*.6+.02)
        self.assertEqual(scene["cuboids"]["box"]["pose"][3:],[1,0,0,0])

    def test_atom_loader_rejects_camera_frame_and_obb(self):
        base=dict(schema_version=1,source="epic_atom",capture_time="now",frame="body",
            calibration_revision="cal-1",obstacles=[dict(id="box",type="aabb",
                center_m=[1,0,1],dims_m=[1,1,1],inflation_m=0,confidence=1)])
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"obstacles.json"
            for field,value in (("frame","camera"),("type","obb")):
                changed=json.loads(json.dumps(base))
                if field=="frame": changed[field]=value
                else: changed["obstacles"][0][field]=value
                path.write_text(json.dumps(changed))
                with self.assertRaises(ValueError):load_atom_obstacles(path)

    def test_conversion_requires_commissioned_calibration_revision(self):
        data=dict(schema_version=1,source="epic_atom",capture_time="now",frame="body",
            calibration_revision="cal-1",obstacles=[dict(id="box",type="aabb",
                center_m=[1,0,1],dims_m=[1,1,1],inflation_m=0,confidence=1)])
        world={"arms":{"right":{"base_xyz_m":[0,-.2,1.2],"base_rpy_rad":[0,0,0]}}}
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/"in.json";output=Path(tmp)/"out.json";geometry=Path(tmp)/"world.json"
            source.write_text(json.dumps(data));geometry.write_text(json.dumps(world))
            with self.assertRaises(RuntimeError):convert_file(source,output,geometry,"right",[])
            convert_file(source,output,geometry,"right",["cal-1"])
            self.assertTrue(output.is_file())


if __name__=="__main__": unittest.main()
