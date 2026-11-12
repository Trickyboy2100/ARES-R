import copy,tempfile,unittest
from pathlib import Path
import numpy as np
from ares_r.motion.independent_path_validation import validate_dense_world

class IndependentNativeTests(unittest.TestCase):
 def test_same_fk_geometry_samples_and_decision(self):
  with tempfile.TemporaryDirectory() as tmp:
   urdf=Path(tmp)/'six.urdf'
   joints=''.join('<joint name="joint%d"><origin xyz=".03 .02 .01" rpy="0 0 0"/><axis xyz="0 0 1"/></joint>'%i for i in range(1,7))
   urdf.write_text('<robot>'+joints+'</robot>')
   box={'center_m':[0,0,.01],'half_extents_m':[.01,.02,.01]}
   t=np.eye(4);t[1,3]=-.2
   r=dict(robot_yaml_urdf=str(urdf),active_arm='right',T_body_model=t.tolist(),T_link6_tcp=np.eye(4).tolist(),
    collision_model=dict(arm_link_boxes={name:box for name in ['base_link']+['link%d'%i for i in range(1,7)]},gripper_max_envelope_link6=box),
    planning_parameters={'active_sphere_cell_m':.035},motion_constraints={'central_exclusion':False,'ignore_cuboid_ids':['ignored']},
    compiled_scene={'cuboids':{'world':{'pose':[.5,0,0,1,0,0,0],'dims':[.1,.1,.1]},'ignored':{'pose':[0,0,0,1,0,0,0],'dims':[1,1,1]}}})
   q=np.linspace(np.zeros(6),np.ones(6)*.02,11).tolist()
   for center in ([.5,0,0],[.06,.04,.02]):
    r['compiled_scene']['cuboids']['world']['pose'][:3]=center
    reference=validate_dense_world(q,r,subdivisions=2)
    candidate=validate_dense_world(q,dict(r,independent_distance_backend='NATIVE_CPU_V1'),subdivisions=2)
    for key in ('collision_free','dense_samples','validation_knots','ignored_object_ids','limiting_object_id'):
     self.assertEqual(reference[key],candidate[key])
    self.assertAlmostEqual(reference['min_clearance_m'],candidate['min_clearance_m'],places=12)
    self.assertEqual(candidate['distance_backend'],'NATIVE_CPU_V1')
   with self.assertRaisesRegex(ValueError,'backend'):
    validate_dense_world(q,dict(r,independent_distance_backend='UNREVIEWED'))
