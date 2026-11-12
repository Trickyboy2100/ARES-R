// Explicit one-shot SDK MoveL: no ART/WebUI, no Servo, no controller setting changes.
#include "JAKAZuRobot.h"
#include <chrono>
#include <thread>
#include <iostream>
#include <iomanip>
#include <cmath>
#include <string>
#include <stdexcept>
#include <fcntl.h>
#include <sys/file.h>
#include <unistd.h>
#include <fstream>
static void ok(int r,const char*n){if(r)throw std::runtime_error(std::string(n)+" code="+std::to_string(r));}
static void pose(const CartesianPose&p){std::cout<<"["<<p.tran.x<<","<<p.tran.y<<","<<p.tran.z<<","<<p.rpy.rx<<","<<p.rpy.ry<<","<<p.rpy.rz<<"]";}
static void safe(JAKAZuRobot&r){RobotStatus_simple s{};MotionStatus m{};BOOL drag=false;ok(r.get_robot_status_simple(&s),"status");ok(r.get_motion_status(&m),"motion status");ok(r.is_in_drag_mode(&drag),"drag status");if(s.errcode||!s.powered_on||!s.enabled||m.isInEstop||m.isInCollision||m.isOnLimit||drag){std::cerr<<"controller message: "<<s.errmsg<<" estop="<<m.isInEstop<<" collision="<<m.isInCollision<<" limit="<<m.isOnLimit<<std::endl;throw std::runtime_error("controller not ready: err="+std::to_string(s.errcode)+" drag="+std::to_string(drag));}}
int main(int argc,char**argv){std::cout<<std::setprecision(12);bool write=argc==3&&std::string(argv[1])=="WRITE_POINTS";bool fromfile=argc==3&&std::string(argv[1])=="EXECUTE_POINTS";bool return_reference=argc==2&&std::string(argv[1])=="RETURN_RECORDED_PRE_1P9MM";bool reverse_reference=argc==2&&std::string(argv[1])=="REVERSE_LAST_REFERENCE_MOVEL";bool execute=reverse_reference||return_reference||fromfile||(argc==2&&std::string(argv[1])=="EXECUTE_RIGHT_BASE_Z_PLUS_200MM");if(!execute&&!write&&(argc!=2||std::string(argv[1])!="PREFLIGHT"))return 2;
 int fd=open("/tmp/ares-r-right-servo.lock",O_CREAT|O_RDWR,0600);if(fd<0||flock(fd,LOCK_EX|LOCK_NB))return 3;
 JAKAZuRobot r;bool logged=false,moving=false;int code=0;
 try{ok(r.login_in("192.168.99.101",false),"login");logged=true;std::this_thread::sleep_for(std::chrono::seconds(1));RobotStatus st{};ok(r.get_robot_status(&st),"warm status");safe(r);MotionStatus m{};ok(r.get_motion_status(&m),"motion status");int user=0;ok(r.get_user_frame_id(&user),"user frame");if(user!=0||m.queue||m.active_queue||!m.inpos)throw std::runtime_error("base frame 0 and stationary empty queue required");CartesianPose start{},target{},actual{};ok(r.get_actual_tcp_position(&start),"TCP");target=start;target.tran.z+=200.;if(return_reference){target.tran.x=29.2405289542;target.tran.y=-571.369648047;target.tran.z=-459.036655186;target.rpy.rx=-2.97647486604;target.rpy.ry=-0.799865658186;target.rpy.rz=-1.57728024924;}if(reverse_reference){double gap=std::sqrt(std::pow(start.tran.x-29.2405289542,2)+std::pow(start.tran.y+571.369648047,2)+std::pow(start.tran.z+459.036655186,2));if(gap>1.||std::abs(start.rpy.rx+2.97647486604)>.01||std::abs(start.rpy.ry+.799865658186)>.01||std::abs(start.rpy.rz+1.57728024924)>.01)throw std::runtime_error("current does not match previous MoveL endpoint");target.tran.x=222.82825839651105;target.tran.y=-580.4326805659335;target.tran.z=-433.5061872858466;target.rpy.rx=-2.8540112909264;target.rpy.ry=-0.75109775032653;target.rpy.rz=-1.7204074737383;}std::cout<<"{\"event\":\"preflight\",\"start_mm_rad\":";pose(start);std::cout<<",\"target_mm_rad\":";pose(target);std::cout<<",\"speed_mm_s\":20,\"acceleration_mm_s2\":50,\"execute\":"<<(execute?"true":"false")<<"}"<<std::endl;
 if(write){std::ifstream old(argv[2]);if(old.good())throw std::runtime_error("points file already exists");int tool=0;ok(r.get_tool_id(&tool),"tool id");std::ofstream f(argv[2]);f<<std::setprecision(17);for(const auto&p:{start,target})f<<p.tran.x<<" "<<p.tran.y<<" "<<p.tran.z<<" "<<p.rpy.rx<<" "<<p.rpy.ry<<" "<<p.rpy.rz<<"\n";f<<tool<<"\n";if(!f)throw std::runtime_error("cannot write points");}
 if(fromfile){CartesianPose a{},b{};int tool=0,actualtool=0;std::ifstream f(argv[2]);f>>a.tran.x>>a.tran.y>>a.tran.z>>a.rpy.rx>>a.rpy.ry>>a.rpy.rz>>b.tran.x>>b.tran.y>>b.tran.z>>b.rpy.rx>>b.rpy.ry>>b.rpy.rz>>tool;ok(r.get_tool_id(&actualtool),"tool id");if(!f||tool!=actualtool)throw std::runtime_error("point/tool binding invalid");double gap=std::sqrt(std::pow(a.tran.x-start.tran.x,2)+std::pow(a.tran.y-start.tran.y,2)+std::pow(a.tran.z-start.tran.z,2));if(gap>1.||std::abs(a.rpy.rx-start.rpy.rx)>.01||std::abs(a.rpy.ry-start.rpy.ry)>.01||std::abs(a.rpy.rz-start.rpy.rz)>.01)throw std::runtime_error("current differs from point A");if(std::abs(b.tran.x-a.tran.x)>1e-6||std::abs(b.tran.y-a.tran.y)>1e-6||std::abs(b.tran.z-a.tran.z-200.)>1e-6||std::abs(b.rpy.rx-a.rpy.rx)>1e-8||std::abs(b.rpy.ry-a.rpy.ry)>1e-8||std::abs(b.rpy.rz-a.rpy.rz)>1e-8)throw std::runtime_error("only fixed orientation Z+200 allowed");target=b;}
 if(execute){ok(r.linear_move(&target,ABS,FALSE,20.,50.),"linear_move");moving=true;auto t=std::chrono::steady_clock::now();int stable=0;
  while(true){safe(r);ok(r.get_actual_tcp_position(&actual),"TCP feedback");ok(r.get_motion_status(&m),"motion feedback");double e=std::sqrt(std::pow(actual.tran.x-target.tran.x,2)+std::pow(actual.tran.y-target.tran.y,2)+std::pow(actual.tran.z-target.tran.z,2));double elapsed=std::chrono::duration<double>(std::chrono::steady_clock::now()-t).count();stable=(m.inpos&&e<1.)?stable+1:0;
   if(stable>=3){moving=false;std::cout<<"{\"event\":\"target_reached\",\"elapsed_s\":"<<elapsed<<",\"position_error_mm\":"<<e<<",\"actual_mm_rad\":";pose(actual);std::cout<<",\"actual_delta_mm\":["<<actual.tran.x-start.tran.x<<","<<actual.tran.y-start.tran.y<<","<<actual.tran.z-start.tran.z<<"]}"<<std::endl;break;}
   if(elapsed>45.)throw std::runtime_error("MoveL timeout");std::this_thread::sleep_for(std::chrono::milliseconds(100));
  }
 }
 }catch(const std::exception&e){if(moving)r.motion_abort();std::cerr<<"direct MoveL failed: "<<e.what()<<std::endl;code=1;}
 if(logged)r.login_out();close(fd);return code;
}
