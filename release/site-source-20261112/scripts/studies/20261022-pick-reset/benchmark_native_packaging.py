"""Frozen-input before/after packaging benchmark; never dispatches motion.

Baseline source is read from the explicit pre-change custody tar, not installed
over the live script. Both variants use the same captured scene and paths.
"""
import argparse,hashlib,json,os,shutil,subprocess,sys,tarfile,time
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--prepared',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--baseline-tar',type=Path,required=True)
    a=p.parse_args();root=Path(__file__).resolve().parents[3]
    if root!=Path('/home/yikun/ARES-R-RC1-20261019'):raise RuntimeError('isolated RC1 benchmark only')
    a.output.mkdir(parents=True,exist_ok=False)
    with tarfile.open(a.baseline_tar) as archive:
        baseline=archive.extractfile('scripts/package_pick_reset_timing.py').read().decode()
    reports={};contents={}
    for variant in ('baseline','optimized'):
        dest=a.output/variant;dest.mkdir()
        for name in ('preparation-ready.json','pick-reset-paths.json','lift230-validation.json',
                     'pregrasp/planner_request.json','package/first_pick_execution_package.json'):
            target=dest/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(a.prepared/name,target)
        script=root/'scripts/package_pick_reset_timing.py'
        if variant=='baseline':
            # Keep the original __file__ so its repository/config resolution is unchanged.
            code='import sys;sys.argv='+repr([str(script),'--prepared',str(dest)])+';exec(compile('+repr(baseline)+','+repr(str(script))+',"exec"),{"__name__":"__main__","__file__":'+repr(str(script))+'})'
            command=[sys.executable,'-c',code]
        else:command=[sys.executable,str(script),'--prepared',str(dest)]
        started=time.monotonic()
        with (a.output/(variant+'.log')).open('x') as log:
            result=subprocess.run(command,cwd=root,env=dict(os.environ,PYTHONPATH=str(root/'src')),stdout=log,stderr=subprocess.STDOUT,timeout=180)
        if result.returncode:raise RuntimeError(variant+' packaging failed')
        manifest=json.loads((dest/'native-manifest.json').read_text())
        reports[variant]=dict(wall_s=time.monotonic()-started,segments=manifest['segments'])
        contents[variant]={row['segment']:(dest/'native'/(row['segment']+'.native.txt')).read_text().splitlines() for row in manifest['segments']}
    identical=all(contents['baseline'][name][1:]==contents['optimized'][name][1:] and
        contents['baseline'][name][0].split()[:3]+contents['baseline'][name][0].split()[4:]==
        contents['optimized'][name][0].split()[:3]+contents['optimized'][name][0].split()[4:]
        for name in contents['baseline'])
    report=dict(physical_motion=False,scene_reused_only_for_frozen_benchmark=True,
        baseline_source_sha256=hashlib.sha256(baseline.encode()).hexdigest(),
        identical_native_except_capture_timestamp=identical,results=reports)
    (a.output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report),flush=True)
    if not identical:raise RuntimeError('optimized native output differs')

if __name__=='__main__':main()
