#include "JAKAZuRobot.h"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <fstream>
#include <csignal>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <thread>

volatile std::sig_atomic_t stop_requested = 0;
void request_stop(int) { stop_requested = 1; }

void check(int result, const char* operation) {
    if (result) throw std::runtime_error(std::string(operation) + " rc=" + std::to_string(result));
}

void healthy(JAKAZuRobot& robot) {
    RobotStatus_simple status{};
    MotionStatus motion{};
    BOOL drag = false;
    check(robot.get_robot_status_simple(&status), "read status");
    check(robot.get_motion_status(&motion), "read motion");
    check(robot.is_in_drag_mode(&drag), "read drag state");
    if (status.errcode || !status.powered_on || !status.enabled || motion.isInEstop ||
        motion.isInCollision || motion.isOnLimit || drag)
        throw std::runtime_error("controller health failed, errcode=" + std::to_string(status.errcode));
}

int main(int argc, char** argv) {
    const bool snapshot = argc == 3 && std::string(argv[1]) == "--snapshot";
    const bool abort_only = argc == 3 && std::string(argv[1]) == "--abort";
    const bool execute = argc == 5 && std::string(argv[4]) == "EXECUTE_MIRROR";
    if (!snapshot && !abort_only && !execute) return 2;
    const std::string ip = (snapshot || abort_only) ? argv[2] : argv[1];
    if (ip != "192.168.99.100" && ip != "192.168.99.101") return 2;
    std::signal(SIGTERM, request_stop);
    std::signal(SIGINT, request_stop);
    JointValue expected{}, goal{}, actual{};
    int expected_tool_id = -1;
    double expected_tool[6]{};
    bool bind_tool = false;
    if (execute) {
        std::ifstream input(argv[2]);
        for (double& value : expected.jVal) input >> value;
        for (double& value : goal.jVal) input >> value;
        if (!input) return 2;
        for (int i=0; i<6; ++i)
            if (!std::isfinite(expected.jVal[i]) || !std::isfinite(goal.jVal[i])) return 2;
        if (input >> expected_tool_id) {
            bind_tool = true;
            for (double& value : expected_tool) input >> value;
            if (!input) return 2;
            for (double value : expected_tool) if (!std::isfinite(value)) return 2;
        }
    }
    // One SDK connection per process; the supervisor monitors the source arm.
    JAKAZuRobot robot;
    bool dispatched = false;
    try {
        check(robot.login_in(ip.c_str(), false), "destination login");
        if (abort_only) {
            check(robot.motion_abort(), "motion abort");
            check(robot.login_out(), "logout");
            return 0;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
        RobotStatus warm{};
        check(robot.get_robot_status(&warm), "warm state");
        healthy(robot);
        if (stop_requested || (execute && std::ifstream(argv[3]).good())) throw std::runtime_error("STOP_REQUESTED");
        check(robot.get_actual_joint_position(&actual), "read start");
        if (snapshot) {
            CartesianPose tcp{}, tool{};
            int tool_id = -1;
            check(robot.get_actual_tcp_position(&tcp), "read actual TCP");
            check(robot.get_tool_id(&tool_id), "tool ID");
            check(robot.get_tool_data(tool_id, &tool), "tool data");
            std::cout << std::setprecision(16) << "{\"event\":\"snapshot\",\"controller_ip\":" << std::quoted(ip)
                      << ",\"actual_rad\":[";
            for (int i=0; i<6; ++i) std::cout << (i ? "," : "") << actual.jVal[i];
            std::cout << "],\"tcp_mm_rad\":[" << tcp.tran.x << ',' << tcp.tran.y << ',' << tcp.tran.z
                      << ',' << tcp.rpy.rx << ',' << tcp.rpy.ry << ',' << tcp.rpy.rz
                      << "],\"tool_mm_rad\":[" << tool.tran.x << ',' << tool.tran.y << ',' << tool.tran.z
                      << ',' << tool.rpy.rx << ',' << tool.rpy.ry << ',' << tool.rpy.rz
                      << "],\"tool_id\":" << tool_id << ",\"controller_health_passed\":true}" << std::endl;
            check(robot.login_out(), "logout");
            return 0;
        }
        for (int i=0; i<6; ++i) {
            if (std::abs(actual.jVal[i]-expected.jVal[i]) > .003) {
                std::cout << std::setprecision(16) << "{\"event\":\"start_mismatch\",\"joint\":" << i+1
                          << ",\"actual_rad\":" << actual.jVal[i]
                          << ",\"expected_rad\":" << expected.jVal[i] << "}" << std::endl;
                throw std::runtime_error("START_STATE_CHANGED");
            }
        }
        if (bind_tool) {
            int actual_tool_id = -1;
            CartesianPose actual_tool{};
            check(robot.get_tool_id(&actual_tool_id), "execution tool ID");
            check(robot.get_tool_data(actual_tool_id, &actual_tool), "execution tool data");
            const double data[] = {actual_tool.tran.x, actual_tool.tran.y, actual_tool.tran.z,
                                  actual_tool.rpy.rx, actual_tool.rpy.ry, actual_tool.rpy.rz};
            if (actual_tool_id != expected_tool_id) throw std::runtime_error("MIRROR_DESTINATION_TOOL_CHANGED");
            for (int i=0; i<6; ++i)
                if (std::abs(data[i]-expected_tool[i]) > 1e-4)
                    throw std::runtime_error("MIRROR_DESTINATION_TOOL_CHANGED");
        }
        check(robot.joint_move(&goal, ABS, false, .08), "joint MoveJ");
        dispatched = true;
        auto start = std::chrono::steady_clock::now();
        int settled = 0;
        while (true) {
            healthy(robot);
            if (stop_requested || std::ifstream(argv[3]).good()) throw std::runtime_error("STOP_REQUESTED");
            check(robot.get_actual_joint_position(&actual), "read feedback");
            double error = 0;
            for (int i=0; i<6; ++i) error = std::max(error, std::abs(actual.jVal[i]-goal.jVal[i]));
            BOOL in_position = false;
            check(robot.is_in_pos(&in_position), "in position");
            settled = in_position && error < .000873 ? settled+1 : 0;
            double elapsed = std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
            auto wall_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
                std::chrono::system_clock::now().time_since_epoch()).count();
            CartesianPose arrival_tcp{};
            if (settled>=3) check(robot.get_actual_tcp_position(&arrival_tcp), "arrival TCP");
            std::cout << std::setprecision(12) << "{\"event\":\"sample\",\"elapsed_s\":" << elapsed
                      << ",\"wall_unix_ns\":" << wall_ns << ",\"controller_ip\":" << std::quoted(ip)
                      << ",\"joint_error_deg\":" << error*180/M_PI << ",\"actual_rad\":[";
            for (int i=0; i<6; ++i) std::cout << (i ? "," : "") << actual.jVal[i];
            std::cout << "]";
            if (settled>=3) {
                std::cout << ",\"tcp_mm_rad\":[" << arrival_tcp.tran.x << ',' << arrival_tcp.tran.y << ',' << arrival_tcp.tran.z
                          << ',' << arrival_tcp.rpy.rx << ',' << arrival_tcp.rpy.ry << ',' << arrival_tcp.rpy.rz << "]";
            }
            std::cout << ",\"completed\":" << (settled>=3 ? "true" : "false") << "}" << std::endl;
            if (settled>=3) break;
            if (elapsed>60) throw std::runtime_error("movement timeout");
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
        check(robot.login_out(), "logout");

        return 0;
    } catch (const std::exception& error) {
        if (dispatched) robot.motion_abort();
        robot.login_out();

        std::cout << "{\"event\":\"failed\",\"reason\":" << std::quoted(error.what())
                  << ",\"motion_dispatched\":" << (dispatched ? "true" : "false") << "}" << std::endl;
        return 1;
    }
}
