#!/bin/bash
set -eo pipefail
cd "$(dirname "$0")/../.."
source "${ARES_OFFLINE_ROS_WORKSPACE:-ws}/devel/setup.bash"
set -u
test_port=${ARES_OFFLINE_ROS_PORT:-12321}
export ROS_MASTER_URI=http://127.0.0.1:$test_port ROS_IP=127.0.0.1
python3 -c 'import socket,sys; s=socket.socket(); s.bind(("127.0.0.1",int(sys.argv[1]))); s.close()' "$test_port"
roscore -p "$test_port" >/tmp/ares-offline-roscore.log 2>&1 &
ros_pid=$!
trap 'kill "$ros_pid" 2>/dev/null || true' EXIT
sleep 2
python3 release/ros1-business-blocks/ros_action_transport.py
python3 release/ros1-business-blocks/ros_session_transport.py
python3 release/ros1-business-blocks/ros_catalog_transport.py
python3 release/ros1-business-blocks/ros_canonical_transport.py
