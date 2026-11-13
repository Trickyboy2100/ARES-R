#!/usr/bin/env python3
"""Build the catkin interface/client deliverable from the canonical definitions."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parent

def build(output):
    package=ROOT/'ros/ares_r_manipulation_blocks'
    files={}
    for pattern in ('action/*.action','srv/*.srv'):
        for path in package.glob(pattern):
            files[str(path.relative_to(package))]=path.read_bytes()
    files['scripts/run_block_client.py']=(package/'scripts/run_block_client.py').read_bytes()
    files['package.xml']=(package/'package.xml').read_bytes()
    cmake=(package/'CMakeLists.txt').read_text()
    cmake=cmake.replace('scripts/run_block_node.py scripts/block_catalog_node.py ','')
    files['CMakeLists.txt']=cmake.encode()
    files['README.md']='''# ARES-R ROS1 取放接口

Action 为 `/ares_r/run_block`，类型为 `ares_r_manipulation_blocks/RunBlockAction`。
ROS Master 使用现场已配置的 `http://192.168.99.32:11321`。

放入 catkin 工作空间的 src 后执行 `catkin_make`，source 对应 devel/setup.bash。

- `/ares_r/blocks/list` 查询功能编号、当前参数版本和发布状态。
- Goal 填写 request_id、block_id、expected_profile_revision 和两项现场确认。
- ScanPlace 额外填写 ScanPick 返回的 payload_session_id。
- 同一请求重发保持相同 request_id。取消使用 Action cancel。
- Result.success=true 且终态匹配业务完成条件，才表示任务完成。

客户端命令如下，功能编号与版本取自查询结果。

```bash
rosrun ares_r_manipulation_blocks run_block_client.py \\
  --block 功能编号 --revision 当前版本 --request-id 唯一请求编号 \\
  --execute --onsite-observer-confirmed --prepared-environment-confirmed
```

ScanPlace 增加 `--payload-session 持物会话编号`。Ctrl+C 提交取消并等待结果。

运行需要机器人主机已发布对应功能块。当前新取放功能尚待现场验收；原 Demo01 使用原 CenterRestore 接口。
'''.encode()
    rows=json.loads((ROOT/'block_registry.json').read_text())['blocks']
    files['BLOCKS.json']=(json.dumps([{k:r.get(k) for k in
        ('id','block_id','display_name','acceptance','physical_start_enabled','profile_revision')}
        for r in rows],ensure_ascii=False,indent=2)+'\n').encode()
    hashes={name:hashlib.sha256(value).hexdigest() for name,value in files.items()}
    files['MANIFEST.json']=(json.dumps(dict(schema_version=1,package='ares_r_manipulation_blocks',
        runblock_action_md5='7b4edfbf807f9526b57393193f680fd1',new_physical_blocks_accepted=0,
        sha256=hashes),indent=2)+'\n').encode()
    output=Path(output)
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED) as archive:
        for name,value in sorted(files.items()):
            info=zipfile.ZipInfo('ares_r_manipulation_blocks/'+name)
            info.external_attr=(0o100755 if name.endswith('.py') else 0o100644)<<16
            info.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(info,value)
    return dict(path=str(output),files=len(files),bytes=output.stat().st_size,
                sha256=hashlib.sha256(output.read_bytes()).hexdigest())

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True)
    print(json.dumps(build(parser.parse_args().output)))
