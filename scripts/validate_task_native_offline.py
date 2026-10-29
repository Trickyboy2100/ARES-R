"""Validate frozen Native geometry using timestamp-renewed DIAGNOSTIC copies.

Never executes motion. Copies have no task-binding and are not live candidates.
"""
import argparse,hashlib,json,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    from ares_r.manipulation.task_contract import task_sender
    p=argparse.ArgumentParser();p.add_argument('--prepared',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);binary=task_sender(ROOT);rows=[]
    for file in sorted((a.prepared/'native').glob('*.native.txt')):
        original=file.read_bytes();lines=original.decode().splitlines();head=lines[0].split();stamp=head[3]
        head[3]=str(int(time.time())-1);lines[0]=' '.join(head);out=a.output/file.name
        out.write_text('\n'.join(lines)+'\n')
        checked=subprocess.run([str(binary),'validate-supervised-path',str(out)],capture_output=True,text=True,timeout=15)
        rows.append(dict(segment=file.name,original_sha256=hashlib.sha256(original).hexdigest(),original_timestamp=stamp,
            diagnostic_timestamp_only_changed=True,returncode=checked.returncode,stdout=checked.stdout,stderr=checked.stderr))
    result=dict(physical_motion=False,controller_connected=False,diagnostic_only=True,execution_allowed=False,
        all_six_valid=len(rows)==6 and all(row['returncode']==0 for row in rows),segments=rows)
    (a.output/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    if not result['all_six_valid']:raise RuntimeError('diagnostic Native validation failed')

if __name__=='__main__':main()
