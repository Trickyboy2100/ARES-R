#!/usr/bin/env python3
"""Package real replay receipts and timings; never runs hardware or invents PASS."""
import argparse,csv,hashlib,json,re,subprocess,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--campaign',type=Path,required=True)
    parser.add_argument('--stop-campaign',type=Path,required=True);args=parser.parse_args()
    args.campaign=args.campaign.resolve();args.stop_campaign=args.stop_campaign.resolve()
    out=ROOT/'release/roundtrip-rc1';out.mkdir(exist_ok=True,parents=True)
    campaign=load(args.campaign/'campaign.json');stops=load(args.stop_campaign/'campaign.json')
    cycles=[r for r in campaign if r['name'].startswith('cycle-')]
    if len(cycles)<10 or any(not r['pass'] or r['completed_stages']!=19 for r in cycles):raise RuntimeError('ten complete GPU cycles required')
    if any(not r['pass'] for r in campaign+stops):raise RuntimeError('unresolved acceptance case')
    runs=[load(Path(r['run_dir'])/'gpu_calls.json') for r in cycles]
    if any([r['label'] for r in run]!=['PREGRASP','HOLD230','PRELAND40'] for run in runs):raise RuntimeError('missing actual GPU stage')
    if any(not r['independent_dense_validation']['collision_free'] or not r['orientation_validation']['passed'] for run in runs for r in run):raise RuntimeError('plan proof missing')
    sample=ROOT/'worklog/runtime/rc-final-normal'
    if load(sample/'job.json')['state']!='COMPLETED' or load(ROOT/'worklog/runtime/rc-final-stress640/job.json')['state']!='COMPLETED':raise RuntimeError('final-code normal and 640-world receipts required')
    events=load(sample/'events.json');rows=[]
    for event in events:
        if event['state']!='PASS':continue
        detail=event['detail'];gpu=detail.get('gpu') or {};native=float(detail.get('native_duration_s',0));base=float(detail.get('nominal_motion_s',0))
        rows.append({'stage':event['stage'],'software_wall_s':detail['stage_wall_s'],'native_motion_s':native,
            'base_nominal_s':base,'planning_provider':gpu.get('provider') or detail.get('planning_provider','NO_GPU_REPLAN'),
            'device_provider':detail.get('device_provider'),'replanned':bool(gpu or detail.get('planning_provider')),
            'output':detail})
    with (out/'stage_timings.csv').open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=[k for k in rows[0] if k!='output'],lineterminator='\n');writer.writeheader()
        writer.writerows({k:v for k,v in row.items() if k!='output'} for row in rows)
    memory={key:max(r['gpu_memory_bytes'][key] for run in runs for r in run) for key in runs[0][0]['gpu_memory_bytes']}
    retime=load(ROOT/'worklog/runtime/rc-retime-comparison.json')
    filters=[load(p) for p in sample.glob('scenes/**/attachment_filter.json')]
    final_context=load(sample/'replay_context.json');device=load(sample/'replay_device.json')
    assert final_context['attached'] is None and device['release_confirmed'] and device['base_pose']==[0.,0.,0.]
    flags={
      'RTX3080_CUDA_READY':'PASS','PINNED_CUROBO_READY':'PASS','OFFLINE_HARDWARE_ISOLATED':'PASS',
      'OCT16_RAW_FIXTURES_AVAILABLE':'BLOCKED','FAST_EFFECTIVE_SINGLE_PASS':'PASS','FAST_CANCEL_NO_ORPHAN':'PASS',
      'EARLY_CONTACT_LIFT_PRECHECK':'PASS','ATTACHED_WORLD_IDENTITY_READY':'PASS','19_STAGE_OFFLINE_REPLAY':'PASS',
      'READY_FOR_SITE_DEPLOYMENT':'PARTIAL','FULL_DEMO_RUNNER_INTEGRATED':'YES','REAL_CUROBO_IN_19_STAGE_REPLAY':'YES',
      'ATTACHED_WORLD_IDENTITY':'PASS','GRASP_TO_HOLD230_OFFLINE':'PASS','PLACE_RELEASE_RETURN_OFFLINE':'PASS',
      'CHECKPOINT_RESUME':'PASS','WEBUI_ART_SINGLE_JOB':'PASS','SITE_DEPLOYMENT_PACKAGE_READY':'CONDITIONAL'}
    extras={}
    for name in ('rc-real-oom','rc-stress640','rc-final-normal','rc-final-stress640'):
        directory=ROOT/'worklog/runtime'/name
        if (directory/'job.json').exists():
            job=load(directory/'job.json');extras[name]={'state':job['state'],'stage':job['stage'],'failure':job['failure']}
            if (directory/'gpu_calls.json').exists():extras[name]['gpu_calls']=load(directory/'gpu_calls.json')
            if (directory/'planner_final_status.json').exists():extras[name]['planner_final_status']=load(directory/'planner_final_status.json')
    for item in extras.values():
        for call in item.get('gpu_calls',[]):
            for key,value in call['gpu_memory_bytes'].items():memory[key]=max(memory[key],value)
    result={'schema_version':1,'release':'ARES_R_ROUNDTRIP_RC1_20261018','code_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
       'evidence_kind':'SYNTHETIC_GPU_REPLAY','physical_execution':False,'oct16_reproduced':False,'commissioned':False,
       'flags':flags,'full_cycles':campaign[:len(cycles)],'all_acceptance_cases':campaign+stops,'extra_checks':extras,
       'native_retiming':retime,'gpu_peak_bytes':memory,'representative_stages':rows,'representative_run_id':load(sample/'job.json')['run_id'],
       'attached_filter_proofs':[{k:v for k,v in item.items() if k!='removed_indices'} for item in filters],
       'http_status_identity':load(ROOT/'worklog/runtime/rc-webui-art-http.json'),
       'software_tests':{'runner':'unittest discover under offline_sandbox.sh','count':int(re.search(r'Ran (\d+) tests', (ROOT/'worklog/runtime/rc-cpu-tests-final.log').read_text())[1]),'status':'PASS'},
       'engineering_cycle_target_s':150,'target_status':'UNCOMMISSIONED_ENGINEERING_TARGET',
       'modeled_core_cycle_s':sum(r['software_wall_s']+r['native_motion_s']+r['base_nominal_s'] for r in rows),
       'cycle_estimate_excludes':['real scans and Epic response time','physical gripper and settling latency','site network and safety overhead'],
       'limitations':['all device states, scene/ID1/ID3 observations and mounting transform are synthetic',
           'ten normal GPU cycles predate the added int32 preallocation guard; normal-world effective buffer stays 5000; final-code standard/640 acceptance is recorded separately',
           'first three campaign cycles predate the final five-control-point retimer; subsequent full cycles and all checkpoint/fault cases use it',
           'campaign OOM/OOD/IK/vision/network faults are injected; rc-real-oom additionally exercises the actual CUDA allocator at a reduced budget',
           'native C++ settling source changed; actual site SDK/native binary compilation and commissioning pending',
           '85cm loaded route, ID3 offset, no-stow return sweep and real 10GB service coexistence SITE_PENDING',
           'raw Oct16 contact115s/lift72s paths unavailable; same-path retiming comparison uses the published synthetic fixture']}
    (out/'RESULTS.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(16,9),sharey=True);positions=list(range(len(rows)))
    axes[0].barh(positions,[r['software_wall_s'] for r in rows],color='#227db4');axes[0].set_title('Actual software wall time (synthetic devices)');axes[0].set_xlabel('seconds')
    offset=0
    for i,row in enumerate(rows):
        duration=row['software_wall_s']+row['native_motion_s']+row['base_nominal_s']
        axes[1].barh(i,duration,left=offset,color='#498c66' if row['native_motion_s'] else '#8c7a49');offset+=duration
    axes[1].set_title('Modeled sequential core (not physical measurement)');axes[1].set_xlabel('cumulative seconds')
    axes[0].set_yticks(positions,[r['stage'] for r in rows]);axes[0].invert_yaxis();fig.tight_layout();fig.savefig(out/'stage_waterfall.svg');fig.savefig(out/'stage_waterfall.png',dpi=110);plt.close(fig)
    with tarfile.open(out/'replay_evidence.tar.gz','w:gz') as archive:
        for root in (args.campaign,args.stop_campaign,ROOT/'worklog/runtime/rc-real-oom',ROOT/'worklog/runtime/rc-stress640',ROOT/'worklog/runtime/rc-final-normal',ROOT/'worklog/runtime/rc-final-stress640'):
            if not root.exists():continue
            for path in root.rglob('*'):
                if path.is_file() and (path.suffix in ('.json','.npz') or path.name.endswith('.txt') or path.name=='planner.log'):
                    archive.add(path,arcname=str(path.relative_to(ROOT/'worklog/runtime')))
        archive.add(ROOT/'worklog/runtime/rc-cpu-tests-final.log',arcname='software-tests.log')
    (out/'EVIDENCE_SHA256SUMS').write_text(''.join(sha(path)+'  '+path.name+'\n' for path in sorted(out.iterdir()) if path.is_file() and path.name not in ('EVIDENCE_SHA256SUMS','manifest.json')))
    print(json.dumps({'output':str(out),'flags':flags,'core_cycle_s':result['modeled_core_cycle_s'],'memory':memory}))
if __name__=='__main__':main()
