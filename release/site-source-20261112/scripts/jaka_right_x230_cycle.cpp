// Direct SDK, explicit two-point X-only cycle. No ART/WebUI or setting changes.
#define main historical_direct_main
#include "jaka_right_linear_up_once.cpp"
#undef main
using Clock=std::chrono::steady_clock;
static double xyz_gap(const CartesianPose&a,const CartesianPose&b){return std::sqrt(std::pow(a.tran.x-b.tran.x,2)+std::pow(a.tran.y-b.tran.y,2)+std::pow(a.tran.z-b.tran.z,2));}
int main(int argc,char**argv){
 if(argc!=3||(std::string(argv[1])!="PREFLIGHT"&&std::string(argv[1])!="EXECUTE_X230_HOLD3_RETURN"))return 2;
 bool execute=std::string(argv[1])=="EXECUTE_X230_HOLD3_RETURN";
 CartesianPose a{},b{};int tool=0;std::ifstream f(argv[2]);f>>a.tran.x>>a.tran.y>>a.tran.z>>a.rpy.rx>>a.rpy.ry>>a.rpy.rz>>b.tran.x>>b.tran.y>>b.tran.z>>b.rpy.rx>>b.rpy.ry>>b.rpy.rz>>tool;
 if(!f||std::abs(b.tran.x-a.tran.x-230)>1e-6||std::abs(b.tran.y-a.tran.y)>1e-8||std::abs(b.tran.z-a.tran.z)>1e-8||std::abs(b.rpy.rx-a.rpy.rx)>1e-8||std::abs(b.rpy.ry-a.rpy.ry)>1e-8||std::abs(b.rpy.rz-a.rpy.rz)>1e-8)return 2;
 int fd=open("/tmp/ares-r-right-servo.lock",O_CREAT|O_RDWR,0600);if(fd<0||flock(fd,LOCK_EX|LOCK_NB))return 3;
 JAKAZuRobot r;bool logged=false,moving=false;int result=0;std::cout<<std::setprecision(12);
 try{ok(r.login_in("192.168.99.101",false),"login");logged=true;std::this_thread::sleep_for(std::chrono::seconds(1));safe(r);int id=0,user=0;ok(r.get_tool_id(&id),"tool");ok(r.get_user_frame_id(&user),"user");MotionStatus m{};ok(r.get_motion_status(&m),"motion");CartesianPose actual{};ok(r.get_actual_tcp_position(&actual),"TCP");
  if(id!=tool||user!=0||m.queue||m.active_queue||!m.inpos||xyz_gap(actual,a)>1.||std::abs(actual.rpy.rx-a.rpy.rx)>.01||std::abs(actual.rpy.ry-a.rpy.ry)>.01||std::abs(actual.rpy.rz-a.rpy.rz)>.01)throw std::runtime_error("current/point A/tool/frame binding mismatch");
  std::cout<<"{\"event\":\"x230_cycle_bound\",\"A_mm_rad\":";pose(a);std::cout<<",\"B_mm_rad\":";pose(b);std::cout<<",\"speed_mm_s\":20,\"hold_s\":3,\"execute\":"<<(execute?"true":"false")<<"}"<<std::endl;
  if(execute){
   auto move=[&](CartesianPose target,const char*leg){ok(r.linear_move(&target,ABS,FALSE,20.,50.),"linear_move");moving=true;auto t=Clock::now();int stable=0;
    while(true){safe(r);ok(r.get_actual_tcp_position(&actual),"TCP feedback");ok(r.get_motion_status(&m),"motion feedback");double error=xyz_gap(actual,target);double elapsed=std::chrono::duration<double>(Clock::now()-t).count();stable=(m.inpos&&error<1.)?stable+1:0;
     if(stable>=3){moving=false;std::cout<<"{\"event\":\"target_reached\",\"leg\":\""<<leg<<"\",\"elapsed_s\":"<<elapsed<<",\"error_mm\":"<<error<<",\"actual_mm_rad\":";pose(actual);std::cout<<"}"<<std::endl;return;}
     if(elapsed>50.)throw std::runtime_error("MoveL timeout");std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }};
   move(b,"lift_x230");auto hold=Clock::now();while(std::chrono::duration<double>(Clock::now()-hold).count()<3.){safe(r);std::this_thread::sleep_for(std::chrono::milliseconds(50));}std::cout<<"{\"event\":\"hold_completed\",\"elapsed_s\":"<<std::chrono::duration<double>(Clock::now()-hold).count()<<"}"<<std::endl;move(a,"lower_return");
  }
 }catch(const std::exception&e){if(moving)r.motion_abort();std::cerr<<"cycle failed: "<<e.what()<<std::endl;result=1;}
 if(logged)r.login_out();close(fd);return result;
}
