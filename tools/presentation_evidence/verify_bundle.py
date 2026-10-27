"""Fail on broken evidence hashes, unequal safety controls or missing panels."""
import argparse,json,hashlib
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();o=a.output
for line in (o/'SHA256SUMS').read_text().splitlines():
 expected,path=line.split('  ',1);assert hashlib.sha256((o/path).read_bytes()).hexdigest()==expected,path
m=json.loads((o/'runlogs/rasc_stage_metrics.json').read_text());assert m['old_point_coverage']==m['new_point_coverage']==m['clean_points'];assert len(m['warm_ms'])==5
g=json.loads((o/'runlogs/compare_planning.json').read_text());assert len(g['rows'])==2;assert len({r['safety_constraints_digest'] for r in g['rows']})==1
for r in g['rows']:
 assert r['result']=='SUCCESS' and r['independent_validation']['collision_free'];assert r['effective_config']['solve_calls']==1;assert r['independent_validation']['self_collision_independently_checked'] is False
manifest=json.loads((o/'ASSET_MANIFEST.json').read_text());assert len({x['path'] for x in manifest['assets']})==len(manifest['assets']);assert len(list((o/'panels/rasc6').glob('*.png')))==18
for entry in manifest['assets']:assert hashlib.sha256((o/entry['path']).read_bytes()).hexdigest()==entry['sha256'],entry['path']
assert all(s['completion'].startswith('ABORTED') for s in json.loads((o/'runlogs/servo_trace_metrics.json').read_text()))
assert not json.loads((o/'runlogs/ui_browser_qa.json').read_text())['errors']
print('BUNDLE_HASHES_COUNTS_SAFETY_NEGATIVE_RESULT_LABELS_PASS')
