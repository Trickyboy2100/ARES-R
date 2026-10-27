#!/usr/bin/env python3
"""Check bundle provenance, hashes, local links and quantitative invariants."""
import argparse, re
from pathlib import Path
from replay_rasc import load, sha

def main():
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args();out=a.output
    m=load(out/'runlogs/rasc_stage_metrics.json');assert m['station']=='GRASP'
    assert m['source_camera_sha256']=='62d45bd32a882bb6e8d3e080cc7b0edb239cdad8fab14d28c1dc69926d4f42a6'
    assert m['body_recomputed_bit_exact'] and m['owned_filter_revision_exact']
    assert m['old_point_coverage']==m['new_point_coverage']==m['clean_points']==8100
    gpu=load(out/'runlogs/grasp_gpu_replay.json');assert gpu['observed_result']=='SUCCESS' and gpu['supervisor_reply']['ok']
    assert gpu['independent_dense_validation']['collision_free'] and gpu['original_scene_unchanged']
    ab=load(out/'runlogs/compare_planning.json');assert len({r['safety_constraints_digest'] for r in ab['rows']})==1
    assert all(r['result']=='BLOCKED_ENDPOINT_COLLISION' and not r['gpu_attempted'] for r in ab['rows'])
    manifest=load(out/'MANIFEST.json');assert len(manifest['source_archives'])==2
    for file in manifest['files']:assert sha(out/file['path'])==file['sha256'],file['path']
    for line in (out/'SHA256SUMS').read_text().splitlines():
        digest,name=line.split('  ',1);assert sha(out/name)==digest,name
    html=(out/'index.html').read_text();assert '__PAYLOAD__' not in html
    for link in re.findall(r'(?:src|href)="([^"]+)"',html):
        assert not link.startswith(('http:','https:','//')),link
        assert (out/link).is_file(),link
    assert load(out/'browser_qa.json')['result']=='PASS'
    isolation=load(out/'runlogs/isolation.json');assert isolation['result']=='PASS' and isolation['gpu_devices']==['nvidia0']
    assert len(list((out/'panels/rasc6').glob('*.png')))==24
    from PIL import Image
    for file in out.rglob('*.png'):
        with Image.open(file) as im:im.verify()
    print('PASS: provenance, point coverage, actual GPU result, strict A/B rejection, hashes, links, 24 stage panels, PNG integrity, browser and isolation')

if __name__=='__main__':main()
