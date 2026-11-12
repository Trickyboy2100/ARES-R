"""Compile a NEW task-scoped sender. Invalid-mode check never logs into JAKA."""
import hashlib,json,os,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'demos/right_arm_shaiwang_pick_reset_v1'
INCLUDE=Path('/home/yikun/ws/SDK v2.2.2/04 Linux/c&c++/inc_of_c++')
LIBRARY=Path('/home/yikun/JAKA/lib')

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    source=BASE/'native_sender.cpp'
    directory=ROOT/'worklog/runtime/task-assets/shaiwang-stage1'/sha(source)
    directory.mkdir(parents=True,exist_ok=True);binary=directory/'jaka_right_task_sender'
    if not binary.exists():
        subprocess.run(['g++','-std=c++11','-O2',str(source),'-I'+str(INCLUDE),'-L'+str(LIBRARY),
            '-Wl,--disable-new-dtags,-rpath,'+str(LIBRARY),'-Wl,-z,now','-ljakaAPI','-pthread','-o',str(binary)],check=True)
    env=dict(os.environ,LD_LIBRARY_PATH=str(LIBRARY),LD_BIND_NOW='1',LD_PRELOAD='',LD_AUDIT='')
    checked=subprocess.run([str(binary),'invalid'],env=env,capture_output=True,text=True,timeout=10)
    if checked.returncode!=2 or 'invalid explicit mode' not in checked.stderr:raise RuntimeError('sender loader/invalid-mode check failed')
    proof=dict(schema_version=1,mode='task_supervised_path',start_tolerance_deg=.1,
        source_sha256=sha(source),binary_sha256=sha(binary),binary_relative_path=str(binary.relative_to(ROOT)),
        sdk_header_sha256=sha(INCLUDE/'JAKAZuRobot.h'),sdk_library=str(LIBRARY/'libjakaAPI.so'),
        sdk_library_sha256=sha(LIBRARY/'libjakaAPI.so'),controller_connected=False,physical_motion=False)
    (BASE/'native_sender.build.json').write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps(proof,indent=2))

if __name__=='__main__':main()
