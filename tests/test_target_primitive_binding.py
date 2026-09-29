import importlib.util
from pathlib import Path
import unittest


_SCRIPT=Path(__file__).resolve().parents[1]/"scripts/build_p3_production_scene.py"
_SPEC=importlib.util.spec_from_file_location("build_p3_production_scene",_SCRIPT)
_MODULE=importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


class TargetPrimitiveBindingTests(unittest.TestCase):
    def box(self,identifier,semantic,center):
        return {"primitive_id":identifier,"semantic":semantic,
                "center_m":center,"dims_m":[.02,.02,.02]}

    def test_far_preferred_semantic_cannot_defeat_spatial_gate(self):
        boxes=[self.box("near_support","SUPPORT_SURFACE",[0,0,0]),
               self.box("far_preferred","PROTRUDING_OBJECT",[1,0,0])]
        bound,distance,_=_MODULE.select_target_primitive(
            [0,0,0],boxes,{"PROTRUDING_OBJECT"},.08)
        self.assertEqual(bound["primitive_id"],"near_support")
        self.assertEqual(distance,0.0)

    def test_place_prefers_support_within_gate(self):
        boxes=[self.box("unknown","UNKNOWN_OCCUPIED",[.03,0,0]),
               self.box("support","SUPPORT_SURFACE",[.04,0,0])]
        bound,_,_=_MODULE.select_target_primitive(
            [0,0,0],boxes,{"SUPPORT_SURFACE"},.08)
        self.assertEqual(bound["primitive_id"],"support")

    def test_no_nearby_geometry_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError,"no matching observed"):
            _MODULE.select_target_primitive(
                [0,0,0],[self.box("far","SUPPORT_SURFACE",[1,0,0])],
                {"SUPPORT_SURFACE"},.08)


if __name__=="__main__":unittest.main()
