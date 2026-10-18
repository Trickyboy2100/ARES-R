#!/usr/bin/env python3
"""Read-only release checks. Never connects to JAKA/AMR/Epic or changes services."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
PIN='8e734f3ced1df898990bcd92de40abce475907db'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,default=ROOT/'release/roundtrip-rc1/manifest.json')
    parser.add_argument('--site-evidence',type=Path);parser.add_argument('--output',type=Path)
    parser.add_argument('--require-site',action='store_true');args=parser.parse_args();checks=[]
    def record(name,status,detail):checks.append({'check':name,'status':status,'detail':detail})
    manifest=json.loads(args.manifest.read_text())
    bad=[name for name,expected in manifest['files_sha256'].items() if not (ROOT/name).is_file() or sha(ROOT/name)!=expected]
    record('RELEASE_FILE_HASHES','FAIL' if bad else 'PASS',bad)
    source=ROOT/'worklog/runtime/curobo-pinned';source_manifest=source/'ARES_R_SOURCE_MANIFEST.json'
    if source_manifest.exists():
        value=json.loads(source_manifest.read_text());bad=[]
        for item in value['files']:
            path=source/item['path']
            if not path.exists():bad.append(item['path']);continue
            data=path.read_bytes();blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
            if blob!=item['sha']:bad.append(item['path'])
        record('PINNED_CUROBO_SOURCE','PASS' if value['commit']==PIN and not bad else 'FAIL',{'commit':value['commit'],'verified_files':len(value['files'])-len(bad),'bad':bad})
    else:record('PINNED_CUROBO_SOURCE','BLOCKED','run fetch_curobo_source.py with exact pin')
    try:
        import torch
        if not torch.cuda.is_available():raise RuntimeError('CUDA unavailable')
        torch.cuda.set_device(0);probe=torch.ones(32,device='cuda:0');torch.cuda.synchronize()
        total=torch.cuda.get_device_properties(0).total_memory
        record('CUDA_GPU0','PASS',{'name':torch.cuda.get_device_name(0),'total_bytes':total,'torch':torch.__version__,'cuda':torch.version.cuda,'allocator_fraction':.75,'budget_bytes':int(total*.75),'probe_sum':probe.sum().item()})
    except Exception as exc:record('CUDA_GPU0','BLOCKED',str(exc))
    preview=ROOT/'worklog/runtime/preview-model'
    valid=all((preview/name).exists() and sha(preview/name)==expected for name,expected in manifest['preview_model_sha256'].items() if name!='robot.yml')
    if (preview/'robot.yml').exists():
        import yaml
        model=yaml.safe_load((preview/'robot.yml').read_text())
        for key in ('asset_root_path','urdf_path'):model['kinematics'][key]='RELOCATABLE_PREVIEW'
        valid=valid and hashlib.sha256(json.dumps(model,sort_keys=True).encode()).hexdigest()==manifest['preview_model_semantics_sha256']
    else:valid=False
    record('PREVIEW_MODEL_ASSETS','PASS' if valid else 'BLOCKED','preview only; commissioned=false; installation paths may relocate')
    obligations=('oct16_raw_fixtures','commissioned_robot_tcp_collision_model','native_sender_rebuilt_and_validated',
        'route_085m_loaded_sweep','id3_lower_middle_offset_and_release40','return_no_stow_sweep','site_10gb_coexistence','onsite_stop_and_resume')
    evidence=json.loads(args.site_evidence.read_text()) if args.site_evidence else {}
    for key in obligations:
        value=evidence.get(key,{});path=Path(value.get('path',''))
        verified=value.get('status')=='PASS' and path.is_file() and value.get('sha256')==sha(path)
        record(key,'PASS' if verified else 'SITE_PENDING','hash-bound measured site evidence required')
    result={'schema_version':1,'release':manifest['release'],'checks':checks,'physical_io_attempted':False,
        'deployment':'CONDITIONAL','site_execution_allowed':all(c['status']=='PASS' for c in checks)}
    if args.output:args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    if any(c['status']=='FAIL' for c in checks) or args.require_site and not result['site_execution_allowed']:sys.exit(2)
if __name__=='__main__':main()
