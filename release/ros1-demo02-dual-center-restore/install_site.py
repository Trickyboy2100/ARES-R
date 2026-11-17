#!/usr/bin/env python3
"""Deploy Demo02 candidate additively. No controller commands or autostart."""
from pathlib import Path
import argparse,ast,hashlib,json,shutil,subprocess,time,urllib.request


def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('/home/yikun/ARES-R-RC1-20261019'));p.add_argument('--overlay',type=Path,default=Path('/home/yikun/ARES-R-ROS-BLOCK01-20261112/ros1-blocks-center-restore/run_backend_overlay.py'));p.add_argument('--apply',action='store_true');a=p.parse_args()
 source=Path(__file__).resolve().parent;root=a.root
 if not a.apply:print('CHECK_ONLY: --apply installs candidate; no robot motion');return
 for path in ['/api/demo-console/status','/api/operations/run-status']:
  value=json.load(urllib.request.urlopen('http://127.0.0.1:8765'+path,timeout=10))
  if value.get('running') or value.get('state')=='RUNNING':raise RuntimeError('ACTIVE_TASK')
 backup=root/'worklog/preservation'/('demo02-'+time.strftime('%Y%m%dT%H%M%S'));backup.mkdir(parents=True)
 binary=backup/'new-native'
 subprocess.run(['g++','-std=c++17','-O2','-pthread',str(source/'native/jaka_dual_arm_supervised.cpp'),'-I/home/yikun/ws/SDK v2.2.2/04 Linux/c&c++/inc_of_c++','-L/home/yikun/JAKA/lib','-Wl,-rpath,/home/yikun/JAKA/lib','-ljakaAPI','-o',str(binary)],check=True)
 old=a.overlay.read_text();needle='ares_r.demos.console.DemoConsole=CenterRestoreConsole'
 if needle not in old and 'dual_center_restore.console' not in old:raise RuntimeError('OVERLAY_LAYOUT_CHANGED')
 dest=root/'release/ros1-demo02-dual-center-restore'
 if dest.exists():shutil.copytree(dest,backup/'previous-demo02')
 shutil.copytree(source,dest,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
 if (root/'native/jaka_dual_arm_supervised').exists():shutil.copy2(root/'native/jaka_dual_arm_supervised',backup/'old-native')
 shutil.copy2(binary,root/'native/jaka_dual_arm_supervised');shutil.copy2(a.overlay,backup/'run_backend_overlay.py')
 new=old.replace(needle,"sys.path.insert(0,str(site/'release/ros1-demo02-dual-center-restore'))\nfrom dual_center_restore.console import install as install_dual_console\nares_r.demos.console.DemoConsole=install_dual_console(CenterRestoreConsole)")
 compile(new,str(a.overlay),'exec');a.overlay.write_text(new)
 # Candidate remains disabled until explicit no-motion planning preflight.
 readiness=root/'worklog/runtime/demo02/readiness.json';readiness.parent.mkdir(parents=True,exist_ok=True)
 readiness.write_text(json.dumps({'planning_preflight_passed':False,'delivered':False,'native_sha256':hashlib.sha256(binary.read_bytes()).hexdigest()}))
 subprocess.run(['systemctl','--user','restart','ares-r-backend.service','ares-r-webui.service'],check=True)
 print('DEMO02_CANDIDATE_INSTALLED_NO_MOTION');print('BACKUP='+str(backup))
if __name__=='__main__':main()
