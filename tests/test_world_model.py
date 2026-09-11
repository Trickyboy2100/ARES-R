from dataclasses import FrozenInstanceError
import json
import time
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from ares_r.world import (AttachedObject,CalibrationSet,InvalidationReason,
    LifecycleState,PointCloudRef,PoseSE3,RobotState,SafetyConstraint,SceneObject,
    SceneObjectRole,WorldModel,digest)


SHA="a"*64


def pose(frame="body",xyz=(0,0,0)):
    return PoseSE3(frame,xyz,(1,0,0,0))


def robot(runtime,mono=None):
    return RobotState(time.time_ns(),time.monotonic_ns() if mono is None else mono,runtime,
        left_joints_rad=(0,)*6,right_joints_rad=(0,)*6,left_tcp=pose(),right_tcp=pose(),
        left_gripper_position=1000,right_gripper_position=1000,
        source_revisions=(("jaka","sdk222"),))


def obstacle(observation_id,role=SceneObjectRole.OBSTACLE):
    return SceneObject("box",role,"cuboid",pose(),(.2,.3,.4),.02,observation_id,.9)


def ready_world(ttl=5.0):
    world=WorldModel(snapshot_ttl_s=ttl,environment_ttl_s=30,runtime_id="runtime")
    world.update_robot_state(robot(world.runtime_id))
    observation_id=world.begin_observation("OBS_1")
    cloud=PointCloudRef("PC_1",SHA,"epic_camera")
    world.register_pointcloud(observation_id,cloud)
    world.register_calibration(observation_id,CalibrationSet((("camera_to_body","C1"),)))
    world.register_obstacles(observation_id,(obstacle(observation_id),),cloud.pointcloud_id,cloud.sha256)
    world.commit_observation(observation_id)
    return world


class WorldModelTest(unittest.TestCase):
    def test_se3_is_normalized_and_immutable(self):
        value=pose()
        with self.assertRaises(FrozenInstanceError):value.xyz_m=(1,2,3)
        with self.assertRaises(ValueError):PoseSE3("body",(0,0,0),(2,0,0,0))

    def test_digest_is_canonical(self):
        self.assertEqual(digest({"b":2,"a":1}),digest({"a":1,"b":2}))
        first=obstacle("OBS")
        second=SceneObject("another",SceneObjectRole.FIXED,"cuboid",pose(),(.1,.1,.1),0,"OBS")
        # Epoch canonicalization makes upstream object ordering irrelevant.
        from ares_r.world import ObservationEpoch
        calibration=CalibrationSet((("camera","C1"),));cloud=PointCloudRef("PC",SHA.upper(),"camera")
        now=time.time_ns()
        a=ObservationEpoch("OBS",now,1,"runtime",calibration,cloud,(first,second))
        b=ObservationEpoch("OBS",now,1,"runtime",calibration,cloud,(second,first))
        self.assertEqual(digest(a),digest(b));self.assertEqual(cloud.sha256,SHA)

    def test_epoch_blocks_mixed_pointcloud_obstacles(self):
        world=WorldModel(runtime_id="runtime");observation_id=world.begin_observation("OBS_1")
        cloud=PointCloudRef("PC_1",SHA,"camera");world.register_pointcloud(observation_id,cloud)
        with self.assertRaisesRegex(RuntimeError,"provenance"):
            world.register_obstacles(observation_id,(obstacle(observation_id),),"PC_2",SHA)
        with self.assertRaisesRegex(RuntimeError,"another observation"):
            world.register_obstacles(observation_id,(obstacle("OBS_2"),),"PC_1",SHA)

    def test_commit_requires_complete_epoch(self):
        world=WorldModel(runtime_id="runtime");world.begin_observation("OBS_1")
        with self.assertRaisesRegex(RuntimeError,"pointcloud"):
            world.commit_observation("OBS_1")

    def test_snapshot_is_immutable_and_external_lifecycle_is_active(self):
        world=ready_world();snapshot=world.freeze_snapshot("mini2-urdf","tool-2")
        self.assertEqual(world.require_active_snapshot(),snapshot)
        self.assertEqual(world.lifecycle.state,LifecycleState.ACTIVE)
        self.assertEqual(snapshot.pointcloud_id,"PC_1")
        self.assertNotIn("valid",snapshot.__dataclass_fields__)
        with self.assertRaises(FrozenInstanceError):snapshot.snapshot_id="changed"

    def test_arm_motion_stales_snapshot_but_preserves_environment(self):
        world=ready_world();snapshot=world.freeze_snapshot("robot","tool")
        environment=world.environment
        world.robot_moved("right")
        self.assertEqual(world.lifecycle.state,LifecycleState.STALE)
        self.assertEqual(world.lifecycle.reason,InvalidationReason.RIGHT_ARM_MOVED)
        self.assertIs(world.environment,environment)
        with self.assertRaises(RuntimeError):world.require_active_snapshot()
        world.update_robot_state(robot(world.runtime_id))
        newer=world.freeze_snapshot("robot","tool")
        self.assertEqual(newer.environment.environment_revision_id,environment.environment_revision_id)
        self.assertNotEqual(newer.snapshot_id,snapshot.snapshot_id)

    def test_base_motion_and_calibration_change_invalidate_environment(self):
        for action in ("base_moved","calibration_changed"):
            world=ready_world();world.freeze_snapshot("robot","tool");getattr(world,action)()
            self.assertIsNone(world.environment)
            self.assertEqual(world.lifecycle.state,LifecycleState.INVALIDATED)

    def test_new_observation_cannot_mix_with_old_environment(self):
        world=ready_world();world.freeze_snapshot("robot","tool")
        world.begin_observation("OBS_2")
        self.assertIsNone(world.environment)
        self.assertEqual(world.status()["observation_open"],"OBS_2")

    def test_attachment_stales_planning_start(self):
        world=ready_world();world.freeze_snapshot("robot","tool")
        shape=obstacle("OBS_1",SceneObjectRole.TARGET)
        attached=AttachedObject("box","right",pose("right_tcp"),shape,"grasp-1")
        world.attach("right",attached)
        self.assertEqual(world.lifecycle.reason,InvalidationReason.OBJECT_ATTACHED_RIGHT)
        self.assertIs(world.right_attached_object,attached)

    def test_snapshot_ttl_uses_current_runtime_monotonic_clock(self):
        world=ready_world(ttl=.001);world.freeze_snapshot("robot","tool")
        lifecycle=world.lifecycle_now(world.lifecycle.changed_monotonic_ns+world.snapshot_ttl_ns+1)
        self.assertEqual(lifecycle.state,LifecycleState.EXPIRED)

    def test_environment_ttl_blocks_freeze(self):
        world=WorldModel(snapshot_ttl_s=1,environment_ttl_s=.001,runtime_id="runtime")
        world.update_robot_state(robot("runtime"));old=time.monotonic_ns()-2_000_000
        obs=world.begin_observation("OBS_1",monotonic_ns=old);cloud=PointCloudRef("PC",SHA,"camera")
        world.register_pointcloud(obs,cloud);world.register_calibration(obs,CalibrationSet((("c","1"),)))
        world.register_obstacles(obs,(),"PC",SHA);world.commit_observation(obs)
        with self.assertRaisesRegex(RuntimeError,"expired"):world.freeze_snapshot("robot","tool")

    def test_artifact_and_event_log_preserve_snapshot(self):
        events=Mock();world=ready_world();world.event_log=events
        constraint=SafetyConstraint("center","CENTRAL_TCP_EXCLUSION",(("half_width_m",.07),))
        with tempfile.TemporaryDirectory() as tmp:
            snapshot=world.freeze_snapshot("robot","tool",(constraint,),tmp)
            data=json.loads((Path(tmp)/(snapshot.snapshot_id+".json")).read_text())
        self.assertEqual(data["snapshot_id"],snapshot.snapshot_id)
        self.assertEqual(data["constraints"][0]["kind"],"CENTRAL_TCP_EXCLUSION")
        self.assertTrue(any(call.args[0]=="world.snapshot_created" for call in events.write.call_args_list))


if __name__=="__main__":unittest.main()
