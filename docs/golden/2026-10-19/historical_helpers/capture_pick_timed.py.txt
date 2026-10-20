"""Timing wrapper over unchanged read-only capture command; never motion."""
import json,os,runpy,sys,time
from pathlib import Path
from ares_r.adapters.epic import EpicClient
from ares_r.motion import live_scene
ROOT=Path('/home/yikun/ARES-R-RC1-20261019');OUT=Path(os.environ['ARES_R_REHEARSAL_DIR'])
if ROOT/'worklog/evidence' not in OUT.parents:raise ValueError('isolated evidence directory required')
trace=[]
def wrapped(name,fn):
 def call(*args,**kwargs):
  t=time.monotonic()
  try:return fn(*args,**kwargs)
  finally:
   trace.append({'phase':name,'wall_s':time.monotonic()-t})
   (OUT/'capture_phase_timing.json').write_text(json.dumps(trace,indent=2)+'\n')
 return call
EpicClient._detect_profile=wrapped('5700_ID1_detection',EpicClient._detect_profile)
live_scene.build_live_planning_scene=wrapped('fresh_camera_and_scene',live_scene.build_live_planning_scene)
sys.argv=['capture_manipulation_observation.py','--output',str(OUT/'epoch2'),'--profile','right_pick']
runpy.run_path(str(ROOT/'scripts/capture_manipulation_observation.py'),run_name='__main__')
