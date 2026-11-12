#!/usr/bin/env python3
"""Import-only ABI check; explicitly denies physical I/O in this process."""
import inspect,os
from pathlib import Path
os.environ['ARES_R_OFFLINE_REPLAY']='1'
from blocks.canonical import load_pinned,bind_hold_tool
site=Path(__file__).resolve().parents[1]/'site-source-20261112'
runner=load_pinned(site,'scripts/run_sift_lift_hold.py')
helper=load_pinned(site,'scripts/run_task_pick_reset_timing.py')
print('Original arrival ABI:',inspect.signature(helper.settle_segment))
bind_hold_tool(runner,helper.settle_segment,3)
print('Scoped adapter ABI:',inspect.signature(runner.settle_segment))
place=load_pinned(site,'scripts/run_dmp_place_demo.py')
assert callable(place.stage_place) and callable(place.stage_center)
print('PINNED_CANONICAL_IMPORT_AND_ABI_PASS; no main/Live/SDK invoked')
