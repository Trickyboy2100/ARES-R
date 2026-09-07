#pragma once
#include <cstdlib>
#include <fstream>
using BOOL=bool;
enum MoveMode {ABS=0,INCR=1};
struct JointValue{double jVal[6];};
struct CartesianTran{double x,y,z;};
struct Rpy{double rx,ry,rz;};
struct CartesianPose{CartesianTran tran;Rpy rpy;};
struct RobotStatus_simple{int errcode=0,powered_on=1,enabled=1;};
struct MotionStatus{bool isInEstop=false,isInCollision=false,isOnLimit=false,inpos=true,paused=true;int queue=0,active_queue=0;};
class JAKAZuRobot{
    JointValue q{};bool servo=false;int sends=0;
    void trace(const char*s){if(const char*p=std::getenv("FAKE_TRACE")){std::ofstream f(p,std::ios::app);f<<s<<"\n";}}
public:
    int login_in(const char*ip,bool){trace(ip);return 0;}
    int login_out(){trace("logout");return 0;}
    int get_robot_status_simple(RobotStatus_simple*s){*s=RobotStatus_simple();return 0;}
    int get_motion_status(MotionStatus*s){*s=MotionStatus();if(std::getenv("FAKE_BUSY"))s->queue=1;return 0;}
    int get_actual_joint_position(JointValue*v){*v=q;if(sends&&std::getenv("FAKE_TRACKING_ERROR"))v->jVal[5]+=.01;return 0;}
    int get_actual_tcp_position(CartesianPose*p){*p=CartesianPose();return 0;}
    int get_tool_id(int*p){*p=2;return 0;}
    int get_user_frame_id(int*p){*p=0;return 0;}
    int is_in_drag_mode(BOOL*p){*p=false;return 0;}
    int get_tool_data(int,CartesianPose*p){*p=CartesianPose();return 0;}
    int is_in_servomove(BOOL*p){*p=servo;return 0;}
    int servo_move_enable(BOOL value){servo=value;trace(value?"servo_on":"servo_off");return 0;}
    int servo_j(const JointValue*v,MoveMode mode,unsigned int step){
        trace("servo_j");++sends;if(mode!=ABS||step!=10)return -99;
        if(std::getenv("FAKE_SERVO_FAIL"))return -3;q=*v;return 0;
    }
    int motion_abort(){trace("abort");return 0;}
};
