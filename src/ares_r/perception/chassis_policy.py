"""Runtime policy for explicitly registered robot-chassis geometry."""
import json
from pathlib import Path


CHASSIS_IDS = frozenset(("body/chassis", "body_chassis_lower"))


def chassis_enabled():
    path = Path(__file__).resolve().parents[3] / 'config/robot_collision_model.json'
    model = json.loads(path.read_text())
    return model.get('geometry_policy', {}).get('chassis_collision_enabled', True)


def is_chassis_geometry(item):
    if isinstance(item, dict):
        identifier = item.get('geometry_id', item.get('object_id', item.get('id')))
        return identifier in CHASSIS_IDS or item.get('owner') == 'chassis'
    return (getattr(item, 'object_id', getattr(item, 'geometry_id', None)) in CHASSIS_IDS
            or getattr(item, 'owner', None) == 'chassis')
