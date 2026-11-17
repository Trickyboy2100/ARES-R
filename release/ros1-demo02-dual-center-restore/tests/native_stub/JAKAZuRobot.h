#pragma once
#include <string>
#include <cstdlib>
using BOOL=bool;
constexpr int ABS=0;
struct JointValue{double jVal[6]{};};
struct CartesianPose{struct{double x=0,y=0,z=0;}tran;struct{double rx=0,ry=0,rz=0;}rpy;};
struct RobotStatus{};
struct RobotStatus_simple{int errcode=0,powered_on=1,enabled=1;};
struct MotionStatus{bool isInEstop=false,isInCollision=false,isOnLimit=false,inpos=true,paused=true;int queue=0,active_queue=0;};
class JAKAZuRobot{
 std::string ip;JointValue actual{};bool servo=false;
 public:
 int login_in(const char* value,bool){ip=value;return 0;}
 int login_out(){return 0;}
 int get_robot_status(RobotStatus*){return 0;}
 int get_robot_status_simple(RobotStatus_simple*){return 0;}
 int get_motion_status(MotionStatus*){return 0;}
 int get_actual_joint_position(JointValue* q){*q=actual;return 0;}
 int get_actual_tcp_position(CartesianPose*){return 0;}
 int get_tool_id(int* id){*id=ip=="192.168.99.100"?2:3;return 0;}
 int get_user_frame_id(int* id){*id=0;return 0;}
 int is_in_drag_mode(BOOL* value){*value=false;return 0;}
 int get_tool_data(int,CartesianPose*){return 0;}
 int is_in_servomove(BOOL* value){*value=servo;return 0;}
 int servo_move_enable(bool value){servo=value;return 0;}
 int motion_abort(){return 0;}
 int servo_j(const JointValue* q,int,int){if(std::getenv("DEMO02_FAIL_LEFT") && ip=="192.168.99.100")return 17;actual=*q;return 0;}
};
