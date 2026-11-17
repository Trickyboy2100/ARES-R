// Contract-test SDK substitute. No network or real hardware APIs.
#pragma once
#include <cstdlib>
#include <fstream>
#include <string>

using BOOL = bool;
constexpr int ABS = 0;
struct JointValue { double jVal[6]{}; };
struct CartesianPose {
    struct { double x=0, y=0, z=0; } tran;
    struct { double rx=0, ry=0, rz=0; } rpy;
};
struct RobotStatus {};
struct RobotStatus_simple { int errcode=0; bool powered_on=true, enabled=true; };
struct MotionStatus { bool isInEstop=false, isInCollision=false, isOnLimit=false; };

class JAKAZuRobot {
    JointValue actual{};
    std::string ip;
public:
    int login_in(const char* address, bool) { ip=address; return 0; }
    int login_out() { return 0; }
    int get_robot_status(RobotStatus*) { return 0; }
    int get_robot_status_simple(RobotStatus_simple*) { return 0; }
    int get_motion_status(MotionStatus*) { return 0; }
    int is_in_drag_mode(BOOL* value) { *value=false; return 0; }
    int get_actual_joint_position(JointValue* value) { *value=actual; return 0; }
    int get_actual_tcp_position(CartesianPose*) { return 0; }
    int get_tool_id(int* value) { *value=ip=="192.168.99.100" ? 2 : 3; return 0; }
    int get_tool_data(int, CartesianPose*) { return 0; }
    int joint_move(const JointValue* goal, int, bool, double) {
        if (const char* path=std::getenv("ARES_MIRROR_TEST_CALLS")) std::ofstream(path,std::ios::app)<<"MOVEJ\n";
        actual=*goal;
        return 0;
    }
    int motion_abort() { return 0; }
    int is_in_pos(BOOL* value) { *value=true; return 0; }
};
