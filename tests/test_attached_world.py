import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from ares_r.manipulation.attached_collision import attach_scene_object,build_attached_collision
from ares_r.manipulation.attached_world import bind_owned_points,filter_attached_points,verify_world_identity
from ares_r.world import SceneObject,SceneObjectRole,PoseSE3


class AttachedWorldTests(unittest.TestCase):
    def attachment(self):
        target=SceneObject('tray',SceneObjectRole.TARGET,'cuboid',PoseSE3('body',(0,0,0),(1,0,0,0)),(.1,.1,.02),0.,'OBS')
        attached=build_attached_collision(attach_scene_object(target,np.eye(4).tolist(),side='right',source_revision='OBS'),np.eye(4).tolist())
        return bind_owned_points(attached,[[0,0,0],[.01,0,0]],np.eye(4),pointcloud_sha256='frozen-source')
    def test_only_source_matched_payload_removed_and_support_wins(self):
        value=self.attachment();T=np.eye(4);T[2,3]=.1
        points=[[0,0,.1],[.01,0,.1],[.05,0,.1],[0,0,0]]
        protected=[{'center_m':[.01,0,.1],'dims_m':[.001,.01,.01]}]
        keep,audit=filter_attached_points(points,value,T,protected)
        self.assertEqual(keep.tolist(),[False,True,True,True])
        self.assertEqual(audit['removed_points'],1);self.assertEqual(audit['ambiguous_preserved'],1)
    def test_duplicate_world_and_revision_mismatch_rejected(self):
        value=self.attachment();scene={'cuboids':{'tray':{}},'attached_object_revision':value['revision']}
        with self.assertRaisesRegex(RuntimeError,'DUPLICATE'):verify_world_identity(scene,value)
        scene['cuboids']={'dock':{},'table':{},'partition':{}}
        verify_world_identity(scene,value)
        scene['attached_object_revision']='other'
        with self.assertRaisesRegex(RuntimeError,'REVISION'):verify_world_identity(scene,value)
    def test_local_scene_rebuilds_attachment_without_second_scan_and_then_reuses(self):
        from ares_r.motion.local_scene_service import LocalSceneService
        with tempfile.TemporaryDirectory() as temp:
            calls=[]
            def builder(config,destination,**kw):
                calls.append(kw);folder=Path(destination)/'scene';folder.mkdir(parents=True)
                (folder/'scene_report.json').write_text(json.dumps({'calibration_revision':'c','geometry_revision':'g','tool_revision':'t'}))
                return {'scene_dir':str(destination),'scene_snapshot_id':str(len(calls)),'scene_digest':'d','pointcloud_sha256':'p'}
            service=LocalSceneService({'scene_aware_motion':{'evidence_directory':temp}},state_path=Path(temp)/'state',scene_builder=builder)
            initial=service.ensure_fresh('pick')
            attachment=self.attachment()
            held=service.ensure_fresh('held',attachment=attachment)
            self.assertEqual(calls[1]['reuse_capture'],initial['scene_dir'])
            self.assertEqual(calls[1]['attachment'],attachment)
            self.assertEqual(service.ensure_fresh('retry',attachment=attachment)['scene_epoch'],held['scene_epoch'])
            self.assertEqual(len(calls),2)
