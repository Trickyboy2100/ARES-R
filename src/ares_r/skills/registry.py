from __future__ import annotations

from .contracts import SkillDefinition


def _object(properties=None, required=()):
    return {"type": "object", "properties": properties or {},
            "required": list(required), "additionalProperties": False}


def _skill(skill_id, category, capability, resources, properties=None, required=(),
           description="", composite=False):
    return SkillDefinition(skill_id, "1.0.0-p39", category, description or skill_id,
        _object(properties, required), _object(), tuple(resources),
        "REPLAY_VERIFIED", capability, composite)


BUILTINS = (
    _skill("observe.capture_scene", "observe", "scene.capture", ["CAMERA_5000", "SCENE_EPOCH"],
           {"profile":{"type":"string"}, "station":{"type":"string"}}),
    _skill("observe.detect_resource", "observe", "resource.detect", ["CAMERA_5700", "SCENE_EPOCH"],
           {"profile":{"type":"string"}, "resource_id":{"type":"string"}}, ("profile",)),
    _skill("observe.verify_predicate", "observe", "predicate.verify", ["SCENE_EPOCH"],
           {"predicate":{"type":"string"}, "method":{"type":"string"}}, ("predicate",)),
    _skill("navigate.registered_relative", "navigate", "base.navigate", ["BASE"],
           {"station":{"type":"string"}, "speed_profile":{"type":"string"}}, ("station",)),
    _skill("navigate.align_for_manipulation", "navigate", "base.align_for_manipulation",
           ["BASE","CAMERA_5700","CAMERA_5000","SCENE_EPOCH","GPU_PLANNER"],
           {"target_profile":{"type":"string"},
            "arm":{"type":"string","enum":["right"]},
            "goal_kind":{"type":"string","enum":["PICK_PREGRASP","PLACE_PREPLACE"]},
            "x_bound_m":{"type":"number","minimum":0.01,"maximum":0.15},
            "y_bound_m":{"type":"number","minimum":0.01,"maximum":0.40},
            "max_corrections":{"type":"integer","minimum":1,"maximum":4}},
           ("target_profile","arm","goal_kind"),
           "Closed-loop 5700 -> IK score -> AMR settle -> fresh epoch -> cuRobo alignment"),
    _skill("manipulation.move_free", "manipulation", "motion.free", ["GPU_PLANNER","ARM_RIGHT"],
           {"target":{"type":"string"}, "planner_policy":{"type":"string","enum":["FAST_FALLBACK"]}}, ("target",)),
    _skill("manipulation.approach", "manipulation", "motion.contact", ["GPU_PLANNER","ARM_RIGHT"],
           {"standoff_m":{"type":"number","minimum":0.0,"maximum":0.2}, "policy":{"type":"string"}}, ("standoff_m",)),
    _skill("manipulation.grasp", "manipulation", "gripper.grasp", ["GRIPPER_RIGHT","ARM_RIGHT"],
           {"opening_percent":{"type":"number","minimum":0,"maximum":100}, "verification":{"type":"string"}}),
    _skill("manipulation.lift", "manipulation", "motion.lift", ["GPU_PLANNER","ARM_RIGHT"],
           {"distance_m":{"type":"number","minimum":0.01,"maximum":0.3}}, ("distance_m",)),
    _skill("manipulation.move_above_place", "manipulation", "motion.free", ["GPU_PLANNER","ARM_RIGHT"],
           {"target":{"type":"string"}, "height_m":{"type":"number"}}, ("target",)),
    _skill("manipulation.release", "manipulation", "gripper.release", ["GRIPPER_RIGHT","ARM_RIGHT"],
           {"opening_percent":{"type":"number","minimum":0,"maximum":100}}),
    _skill("manipulation.retreat", "manipulation", "motion.contact", ["GPU_PLANNER","ARM_RIGHT"],
           {"distance_m":{"type":"number","minimum":0.01,"maximum":0.3}}, ("distance_m",)),
    _skill("execution.authorize", "execution", "execution.authorize", [],
           {"policy":{"type":"string"}}, ("policy",)),
    _skill("execution.execute_trajectory", "execution", "motion.execute", ["ARM_RIGHT"],
           {"trajectory_binding":{"type":"string"}}, ("trajectory_binding",)),
    _skill("manipulation.pick", "composite", "composite.pick", ["ARM_RIGHT","GRIPPER_RIGHT"], composite=True),
    _skill("manipulation.place", "composite", "composite.place", ["ARM_RIGHT","GRIPPER_RIGHT"], composite=True),
    _skill("manipulation.transfer_object", "composite", "composite.transfer", ["ARM_RIGHT","GRIPPER_RIGHT","BASE"], composite=True),
)


class SkillRegistry:
    def __init__(self, definitions=()): self._items = {x.skill_id:x for x in definitions}
    def register(self, definition):
        if definition.skill_id in self._items: raise ValueError("duplicate skill %s" % definition.skill_id)
        self._items[definition.skill_id] = definition
    def get(self, skill_id):
        if skill_id not in self._items: raise KeyError("unknown skill %s" % skill_id)
        return self._items[skill_id]
    def list(self): return [self._items[k].to_dict() for k in sorted(self._items)]


def default_registry(): return SkillRegistry(BUILTINS)
