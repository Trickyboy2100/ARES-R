import os,sys,runpy
from pathlib import Path
here=Path(__file__).resolve().parent
sys.path.insert(0,'/home/yikun/ARES-R-ROS-BLOCK01-20261112/ros1-blocks-center-restore')
sys.path.insert(0,str(here))
path=here/'turbo_runner.py'
exec(compile(path.read_text(),str(path),'exec'),{'__name__':'__main__','__package__':'center_restore','__file__':str(path)})
