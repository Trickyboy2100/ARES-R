"""Shared operator-configured SLAM drift tolerances, not commanded arrival."""
import json,math,os,uuid
from pathlib import Path

def policy_path(root=None):
 return Path(root or os.environ.get('ARES_R_SITE_ROOT') or Path(__file__).resolve().parents[3])/'config/slam_localization_policy.json'
def read_policy(root=None):
 p=policy_path(root)
 value=json.loads(p.read_text()) if p.exists() else {'schema_version':1,'revision':'SLAM_YAW_4DEG_DEFAULT_V1','yaw_tolerance_deg':4.0}
 x=float(value['yaw_tolerance_deg'])
 if not math.isfinite(x) or not 0<x<=180:raise ValueError('INVALID_SLAM_YAW_TOLERANCE')
 t=float(value.get('translation_tolerance_m',.05))
 if not math.isfinite(t) or t<=0:raise ValueError('INVALID_SLAM_TRANSLATION_TOLERANCE')
 return dict(value,yaw_tolerance_deg=x,translation_tolerance_m=t)
def yaw_tolerance_deg(root=None):return read_policy(root)['yaw_tolerance_deg']
def translation_tolerance_m(root=None):return read_policy(root)['translation_tolerance_m']
def write_policy(root,value):
 current=read_policy(root)
 x=float(value.get('yaw_tolerance_deg',current['yaw_tolerance_deg']))
 if not math.isfinite(x) or not 0<x<=180:raise ValueError('INVALID_SLAM_YAW_TOLERANCE')
 t=float(value.get('translation_tolerance_m',current['translation_tolerance_m']))
 if not math.isfinite(t) or t<=0:raise ValueError('INVALID_SLAM_TRANSLATION_TOLERANCE')
 v=dict(schema_version=1,revision=uuid.uuid4().hex,yaw_tolerance_deg=x,translation_tolerance_m=t)
 p=policy_path(root);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix('.tmp-'+uuid.uuid4().hex);tmp.write_text(json.dumps(v,indent=2));tmp.replace(p);return v
