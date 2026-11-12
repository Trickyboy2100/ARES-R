"""Stage1 adapter for shared Live I/O, without old pick1/place3 startup gates.

Only task state is initialized here. Native I/O, gripper, verification, stop,
and telemetry methods remain inherited from the commissioned implementation.
"""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from .task_contract import task_config,digest

def make_task_live(base_class,parameters,out,event,root,task):
    class TaskLive(base_class):
        def __init__(self):
            from ares_r.offline import reject_physical_io
            reject_physical_io()
            self.p=parameters;self.out=Path(out);self.event=event;self.attached=None;self.job=None
            self.command_id=None;self.command_records=self.out/'command_records';self.command_records.mkdir(exist_ok=True)
            self.pool=ThreadPoolExecutor(max_workers=2)
            self.package=None;self.child=None;self.preland=None
            self.release_confirmed=False;self.preland_arrived=False;self.place_descent_arrived=False
            self.stopfile=self.out/'stop.request'
            self.config=task_config(json.loads((Path(root)/'config/system.json').read_text()),task)
            profile=self.config['epic']['task_profiles'][task['epic_profile']]
            if profile.get('arm')!='right':raise ValueError('task profile arm mismatch')
            self.site_profile_contract=digest(dict(task=task,profile=profile))
    return TaskLive()
