#!/usr/bin/env python3
"""Launch only when canonical backend is idle and its old process stopped.
No production source files are modified. Existing WebUI/TCP keep the same API.
"""
import os,sys,runpy
from pathlib import Path
site=Path(os.environ.get('ARES_R_SITE_ROOT','/home/yikun/ARES-R-RC1-20261019'))
overlay=Path(__file__).resolve().parent
sys.path.insert(0,str(site/'src'));sys.path.insert(0,str(overlay))
os.environ['ARES_R_SITE_ROOT']=str(site)
os.environ['PYTHONPATH']=str(overlay)+os.pathsep+str(site/'src')
import ares_r.demos.console
from center_restore.console import CenterRestoreConsole
# Keep original console class as base; only this process gets the extension.
ares_r.demos.console.DemoConsole=CenterRestoreConsole
os.chdir(site)
runpy.run_module('ares_r.canonical_backend',run_name='__main__')
