// Supervised RIGHT-ONLY SDK 2.2.2 bridge. Never enables power/robot or resumes programs.
#include "JAKAZuRobot.h"
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <csignal>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>
#include <ctime>
#include <fcntl.h>
#include <sys/file.h>
#include <unistd.h>
using Clock=std::chrono::steady_clock;
using Q=std::array<double,6>;
static volatile std::sig_atomic_t interrupted=0;
static void stop_signal(int){interrupted=1;}
static void check(int rc,const char* op){if(rc)throw std::runtime_error(std::string(op)+" code="+std::to_string(rc));}
static double rad(double deg){return deg*3.14159265358979323846/180;}
static Q pose(CartesianPose p){return {{p.tran.x,p.tran.y,p.tran.z,p.rpy.rx,p.rpy.ry,p.rpy.rz}};}
static void array_json(const Q& q){std::cout<<"[";for(int i=0;i<6;++i)std::cout<<(i?",":"")<<q[i];std::cout<<"]";}
static double distance(const Q&a,const Q&b){double d=0;for(int j=0;j<6;++j)d=std::max(d,std::abs(a[j]-b[j]));return d;}
struct State{Q q,tcp,tool;int tool_id,user_id;MotionStatus motion;};
static State read(JAKAZuRobot& robot,bool tool_data=false){
    RobotStatus_simple status{};State s{};JointValue q{};CartesianPose tcp{};BOOL drag=false;
    check(robot.get_robot_status_simple(&status),"status");
    check(robot.get_motion_status(&s.motion),"motion status");
    check(robot.get_actual_joint_position(&q),"actual q");
    check(robot.get_actual_tcp_position(&tcp),"actual TCP");
    check(robot.get_tool_id(&s.tool_id),"tool ID");
    check(robot.get_user_frame_id(&s.user_id),"user ID");
    check(robot.is_in_drag_mode(&drag),"drag status");
    if(status.errcode||!status.powered_on||!status.enabled||s.motion.isInEstop||s.motion.isInCollision||s.motion.isOnLimit||drag)
        throw std::runtime_error("controller safety gate");
    for(int j=0;j<6;++j){s.q[j]=q.jVal[j];if(!std::isfinite(s.q[j]))throw std::runtime_error("non-finite feedback");}
    s.tcp=pose(tcp);for(double v:s.tcp)if(!std::isfinite(v))throw std::runtime_error("non-finite TCP");
    if(tool_data){check(robot.get_tool_data(s.tool_id,&tcp),"tool data");s.tool=pose(tcp);}
    return s;
}
struct Path{std::vector<Q> q;double dt,captured;int tool_id;Q tool,lo,hi;};
static Path load(const char* file,bool micro){
    std::ifstream f(file);std::string magic,extra;int n=0;Path p{};
    f>>magic>>n>>p.dt>>p.captured>>p.tool_id;
    if(!f||magic!="ARES_R_RIGHT_V1"||n<2||n>10000||!std::isfinite(p.dt)||std::abs(p.dt-.08)>1e-9)
        throw std::runtime_error("invalid trajectory header");
    if(!std::isfinite(p.captured)||std::time(nullptr)-p.captured<0||std::time(nullptr)-p.captured>300)
        throw std::runtime_error("expired live planning snapshot");
    for(auto* row:{&p.tool,&p.lo,&p.hi})for(double& v:*row)if(!(f>>v)||!std::isfinite(v))throw std::runtime_error("invalid metadata");
    for(int j=0;j<6;++j)if(p.lo[j]>=p.hi[j]||p.lo[j]<-7||p.hi[j]>7)throw std::runtime_error("invalid limits");
    p.q.resize(n);Q previous_v{};
    for(int i=0;i<n;++i){
        for(double& v:p.q[i])if(!(f>>v)||!std::isfinite(v))throw std::runtime_error("invalid target");
        for(int j=0;j<6;++j){
            if(p.q[i][j]<p.lo[j]||p.q[i][j]>p.hi[j])throw std::runtime_error("joint limit");
            const double cap=micro?(j==5?.5001:.005):20;
            if(std::abs(p.q[i][j]-p.q[0][j])>rad(cap))throw std::runtime_error("excursion cap");
            double v=i?(p.q[i][j]-p.q[i-1][j])/p.dt:0;
            if(std::abs(v)>rad(micro?.5:3.0)||std::abs(v-previous_v[j])/p.dt>(micro?rad(1):.2))
                throw std::runtime_error("velocity/acceleration cap");
            previous_v[j]=v;
        }
    }
    for(double v:previous_v)if(std::abs(v)/p.dt>(micro?rad(1):.2))throw std::runtime_error("end acceleration");
    if(f>>extra)throw std::runtime_error("trailing data");
    if(n*p.dt>120)throw std::runtime_error("duration cap");
    return p;
}
int main(int argc,char**argv){
    std::signal(SIGINT,stop_signal);std::signal(SIGTERM,stop_signal);
    std::signal(SIGPIPE,SIG_IGN);
    std::cout<<std::setprecision(16);
    const bool snapshot=argc==2&&std::string(argv[1])=="snapshot";
    const bool micro=argc==4&&std::string(argv[1])=="micro";
    const bool demo=argc==4&&std::string(argv[1])=="demo20";
    if(!snapshot&&(!(micro||demo)||std::string(argv[3])!="CONFIRMED_RIGHT_CLEAR")){std::cerr<<"invalid explicit mode/confirmation\n";return 2;}
    Path path;try{if(!snapshot)path=load(argv[2],micro);}catch(const std::exception&e){std::cerr<<e.what()<<std::endl;return 2;}
    int lock=open("/tmp/ares-r-right-servo.lock",O_CREAT|O_RDWR,0600);
    if(lock<0||flock(lock,LOCK_EX|LOCK_NB)){std::cerr<<"right lock occupied\n";if(lock>=0)close(lock);return 2;}
    JAKAZuRobot robot;bool logged=false,servo=false;int result=1;
    try{
        check(robot.login_in("192.168.99.101",false),"login");logged=true;
        read(robot,true); // Warm-up only, before arming.
        State start=read(robot,true);
        std::cout<<"{\"event\":\"snapshot\",\"captured_at_unix\":"<<std::time(nullptr)<<",\"actual_rad\":";
        array_json(start.q);std::cout<<",\"tcp_mm_rad\":";array_json(start.tcp);
        std::cout<<",\"tool_mm_rad\":";array_json(start.tool);
        std::cout<<",\"tool_id\":"<<start.tool_id<<",\"user_id\":"<<start.user_id
                 <<",\"queue\":"<<start.motion.queue<<",\"active_queue\":"<<start.motion.active_queue
                 <<",\"inpos\":"<<start.motion.inpos<<",\"paused\":"<<start.motion.paused<<"}"<<std::endl;
        if(!snapshot){
            BOOL active=false;check(robot.is_in_servomove(&active),"servo state");
            if(active||start.motion.queue||start.motion.active_queue||!start.motion.inpos||interrupted)
                throw std::runtime_error("not idle / pre-existing servo");
            if(start.tool_id!=path.tool_id||distance(start.tool,path.tool)>1e-6||start.user_id!=0)
                throw std::runtime_error("tool/user changed");
            if(distance(start.q,path.q.front())>rad(.02))throw std::runtime_error("start moved; replan");
            check(robot.servo_move_enable(true),"servo enable");servo=true;
            auto deadline=Clock::now();Q previous=path.q.front();
            for(size_t i=0;i<path.q.size();++i){
                std::this_thread::sleep_until(deadline);
                if(interrupted)throw std::runtime_error("interrupted");
                auto before=Clock::now();State actual=read(robot,true);
                double lag=std::chrono::duration<double>(Clock::now()-deadline).count();
                if(lag>.04)throw std::runtime_error("feedback/send deadline");
                if(actual.tool_id!=start.tool_id||actual.user_id!=start.user_id)throw std::runtime_error("tool/user changed");
                if(distance(actual.tool,start.tool)>1e-6)throw std::runtime_error("tool offset changed");
                if(distance(actual.q,previous)>rad(micro?.1:.2))throw std::runtime_error("tracking error");
                double tcp_displacement=0;for(int j=0;j<3;++j)tcp_displacement+=std::pow(actual.tcp[j]-start.tcp[j],2);
                if(std::sqrt(tcp_displacement)>(micro?5:250))throw std::runtime_error("actual TCP displacement cap");
                JointValue target{};for(int j=0;j<6;++j)target.jVal[j]=path.q[i][j];
                check(robot.servo_j(&target,ABS,10),"servo_j");
                if(Clock::now()-before>std::chrono::milliseconds(40))throw std::runtime_error("cycle budget");
                std::cout<<"{\"event\":\"sample\",\"index\":"<<i<<",\"tracking_error_deg\":"<<distance(actual.q,previous)*180/3.14159265358979323846<<",\"actual_rad\":";array_json(actual.q);
                std::cout<<",\"target_rad\":";array_json(path.q[i]);std::cout<<",\"tcp_mm_rad\":";array_json(actual.tcp);std::cout<<"}"<<std::endl;
                if(!std::cout)throw std::runtime_error("log write failed");
                previous=path.q[i];deadline+=std::chrono::milliseconds(80);
            }
            std::this_thread::sleep_until(deadline);
            if(interrupted)throw std::runtime_error("interrupted");
            auto before=Clock::now();State final=read(robot);
            if(Clock::now()-before>std::chrono::milliseconds(40)||distance(final.q,path.q.back())>rad(.05))
                throw std::runtime_error("final feedback mismatch");
            std::cout<<"{\"event\":\"target_reached\",\"actual_rad\":";array_json(final.q);
            std::cout<<",\"tcp_mm_rad\":";array_json(final.tcp);std::cout<<"}"<<std::endl;
        }
        result=0;
    }catch(const std::exception&e){
        std::cerr<<"FAILED "<<e.what()<<std::endl;
        if(servo)std::cout<<"{\"event\":\"abort\",\"code\":"<<robot.motion_abort()<<"}"<<std::endl;
    }
    if(servo){int rc=robot.servo_move_enable(false);std::cout<<"{\"event\":\"servo_disabled\",\"code\":"<<rc<<"}"<<std::endl;if(rc)result=1;}
    if(logged){int rc=robot.login_out();std::cout<<"{\"event\":\"logout\",\"code\":"<<rc<<"}"<<std::endl;if(rc)result=1;}
    close(lock);return result;
}
