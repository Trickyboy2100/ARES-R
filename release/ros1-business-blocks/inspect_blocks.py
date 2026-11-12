#!/usr/bin/env python3
import argparse, json
from pathlib import Path
from blocks.contracts import registry, prepare
p=argparse.ArgumentParser(description='Offline registry / parameter hash check. No robot connection.')
p.add_argument('--block');p.add_argument('--revision');p.add_argument('--return-center',action='store_true')
a=p.parse_args()
print(json.dumps(prepare(a.block,a.revision,Path(__file__).resolve().parents[2],return_center=a.return_center)
                 if a.block else registry(),ensure_ascii=False,indent=2))
