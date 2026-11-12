#!/usr/bin/env python3
"""Create the tracked Mini2 site file only when an older clone lacks it."""

import shutil
from pathlib import Path

root = Path(__file__).resolve().parent.parent
source = root / "config" / "jaka_mini2_motion.site.example.json"
target = root / "config" / "jaka_mini2_motion.site.json"
if target.exists():
    print("site config already present; left unchanged: %s" % target)
    raise SystemExit(0)
shutil.copy2(source, target)
print("created %s" % target)
print("Fill Mini2 limits from both JAKA controllers/APP; keep commissioning_confirmed=false until reviewed.")
print("This safety configuration is intended for review and Git tracking; never add credentials or secrets.")
