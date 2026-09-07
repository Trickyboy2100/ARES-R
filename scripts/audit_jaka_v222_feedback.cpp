// SDK V2.2.2 public C++ API, right-only READ-ONLY audit.
// No power, enable, servo, motion, configuration-write or automatic retry API.
#include "JAKAZuRobot.h"
#include <chrono>
#include <cmath>
#include <csignal>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <thread>

static volatile std::sig_atomic_t interrupted = 0;
static void on_signal(int) { interrupted = 1; }
static void checked(int rc, const char* name) {
    if (rc != 0) throw std::runtime_error(std::string(name)+" code="+std::to_string(rc));
}

int main(int argc,char** argv) {
    int seconds=30;
    try {
        if (argc>2) throw std::runtime_error("usage: audit [5..600 seconds]");
        if (argc==2) seconds=std::stoi(argv[1]);
        if (seconds<5 || seconds>600) throw std::runtime_error("duration outside 5..600");
    } catch (const std::exception& e) { std::cerr<<e.what()<<std::endl; return 2; }
    std::signal(SIGINT,on_signal); std::signal(SIGTERM,on_signal);
    JAKAZuRobot robot;
    bool logged=false;
    int exit_code=1;
    try {
        checked(robot.login_in("192.168.99.101",false),"login");
        logged=true;
        char version[1024]={0};
        checked(robot.get_sdk_version(version),"version");
        std::cout<<"SDK "<<version<<std::endl;
        std::this_thread::sleep_for(std::chrono::milliseconds(200));
        // Prime the public status/RPC paths before timing the steady-state loop.
        RobotStatus initial_status{};
        JointValue initial_actual{},initial_reported{};
        checked(robot.get_robot_status(&initial_status),"warm status");
        checked(robot.get_actual_joint_position(&initial_actual),"warm actual");
        checked(robot.get_joint_position(&initial_reported),"warm reported");
        using Clock=std::chrono::steady_clock;
        auto start=Clock::now(),deadline=start;
        double max_read_s=0;
        int tool=-1,user=-1;
        int frames=0;
        while (Clock::now()-start<std::chrono::seconds(seconds) && !interrupted) {
            std::this_thread::sleep_until(deadline);
            if (Clock::now()-deadline>std::chrono::milliseconds(40))
                throw std::runtime_error("schedule exceeded 40 ms");
            auto before=Clock::now();
            RobotStatus_simple status{};
            MotionStatus motion{};
            int current_tool=-1,current_user=-1;
            JointValue actual{},reported{};
            checked(robot.get_robot_status_simple(&status),"simple status");
            checked(robot.get_motion_status(&motion),"motion status");
            checked(robot.get_tool_id(&current_tool),"tool ID");
            checked(robot.get_user_frame_id(&current_user),"user ID");
            auto after_status=Clock::now();
            checked(robot.get_actual_joint_position(&actual),"actual joints");
            auto after_actual=Clock::now();
            checked(robot.get_joint_position(&reported),"reported joints");
            const double elapsed=std::chrono::duration<double>(Clock::now()-before).count();
            max_read_s=std::max(max_read_s,elapsed);
            if (elapsed>0.04) {
                std::cout<<"READ_LATENCY status="<<std::chrono::duration<double>(after_status-before).count()
                         <<" actual="<<std::chrono::duration<double>(after_actual-after_status).count()
                         <<" reported="<<std::chrono::duration<double>(Clock::now()-after_actual).count()<<std::endl;
                throw std::runtime_error("read exceeded 40 ms: "+std::to_string(elapsed));
            }
            if (status.errcode || motion.isInEstop || motion.isInCollision || motion.isOnLimit
                || !status.powered_on || !status.enabled) {
                std::cout<<"STATE error="<<status.errcode<<" estop="<<motion.isInEstop
                         <<" collision="<<motion.isInCollision<<" limit="<<motion.isOnLimit
                         <<" paused="<<motion.paused<<" power="<<status.powered_on
                         <<" enabled="<<status.enabled<<std::endl;
                throw std::runtime_error("controller state gate failed");
            }
            if (!frames) {tool=current_tool;user=current_user;}
            if (tool!=current_tool || user!=current_user)
                throw std::runtime_error("tool/user frame changed");
            for (int j=0;j<6;++j) if (!std::isfinite(actual.jVal[j]) || !std::isfinite(reported.jVal[j]))
                throw std::runtime_error("non-finite joint feedback");
            std::cout<<std::setprecision(15)<<"{\"frame\":"<<frames<<",\"read_s\":"<<elapsed<<",\"actual_rad\":[";
            for (int j=0;j<6;++j) std::cout<<(j?",":"")<<actual.jVal[j];
            std::cout<<"],\"reported_rad\":[";
            for (int j=0;j<6;++j) std::cout<<(j?",":"")<<reported.jVal[j];
            // Program pause does not invalidate a READ-ONLY telemetry test.
            // Never resume the program here or reuse this as a motion gate.
            std::cout<<"],\"in_position\":"<<motion.inpos<<",\"program_paused\":"<<motion.paused<<"}"<<std::endl;
            ++frames;deadline+=std::chrono::milliseconds(80);
        }
        if (interrupted) throw std::runtime_error("interrupted");
        std::cout<<"READ_ONLY_SDK_SOAK_PASSED frames="<<frames<<" max_read_s="<<max_read_s
                 <<"; cache age/servo coexistence NOT certified"<<std::endl;
        exit_code=0;
    } catch (const std::exception& e) {std::cout<<"FAILED "<<e.what()<<std::endl;}
    if (logged) {
        int rc=robot.login_out();
        std::cout<<"LOGOUT rc="<<rc<<std::endl;
        if (rc) exit_code=1;
    }
    return exit_code;
}
