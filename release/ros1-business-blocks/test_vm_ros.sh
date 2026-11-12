#!/bin/bash
set -eo pipefail
cd "$(dirname "$0")/../.."
source ws/devel/setup.bash
set -u
export ROS_MASTER_URI=http://127.0.0.1:12321 ROS_IP=127.0.0.1
roscore -p 12321 >/tmp/ares-offline-roscore.log 2>&1 &
ros_pid=$!
trap 'kill "$ros_pid" 2>/dev/null || true' EXIT
sleep 2
python3 release/ros1-business-blocks/ros_action_transport.py
python3 release/ros1-business-blocks/ros_session_transport.py
