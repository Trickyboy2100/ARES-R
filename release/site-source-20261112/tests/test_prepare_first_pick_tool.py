import importlib.util,json,tempfile,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('prepare_first_pick',ROOT/'scripts/prepare_authorized_first_pick.py')
prepare=importlib.util.module_from_spec(spec);spec.loader.exec_module(prepare)

TEMPLATE_TOOL=[-3.013000011444092,-4.789999961853027,184.3800048828125,
               -0.043563419028595333,0.001658062768588667,1.540078494675541]
LIVE_TOOL=[-5.048999786376953,-29.898000717163086,167.78900146484375,
           -0.04075343869985787,-0.05733406742604184,1.591164315969877]


class RefreshToolBindingTests(unittest.TestCase):
    """The frozen 2026-09-24 template must never supply the tool to a fresh plan."""
    def _epoch(self,root):
        (root/'live_scene').mkdir()
        (root/'live_scene/right_fk_audit.json').write_text(json.dumps(
            dict(diagnostics=dict(tool_id=3,tool_data=dict(pose_mm_rad=LIVE_TOOL)))))
        return dict(arm='right')

    def test_template_tool_is_replaced_by_live_tool(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);observation=self._epoch(root)
            request=dict(controller_tool_pose_mm_rad=list(TEMPLATE_TOOL),
                         T_link6_tcp=[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]])
            report=dict(tool_revision='sha256:live-tool-revision')
            out=prepare.refresh_tool_binding(request,root,observation,report)
            self.assertEqual(out['controller_tool_pose_mm_rad'],LIVE_TOOL)
            self.assertEqual(out['controller_tool_id'],3)
            self.assertEqual(out['tool_revision'],'sha256:live-tool-revision')
            matrix=out['T_link6_tcp']
            self.assertEqual(len(matrix),4)
            for row in matrix: self.assertEqual(len(row),4)
            # translation column carries the live XYZ in metres
            self.assertAlmostEqual(matrix[0][3],LIVE_TOOL[0]/1000.0,places=12)
            self.assertAlmostEqual(matrix[2][3],LIVE_TOOL[2]/1000.0,places=12)

    def test_matching_tool_is_left_identical(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);observation=self._epoch(root)
            request=dict(controller_tool_pose_mm_rad=list(LIVE_TOOL),
                         T_link6_tcp=prepare.pose_mm_rad_to_matrix(LIVE_TOOL))
            before=json.dumps(request['T_link6_tcp'])
            out=prepare.refresh_tool_binding(request,root,observation,dict(tool_revision='r'))
            self.assertEqual(json.dumps(out['T_link6_tcp']),before)


class ExtraAllowedContactIdsTests(unittest.TestCase):
    """Option C: an operator-approved waiver must be explicit, scoped and loud."""
    SCENE={'observed_support_01_component_00_protruding_obstacle_014':{},
           'observed_tray':{}}

    def test_present_id_is_added_and_absent_id_is_reported(self):
        allowed,absent=prepare.extra_allowed_ids(
            ['observed_support_01_component_00_protruding_obstacle_014','observed_gone_021'],
            self.SCENE)
        self.assertEqual(allowed,['observed_support_01_component_00_protruding_obstacle_014'])
        self.assertEqual(absent,['observed_gone_021'])

    def test_target_already_ignored_does_not_shadow_the_waiver(self):
        allowed,absent=prepare.extra_allowed_ids(['observed_tray'],self.SCENE,
                                                 already_ignored=['observed_tray'])
        self.assertEqual(allowed,['observed_tray'])
        self.assertEqual(absent,[])

    def test_empty_or_duplicate_config_is_harmless(self):
        self.assertEqual(prepare.extra_allowed_ids(None,self.SCENE),([],[]))
        self.assertEqual(prepare.extra_allowed_ids(['',' '],self.SCENE),([],[]))
        allowed,absent=prepare.extra_allowed_ids(['observed_tray','observed_tray'],self.SCENE)
        self.assertEqual(allowed,['observed_tray'])
        self.assertEqual(absent,[])


class ProtrusionWaiverTests(unittest.TestCase):
    """The waiver is anchored by geometry because scans renumber primitives."""
    PRIMITIVES=[
        dict(primitive_id='support_01_component_00_protruding_obstacle_015',semantic='PROTRUDING_OBSTACLE',
             point_count=6,center_m=[0.6897,-0.2234,1.0303]),
        dict(primitive_id='support_01_component_00_protruding_obstacle_000',semantic='PROTRUDING_OBSTACLE',
             point_count=31,center_m=[0.6899,-0.2235,1.0301]),
        dict(primitive_id='support_01_component_00_protruding_obstacle_030',semantic='PROTRUDING_OBSTACLE',
             point_count=6,center_m=[0.9000,-0.5000,1.1000])]
    SCENE={('observed_'+p['primitive_id']):{} for p in PRIMITIVES}
    WAIVER=dict(center_body_m=[0.6916,-0.2239,1.0295],radius_m=0.015,max_point_count=30,
                semantic='PROTRUDING_OBSTACLE')

    def test_matches_the_same_sparse_speck_after_renumbering(self):
        matched,absent=prepare.match_protrusion_waivers([self.WAIVER],self.PRIMITIVES,self.SCENE)
        self.assertEqual(matched,['observed_support_01_component_00_protruding_obstacle_015'])
        self.assertEqual(absent,[])

    def test_dense_protrusion_and_far_speck_are_not_waived(self):
        matched,_=prepare.match_protrusion_waivers([self.WAIVER],self.PRIMITIVES,self.SCENE)
        self.assertNotIn('observed_support_01_component_00_protruding_obstacle_000',matched)
        self.assertNotIn('observed_support_01_component_00_protruding_obstacle_030',matched)

    def test_unmatched_waiver_is_reported_not_silently_dropped(self):
        far=dict(self.WAIVER,center_body_m=[0.0,0.0,0.0])
        matched,absent=prepare.match_protrusion_waivers([far],self.PRIMITIVES,self.SCENE)
        self.assertEqual(matched,[])
        self.assertEqual(len(absent),1)
        self.assertEqual(absent[0]['center_body_m'],[0.0,0.0,0.0])

    def test_waiver_never_invents_objects_missing_from_the_scene(self):
        matched,absent=prepare.match_protrusion_waivers([self.WAIVER],self.PRIMITIVES,{})
        self.assertEqual(matched,[])
        self.assertEqual(len(absent),1)


if __name__=='__main__':unittest.main()
