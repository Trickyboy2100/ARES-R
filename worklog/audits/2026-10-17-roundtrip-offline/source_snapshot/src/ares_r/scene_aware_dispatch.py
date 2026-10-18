"""Shared command dispatcher for ART and the scene-aware Web UI."""

from __future__ import annotations

import json
import shlex
from pathlib import Path

from .motion.ab_client import ABDemoClient
from .manipulation.attached_collision import verify_attached_collision
from .motion.local_scene_service import ScenePolicy
from .motion.scene_aware_motion import (MotionConstraints, MotionGoal, MotionRequest,
                                        OrientationMode, build_services)
from .demos import DemoRegistry
from .task_studio import TaskStudio
from .runtime_identity import runtime_identity


RIGHT_CENTER_BODY_M = (0.3583093030168863, -0.0800000000000000,
                       1.0278356006116391)
RIGHT_CENTER_YAW_RAD = 1.5707963267948966


def _motion_request(payload, default_central_exclusion=True):
    arbitrary = "position_m" in payload or "goal" in payload
    orientation = OrientationMode(payload.get(
        "orientation", "LEVEL_YAW_FREE" if arbitrary else "FREE"))
    # A carried payload must reach cuRobo as a collision body.  Until now this
    # field was never read from the payload, so every plan made through the
    # Web UI or ART was computed with the held tray invisible to collision
    # checking while the arm swept the workspace.  Bind the revision to the
    # geometry itself so the planner and the independent validator cannot
    # silently disagree about which payload they were given.
    attached_geometry = payload.get("attached_object_geometry")
    attached_revision = payload.get("attached_object_revision")
    if attached_geometry is not None:
        verify_attached_collision(attached_geometry, attached_revision)
        if attached_revision is None:
            attached_revision = attached_geometry["revision"]
    constraints = MotionConstraints(
        orientation=orientation,
        explicit_rotation=payload.get("explicit_rotation"),
        central_exclusion=payload.get("central_exclusion", default_central_exclusion),
        keepout_ids=tuple(payload.get("keepout_ids", ())),
        attached_object_revision=attached_revision,
        attached_object_geometry=attached_geometry)
    from dataclasses import replace
    constraints = replace(constraints, environment_avoidance=payload.get('environment_avoidance', 'AUTO'))
    goal_payload = payload.get("goal")
    if goal_payload is None and "position_m" in payload:
        goal_payload = {
            "position_m": payload["position_m"], "orientation": orientation.value,
            "yaw_target_rad": payload.get("yaw_target_rad"),
            "explicit_rotation": payload.get("explicit_rotation"),
            "source": payload.get("source", "runtime"),
        }
    goal = (None if goal_payload is None else MotionGoal(
        position_m=goal_payload["position_m"],
        frame=goal_payload.get("frame", "BODY"),
        orientation=OrientationMode(goal_payload.get("orientation", orientation.value)),
        yaw_target_rad=goal_payload.get("yaw_target_rad"),
        explicit_rotation=goal_payload.get("explicit_rotation"),
        position_tolerance_m=float(goal_payload.get("position_tolerance_m", .003)),
        orientation_tolerance_deg=float(goal_payload.get("orientation_tolerance_deg", 3.0)),
        source=goal_payload.get("source", payload.get("source", "runtime"))))
    return MotionRequest(
        arm=payload["arm"], goal_joints_rad=payload.get("goal_joints_rad"), goal=goal,
        goal_pose_body_m_rad=payload.get("goal_pose_body_m_rad"),
        constraints=constraints,
        speed_profile=payload.get("speed_profile", "slow"),
        scene_policy=ScenePolicy(payload.get("scene_policy", "AUTO_FRESH")),
        request_label=payload.get("request_label", "free_space_motion"),
        planning_mode=payload.get('planning_mode','QUALITY'))


class SceneAwareDispatcher:
    def __init__(self, config):
        self.config = config
        self._studio = TaskStudio(Path.cwd())
        from .operations import OperationsRegistry
        self.operations = OperationsRegistry(Path.cwd())

    def operations_status(self):
        state = self.operations.read()
        from .offset_frames import offset_context
        state['offset_frame_context']=offset_context(state,self.scene_status())
        root = self.operations.root
        from .motion.scene_aware_planner import load_profile
        profiles = load_profile()['speed_profiles']
        state['installed_speed_profiles'] = profiles
        state['selectable_speed_profiles'] = dict(profiles, **{
            'draft:' + name: value for name,value in state['speed_drafts'].items()})
        state['limit_inventory'] = []
        for file in ('jaka_mini2_motion.site.json', 'scene_aware_motion.json', 'speed_profiles.json'):
            path = root / 'config' / file
            if path.exists():
                state['limit_inventory'].append({'source': str(path.relative_to(root)),
                    'values': json.loads(path.read_text())})
        state['controller_protections'] = ['ESTOP', 'COLLISION', 'CONTROLLER_JOINT_LIMIT',
                                          'SERVO_DEADLINE', 'TRACKING_STOP']
        return state

    def operations_update(self, action, body):
        result = self.operations.update(action, body,scene_context=self.scene_status())
        if action in ('policy', 'software_limits', 'complete'):
            self.scene_invalidate('OPERATIONS_' + action.upper() + '_CHANGED')
        return result

    def operations_offset_convert(self,body):
        return self.operations.convert_offsets(body,self.scene_status())

    def berth_select(self, operation):
        return self.operations.select(operation.upper())

    def berth_target(self, slot_id):
        scene = self.scene_status()
        if scene.get('state') != 'READY': raise ValueError('fresh scene required')
        return self.operations.target(slot_id, scene['base_pose_revision'], scene['scene_epoch'])

    def berth_detect_corner(self):
        """Use existing 5700 parser and ObservationV2, with no task motion."""
        import copy
        import time
        import uuid
        import numpy as np
        from .adapters.epic import EpicClient
        from .manipulation.observation_transaction import detection_dict
        from .manipulation.observation_transaction_v2 import ObservationTransactionV2
        from .perception.robot_collision import transform_xyz_rpy
        registry = self.operations.read(); dryer = registry['dryer']
        name = dryer['anchor_profile']
        config = copy.deepcopy(self.config['epic'])
        if dryer.get('detection_profile'):
            config['task_profiles'][name] = dryer['detection_profile']
        if name not in config['task_profiles']:
            raise ValueError('configure the explicit dryer corner 5700 profile first')
        profile = config['task_profiles'][name]; side = profile['arm']
        if profile.get('orientation_convention') != 'ZYX':
            raise ValueError('corner profile needs verified ZYX rotation semantics')
        if not str(profile['output_frame']).startswith(side + '_arm_base'):
            raise ValueError('corner must use the declared arm-base frame')
        def read_state(_):
            live = self.robot_telemetry()
            if live['errors']: raise ValueError('stationary live telemetry required: ' + str(live['errors']))
            return {**{s: {'joint_position_rad':live['arms'][s]['joints_rad']} for s in ('left','right')},
                    'base':live['base']}
        def detect(_):
            result = detection_dict(EpicClient(config)._detect_profile(name, 'place:dryer_corner'))
            if not result['success'] or result['pose'] is None:
                raise ValueError('corner detection failed')
            return result
        def capture(_):
            scene = self.scene_scan(True, side)
            pointer = json.loads((Path(scene['scene_dir']) / 'capture_pointer.json').read_text())
            manifest = json.loads(Path(pointer['capture_manifest']).read_text())
            return {'sha256':scene['pointcloud_sha256'], 'captured_at_unix':manifest['captured_at_unix'],
                    'scene':scene}
        destination = self.operations.root / 'worklog/evidence/dryer-corner' / uuid.uuid4().hex
        tx = ObservationTransactionV2(read_robot_state=read_state, detect_resource=detect,
            capture_pointcloud=capture, commit_scene=lambda cloud, detection, path:cloud['scene'])
        artifact = tx.capture(destination, profile=name, purpose='DRYER_CORNER')
        before = artifact['robot_state_before']['base']['info']
        after = artifact['robot_state_after']['base']['info']
        if (before['mapId'] != after['mapId'] or np.hypot(float(before['x'])-float(after['x']),
                float(before['y'])-float(after['y'])) > .005 or
                abs((float(before['yawNumber'])-float(after['yawNumber'])+180)%360-180) > .1):
            self.scene_invalidate('BASE_MOVED_DURING_CORNER_OBSERVATION')
            raise ValueError('base moved; corner not bound')
        scene = artifact['provenance']['5000']['scene']
        detection = artifact['provenance']['5700']
        pose = detection['pose']['values']
        world = json.loads((self.operations.root / 'config/robot_world.json').read_text())['arms'][side]
        transform = transform_xyz_rpy(world['base_xyz_m'], world['base_rpy_rad']) @ transform_xyz_rpy(pose[:3],pose[3:])
        bound = self.operations.update('anchor', {'expected_revision':registry['revision'],
            'T_body_corner':transform.tolist(), 'profile':name, 'observation_epoch':scene['scene_epoch'],
            'base_pose_revision':scene['base_pose_revision'], 'captured_at_unix':detection['timestamp']})
        return {'anchor':bound, 'observation_artifact':str(destination / 'observation_v2.json'),
                'profile_state':profile.get('state','UNCOMMISSIONED')}

    def robot_telemetry(self):
        """Explicit read-only refresh; no fabricated state on disconnection."""
        import time
        from .adapters.jaka_sdk import JakaSdkArm
        from .adapters.amr_http import AmrHttpBase
        from .operations import matrix
        from .motion.se3 import pose_mm_rad_to_matrix
        from .perception.robot_collision import transform_xyz_rpy
        import numpy as np
        world = json.loads((self.operations.root / 'config/robot_world.json').read_text())
        value = {'captured_at_unix': time.time(), 'arms': {}, 'base': None, 'errors': {}}
        for side in ('left', 'right'):
            arm = None
            try:
                cfg = self.config['jaka']
                arm = JakaSdkArm(side, cfg['arms'][side], cfg)
                d = arm.diagnostics()
                base = world['arms'][side]
                t = transform_xyz_rpy(base['base_xyz_m'], base['base_rpy_rad']) @ np.asarray(
                    pose_mm_rad_to_matrix(d['tcp_position_mm_rad']))
                value['arms'][side] = {'joints_rad': d['joint_position_rad'],
                    'T_body_tcp': matrix(t).tolist(), 'position_m': t[:3, 3].tolist(),
                    'tool_id': d['tool_id'], 'controller_status': d['robot_status'],
                    'source': 'LIVE_READONLY_SDK'}
            except Exception as exc:
                value['arms'][side] = None; value['errors'][side] = str(exc)
            finally:
                if arm is not None: arm.close()
        try:
            value['base'] = AmrHttpBase(self.config['base'])._request('GET', '/robot/status')
        except Exception as exc: value['errors']['base'] = str(exc)
        return value

    def jog_plan(self, body):
        """Discrete BODY translation/rotation or joint increment through cuRobo."""
        import math
        import numpy as np
        from .operations import vector
        from .perception.robot_collision import transform_xyz_rpy
        side = body.get('arm', 'right')
        if side not in ('left', 'right'): raise ValueError('invalid arm')
        live = self.robot_telemetry()
        arm = live['arms'].get(side)
        if arm is None: raise ValueError('live arm state unavailable: ' + str(live['errors']))
        payload = {'arm': side, 'source': 'OPERATIONS_BODY_JOG',
                   'scene_policy': 'FORCE_RESCAN', 'request_label': 'BODY_JOG_PREVIEW'}
        if body.get('mode') == 'JOINT':
            delta = vector(body['delta_rad'], 6)
            payload['goal_joints_rad'] = [a+b for a,b in zip(arm['joints_rad'], delta)]
            payload['orientation'] = 'FREE'
        else:
            delta = vector(body.get('delta_m_rad', [0]*6), 6)
            t = np.asarray(arm['T_body_tcp'])
            payload.update(position_m=(t[:3, 3] + np.asarray(delta[:3])).tolist(),
                orientation=('TERMINAL_EXPLICIT' if any(abs(x)>1e-12 for x in delta[3:]) else 'EXPLICIT'),
                explicit_rotation=(transform_xyz_rpy([0]*3,
                    delta[3:])[:3, :3] @ t[:3, :3]).tolist())
        payload.update({k: body[k] for k in ('environment_avoidance', 'central_exclusion',
                                            'speed_profile','planning_mode') if k in body})
        return self.motion_plan(payload)

    def save_trajectory(self, body):
        import hashlib
        import shutil
        import uuid
        handle = self.motion_preview(body.get('plan_id'))
        destination = self.operations.root / 'worklog/runtime/operations/recordings' / uuid.uuid4().hex
        source = Path(handle['plan_artifact']).resolve()
        try:
            source.relative_to((self.operations.root / 'worklog/evidence').resolve())
        except ValueError:
            raise ValueError('trajectory source outside evidence root')
        destination.mkdir(parents=True)
        files = []
        for name in ('plan_handle.json', 'planning.json', 'planner_request.json'):
            p = source / name
            if p.is_file():
                shutil.copy2(p, destination / name)
                files.append({'file': name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})
        result = {'name': str(body.get('name', 'saved trajectory')), 'files': files,
                  'scene_snapshot_id': handle['scene_snapshot_id'],
                  'trajectory_hash': handle['trajectory_hash'], 'replay_only': True,
                  'note': 'Recorded trajectories require fresh scene/state validation before execution'}
        (destination / 'manifest.json').write_text(json.dumps(result, indent=2))
        return dict(result, directory=str(destination))

    def base_preview(self, body):
        from .operations import vector
        import math
        x, y, yaw = vector([body['x_m'], body['y_m'], body.get('yaw_deg', 0)], 3)
        cfg = self.config['base']
        speed = float(body.get('linear_mps', cfg['default_linear_speed_mps']))
        if not math.isfinite(speed) or not 0 < speed <= cfg['max_linear_speed_mps']:
            raise ValueError('base speed exceeds configured limit')
        if math.hypot(x, y) > cfg['max_relative_translation_m'] or abs(yaw) > cfg['max_relative_rotation_deg']:
            raise ValueError('relative base request exceeds configured envelope')
        if math.hypot(x, y) < .001 and abs(yaw) < .1:
            raise ValueError('base request is zero; enter a translation or rotation')
        return {'frame': 'BODY', 'x_m': x, 'y_m': y, 'yaw_deg': yaw, 'linear_mps': speed,
                'execution': 'PREVIEW_ONLY', 'scene_invalidated_on_execution': True,
                'coordinate_note': 'map pose and BODY-relative delta are different frames'}

    def services(self):
        return build_services(self.config)

    def scene_status(self):
        scene, _ = self.services();return scene.status()

    def scene_scan(self, force=True, active_arm="right"):
        scene, _ = self.services();return scene.scan(force=force, active_arm=active_arm)

    def scene_invalidate(self, reason="OPERATOR_INVALIDATION"):
        scene, motion = self.services()
        motion.invalidate_plans("SCENE_INVALIDATED:" + reason)
        return scene.invalidate(reason, required=True)

    def motion_status(self):
        _, motion = self.services();return motion.status()

    def motion_plan(self, payload):
        _, motion = self.services()
        profile_path=Path(__file__).resolve().parents[2]/"config/scene_aware_motion.json"
        policy=(json.loads(profile_path.read_text()).get("central_exclusion") or {})
        state = self.operations.read()
        payload = dict(payload)
        payload.setdefault('planning_mode','FAST')
        payload.setdefault('environment_avoidance', state['policy']['environment_avoidance'])
        payload.setdefault('central_exclusion', state['policy']['central_exclusion'])
        return motion.plan(_motion_request(payload, bool(policy.get("enabled", False))))

    def motion_plan_right_center(self):
        """Plan the commissioned right-arm center pose through the shared stack."""
        return self.motion_plan({
            "arm": "right",
            "position_m": list(RIGHT_CENTER_BODY_M),
            "orientation": "LEVEL_YAW_TARGET",
            "yaw_target_rad": RIGHT_CENTER_YAW_RAD,
            "speed_profile": "right_scene_aware_0_20",
            "scene_policy": "FORCE_RESCAN",
            "source": "NAMED_POSE_CENTER_BODY_V1",
            "request_label": "WEBUI_COMMON_RIGHT_CENTER_CUROBO",
        })

    def motion_preview(self, plan_id=None):
        _, motion = self.services();return motion.preview(plan_id)

    def motion_stop(self):
        scene, motion = self.services()
        result = motion.stop();scene.invalidate("MOTION_STOP", required=True)
        return result

    def ab_plan_next(self, destination):
        _, motion = self.services();return ABDemoClient(motion).plan(destination)

    def demo_list(self): return DemoRegistry().list()

    def demo_status(self): return DemoRegistry().status()

    def demo_inspect(self, demo_id=None): return DemoRegistry().selected(demo_id)

    def demo_select(self, demo_id): return DemoRegistry().select(demo_id)

    def demo_prepare(self, demo_id=None): return DemoRegistry().prepare(demo_id)

    def demo_stop(self): return DemoRegistry().stop()

    def studio(self): return self._studio

    def skill_list(self): return self.studio().skill_list()
    def skill_show(self, skill_id): return self.studio().skill_show(skill_id)
    def scheme_list(self): return self.studio().scheme_list()
    def scheme_show(self, scheme_id): return self.studio().scheme_show(scheme_id)
    def scheme_clone(self, source, new_id): return self.studio().scheme_clone(source, new_id)
    def scheme_validate(self, scheme): return self.studio().scheme_validate(scheme)
    def scheme_preview(self, scheme): return self.studio().scheme_preview(scheme)
    def scheme_save(self, scheme): return self.studio().scheme_save_draft(scheme)
    def task_list(self): return self.studio().task_list()
    def task_show(self, task_id): return self.studio().task_show(task_id)
    def task_prepare(self, task_id): return self.studio().prepare(task_id)
    def task_replay(self, task_id): return self.studio().start_replay(task_id)
    def task_status(self): return self.studio().status()
    def task_stop(self): return self.studio().stop()

    def system_info(self):
        task=self.task_status()
        return runtime_identity(Path.cwd(),active_scheme=task.get("scheme_id"))

    def dispatch(self, text):
        args = shlex.split(text)
        if args == ['berth', 'list']: return self.operations.read()['dryer']
        if args == ['berth', 'detect-corner']: return self.berth_detect_corner()
        if args[:2] == ['berth', 'set'] and len(args) == 4:
            return self.operations_update('slot', {'slot_id': args[2], 'occupancy': args[3].upper(),
                'expected_revision': self.operations.read()['revision']})
        if args[:2] == ['berth', 'offset'] and len(args) == 9:
            import math
            values = [float(x) for x in args[3:]]
            return self.operations_update('slot', {'slot_id':args[2],
                'offset_m_rad':[v/1000 if i<3 else math.radians(v) for i,v in enumerate(values)],
                'expected_revision':self.operations.read()['revision']})
        if args == ['ops', 'policy']: return self.operations.read()['policy']
        if args[:2] == ['ops', 'avoidance'] and len(args) == 3:
            return self.operations_update('policy', {'environment_avoidance':args[2].upper(),
                'expected_revision':self.operations.read()['revision']})
        if args[:2] == ['ops', 'central'] and len(args) == 3:
            if args[2].lower() not in ('on','off'): raise ValueError('use on or off')
            return self.operations_update('policy', {'central_exclusion':args[2].lower()=='on',
                'expected_revision':self.operations.read()['revision']})
        if args[:3] == ['ops', 'speed', 'save'] and len(args) == 6:
            return self.operations_update('speed', {'name':args[3], 'max_velocity_rad_s':float(args[4]),
                'max_acceleration_rad_s2':float(args[5]),
                'expected_revision':self.operations.read()['revision']})
        if args == ['ops', 'status']: return self.operations_status()
        if args == ['ops', 'telemetry']: return self.robot_telemetry()
        if args[:2] == ['ops', 'base-preview'] and len(args) == 3:
            return self.base_preview(json.loads(args[2]))
        if args[:2] == ['berth', 'select'] and len(args) == 3: return self.berth_select(args[2])
        if args[:2] == ['berth', 'target'] and len(args) == 3: return self.berth_target(args[2])
        if args[:2] == ['ops', 'update'] and len(args) == 4:
            return self.operations_update(args[2], json.loads(args[3]))
        if args[:2] == ['ops', 'jog'] and len(args) == 3: return self.jog_plan(json.loads(args[2]))
        if args[:2] == ['trajectory', 'save']:
            return self.save_trajectory({'name': ' '.join(args[2:]) or 'ART recording'})
        if args in (["version"],["system","info"]): return self.system_info()
        if args == ["scene", "status"]: return self.scene_status()
        if args == ["scene", "scan"]: return self.scene_scan(True)
        if args[:2] == ["scene", "invalidate"]:
            return self.scene_invalidate(" ".join(args[2:]) or "ART_INVALIDATION")
        if args == ["motion", "status"]: return self.motion_status()
        if args == ["motion", "plan-center", "right"]:
            return self.motion_plan_right_center()
        if args[:2] == ["motion", "preview"]:
            return self.motion_preview(args[2] if len(args) == 3 else None)
        if args == ["motion", "stop"]: return self.motion_stop()
        if args[:2] == ["motion", "plan"] and "--xyz" in args:
            if len(args) < 7:
                raise ValueError("usage: motion plan SIDE --xyz X Y Z [--orientation MODE] [--yaw DEG]")
            side = args[2];xyz_at = args.index("--xyz")
            xyz = [float(value) for value in args[xyz_at + 1:xyz_at + 4]]
            mode = "LEVEL_YAW_FREE"
            if "--orientation" in args:
                mode = args[args.index("--orientation") + 1]
            payload = {"arm": side, "position_m": xyz, "orientation": mode,
                       "scene_policy": "AUTO_FRESH",
                       "speed_profile": "right_scene_aware_0_20",
                       "source": "ART_RUNTIME_XYZ", "request_label": "ART_RUNTIME_TARGET"}
            payload['planning_mode']=(args[args.index('--planner')+1] if '--planner' in args else 'FAST')
            if "--yaw" in args:
                payload["yaw_target_rad"] = float(args[args.index("--yaw") + 1]) * 3.141592653589793 / 180.0
            return self.motion_plan(payload)
        if len(args) == 4 and args[:3] == ["demo", "ab", "plan-next"]:
            return self.ab_plan_next(args[3].upper())
        if args == ["demo", "list"]: return self.demo_list()
        if args == ["demo", "status"]: return self.demo_status()
        if args[:2] == ["demo", "show"] and len(args) in (2, 3):
            return self.demo_inspect(args[2] if len(args) == 3 else None)
        if args[:2] == ["demo", "select"] and len(args) == 3:
            return self.demo_select(args[2])
        if args[:2] == ["demo", "prepare"] and len(args) in (2, 3):
            return self.demo_prepare(args[2] if len(args) == 3 else None)
        if args == ["demo", "stop"]: return self.demo_stop()
        if args == ["skill", "list"]: return self.skill_list()
        if args[:2] == ["skill", "show"] and len(args) == 3: return self.skill_show(args[2])
        if args == ["scheme", "list"]: return self.scheme_list()
        if args[:2] == ["scheme", "show"] and len(args) == 3: return self.scheme_show(args[2])
        if args[:2] == ["scheme", "clone"] and len(args) == 4: return self.scheme_clone(args[2],args[3])
        if args[:2] == ["scheme", "validate"] and len(args) == 3: return self.scheme_validate(args[2])
        if args[:2] == ["scheme", "preview"] and len(args) == 3: return self.scheme_preview(args[2])
        if args[:2] == ["scheme", "save-draft"] and len(args) == 3:
            return self.scheme_save(self.scheme_show(args[2]))
        if args == ["task", "list"]: return self.task_list()
        if args[:2] == ["task", "show"] and len(args) == 3: return self.task_show(args[2])
        if args[:2] == ["task", "prepare"] and len(args) == 3: return self.task_prepare(args[2])
        if args[:2] == ["task", "preview"] and len(args) == 3:
            return self.scheme_preview(self.task_show(args[2])["scheme_id"])
        if args[:2] == ["task", "replay"] and len(args) == 3: return self.task_replay(args[2])
        if args[:2] == ["task", "status"]: return self.task_status()
        if args[:2] == ["task", "stop"]: return self.task_stop()
        if args[:2] == ["task", "run"]: raise RuntimeError("physical task run locked in P3.9")
        raise ValueError("unsupported scene-aware command")


def shared_dispatcher(config):
    """Return the canonical backend client when deployed, local owner in tests."""
    import os
    url=os.environ.get("ARES_R_BACKEND_URL")
    if url:
        from .canonical_backend import CanonicalBackendClient
        return CanonicalBackendClient(url)
    return SceneAwareDispatcher(config)
