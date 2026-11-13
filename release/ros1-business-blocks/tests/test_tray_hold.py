"""Run the patched original main against a hardware-free boundary adapter."""
import contextlib
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest
import numpy as np
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT.parent / 'site-source-20261112'
sys.path[:0] = [str(ROOT), str(SITE / 'src'), str(SITE / 'scripts')]
from blocks.tray_hold import load_tray_hold
from ares_r.manipulation.pick_reset_pipeline import digest


class TrayHoldTests(unittest.TestCase):
    def test_pinned_source_is_unchanged(self):
        before = (SITE / 'scripts/run_pick_reset_timing.py').read_bytes()
        module = load_tray_hold(SITE)
        self.assertEqual(module.ROOT, SITE.resolve())
        self.assertEqual(before, (SITE / 'scripts/run_pick_reset_timing.py').read_bytes())

    def test_hold_and_return_cannot_be_combined(self):
        module = load_tray_hold(SITE)
        with patch.object(sys, 'argv', ['runner', '--prepared', '/tmp/p', '--output', '/tmp/o',
                                       '--authorization', module.HOLD_AUTH,
                                       '--hold-after-lift', '--return-only']):
            with self.assertRaisesRegex(ValueError, 'mutually exclusive'):
                module.main()

    def run_original(self, hold, verification_failure=False):
        module = load_tray_hold(SITE)
        with tempfile.TemporaryDirectory() as folder:
            site = Path(folder).resolve()
            module.ROOT = site
            prepared = site / 'worklog/evidence/prepare'
            prepared.mkdir(parents=True)
            out = prepared / ('hold-execution' if hold else 'execution')
            def save(path, value):
                target = prepared / path
                target.parent.mkdir(exist_ok=True, parents=True)
                target.write_text(json.dumps(value))
            names = ['pregrasp', 'contact', 'lift230', 'lower230', 'retreat', 'center']
            paths = {name: [[0.] * 6, [0.] * 6] for name in names}
            params = dict(contact_sender='/offline/native', curobo_python=sys.executable,
                          gripper_delayed_readback_s=[.01, .02], gripper_pregrasp_raw=400,
                          gripper_closed_raw=0, gripper_release_raw=400)
            rows = []
            for name in names:
                native = prepared / 'native' / (name + '.native.txt')
                native.parent.mkdir(exist_ok=True)
                native.write_text('test 0 0 0 3\n0\n0\n0\n0 0 0 0 0 0\n0 0 0 0 0 0\n')
                rows.append(dict(segment=name, native_path_sha256=module.path_hash(paths[name])))
                save('native/' + name + '.audit.json', dict(duration_s=0))
            save('native-manifest.json', dict(parameters=params, package_sha256='pkg',
                scene_snapshot_id='scene', path_set_sha256=digest(paths), segments=rows))
            save('package/first_pick_execution_package.json', dict(package_sha256='pkg'))
            save('pregrasp/planner_request.json', dict(scene_snapshot_id='scene',
                robot_yaml_urdf='offline', T_body_model=[], T_link6_tcp=[]))
            save('pick-reset-paths.json', paths)
            save('epoch/manipulation_observation.json', dict(captured_at_unix=time.time()))
            save('epoch/epic_5700_detection.json', dict(pose=dict(values=[0.] * 6)))
            commands = []
            transform = [[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]
            arm = dict(joints_rad=[0.] * 6, tool_id=3, position_m=[0,0,.23], T_body_tcp=transform,
                       controller_status=dict(in_position=True, errcode=0, emergency_stop=False,
                           protective_stop=False, drag_mode=False, on_soft_limit=False))
            class Live:
                def __init__(self, *args):
                    self.config={'epic':{}}
                    self.pool=types.SimpleNamespace(shutdown=lambda **kwargs: None)
                def telemetry(self): return {'arms': {'left': arm, 'right': arm}}
                def check_cancelled(self): pass
                def invalidate(self, reason): pass
                def _mark_dispatch(self, reason): pass
                def _grasp_position(self): return [0,0,0]
                def stop(self): commands.append('STOP')
                def gripper(self, raw): commands.append(('gripper',raw)); return {'readback_raw':raw}
                def verify_grasp(self): return {'result':'PASS'}
                def post(self, *args, **kwargs): return {'scene_dir':'offline-scene'}
                def command(self, args, log, *extra):
                    args=list(map(str,args));log=Path(log)
                    if 'supervised_path' in args:
                        commands.append(Path(args[2]).name)
                        log.write_text('{"event":"target_reached"}\n{"event":"servo_disabled","code":0}\n')
                    elif 'scripts/gripper_direct_once.py' in args:
                        log.write_text('{"fault_code":0}')
                    elif 'scripts/verify_authorized_first_pick.py' in args:
                        if verification_failure: raise RuntimeError('POST_LIFT_VERIFICATION_FAILED')
                        Path(args[args.index('--output')+1]).write_text('{"verification":{"result":"PASS"}}')
                    else: log.write_text('')
            class Monitor:
                def __init__(self, read): pass
                def start(self): return self
                def wait_ready(self, cancel): return {}
                def snapshot(self): return {}
                def close(self): pass
            class Epic:
                def __init__(self, config): pass
                def _detect_profile(self,*args):
                    return types.SimpleNamespace(success=True,pose=types.SimpleNamespace(values=lambda:[0.]*6))
                def close(self): pass
            original_spec=importlib.util.spec_from_file_location
            def spec(name, path, *args, **kwargs):
                if str(path).endswith('run_grasp_place_roundtrip.py'):
                    loader=types.SimpleNamespace(create_module=lambda spec: None,
                        exec_module=lambda module: setattr(module,'Live',Live))
                    return importlib.util.spec_from_loader(name, loader)
                return original_spec(name,path,*args,**kwargs)
            def readback(args, **kwargs):
                self.assertEqual(args[1:], ['scripts/gripper_direct_once.py','read'])
                kwargs['stdout'].write(json.dumps(dict(action='read',position_raw=100,captured_at_unix=time.time())))
                return types.SimpleNamespace(returncode=0)
            def collect(scan, read, **kwargs): return scan(), [read(0),read(1)]
            argv=['runner','--prepared',str(prepared),'--output',str(out),'--authorization',
                  module.HOLD_AUTH if hold else module.AUTH,'--onsite-observer-confirmed']
            if hold: argv.append('--hold-after-lift')
            old_cwd=Path.cwd()
            with contextlib.ExitStack() as stack:
                stack.callback(lambda: __import__('os').chdir(old_cwd))
                for target,value in [
                    ('ares_r.manipulation.first_pick_package.verify_first_pick_package',lambda p:None),
                    ('ares_r.motion.native_execution_package.verify_installed_sender',lambda p:None),
                    ('ares_r.manipulation.pick_reset_pipeline.StationaryBaseMonitor',Monitor),
                    ('ares_r.manipulation.pick_reset_pipeline.collect_during_scene',collect),
                    ('ares_r.adapters.epic.EpicClient',Epic),
                    ('importlib.util.spec_from_file_location',spec),
                    ('subprocess.run',readback),
                ]: stack.enter_context(patch(target,value))
                stack.enter_context(patch.dict(sys.modules, {'ares_r.motion.runtime_goal_ik': types.SimpleNamespace(RuntimeGoalIK=lambda *args: types.SimpleNamespace(fk=lambda q: np.array(transform)))}))
                stack.enter_context(patch.object(module,'preflight',return_value=3))
                stack.enter_context(patch.object(module,'settle_segment',side_effect=lambda live,*a,**k:dict(final_telemetry=live.telemetry())))
                stack.enter_context(patch.object(sys,'argv',argv))
                stack.enter_context(patch('socket.socket',side_effect=AssertionError('network forbidden')))
                stack.enter_context(patch('subprocess.Popen',side_effect=AssertionError('process forbidden')))
                if verification_failure:
                    with self.assertRaisesRegex(RuntimeError,'POST_LIFT'): module.main()
                    self.assertEqual(json.loads((out/'status.json').read_text())['state'],'FAULT')
                else:
                    module.main()
                    result=json.loads((out/'result.json').read_text())
                    self.assertEqual(result['result'],'TRAY_PICK_LIFT230_HOLD' if hold else 'PICK_LIFT_REPLACE_RESET_COMPLETE')
            return commands

    def test_actual_main_holds_without_release_or_return(self):
        calls=self.run_original(True)
        self.assertEqual(calls,[('gripper',400),'pregrasp.execute.txt','contact.execute.txt',
                                ('gripper',0),'lift230.execute.txt'])

    def test_default_main_still_completes_original_reset(self):
        calls=self.run_original(False)
        self.assertEqual(calls[-4:],['lower230.execute.txt',('gripper',400),'retreat.execute.txt','center.execute.txt'])

    def test_failed_verification_stops_before_return_or_success(self):
        calls=self.run_original(True,True)
        self.assertEqual(calls[-1],'STOP')
        self.assertNotIn('lower230.execute.txt',calls)
