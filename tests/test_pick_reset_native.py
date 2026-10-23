import importlib.util,unittest,json,tempfile,io,contextlib
from unittest.mock import patch
from pathlib import Path
from ares_r.motion.latency_solver import cuboid_cache_capacity
spec=importlib.util.spec_from_file_location('pick_reset_pack',Path(__file__).resolve().parents[1]/'scripts/package_pick_reset_timing.py');pack=importlib.util.module_from_spec(spec);spec.loader.exec_module(pack)


class PickResetNativeTests(unittest.TestCase):
    def _candidate(self,root):
        (root/'pregrasp').mkdir();(root/'package').mkdir()
        pre=[[0.]*6,[.1]*6];contact=[pre[-1],[.2]*6];lift=[contact[-1],[.3]*6]
        paths=dict(pregrasp=pre,contact=contact,lift230=lift,lower230=list(reversed(lift)),
                   retreat=list(reversed(contact)),center=list(reversed(pre)))
        package=dict(package_sha256='package',pointcloud_sha256='cloud',observation_id='obs',
            prechecked_branch={'approach_direction_body':[1,0,0]},controller_tool_pose_mm_rad=[0]*6)
        request=dict(scene_snapshot_id='scene',motion_constraints={})
        for path,value in ((root/'preparation-ready.json',{'geometry_prepared':True}),
                (root/'pick-reset-paths.json',paths),(root/'pregrasp/planner_request.json',request),
                (root/'package/first_pick_execution_package.json',package)):
            path.write_text(json.dumps(value))
        return paths

    def _run_pack(self,root,*extra):
        def fake(points,*args,**kwargs):
            proof=kwargs['geometry_validator'](points)
            if not proof.get('passed'):raise ValueError('rejected')
            text='header\ntool\nlower\nupper\n'+'\n'.join(' '.join(str(x) for x in q) for q in points)+'\n'
            return text,dict(native_path_sha256=pack.path_hash(points),duration_s=1.,max_joint_speed_rad_s=.01,
                predicted_tracking_gate_deg=.1,geometry_validation=proof)
        with patch('sys.argv',['pack','--prepared',str(root),*extra]),patch.object(pack,'verify_installed_sender'),\
             patch.object(pack,'package_native_preview',side_effect=fake),\
             patch.object(pack,'validate_dense_world',return_value={'collision_free':True}),\
             patch.object(pack,'validate_short_motion',return_value={'passed':True}),\
             patch.object(pack,'validate_path',return_value={'passed':True}),contextlib.redirect_stdout(io.StringIO()):
            pack.main()

    def test_partial_manifest_then_append_preserves_all_samples(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);paths=self._candidate(root)
            self._run_pack(root,'--segments','pregrasp,contact,retreat,center')
            first=json.loads((root/'native-manifest.json').read_text())
            self.assertEqual(set(first['pending_segments']),{'lift230','lower230'})
            old=(root/'native/pregrasp.native.txt').read_bytes()
            self._run_pack(root,'--segments','lift230,lower230','--append')
            final=json.loads((root/'native-manifest.json').read_text())
            self.assertEqual(final['pending_segments'],[]);self.assertEqual(len(final['segments']),6)
            self.assertEqual((root/'native/pregrasp.native.txt').read_bytes(),old)
            for name,points in paths.items():
                text=(root/'native'/(name+'.native.txt')).read_text().splitlines()
                self.assertEqual([[float(v) for v in line.split()] for line in text[4:]],points)

    def test_append_rejects_changed_candidate_or_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);paths=self._candidate(root)
            self._run_pack(root,'--segments','pregrasp,contact,retreat,center')
            with self.assertRaisesRegex(ValueError,'overwrite'):
                self._run_pack(root,'--segments','pregrasp','--append')
            paths['lift230'][-1]=[.4]*6
            (root/'pick-reset-paths.json').write_text(json.dumps(paths))
            with self.assertRaisesRegex(ValueError,'candidate changed'):
                self._run_pack(root,'--segments','lift230,lower230','--append')

    def test_reverse_is_exact_same_samples_and_hash_bound(self):
        points=[[0.]*6,[.1]*6,[.2]*6];text='header\ntool\nlower\nupper\n'+'\n'.join(' '.join(str(x) for x in q) for q in points)+'\n'
        result,audit=pack.reverse_native(text,dict(native_path_sha256=pack.path_hash(points)),list(reversed(points)),'contact')
        self.assertEqual(result.splitlines()[4:],list(reversed(text.splitlines()[4:])))
        self.assertEqual(audit['native_path_sha256'],pack.path_hash(list(reversed(points))))
        with self.assertRaises(ValueError):pack.reverse_native(text,dict(native_path_sha256='bad'),list(reversed(points)),'contact')
    def test_capacity_floor_prevents_unnecessary_512_768_flip(self):
        self.assertEqual(cuboid_cache_capacity({},456),512)
        self.assertEqual(cuboid_cache_capacity({},505),768)
        for n in (456,505):self.assertEqual(cuboid_cache_capacity({'cuboid_capacity_floor':768},n),768)
        with self.assertRaises(ValueError):cuboid_cache_capacity({'cuboid_capacity_floor':513},3)
