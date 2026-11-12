"""Explain existing 5cm filtering using frozen primitive and point connectivity."""
import json,time
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
R=Path('/home/yikun/ARES-R-RC1-20261019')
S=R/'worklog/evidence/scene-aware-motion/scene_20261019T105247Z_e546b192/scene'
O=R/'worklog/evidence/20261019-v17-micro-component-audit';O.mkdir(exist_ok=False)
report=json.loads((S/'support_decomposition.json').read_text());p=report['primitives']
points=np.load(S/'clean_residual.npz')['points_body_m']
idx=[i for i,x in enumerate(p) if x.get('semantic')!='SUPPORT_SURFACE'];members={};trees={}
for i in idx:
    low,hi=np.asarray(p[i]['observed_bounds_m']);q=points[np.all((points>=low-1e-9)&(points<=hi+1e-9),axis=1)]
    members[i]=q
    if len(q):trees[i]=cKDTree(q)
def gap(i,j):
    low,hi=np.asarray(p[i]['observed_bounds_m']);a,b=np.asarray(p[j]['observed_bounds_m'])
    return float(np.linalg.norm(np.maximum(np.maximum(low-b,a-hi),0)))
edges=[]
for k,i in enumerate(idx):
    for j in idx[k+1:]:
        d=gap(i,j)
        if d>.02:continue
        observed=float(np.min(trees[i].query(members[j])[0])) if i in trees and len(members[j]) else None
        edges.append((i,j,d,observed))
def groups(point_level):
    parent={i:i for i in idx}
    def root(i):
        while i!=parent[i]:parent[i]=parent[parent[i]];i=parent[i]
        return i
    for i,j,d,q in edges:
        if not point_level or q is None or q<=.02:parent[root(i)]=root(j)
    groups={}
    for i in idx:groups.setdefault(root(i),[]).append(i)
    rows=[]
    for group in groups.values():
        lo=np.min([p[i]['observed_bounds_m'][0] for i in group],axis=0);hi=np.max([p[i]['observed_bounds_m'][1] for i in group],axis=0)
        ids=[p[i]['primitive_id'] for i in group];dims=hi-lo
        rows.append({'primitive_ids':ids,'count':len(group),'aggregate_dims_m':dims.tolist(),'below_5cm':bool(dims.max()<.05),
          'point_count_sum':sum(p[i]['point_count'] for i in group),'contains_limiting_pair':any(x.endswith(('occupied_002','occupied_003')) for x in ids)})
    return rows
old=groups(False);new=groups(True)
data={'physical_motion':False,'configured_max_extent_m':.05,'configured_connection_gap_m':.02,
 'source_scene':str(S),'existing_filter':report.get('isolated_micro_filter'),
 'aabb_groups_for_limiting_pair':[x for x in old if x['contains_limiting_pair']],
 'point_groups_for_limiting_pair':[x for x in new if x['contains_limiting_pair']],
 'false_aabb_edges':[{'a':p[i]['primitive_id'],'b':p[j]['primitive_id'],'aabb_gap_m':d,'point_gap_m':q}
    for i,j,d,q in edges if q is not None and q>.02],
 'candidate_removed_groups':[x for x in new if x['below_5cm']]}
(O/'REPORT.json').write_text(json.dumps(data,indent=2));print(json.dumps({k:v for k,v in data.items() if k not in ('existing_filter','false_aabb_edges','candidate_removed_groups')})[:7000],flush=True)
print(json.dumps({'false_aabb_edges':len(data['false_aabb_edges']),'candidate_removed_groups':len(data['candidate_removed_groups'])}),flush=True)
