#!/usr/bin/env bash
# Compile only; does not connect to any controller.
set -euo pipefail
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
sdk_include="/home/yikun/ws/SDK v2.2.2/04 Linux/c&c++/inc_of_c++"
sdk_library="/home/yikun/JAKA/lib"
demo_output="/home/yikun/ares-r-curobo-assets/jaka_right_demo"
test -f "$sdk_include/JAKAZuRobot.h"
test -f "$sdk_library/libjakaAPI.so"
test -d /home/yikun/ares-r-curobo-assets
exec 9>>/tmp/ares-r-right-servo.lock
flock -n 9 || { echo "Right native bridge occupied; build blocked." >&2; exit 2; }
g++ -std=c++11 -O2 "$repo_dir/scripts/jaka_right_demo.cpp" -I"$sdk_include" \
  -L"$sdk_library" -Wl,--disable-new-dtags,-rpath,"$sdk_library" -Wl,-z,now -ljakaAPI -pthread -o "$demo_output"
# Resolve symbols without opening a controller connection (invalid mode exits 2).
set +e
LD_LIBRARY_PATH="$sdk_library" LD_PRELOAD= LD_AUDIT= LD_BIND_NOW=1 "$demo_output" invalid
loader_result=$?
set -e
test "$loader_result" -eq 2
echo "Built right-only SDK222 demo (no robot connection): $demo_output"
