"""No hardware I/O: verify custody, source identity, configs and pinned assets."""
from pathlib import Path
import hashlib,json,subprocess,shutil,time
ROOT=Path('/home/yikun/ARES-R-RC1-20261019')
SITE=Path('/home/yikun/ARES-R')
BACKUP=Path('/home/yikun/ARES-R_SITE_PRESERVE_20261019T100713')
OUT=ROOT/'worklog/runtime/site-integration'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def blob(p):
    b=p.read_bytes();return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def save(name,v):(OUT/name).write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
tree=json.loads((BACKUP/'RC1_RUNTIME_TREE.json').read_text())
bad=[v['path'] for v in tree if not (ROOT/v['path']).is_file() or blob(ROOT/v['path'])!=v['sha']]
intentional=['scripts/jaka_right_demo.cpp','tests/fixtures/jaka_fake/JAKAZuRobot.h','tests/test_native_demo.py']
save('runtime-integrity.json',{'upstream_commit':'2619cb4bb6156d9146820d2f1e28df6fa81a0c2a','scope':'runtime subset, not full Git checkout','files':len(tree),'differences':bad,'intentional_site_compatibility_patch':intentional,'unexpected_differences':[x for x in bad if x not in intentional]})
configs=[]
private=OUT/'site-config-snapshot';private.mkdir(exist_ok=True)
for p in sorted((SITE/'config').rglob('*')):
    if not p.is_file() or p.suffix not in ('.json','.yaml','.yml'):continue
    rel=p.relative_to(SITE);dest=private/rel.relative_to('config');dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(p,dest)
    configs.append({'path':str(rel),'site_sha256':sha(p),'rc1_sha256':sha(ROOT/rel) if (ROOT/rel).is_file() else None,'site_snapshot':str(dest)})
save('config-comparison.private.json',configs)
source=Path('/home/yikun/ares-r-curobo-assets/source-8e734f3')
m=json.loads((source/'ARES_R_SOURCE_MANIFEST.json').read_text())
bad=[v['path'] for v in m['files'] if not (source/v['path']).exists() or blob(source/v['path'])!=v['sha']]
save('curobo-source-integrity.json',{'commit':m['commit'],'files':len(m['files']),'bad':bad})
save('sdk-native-integrity.json',{str(p):sha(p) for p in [ROOT/'scripts/jaka_right_demo.cpp',ROOT/'native/jaka_right_rc1',Path('/home/yikun/JAKA/lib/libjakaAPI.so'),Path('/home/yikun/JAKA/libjakaAPI.so'),Path('/home/yikun/JAKA/jkrc.so')]})
git=lambda *a:subprocess.check_output(['git','-C',str(SITE),*a],text=True)
before=json.loads((BACKUP/'git-state.private.json').read_text())
custody={'head_unchanged':before['head']['stdout'].strip()==git('rev-parse','HEAD').strip(),'dirty_status_unchanged':before['status']['stdout']==git('status','--porcelain=v1','-z','--untracked-files=all')}
save('custody-final-validation.json',custody)
save('site-final-state.private.json',{'head':git('rev-parse','HEAD').strip(),'status':git('status','--porcelain=v1','--untracked-files=all'),'golden':{p:sha(SITE/p) for p in ['scripts/run_first_pick_demo.py','demos/right_arm_epic_pick_lift_v1/demo.json']},'services':subprocess.check_output(['systemctl','--user','is-active','ares-r-backend.service','ares-r-webui.service'],text=True),'physical_motion_attempted':False})
save('provenance.json',{'upstream_rc1_commit':'2619cb4bb6156d9146820d2f1e28df6fa81a0c2a','site_original_head':git('rev-parse','HEAD').strip(),'backup':str(BACKUP),'created_at_unix':time.time(),'original_services_switched':False,'physical_motion_attempted':False,'deployment_scope':'runtime source + fixture subset; no complete RC visual/media archive','python_environment':'isolated .venv; original cuRobo package read-only; added einops 0.8.1'})
print(json.dumps({'runtime_unexpected_differences':len(json.loads((OUT/'runtime-integrity.json').read_text())['unexpected_differences']),'pinned_curobo_bad':len(bad),'config_files':len(configs),'custody':custody,'output':str(OUT)}))
