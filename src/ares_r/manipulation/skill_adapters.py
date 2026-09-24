"""Thin Skill adapters over canonical motion, observation and execution services.

These classes intentionally contain no obstacle processing or alternate motion
implementation.  They make the service boundaries callable by the Scheme layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .contact_motion import plan_constrained_contact


@dataclass
class NavigationSkills:
    base: object

    def go_to_station(self, station_id):
        return self.base.navigate(str(station_id))

    def registered_relative(self, x_m, y_m, yaw_deg, *args, **kwargs):
        return self.base.move_relative(float(x_m), float(y_m), float(yaw_deg), *args, **kwargs)


@dataclass
class ObservationSkills:
    transaction: object

    def capture_scene_and_detect_resource(self, destination, profile="right_pick"):
        return self.transaction.capture(destination, profile=profile)


@dataclass
class ManipulationSkills:
    scene_motion: object
    world_model: object
    contact_geometry: Callable
    contact_ik: Callable

    def move_free(self, request):
        """All free-space motion delegates to SceneAwareMotionService."""
        return self.scene_motion.plan(request)

    def approach(self, start_pose_body, goal_pose_body, *, policy, target, obstacles,
                 dense_step_m=.002):
        return plan_constrained_contact(
            start_pose_body, goal_pose_body, policy=policy,
            solve_ik=self.contact_ik, geometry_at=self.contact_geometry,
            target=target, obstacles=obstacles, dense_step_m=dense_step_m)

    def grasp(self, side, attached_object):
        """Logical planning transition only; physical gripper command is elsewhere."""
        self.world_model.attach(side, attached_object)
        return {"transition": "ATTACHED", "object_id": attached_object.object_id,
                "source_revision": attached_object.source_revision}

    def lift(self, request):
        return self.move_free(request)

    def move_above_place(self, request):
        return self.move_free(request)

    def release(self, side):
        self.world_model.detach(side)
        return {"transition": "DETACHED", "side": side}

    def retreat(self, request):
        return self.move_free(request)


@dataclass
class ExecutionSkills:
    safety_kernel: object
    executor: Callable

    def authorize(self, **kwargs):
        return self.safety_kernel.authorize(**kwargs)

    def execute_trajectory(self, permit, trajectory):
        return self.executor(permit, trajectory)
