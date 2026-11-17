#!/bin/bash
set -e
source /opt/ros/noetic/setup.bash
source /home/yikun/ARES-R-ROS-BLOCK01-20261112/catkin_ws/devel/setup.bash
export ROS_MASTER_URI=http://192.168.99.32:11321
export ROS_IP=192.168.99.32
source /home/yikun/anaconda3/etc/profile.d/conda.sh
conda activate dope3.8
# roslaunch owns its master and node and propagates process exit to systemd.
exec roslaunch -p 11321 ares_r_center_restore center_restore.launch
