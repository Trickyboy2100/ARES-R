#!/usr/bin/env python3
"""Read/index the entire frozen archive and materialize only selected visual runs."""
import hashlib,io,json,shutil,tarfile
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
def main():
 out=ROOT/'worklog/runtime/visual-review-evidence';out.mkdir(parents=True,exist_ok=True);catalog=[]
 with tarfile.open(ROOT/'release/roundtrip-rc1/replay_evidence.tar.gz') as archive:
  for member in archive:
   if not member.isfile():continue
   name=Path(member.name)
   if name.is_absolute() or '..' in name.parts:raise ValueError('unsafe archive path')
   data=archive.extractfile(member).read();entry={'path':member.name,'size':len(data),'sha256':hashlib.sha256(data).hexdigest()}
   if name.suffix=='.json':
    value=json.loads(data);entry['kind']='json';entry['top_keys']=list(value)[:12] if isinstance(value,dict) else ['list',len(value)]
    if isinstance(value,dict) and 'trajectory_points_rad' in value:entry['trajectory_samples']=len(value['trajectory_points_rad'] or [])
   elif name.suffix=='.npz':
    arrays=np.load(io.BytesIO(data));entry['arrays']={key:list(arrays[key].shape) for key in arrays.files}
   elif name.suffix=='.txt':
    lines=data.decode().splitlines();entry.update(header=lines[0],lines=len(lines))
   catalog.append(entry)
   if name.parts[0] in ('rc-final-normal','rc-final-stress640'):
    path=out/name;path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and path.read_bytes()!=data:raise RuntimeError('refuse modified extracted evidence: '+str(path))
    path.write_bytes(data)
 (out/'archive_catalog.json').write_text(json.dumps(catalog,indent=2)+'\n')
 near=ROOT/'worklog/runtime/visual-near-obstacles'
 if not near.exists():shutil.copytree(ROOT/'release/roundtrip-rc1/visuals/near_obstacle_evidence',near)
 print('read frozen archive members',len(catalog))
if __name__=='__main__':main()
