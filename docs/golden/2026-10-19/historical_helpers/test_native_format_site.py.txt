"""Runs validate-only binary in offline sandbox; never a live sender mode."""
import json,subprocess,time,math
from pathlib import Path
root=Path('/home/yikun/ARES-R-RC1-20261019');out=root/'worklog/runtime/site-integration'
cases=[('fresh_fractional_%d'%i,0,0) for i in range(10)]+[('expired',-301,2),('future',30,2)]
records=[]
for label,delta,expected in cases:
    p=out/(label+'.synthetic-native.txt')
    p.write_text('ARES_R_RIGHT_V2 3 0.08 %.17g 1 0.2 0.2 1.5\n'%(time.time()+delta)+
        '0 0 0 0 0 0\n-6 -6 -6 -6 -6 -6\n6 6 6 6 6 6\n'+'0 0 0 0 0 0\n'*3)
    r=subprocess.run(['bash','scripts/offline_sandbox.sh','native/jaka_right_rc1','validate-supervised-path',str(p)],cwd=root,capture_output=True,text=True)
    records.append({'case':label,'expected_rc':expected,'actual_rc':r.returncode,'passed':r.returncode==expected,'stdout':r.stdout,'stderr':r.stderr})
result={'kind':'SYNTHETIC_FORMAT_VALIDATION_ONLY','physical_motion':False,'passed':all(x['passed'] for x in records),'records':records}
(out/'native-format-regression.json').write_text(json.dumps(result,indent=2)+'\n')
print('NATIVE_FORMAT',result['passed'],sum(r['passed'] for r in records),len(records))
raise SystemExit(0 if result['passed'] else 1)
