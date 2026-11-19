"""Run the existing prepare pipeline with a B-only per-observation composition."""
from pathlib import Path
import sys,hashlib,json,os
root=Path(__file__).resolve().parents[2];source=root/'scripts/studies/20261022-pick-reset/prepare_pick_reset_bundle.py';text=source.read_text()
needle="json.dumps(p.get('task_tcp_offset_m_rad',[0]*6))"
if text.count(needle)!=1:raise RuntimeError('B_PREPARATION_BOUNDARY_CHANGED')
text=text.replace(needle,'json.dumps(effective_offset(p,E,O))')
if '--parameters' in sys.argv:
 profile=Path(sys.argv[sys.argv.index('--parameters')+1]).resolve()
 if json.loads(profile.read_text()).get('capability_version') in ('1.2','1.3','1.4','1.5'):
  child="'scripts/prepare_authorized_first_pick.py'"
  if text.count(child)!=1:raise RuntimeError('B_CONTACT_PREPARER_BOUNDARY_CHANGED')
  text=text.replace(child,"'release/function-AA0F0/prepare_contact_biased.py'")
  os.environ['ARES_R_AA0F0_B_PROFILE']=str(profile)
  if json.loads(profile.read_text()).get('capability_version')=='1.5':
   os.environ['ARES_R_AA0F0_B_V15_PARALLEL_STATE']='1'
text='from calibration_model import effective_offset\n'+text
namespace={'__name__':'__main__','__file__':str(source)}
exec(compile(text,str(source)+'[AA0F0-B]','exec'),namespace)
