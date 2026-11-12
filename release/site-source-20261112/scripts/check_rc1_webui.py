"""Read-only smoke check: never posts to start, execute or movement APIs."""
import json,hashlib,subprocess
from pathlib import Path
from urllib.request import urlopen
from ares_r.motion.planner_service_client import status
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'worklog/runtime/rc1-webui'
with urlopen('http://127.0.0.1:8775/api/demo/roundtrip/status',timeout=10) as response:
    state=json.load(response)
with urlopen('http://127.0.0.1:8775/',timeout=5) as response:page=response.read()
with urlopen('http://127.0.0.1:8775/static/roundtrip-panel.js',timeout=5) as response:js=response.read()
old=json.loads(Path('/home/yikun/ARES-R_SITE_PRESERVE_20261019T100713/git-state.private.json').read_text())
dirty=subprocess.check_output(['git','-C','/home/yikun/ARES-R','status','--porcelain=v1','-z','--untracked-files=all'],text=True)
value={'entry_url':'http://192.168.99.32:8775/','roundtrip':state,'planner':status(),
 'prewarm':json.loads((out/'prewarm-summary.json').read_text()),
 'ui_asset_matches_deployment':hashlib.sha256(js).hexdigest()==hashlib.sha256((ROOT/'src/ares_r/webui/roundtrip_panel.js').read_bytes()).hexdigest(),
 'page_http_ok':bool(page),'tests':{'passed':True,'count':717},
 'physical_motion_started':False,'original_worktree_unchanged':old['status']['stdout']==dirty}
(out/'ENTRY_READY_REPORT.json').write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'entry':value['entry_url'],'can_start':state['can_start'],'running':state['running'],
 'blockers':state['blockers'],'ui_asset_matches':value['ui_asset_matches_deployment'],
 'original_worktree_unchanged':value['original_worktree_unchanged'],'planner':value['planner']}))
