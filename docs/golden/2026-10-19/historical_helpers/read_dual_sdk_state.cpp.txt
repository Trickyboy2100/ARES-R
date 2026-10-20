// Bounded read-only site probe. No power, enable, abort, servo or write APIs.
#include "JAKAZuRobot.h"
#include <chrono>
#include <thread>
#include <iostream>
#include <iomanip>
int main() {
  for (auto ip : {"192.168.99.100", "192.168.99.101"}) {
    JAKAZuRobot robot;
    int rc=robot.login_in(ip,false);
    std::cout << "HOST " << ip << " login=" << rc << std::endl;
    if(rc) continue;
    char version[1024]={};
    std::cout << "sdk_rc=" << robot.get_sdk_version(version) << " version=" << version << std::endl;
    for(int i=0;i<5;++i) {
      std::this_thread::sleep_for(std::chrono::milliseconds(250));
      RobotStatus full{}; RobotStatus_simple simple{}; MotionStatus motion{};
      JointValue joints{}; CartesianPose tcp{},tool{}; int tool_id=-1,user_id=-1;
      int a=robot.get_robot_status(&full),b=robot.get_robot_status_simple(&simple);
      int c=robot.get_motion_status(&motion),d=robot.get_actual_joint_position(&joints);
      int e=robot.get_actual_tcp_position(&tcp),f=robot.get_tool_id(&tool_id);
      int g=robot.get_user_frame_id(&user_id),h=robot.get_tool_data(tool_id,&tool);
      std::cout << std::setprecision(16) << "sample=" << i << " rc=" << a << ',' << b << ',' << c << ',' << d << ',' << e << ',' << f << ',' << g << ',' << h
        << " full_error=" << full.errcode << " simple_error=" << simple.errcode << " errmsg=" << simple.errmsg
        << " power=" << full.powered_on << " enabled=" << full.enabled << " estop=" << motion.isInEstop
        << " collision=" << motion.isInCollision << " limit=" << motion.isOnLimit << " inpos=" << motion.inpos
        << " queue=" << motion.queue << " active_queue=" << motion.active_queue << " tool_id=" << tool_id << " user_id=" << user_id << " joints=";
      for(double q:joints.jVal) std::cout << q << ',';
      std::cout << " tcp=" << tcp.tran.x << ',' << tcp.tran.y << ',' << tcp.tran.z << ',' << tcp.rpy.rx << ',' << tcp.rpy.ry << ',' << tcp.rpy.rz
        << " tool=" << tool.tran.x << ',' << tool.tran.y << ',' << tool.tran.z << ',' << tool.rpy.rx << ',' << tool.rpy.ry << ',' << tool.rpy.rz << std::endl;
    }
    std::cout << "logout=" << robot.login_out() << std::endl;
  }
}
