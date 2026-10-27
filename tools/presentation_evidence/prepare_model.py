"""Reconstruct arm-only planner configuration from pinned ARES sources.
No URDF edits. Gripper geometry comes from the captured execution_tool_envelope.
This is a derived offline runtime, not the absent commissioned site runtime YAML.
"""
import argparse,subprocess,json,hashlib
from pathlib import Path
import yaml
p=argparse.ArgumentParser();p.add_argument('--ares-repo',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(exist_ok=True,parents=True);commit='b978cbd669b5a3f6bc0bd19defcbe5256692f145';hashes={}
for name in ['jaka_minicobo_gripper.urdf','jaka_minicobo_curobo.yml']:
 data=subprocess.check_output(['git','show',commit+':robot/'+name],cwd=a.ares_repo);(a.output/name).write_bytes(data);hashes[name]=hashlib.sha256(data).hexdigest()
y=yaml.safe_load((a.output/'jaka_minicobo_curobo.yml').read_text());k=y['kinematics'];k.update(urdf_path=str((a.output/'jaka_minicobo_gripper.urdf').resolve()),asset_root_path=str(a.output.resolve()),load_meshes=False,use_external_assets=False,tool_frames=['link6'],lock_joints={'4C2_Joint1':0.0});c=k['cspace'];assert c['joint_names']==['joint%d'%i for i in range(1,7)]+['4C2_Joint1']
for key,value in list(c.items()):
 if isinstance(value,list) and len(value)==7:c[key]=value[:6]
(a.output/'robot.yml').write_text(yaml.safe_dump(y));(a.output/'derivation.json').write_text(json.dumps(dict(source_commit=commit,source_hashes=hashes,commissioned=False,changes=['Relocate URDF/assets','Disable mesh rendering only','Export link6 tool frame','Keep first six arm c-space entries unchanged; remove finger DOF from arm solve','Worker uses captured gripper component envelope and attached payload'],limit='Not a site YAML equivalence claim; URDF geometry unchanged'),indent=2)+'\n')
