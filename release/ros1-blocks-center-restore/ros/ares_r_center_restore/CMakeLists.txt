cmake_minimum_required(VERSION 3.0.2)
project(ares_r_center_restore)
find_package(catkin REQUIRED COMPONENTS rospy actionlib actionlib_msgs message_generation)
add_action_files(FILES CenterRestore.action)
generate_messages(DEPENDENCIES actionlib_msgs)
catkin_package(CATKIN_DEPENDS rospy actionlib actionlib_msgs message_runtime)
catkin_install_python(PROGRAMS scripts/center_restore_node.py scripts/center_restore_client.py DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION})

install(DIRECTORY launch DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION})
