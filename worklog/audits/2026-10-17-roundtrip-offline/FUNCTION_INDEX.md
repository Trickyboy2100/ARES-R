# 本地代码函数和限制索引

离线AST索引。每项分支不等于实际运行的安全门；仅critical文件进入冻结源码副本。

## scripts/audit_curobo_fk.py

SHA256 `88d3c8df5c72acce904369962cfc26a6a8b83016a99475d0d66fedd7fcb911d5`

- `pose(values)` — L15–22
- `urdf_fk(root, q)` — L25–34
- `main()` — L37–82

## scripts/build_first_pick_execution_package.py

SHA256 `e08e2097f4a7470afcd27b2620d48a0a4c309aa1a840930211dba98240cf4b6b`

- `load(p)` — L19–19
- `sha(value)` — L20–20
- `qrot(q)` — L21–23
- `body_box(name, value, T)` — L24–27
- `arm_geometry(q, request)` — L28–37
- `trajectory_hash(points)` — L38–38
- `main()` — L41–143

## scripts/build_p3_production_scene.py

SHA256 `dad753ec51aeb65464fdb454dbfc2f4b444abe4d949d716552e8bcf80204cc1c`

- `deployment_prefilter(points, voxel_m, roi)` — L27–41
- `load(path)` — L44–44
- `quaternion(matrix)` — L47–55
- `obb_aabb(box)` — L58–64
- `point_aabb_distance(point, box)` — L67–70
- `select_target_primitive(target_body, planning_boxes, preferred_semantics, maximum_distance_m)` — L73–92
- `planning_inflation(role, observed_inflation_m, semantic=None)` — L95–104
- `targets(active, audit, world, model, existing=None, goal_delta_rad=None)` — L107–133
- `targets.matrix(q)` — L124–124
- `add(objects, observation, identifier, role, center, dims, inflation, source)` — L136–140
- `main()` — L143–328

## scripts/capture_manipulation_observation.py

SHA256 `1e308e05200caea823a94ae7a92fb057a0be00028a6788b9641cfa9769607efc`

- `main()` — L21–49
- `main.read_state(label)` — L31–41

## scripts/epic_capture_service.py

SHA256 `b16db4a7a75194c769670a824fa75266429e66c8a4dfe79a8360ae3fffa22b7c`

- `capture(endpoint: str, output: Path)` — L18–63
- `serve(path: Path)` — L66–87

## scripts/finish_confirmed_lift_hold.py

SHA256 `afe36af29eaeffe6634023e91d172e0d9303462ee5b5d20d1db21446ab81742d`

- `main()` — L18–96
- `main.event(stage, state, detail)` — L67–69

## scripts/gripper_direct_once.py

SHA256 `f8c607b82d151d780f126d86237ac80554d9fb67712574458d8f268fc1024260`

- `frame(device_id, command, data=b'')` — L16–18
- `exchange(port, payload, expected)` — L21–39
- `main()` — L42–59

## scripts/jaka_right_demo.cpp

SHA256 `d6ce1fd4986705f5562cb6a397304da47fa9a7ee2c4c41ddfca0b807ed348e67`


C++/JS检查位置：
- L25: `static void check(int rc,const char* op){if(rc)throw std::runtime_error(std::string(op)+" code="+std::to_string(rc));}`
- L36: `std::cout<<"\"";for(char c:s){if(c=='\"'||c=='\\')std::cout<<'\\';if(c=='\n')std::cout<<"\\n";else std::cout<<c;}std::cout<<"\"";`
- L48: `if(status.errcode||!status.powered_on||!status.enabled||s.motion.isInEstop||s.motion.isInCollision||s.motion.isOnLimit||drag)`
- L49: `throw std::runtime_error(`
- L57: `for(int j=0;j<6;++j){s.q[j]=q.jVal[j];if(!std::isfinite(s.q[j]))throw std::runtime_error("non-finite feedback");}`
- L58: `s.tcp=pose(tcp);for(double v:s.tcp)if(!std::isfinite(v))throw std::runtime_error("non-finite TCP");`
- L59: `if(tool_data){check(robot.get_tool_data(s.tool_id,&tcp),"tool data");s.tool=pose(tcp);}`
- L69: `if(magic=="ARES_R_RIGHT_V2")f>>p.speed_cap>>p.accel_cap>>p.tracking_stop_deg;`
- L70: `if(!f||(magic!="ARES_R_RIGHT_V1"&&magic!="ARES_R_RIGHT_V2")||n<2||n>10000||!std::isfinite(p.dt)||std::abs(p.dt-.08)>1e-9)`
- L71: `throw std::runtime_error("invalid trajectory header");`
- L72: `if(supervised_path&&(!(p.speed_cap>0&&p.speed_cap<=.20)||!(p.accel_cap>0&&p.accel_cap<=.20)||`
- L74: `throw std::runtime_error("invalid A/B demo profile limits");`
- L75: `if(!std::isfinite(p.captured)||std::time(nullptr)-p.captured<0||std::time(nullptr)-p.captured>300)`
- L76: `throw std::runtime_error("expired live planning snapshot");`
- L77: `for(auto* row:{&p.tool,&p.lo,&p.hi})for(double& v:*row)if(!(f>>v)||!std::isfinite(v))throw std::runtime_error("invalid metadata");`
- L78: `for(int j=0;j<6;++j)if(p.lo[j]>=p.hi[j]||p.lo[j]<-7||p.hi[j]>7)throw std::runtime_error("invalid limits");`
- L81: `for(double& v:p.q[i])if(!(f>>v)||!std::isfinite(v))throw std::runtime_error("invalid target");`
- L83: `if(p.q[i][j]<p.lo[j]||p.q[i][j]>p.hi[j])throw std::runtime_error("joint limit");`
- L88: `if(std::abs(p.q[i][j]-p.q[0][j])>rad(cap))throw std::runtime_error("excursion cap");`
- L92: `if(std::abs(v)>speed_cap+1e-10||std::abs(v-previous_v[j])/p.dt>accel_cap+1e-10)`
- L93: `throw std::runtime_error("velocity/acceleration cap");`
- L97: `for(double v:previous_v)if(std::abs(v)/p.dt>(supervised_path?p.accel_cap:(micro?rad(1):.2))+1e-10)throw std::runtime_error("end acceleration");`
- L98: `if(f>>extra)throw std::runtime_error("trailing data");`
- L99: `if((n-1)*p.dt>(long_move?240:115))throw std::runtime_error("duration cap");`
- L115: `if(!snapshot&&!validate_supervised&&(!(micro||demo||reset||pregrasp||supervised_path)||std::string(argv[3])!="CONFIRMED_RIGHT_CLEAR")){std::cerr<<"invalid explicit mode/confirmation\n";return 2;}`
- L116: `Path path;try{if(!snapshot)path=load(argv[2],micro,reset,pregrasp,supervised_path||validate_supervised);}catch(const std::exception&e){std::cerr<<e.what()<<std::endl;return 2;}`
- L117: `if(validate_supervised){std::cout<<"VALID_SUPERVISED_PATH samples="<<path.q.size()<<" duration_s="<<(path.q.size()-1)*path.dt<<" speed_cap_rad_s="<<path.speed_cap<<" accel_cap_rad_s2="<<path.accel_cap<<" tracking_stop_deg="<<path.tracking_stop_deg<<"; no controller connection"<<std::endl;return 0;}`
- L119: `if(lock<0||flock(lock,LOCK_EX|LOCK_NB)){std::cerr<<"right lock occupied\n";if(lock>=0)close(lock);return 2;}`
- L125: `std::this_thread::sleep_for(std::chrono::milliseconds(200));`
- L134: `if(!snapshot){`
- L136: `if(active||start.motion.queue||start.motion.active_queue||!start.motion.inpos||interrupted)`
- L137: `throw std::runtime_error("not idle / pre-existing servo");`
- L138: `if(start.tool_id!=path.tool_id||distance(start.tool,path.tool)>1e-6||start.user_id!=0)`
- L139: `throw std::runtime_error("tool/user changed");`
- L140: `if(distance(start.q,path.q.front())>rad(.02))throw std::runtime_error("start moved; replan");`
- L142: `auto deadline=Clock::now();Q previous=path.q.front();`
- L144: `std::this_thread::sleep_until(deadline);`
- L145: `if(interrupted || (supervised_path && getppid()!=launch_parent))throw std::runtime_error("interrupted / supervisor lost");`
- L147: `double lag=std::chrono::duration<double>(Clock::now()-deadline).count();`
- L148: `if(lag>.04)throw std::runtime_error("feedback/send deadline");`
- L149: `if(actual.tool_id!=start.tool_id||actual.user_id!=start.user_id)throw std::runtime_error("tool/user changed");`
- L150: `if(distance(actual.tool,start.tool)>1e-6)throw std::runtime_error("tool offset changed");`
- L151: `if(distance(actual.q,previous)>rad(micro?.1:(supervised_path?path.tracking_stop_deg:.2)))throw std::runtime_error("tracking error");`
- L153: `if(std::sqrt(tcp_displacement)>(micro?5:(long_move?1500:250)))throw std::runtime_error("actual TCP displacement cap");`
- L155: `check(robot.servo_j(&target,ABS,10),"servo_j");`
- L156: `if(Clock::now()-before>std::chrono::milliseconds(40))throw std::runtime_error("cycle budget");`
- L157: `std::cout<<"{\"event\":\"sample\"";stamp();std::cout<<",\"planned_time_s\":"<<i*path.dt<<",\"deadline_lag_ms\":"<<lag*1000<<",\"read_send_ms\":"<<std::chrono::duration<double,std::milli>(Clock::now()-before).count()<<",\"index\":"<<i<<",\"tracking_error_deg\":"<<distance(actual.q,previous)*180/3.14159265358979323846<<",\"actual_rad\":";array_json(actual.q);`
- L159: `if(!std::cout)throw std::runtime_error("log write failed");`
- L160: `previous=path.q[i];deadline+=std::chrono::milliseconds(80);`
- L162: `std::this_thread::sleep_until(deadline);`
- L163: `if(interrupted || (supervised_path && getppid()!=launch_parent))throw std::runtime_error("interrupted / supervisor lost");`
- L165: `if(Clock::now()-before>std::chrono::milliseconds(40)||distance(final.q,path.q.back())>rad(.05))`
- L166: `throw std::runtime_error("final feedback mismatch");`
- L174: `if(servo){int rc=robot.motion_abort();std::cout<<"{\"event\":\"abort\"";stamp();std::cout<<",\"code\":"<<rc<<"}"<<std::endl;}`
- L176: `if(servo){int rc=robot.servo_move_enable(false);std::cout<<"{\"event\":\"servo_disabled\"";stamp();std::cout<<",\"code\":"<<rc<<"}"<<std::endl;if(rc)result=1;}`
- L177: `if(logged){int rc=robot.login_out();std::cout<<"{\"event\":\"logout\"";stamp();std::cout<<",\"code\":"<<rc<<"}"<<std::endl;if(rc)result=1;}`

## scripts/p32_scan_scene.py

SHA256 `4b56dc32ea15d5ffade9c7b76c0e260661f7bb3ac9a3b27ff548709620933a54`

- `run(*args, python=None)` — L21–23
- `audit_with_readonly_retry(urdf, output, side)` — L26–38
- `main()` — L41–131

## scripts/prepare_authorized_first_pick.py

SHA256 `80e35ab8aad99a9a494d08853d25d52226bf66dd7d7201f2a92c4643f7d3d0e1`

- `load(path)` — L28–29
- `main()` — L32–206

## scripts/resume_confirmed_grasp_lift.py

SHA256 `d9df5d207516676503d1446bc81b0a684dbd2b19dcfb954ad2e017e4561cdd1a`

- `validate_checkpoint(events)` — L17–25
- `lift_only(live, event)` — L28–38
- `main()` — L41–177
- `main.event(stage, state, detail)` — L107–111
- `main.abort(*_)` — L133–134

## scripts/run_first_pick_demo.py

SHA256 `e158482004601bbb1e562ee842fb590f27805813b7d7ee029ce5e59e41ea2bb0`

- `_run(command, **kwargs)` — L31–33
- `_write_state(**updates)` — L36–41
- `prepare()` — L44–74
- `_sender(path, log)` — L77–98
- `execute(run_dir)` — L101–140
- `main()` — L143–154

## scripts/run_grasp_place_roundtrip.py

SHA256 `682eb9a40beb14724e349ca3bea54be422f1e01c3c5664422be85269447654ff`

- `load(path)` — L27–27
- `write(path, value)` — L28–32
- `Live.__init__(self, p, out, event)` — L36–41
- `Live.check_cancelled(self)` — L42–43
- `Live.get(self, path)` — L44–45
- `Live.post(self, path, body, timeout=150)` — L46–53
- `Live.stop(self)` — L54–62
- `Live.command(self, args, log, timeout=300)` — L63–77
- `Live.telemetry(self)` — L78–81
- `Live.invalidate(self, reason)` — L82–82
- `Live._level(self, points, request)` — L83–90
- `Live.prepare_pick(self)` — L91–92
- `Live._prepare_pick_once(self, mode, index)` — L93–145
- `Live.pick_segment(self, segment)` — L146–180
- `Live.gripper(self, raw)` — L181–191
- `Live.verify_grasp(self)` — L192–205
- `Live.attach(self)` — L206–208
- `Live.detach(self)` — L209–211
- `Live.free_move(self, position, label)` — L212–249
- `Live.free_move.attempt(mode, index)` — L220–230
- `Live.lift_remaining(self, distance_m)` — L250–252
- `Live.base(self, delta)` — L253–272
- `Live.place_target(self, slot_id, height_m)` — L273–298
- `Live.move_preland(self)` — L299–299
- `main()` — L302–371
- `main.event(stage, state, detail)` — L323–326
- `main.Mock.check_cancelled(self)` — L347–347
- `main.Mock.stop(self)` — L348–348
- `main.Mock.__getattr__(self, name)` — L349–349
- `main.abort(*_)` — L361–362

## scripts/run_scene_aware_supervised.py

SHA256 `0a5314fbc4843d70ab5a26e315c782dc4dfd4cae15ebe3e31e9683154b29d6c5`

- `operations_abort_requested()` — L34–36
- `load(path)` — L39–40
- `write(path, value)` — L43–45
- `monitor(package, native, output)` — L48–134
- `main()` — L137–181

## scripts/test_grasp_place_base_roundtrip.py

SHA256 `a6c365d0628ec0fc2557e5849cd1ace793c12fec3eb8352497bf5f811e0eb9e9`

- `main()` — L16–101
- `main.post(path, body, timeout=135)` — L28–31
- `main.read()` — L32–34
- `main.save()` — L38–39

## scripts/verify_authorized_first_pick.py

SHA256 `c1a43f85704a9b046d71e1b888dd94ee5ffb6770e44d6e876aa589a36bf78eaf`

- `main()` — L17–44

## src/ares_r/adapters/amr_http.py

SHA256 `16c938643304b880e47a39e7bad81f9861916acf8553a9d1dc8a4737f3e01671`

- `AmrHttpBase.__init__(self, config)` — L14–23
- `AmrHttpBase._request(self, method, path, query=None, body=None)` — L25–49
- `AmrHttpBase.battery(self)` — L51–53
- `AmrHttpBase.current_map(self)` — L54–54
- `AmrHttpBase.position_types(self)` — L55–55
- `AmrHttpBase.move_position(self, position_id, position_name, retries=1)` — L57–65
- `AmrHttpBase.move_relative(self, x_m, y_m, yaw_deg, linear_mps=None, angular_radps=None, timeout_s=None)` — L71–89
- `AmrHttpBase.run_task(self, task_id)` — L91–94
- `AmrHttpBase.navigate(self, station)` — L96–100
- `AmrHttpBase.stop(self)` — L102–102
- `AmrHttpBase.station(self)` — L103–103
- `AmrHttpBase.state(self)` — L105–110

## src/ares_r/adapters/epic.py

SHA256 `de0ce91784aeeffc0b7a6fdbb3facbc91c58fb9d0a96ea2abc25b71f1022e3dc`

- `EpicClient.__init__(self, config: Dict[str, object])` — L19–29
- `EpicClient._connect(self)` — L31–41
- `EpicClient._exchange(self, command: str)` — L43–66
- `EpicClient._as_pose(self, values, profile: EpicTaskProfile)` — L68–81
- `EpicClient._parse_pose(self, raw: str, kind: str, request_id: str, profile: EpicTaskProfile)` — L83–129
- `EpicClient._detect_profile(self, profile_name: str, kind: str)` — L131–144
- `EpicClient.detect_pick(self, arm: Optional[str]=None)` — L146–148
- `EpicClient.detect_place(self, dock_id: int, arm: Optional[str]=None)` — L150–152
- `EpicClient.switch_space(self, space_id: int, object_id: int)` — L154–169
- `EpicClient.state(self)` — L171–177
- `EpicClient.probe(self)` — L179–186
- `EpicClient.close(self)` — L188–191

## src/ares_r/adapters/epic_profiles.py

SHA256 `bf703bc8eca7abf0ed4102a64650895df67abc8762a3fe8846afa073062e84da`

- `EpicTaskProfile.commissioned(self)` — L30–31
- `EpicTaskProfile.from_mapping(cls, name: str, raw: Mapping[str, object])` — L34–49
- `EpicTaskProfile.validate(self)` — L51–67
- `load_profiles(config: Mapping[str, object])` — L70–74

## src/ares_r/adapters/epic_protocol.py

SHA256 `6021a1df99b48318a4300c803b9b8162d13c8c31e77322983eb59233e4dcec19`

- `describe_status(response: str)` — L37–47
- `EpicAcknowledgement.description(self)` — L57–58
- `parse_acknowledgement(raw: str)` — L61–73
- `parse_5700_response(raw: str)` — L92–134

## src/ares_r/adapters/jaka_sdk.py

SHA256 `a0055c1d02b9e6cecd2e4c09bb109c0274d9fa40f3e15617527e6472e2a09b4d`

- `_value(result: object, label: str)` — L24–27
- `_payload(result: object, label: str)` — L30–33
- `parse_robot_status(status: object)` — L36–57
- `load_jkrc(python_path: str, library_path: str)` — L60–65
- `JakaSdkArm.__init__(self, name: str, config: Dict[str, object], sdk_config: Dict[str, object], motion_enabled: bool=False)` — L71–81
- `JakaSdkArm._query(self, method_name: str, label: str, attempts: int=4)` — L83–105
- `JakaSdkArm.joint_position(self)` — L107–108
- `JakaSdkArm.diagnostics(self)` — L110–138
- `JakaSdkArm.state(self)` — L140–152
- `JakaSdkArm._motion_locked(self)` — L154–155
- `JakaSdkArm.move_joints_absolute(self, target_rad: Sequence[float], speed_rad_s: float, progress=None, timeout_s: float=None, *, safety_permit=None, authorized_points=None, sample_period_s=None)` — L157–217
- `JakaSdkArm.abort_motion(self)` — L219–224
- `JakaSdkArm.move_to_pose(self, pose: Pose)` — L226–227
- `JakaSdkArm.move_linear_tool(self, distance_m: float)` — L229–230
- `JakaSdkArm.move_named(self, name: str)` — L232–233
- `JakaSdkArm.stop(self)` — L235–236
- `JakaSdkArm.close(self)` — L238–241
- `build_jaka_arms(config: Dict[str, object], motion_enabled: bool=False)` — L244–256
- `build_readonly_arms(config: Dict[str, object])` — L259–260
- `readonly_trajectory_preflight(arm: JakaSdkArm, trajectory: Trajectory, limits: MotionLimits)` — L263–284
- `readonly_trajectory_preflight.add(code: str, message: str)` — L271–272

## src/ares_r/canonical_backend.py

SHA256 `b8de12cd066b42ebcca123a602c3862ea7ebf58fc621dc202adb6f6633c09957`

- `CanonicalBackend.__init__(self, config, root='.')` — L23–41
- `CanonicalBackend.system_info(self)` — L42–46
- `CanonicalBackend.physical_status(self)` — L47–64
- `CanonicalBackend.motion_execute(self, body)` — L66–107
- `CanonicalBackend.operations_stop(self)` — L109–129
- `CanonicalBackend.base_move(self, body)` — L131–168
- `CanonicalBackend.base_move.sample()` — L149–151
- `CanonicalBackend.run_p39b(self, body)` — L169–192
- `CanonicalBackend.roundtrip_start(self, body)` — L193–198
- `CanonicalBackend.roundtrip_status(self)` — L199–199
- `CanonicalBackend.call(self, method, args=(), kwargs=None)` — L200–216
- `_Handler._json(self, value, status=200)` — L221–224
- `_Handler._body(self)` — L225–226
- `_Handler.do_GET(self)` — L227–230
- `_Handler.do_POST(self)` — L231–239
- `_Handler.log_message(self, pattern, *args)` — L240–240
- `CanonicalBackendClient.__init__(self, url=None)` — L245–245
- `CanonicalBackendClient._request(self, path, payload=None)` — L246–253
- `CanonicalBackendClient.system_info(self)` — L254–254
- `CanonicalBackendClient.__getattr__(self, name)` — L255–256
- `main()` — L259–267

## src/ares_r/cli.py

SHA256 `4d8f8c22bad38ccc646aa627b0f863127eb1b1a9336e7c4b5bdabb0a16f69ec6`

- `load_config(path: str)` — L11–17
- `main()` — L20–58

## src/ares_r/demos/registry.py

SHA256 `c170921a1752844816fd65f68e84c157896284a5cffa958e294433481e3bfe1e`

- `_atomic_json(path: Path, value: Mapping[str, object])` — L15–20
- `DemoRegistry.__init__(self, root='demos', state_path='logs/demo_runtime.json')` — L26–28
- `DemoRegistry._definitions(self)` — L30–44
- `DemoRegistry.list(self)` — L46–53
- `DemoRegistry.inspect(self, demo_id)` — L55–59
- `DemoRegistry.status(self)` — L61–70
- `DemoRegistry.select(self, demo_id)` — L72–78
- `DemoRegistry.selected(self, demo_id=None)` — L80–84
- `DemoRegistry.prepare(self, demo_id=None)` — L86–98
- `DemoRegistry.stop(self)` — L100–115

## src/ares_r/demos/roundtrip_launcher.py

SHA256 `c0ee6367b4b46bb26adc15503c8e61ff5011f0ea6283f5e41d67086707b6210e`

- `read(path)` — L17–17
- `write(path, value)` — L18–20
- `RoundtripLauncher.__init__(self, root)` — L24–27
- `RoundtripLauncher.contract(self)` — L29–48
- `RoundtripLauncher._meta(self)` — L50–52
- `RoundtripLauncher._running(self, meta)` — L54–59
- `RoundtripLauncher.status(self)` — L61–84
- `RoundtripLauncher.check_physical_access(self, body)` — L86–90
- `RoundtripLauncher.start(self, body)` — L92–126

## src/ares_r/epic_pointcloud.py

SHA256 `728bf97d7681c3bde0b871472042e7e82699d7bb71bf2bca5c33b3786a51ec10`

- `inspect_ply(path)` — L14–57
- `_header_int(text, key)` — L60–62
- `planning_assessment(stats, config)` — L65–78
- `_fast_capture(config, root)` — L81–112
- `_fast_capture.request()` — L85–100
- `capture(config, output_root=None, fast=False)` — L115–137

## src/ares_r/manipulation/attached_collision.py

SHA256 `76893a8ebc0f4962e5da635d0cce222d5b87df8344648b215898127693fc0975`

- `_matrix_multiply(left, right)` — L12–14
- `_pose_matrix(pose)` — L17–24
- `_transform_point(matrix, point)` — L27–29
- `_rigid_inverse(matrix)` — L32–39
- `_quaternion_wxyz(rotation)` — L42–58
- `attach_scene_object(target, T_body_tcp, *, side: str, source_revision: str)` — L61–70
- `build_attached_collision(attached, T_link6_tcp: Sequence[Sequence[float]], inflation_m: float=0.008)` — L73–101
- `verify_attached_collision(value: Mapping[str, object], expected_revision=None)` — L104–118
- `attached_spheres_body(attached_collision, T_body_link6, sphere_builder)` — L121–129

## src/ares_r/manipulation/contact_bypass.py

SHA256 `37aa33c362a2f257d14ca11a5f465e64dd732cdf57493ec4f920a54e50272847`

- `_digest(value)` — L18–20
- `ContactBypassPolicy.for_manipulation_skill(cls, stage, observation_id, *, central_exclusion=True)` — L40–49
- `ContactBypassPolicy.as_dict(self)` — L51–51
- `validate_bypass_segment(samples: Sequence[Mapping[str, object]], world_obstacles: Mapping[str, Mapping[str, object]], policy: ContactBypassPolicy, *, expected_direction_body, joint_lower, joint_upper, expire_at_end=True)` — L54–100

## src/ares_r/manipulation/first_pick_package.py

SHA256 `2915ff6607b90696f32e03ef6f2dee0a49e0b3f01c27a5ed3c26000d82a4bb3d`

- `_sha(value)` — L13–14
- `verify_first_pick_package(value)` — L17–39

## src/ares_r/manipulation/grasp_verification.py

SHA256 `de6610eee4e2614b259d348d4c29b790593c31ec48c33a44e80193d5cfe6351a`

- `_local_voxels(points, center, radius_m, voxel_m)` — L12–21
- `local_tcp_scene_delta(before_points: Sequence[Sequence[float]], after_points: Sequence[Sequence[float]], tcp_center_body_m: Sequence[float], *, radius_m: float=0.15, voxel_m: float=0.005)` — L24–45
- `delayed_gripper_readback(read_position: Callable[[], int], delays_s, *, sleep: Callable[[float], None]=time.sleep, clock: Callable[[], float]=time.time)` — L48–63
- `classify_scene_delta(scene_delta: Mapping[str, object], parameters: Mapping[str, object])` — L66–76
- `verify_grasp_v1(scene_delta: Mapping[str, object], readbacks, parameters: Mapping[str, object])` — L79–93

## src/ares_r/manipulation/observation_transaction.py

SHA256 `3b8173e105e14318f3bf274c2b39f0e49af9d33d00affb257795243001773ca9`

- `_atomic_json(path: Path, value: Mapping[str, object])` — L16–20
- `detection_dict(detection)` — L23–34
- `_joints(state: Mapping[str, object], side: str)` — L37–44
- `ManipulationObservationTransaction.__init__(self, config: Mapping[str, object], *, detect: Callable, read_robot_state: Callable, scene_builder: Callable, clock: Callable[[], float]=time.time, joint_stability_rad: float=math.radians(0.25))` — L52–61
- `ManipulationObservationTransaction.capture(self, destination: Path, *, profile: str='right_pick')` — L63–131

## src/ares_r/manipulation/observation_transaction_v2.py

SHA256 `439f147cd82c46c7f51037e5a92ad4688406893cd98ce1d1c74120e756db4dfe`

- `ObservationTransactionV2.__init__(self, *, read_robot_state, detect_resource, capture_pointcloud, commit_scene, clock=time.time, joint_stability_rad=math.radians(0.25), max_capture_skew_s=3.0)` — L14–19
- `ObservationTransactionV2._joints(state, side)` — L21–22
- `ObservationTransactionV2.capture(self, destination, *, profile, purpose='pick')` — L23–54

## src/ares_r/manipulation/roundtrip_demo.py

SHA256 `5cd716932b543e851fb25f487fff08b2b6f8c25152fb933a240cb9cf2c6ac934`

- `validate_parameters(p)` — L11–39
- `recipe(p, route)` — L42–71
- `digest(value)` — L74–75
- `plan_with_retries(parameters, attempt, event, check_cancelled)` — L82–97
- `CycleRunner.__init__(self, parameters, route, transport, event)` — L101–104
- `CycleRunner.run(self)` — L106–117

## src/ares_r/motion/base_motion_observer.py

SHA256 `51208d1f4eae8268f7dd611da48b0e3384e262a28cb35f67b40e0cff709b7e0f`

- `BaseObservation.from_robot_status(cls, value: Mapping[str, object], *, clock=time.time)` — L34–39
- `_yaw_delta_deg(first: float, second: float)` — L42–43
- `observation_delta(first: BaseObservation, second: BaseObservation)` — L46–58
- `BaseMotionObserver.__init__(self, sample: Callable[[], BaseObservation], config: Mapping[str, object], *, sleep: Callable[[float], None]=time.sleep, clock: Callable[[], float]=time.time)` — L64–70
- `BaseMotionObserver.capture(self)` — L72–73
- `BaseMotionObserver.wait(self, baseline: BaseObservation, *, timeout_s: Optional[float]=None, expected_translation_m: float=0.0, expected_yaw_deg: float=0.0)` — L75–157
- `amr_status_sampler(base, *, clock=time.time)` — L160–164
- `amr_status_sampler.sample()` — L161–163

## src/ares_r/motion/execution_candidate.py

SHA256 `c3ebd4b7513a85d712590ed158323cc79f30ff4f6f551e6c708bee22424c31d4`

- `digest(value)` — L18–20
- `trajectory_hash(points, sample_period_s)` — L23–27
- `trial_summary(plan, *, expected_envelope_revision, minimum_clearance_m=MIN_FIRST_DEMO_CLEARANCE_M)` — L30–75
- `select_reproducible_candidate(trials, *, minimum_repeats=3)` — L78–89
- `make_candidate_manifest(*, plan, selection, scene_report, pointcloud_sha256, actual_start_joints_rad, tool_id, controller_tool_pose_mm_rad, planner_profile_revision, timing_profile_revision, native_trajectory_hash, native_duration_s, native_sender_binary_sha256, expected_destination, scene_captured_at_unix, created_at_unix=None, ttl_s=300)` — L92–140
- `candidate_binding_reasons(candidate, live, *, now=None)` — L143–167
- `make_execution_lease_draft(candidate)` — L170–183

## src/ares_r/motion/execution_tool_envelope.py

SHA256 `2c7646d8318840df470aa6697c10d3957d2367c4adf3f23ef116a637f118c52d`

- `_digest(value)` — L10–12
- `build_execution_tool_envelope(collision_model, tool_pose_mm_rad, *, inflation_m=0.008, observed_demo_only=False, max_opening_percent=None, use_component_geometry=False, component_inflation_m=0.0)` — L15–101
- `verify_execution_tool_envelope(envelope, collision_model, tool_pose_mm_rad)` — L104–113

## src/ares_r/motion/latency_solver.py

SHA256 `e853aac0c60ac86595541ed84229f6d176c5d540746446ec77a93db9f73bae72`

- `orientation_runtime_key(lock)` — L4–8
- `validate_solver_policy(value)` — L11–23
- `solve_single_pass(planner, goal, start, policy, seed=None)` — L26–30

## src/ares_r/motion/live_scene.py

SHA256 `95516b3dfa0931f77419e1e0c355fd0c8659ca8d4346d2c16256fea4f70176d3`

- `_stamp()` — L21–22
- `build_live_planning_scene(config: dict, destination: Path | None=None, active_arm: str='right', detection_artifact: Path | None=None)` — L25–68

## src/ares_r/motion/live_state.py

SHA256 `3a033a56afc81986ac56cfc85137a3cba75e81775529d8aba2b7c5b3dd875f24`

- `base_stationarity(config, *, count=3, interval_s=1.0)` — L11–40

## src/ares_r/motion/local_scene_service.py

SHA256 `955cdd21c45dbd7a6ba4f47392fa54b842205cd3ec7955de6434c7e099d27bf7`

- `_atomic_json(path: Path, value: Mapping[str, object])` — L37–41
- `LocalSceneService.__init__(self, config: Mapping[str, object], *, state_path=None, scene_builder: Callable=build_live_planning_scene, clock: Callable[[], float]=time.time)` — L49–57
- `LocalSceneService._empty(self, state: SceneState, reason: str)` — L59–76
- `LocalSceneService._read(self)` — L78–82
- `LocalSceneService._write(self, value: Mapping[str, object])` — L84–88
- `LocalSceneService.status(self)` — L90–101
- `LocalSceneService.invalidate(self, reason: str, *, required: bool=False)` — L103–109
- `LocalSceneService.base_motion_started(self)` — L111–112
- `LocalSceneService.base_settled(self)` — L114–120
- `LocalSceneService.scan(self, *, force: bool=False, active_arm: str='right')` — L122–170
- `LocalSceneService.ensure_fresh(self, reason: str, policy=ScenePolicy.AUTO_FRESH, active_arm: str='right')` — L172–184
- `LocalSceneService.snapshot(self)` — L186–190

## src/ares_r/motion/native_demo.py

SHA256 `38c150448e258aab37a34a8d46df5dde9295a884387472825f581dc92d7767b9`

- `NativeExecutionError.__init__(self, message, code='NATIVE_EXECUTION_FAILED', log=None, recoverable=False)` — L23–24
- `classify_native_failure(text, events)` — L27–33
- `native_environment()` — L36–43
- `exclusive_right(controller)` — L47–60
- `snapshot()` — L63–71
- `plan_micro(config)` — L74–80
- `native_move_caps(motion_limits)` — L124–136
- `predicted_tracking_gate_deg(points, dt, lag_s=NATIVE_TRACKING_LAG_S)` — L139–153
- `native_move_violations(points, dt, speed_cap, accel_cap)` — L156–178
- `native_move_excess(points, dt, speed_cap, accel_cap)` — L181–197
- `resample_for_native(points, source_dt, target_dt, speed_cap, accel_cap, max_duration_s=None)` — L200–232
- `resample_uniform(points, source_dt, target_dt, velocity_cap_rad_s, acceleration_cap_rad_s2, extra_stretch=1.0, max_duration_s=None)` — L235–298
- `resample_uniform.at_source_time(seconds)` — L279–285
- `prepare_native_file(config, path, mode)` — L301–369
- `validate_demo20(raw, trajectory, reset=False)` — L372–389
- `execute(config, path, mode, confirmed=False, safety_permit=None)` — L392–426

## src/ares_r/motion/native_execution_package.py

SHA256 `e42bff026233df3a81df40550c736414ff4d78a54c46133e9cda63a0d7cf240f`

- `verify_installed_sender(path)` — L35–39
- `_geometry_error(source, sampled)` — L42–57
- `package_native_preview(points, source_dt_s, site_limits, *, tool_id, controller_tool_pose_mm_rad, captured_at_unix, max_duration_s=NATIVE_MAX_DURATION_S, speed_ceiling_rad_s=FIRST_DEMO_SPEED_RAD_S, accel_ceiling_rad_s2=FIRST_DEMO_ACCEL_RAD_S2, tracking_stop_threshold_deg=SUPERVISED_HARD_TRACKING_GATE_DEG, max_excursion_rad=NATIVE_MAX_EXCURSION_RAD)` — L60–152

## src/ares_r/motion/persistent_planner_service.py

SHA256 `37a5243fb836b76c36e7629eb3114c07b025001241b69b01c65a071c7f26c632`

- `serve(path: Path)` — L15–50

## src/ares_r/motion/planner_service_client.py

SHA256 `67762e8faa23f6b6bde4628adce04a66e473aa7cffdea7e6bb6536994dd6440e`

- `_call(payload, timeout_s)` — L13–22
- `plan(python, repository, request, output, log, timeout_s=180.0, autostart=True)` — L25–46
- `status()` — L49–52
- `start(python, repository)` — L55–67
- `stop()` — L70–73

## src/ares_r/motion/production_scene_worker.py

SHA256 `6a706b15843f1211fa9117a339d03b4e8a1996567d36e813aecac78314978329`

- `transform(xyz, rpy)` — L24–29
- `path_metrics(points)` — L32–39
- `bounded_validation_knots(points, max_joint_step_rad=0.002)` — L42–49
- `main()` — L52–484
- `main.fk(q)` — L111–114
- `main.state(rows)` — L178–180
- `main.runtime_goal_candidates(start)` — L181–206
- `main.quaternion_rotation(q)` — L207–211
- `main.clearance_by_sample(rows)` — L212–225
- `main.clearance_details(rows)` — L226–227
- `main.clearance_trace(rows)` — L228–231
- `main.clearance(rows)` — L232–234
- `main.solve_segment(begin, end, seed_rows=None)` — L299–310
- `main.solve(goal_value, candidate_index=0)` — L311–318

## src/ares_r/motion/runtime_goal_ik.py

SHA256 `bbb91cc7a6a2b006e29d5f274305e1a072176c8227e09141d7bc3599a9e405a6`

- `RuntimeGoalIK.__init__(self, urdf, body_model, link6_tcp)` — L22–30
- `RuntimeGoalIK.fk(self, joints)` — L32–36
- `RuntimeGoalIK.solve(self, xyz, rotation, seed)` — L38–51
- `RuntimeGoalIK.solve.residual(q)` — L42–44

## src/ares_r/motion/safety_kernel.py

SHA256 `6d5d1c38f792ac2ab253144423a7c17962f1573f127b9ff96b188c505c77ac43`

- `trajectory_digest(arm: str, points: Sequence[Sequence[float]], sample_period_s: float)` — L33–36
- `require_permit(permit, arm, points, sample_period_s)` — L39–43
- `DualArmSafetyKernel.__init__(self, execution_enabled: bool, speed_profiles: Mapping[str, object])` — L47–49
- `DualArmSafetyKernel.preflight_execution_candidate(self, candidate, live, native_audit, *, now=None, speed_profile='slow', execution_limits=None)` — L51–140
- `DualArmSafetyKernel.scene_aware_collision_gate(candidate)` — L143–150
- `DualArmSafetyKernel.component_geometry_gate(candidate)` — L153–170
- `DualArmSafetyKernel.authorize(self, *, arm, points, sample_period_s, geometry_samples, speed_profile, live_start, tool_revision, planned_tool_revision, scene_snapshot_id, collision_checked, base_stationary, inactive_arm_state_known, controller_fault=False, attached_object=False, central_exclusion_enabled=True)` — L172–207
- `DualArmSafetyKernel._check_dynamics(points, dt, profile)` — L210–219
- `DualArmSafetyKernel._check_geometry(arm, samples, point_count, attached_object, central_exclusion_enabled=True)` — L222–235
- `DualArmSafetyKernel._check_side(side, spheres)` — L238–250
- `central_plane_in_arm_base(arm: str, base_xyz_m, base_yaw_rad: float)` — L253–269

## src/ares_r/motion/scene_aware_execution.py

SHA256 `7628a648624403561ea2b01ab4aa9aa5b820548f1f6f88b39ace47792c6bcd69`

- `finite_or_none(value)` — L25–34
- `central_exclusion_gate(manifest)` — L37–46
- `_load(path)` — L49–50
- `_write(path, value)` — L53–56
- `GenericNativePackager.__init__(self, config, profile)` — L60–62
- `GenericNativePackager.__call__(self, motion, scene, output, plan, hard_validity)` — L64–150
- `_audit_arm(config, output, side)` — L153–163
- `preflight(config, local_scene, candidate, native_audit, profile)` — L166–219

## src/ares_r/motion/scene_aware_motion.py

SHA256 `0746bb51e71e701747c5c39a677c1f5955b4ff14daa6dafe0b9ab5aa97fe2218`

- `MotionGoal.validate(self)` — L64–82
- `MotionRequest.validate(self)` — L99–147
- `ClearancePolicy.validate(self)` — L157–163
- `evaluate_hard_validity(plan: Mapping[str, object], policy: ClearancePolicy)` — L166–209
- `SceneAwareMotionService.__init__(self, config: Mapping[str, object], local_scene: LocalSceneService, planner: Callable[[MotionRequest, Mapping[str, object], Path], Mapping[str, object]], packager: Optional[Callable]=None, *, state_path='logs/scene_aware_motion.json', clearance_policy: Optional[ClearancePolicy]=None, clock: Callable[[], float]=time.time)` — L215–230
- `SceneAwareMotionService._read(self)` — L232–233
- `SceneAwareMotionService._write(self, value)` — L235–238
- `SceneAwareMotionService.status(self)` — L240–243
- `SceneAwareMotionService.invalidate_plans(self, reason: str)` — L245–248
- `SceneAwareMotionService.plan(self, request: MotionRequest)` — L250–346
- `SceneAwareMotionService.preview(self, plan_id: Optional[str]=None)` — L348–365
- `SceneAwareMotionService.execute(self, plan_id: str)` — L367–370
- `SceneAwareMotionService.stop(self)` — L372–373
- `build_services(config: Mapping[str, object], *, scene_state_path=None, motion_state_path=None)` — L376–403

## src/ares_r/motion/scene_aware_planner.py

SHA256 `d39f2b72b4d9610239f13d6fe49b341eb762194ff0671d802b41c3abe445bd9a`

- `_load(path)` — L26–27
- `load_profile(path=None)` — L30–31
- `apply_latency_profile(parameters, motion)` — L34–43
- `_orientation_lock(request: MotionRequest, report, audit, collision_model)` — L46–72
- `_runtime_goal_spec(request, report, audit, collision_model)` — L75–102
- `PersistentCuroboPlanner.__init__(self, config: Mapping[str, object], profile=None)` — L106–108
- `PersistentCuroboPlanner.__call__(self, motion: MotionRequest, scene: Mapping[str, object], output: Path)` — L110–262

## src/ares_r/motion/tcp_orientation.py

SHA256 `56aa203443d77bf2b0a87306dbeb5c17d16f7fab050f72f9dcb2b6a6b2cc7f94`

- `level_rotation(yaw_rad, roll_branch=0)` — L19–32
- `nearest_level_roll_branch(rotation)` — L35–41
- `tcp_yaw_rad(rotation)` — L44–47
- `validate_level_path(fk_body_tcp, joints, *, subdivisions=4, tolerance_deg=MAX_ORIENTATION_ERROR_DEG, final_yaw_rad=None)` — L50–96
- `validate_path(fk_body_tcp, joints, *, subdivisions=4, tolerance_deg=MAX_ORIENTATION_ERROR_DEG, target_rotation=HORIZONTAL_FORWARD_R_BODY)` — L99–138

## src/ares_r/offset_frames.py

SHA256 `ebfaefd82846e680e229a80b5c35916bde53332bc060b7c2aed3f4ef5a3d9bed`

- `offset_context(state, scene=None, now=None)` — L14–33
- `_rpy(rotation)` — L36–41
- `convert_offset(value, from_frame, to_frame, rotation=R_BODY_DETECTION)` — L44–54

## src/ares_r/operations.py

SHA256 `9008114e2ba246b6a48c415031c864a878d892b0779535237486866dedf9830a`

- `vector(value, count)` — L28–32
- `matrix(value)` — L35–42
- `initial_state()` — L45–57
- `OperationsRegistry.__init__(self, root='.')` — L61–63
- `OperationsRegistry._locked(self)` — L66–70
- `OperationsRegistry.read(self)` — L72–74
- `OperationsRegistry._write(self, state)` — L76–86
- `OperationsRegistry.update(self, action, body, scene_context=None)` — L88–100
- `OperationsRegistry._apply(self, state, action, body, scene_context=None)` — L102–222
- `OperationsRegistry.select(self, operation, state=None)` — L224–233
- `OperationsRegistry.target(self, slot_id, base_pose_revision, observation_epoch)` — L235–249
- `OperationsRegistry.convert_offsets(self, body, scene_context=None)` — L251–263
- `planning_world(compiled, environment_avoidance)` — L266–282

## src/ares_r/perception/body_pointcloud.py

SHA256 `9e9f3545f7ae6fc5dedbd8658ab6c50a680c8b49d2e0519f093588a97c638e83`

- `_sha256(path: Path)` — L41–46
- `load_epic_ply_camera_mm(path: Path)` — L49–81
- `transform_camera_mm_to_body(points_camera_mm: np.ndarray, colors_rgb: np.ndarray, config: dict, *, source_ply: str='', source_sha256: str='', load_s: float=0.0)` — L84–124
- `build_body_cloud(path: Path, config: dict)` — L127–132
- `build_body_cloud_npy(path: Path, source_sha256: str, config: dict)` — L135–144
- `fit_support_table(cloud: BodyPointCloud, expected_z_m: float=0.75, search_half_width_m: float=0.1, inlier_half_width_m: float=0.012)` — L147–181
- `_metadata(cloud: BodyPointCloud, table: dict, npz_path: Path)` — L184–201
- `save_artifact(cloud: BodyPointCloud, table: dict, directory: Path)` — L204–213
- `load_artifact(manifest_path: Path)` — L215–228
- `artifact_root(config: dict)` — L231–232
- `latest_manifest(config: dict)` — L235–242
- `capture_body_cloud(config: dict)` — L245–263

## src/ares_r/perception/residual_cloud.py

SHA256 `6a532c481ac41c3f9dd48adb632612308ecf3fe159f4b3beb92bc72dc242ef10`

- `workspace_crop(points, roi, table_z_m=0.75, table_half_band_m=0.04)` — L37–44
- `_cloud(points)` — L47–49
- `_filter(voxel_cloud, profile)` — L52–62
- `_bounds(points)` — L65–71
- `clean_and_cluster(points_body_m, roi, profile, table_z_m=0.75, table_half_band_m=0.04, box_bounds=None)` — L74–126

## src/ares_r/perception/robot_collision.py

SHA256 `6500252f3990261e04de69aa067e9367ae80a97b56e995b00e504a655ee97eec`

- `_digest(value)` — L20–22
- `transform_xyz_rpy(xyz, rpy)` — L25–36
- `_origin(joint)` — L39–43
- `_axis_rotation(axis, angle)` — L46–54
- `arm_link_transforms(urdf_path: Path, joints_rad)` — L57–73
- `CollisionBox.as_dict(self)` — L87–92
- `CollisionBox.from_dict(cls, value)` — L95–99
- `RobotGeometrySnapshot.as_dict(self)` — L113–120
- `RobotGeometrySnapshot.from_dict(cls, value)` — L123–128
- `_world_arm_transform(world: dict, side: str)` — L131–133
- `_box_from_local(identifier, owner, kind, local, transform, source, filter_owned=True)` — L136–143
- `build_geometry_snapshot(model: dict, world: dict, audits: dict)` — L146–198
- `save_geometry_snapshot(snapshot: RobotGeometrySnapshot, path: Path)` — L201–204
- `load_geometry_snapshot(path: Path)` — L207–208
- `_inside_box(points: np.ndarray, box: CollisionBox, margin_m: float)` — L211–214
- `self_filter_body_cloud(points_body_m: np.ndarray, snapshot: RobotGeometrySnapshot, margin_m: float)` — L217–243
- `inactive_arm_obstacles(snapshot: RobotGeometrySnapshot, active_side: str)` — L246–260
- `obb_overlap(first: CollisionBox, second: CollisionBox, epsilon=1e-09)` — L263–280
- `mutual_arm_collisions(snapshot: RobotGeometrySnapshot, active_side: str)` — L283–291

## src/ares_r/perception/robot_owned_filter.py

SHA256 `2657c51ccd27c2807953e2fd7bf926a9153d90e33186a475924f6c19f29b91c3`

- `_digest(value)` — L21–23
- `RobotOwnedSphere.as_dict(self)` — L34–38
- `RobotOwnedFilterGeometry.as_dict(self)` — L52–67
- `grid_spheres_local(box, max_cell_m=0.035)` — L70–80
- `_box_grid_spheres(box: CollisionBox, cell_m: float)` — L83–93
- `build_robot_owned_filter(snapshot: RobotGeometrySnapshot, *, planning_sphere_cell_m=0.035, obb_sensor_margin_m=0.02, gripper_sensor_margin_m=0.02, sphere_sensor_margin_m=0.003)` — L96–121
- `_sphere_assign(points, spheres, margin_m)` — L124–134
- `filter_robot_owned(points_body_m, geometry: RobotOwnedFilterGeometry)` — L137–174
- `point_signed_distance_to_box(points, box: CollisionBox)` — L177–182
- `attribute_cluster(points, geometry: RobotOwnedFilterGeometry)` — L185–210

## src/ares_r/perception/support_decomposition.py

SHA256 `acf17149abc0c55bd7afbf82d22d0cb215438deaf65bff0f623a600bf35c7bf6`

- `_cloud(points)` — L34–36
- `_bounds(points)` — L39–41
- `_volume(low, high)` — L44–45
- `detect_support_levels(points, profile=DecompositionProfile())` — L48–105
- `_support_assignment(points, supports, profile)` — L108–123
- `_spatial_components(points, profile)` — L126–133
- `_tile_component(points, profile, semantic, source_id, minimum_points=None)` — L136–159
- `decompose_support_objects(points_body_m, old_boxes, profile=DecompositionProfile())` — L162–238
- `filter_isolated_micro_primitives(report, profile=DecompositionProfile())` — L241–315
- `filter_isolated_micro_primitives.find(index)` — L254–258
- `filter_isolated_micro_primitives.union(first, second)` — L260–263
- `filter_isolated_micro_primitives.gap(first, second)` — L265–269
- `_aabb_sphere_gap(low, high, sphere, inflation)` — L318–321
- `refine_robot_adjacent_primitives(points_body_m, report, robot_owned, cell_m=0.015, inflation_m=0.003)` — L324–378

## src/ares_r/scene_aware_dispatch.py

SHA256 `28693f10f97d1c7577ca36291eff070ebd3bc9f04fb83fd2ad8a44ac52b3f125`

- `_motion_request(payload, default_central_exclusion=True)` — L24–73
- `SceneAwareDispatcher.__init__(self, config)` — L77–81
- `SceneAwareDispatcher.operations_status(self)` — L83–101
- `SceneAwareDispatcher.operations_update(self, action, body)` — L103–107
- `SceneAwareDispatcher.operations_offset_convert(self, body)` — L109–110
- `SceneAwareDispatcher.berth_select(self, operation)` — L112–113
- `SceneAwareDispatcher.berth_target(self, slot_id)` — L115–118
- `SceneAwareDispatcher.berth_detect_corner(self)` — L120–178
- `SceneAwareDispatcher.berth_detect_corner.read_state(_)` — L142–146
- `SceneAwareDispatcher.berth_detect_corner.detect(_)` — L147–151
- `SceneAwareDispatcher.berth_detect_corner.capture(_)` — L152–157
- `SceneAwareDispatcher.robot_telemetry(self)` — L180–211
- `SceneAwareDispatcher.jog_plan(self, body)` — L213–239
- `SceneAwareDispatcher.save_trajectory(self, body)` — L241–264
- `SceneAwareDispatcher.base_preview(self, body)` — L266–280
- `SceneAwareDispatcher.services(self)` — L282–283
- `SceneAwareDispatcher.scene_status(self)` — L285–286
- `SceneAwareDispatcher.scene_scan(self, force=True, active_arm='right')` — L288–289
- `SceneAwareDispatcher.scene_invalidate(self, reason='OPERATOR_INVALIDATION')` — L291–294
- `SceneAwareDispatcher.motion_status(self)` — L296–297
- `SceneAwareDispatcher.motion_plan(self, payload)` — L299–308
- `SceneAwareDispatcher.motion_plan_right_center(self)` — L310–321
- `SceneAwareDispatcher.motion_preview(self, plan_id=None)` — L323–324
- `SceneAwareDispatcher.motion_stop(self)` — L326–329
- `SceneAwareDispatcher.ab_plan_next(self, destination)` — L331–332
- `SceneAwareDispatcher.demo_list(self)` — L334–334
- `SceneAwareDispatcher.demo_status(self)` — L336–336
- `SceneAwareDispatcher.demo_inspect(self, demo_id=None)` — L338–338
- `SceneAwareDispatcher.demo_select(self, demo_id)` — L340–340
- `SceneAwareDispatcher.demo_prepare(self, demo_id=None)` — L342–342
- `SceneAwareDispatcher.demo_stop(self)` — L344–344
- `SceneAwareDispatcher.studio(self)` — L346–346
- `SceneAwareDispatcher.skill_list(self)` — L348–348
- `SceneAwareDispatcher.skill_show(self, skill_id)` — L349–349
- `SceneAwareDispatcher.scheme_list(self)` — L350–350
- `SceneAwareDispatcher.scheme_show(self, scheme_id)` — L351–351
- `SceneAwareDispatcher.scheme_clone(self, source, new_id)` — L352–352
- `SceneAwareDispatcher.scheme_validate(self, scheme)` — L353–353
- `SceneAwareDispatcher.scheme_preview(self, scheme)` — L354–354
- `SceneAwareDispatcher.scheme_save(self, scheme)` — L355–355
- `SceneAwareDispatcher.task_list(self)` — L356–356
- `SceneAwareDispatcher.task_show(self, task_id)` — L357–357
- `SceneAwareDispatcher.task_prepare(self, task_id)` — L358–358
- `SceneAwareDispatcher.task_replay(self, task_id)` — L359–359
- `SceneAwareDispatcher.task_status(self)` — L360–360
- `SceneAwareDispatcher.task_stop(self)` — L361–361
- `SceneAwareDispatcher.system_info(self)` — L363–365
- `SceneAwareDispatcher.dispatch(self, text)` — L367–459
- `shared_dispatcher(config)` — L462–469

## src/ares_r/task_runtime.py

SHA256 `d041c25c5da300d90cde124ccececfbafa8d2273a7c0d598f40e3aa423ec28f7`

- `canonical_digest(value)` — L19–20
- `atomic_json(path, value)` — L23–25
- `SchemeStore.__init__(self, root='schemes')` — L29–31
- `SchemeStore._files(self)` — L32–32
- `SchemeStore.list(self)` — L33–35
- `SchemeStore.load(self, scheme_id)` — L36–40
- `SchemeStore.clone(self, source, new_id)` — L41–46
- `SchemeStore.save_draft(self, value)` — L47–53
- `SchemeValidator.__init__(self, registry)` — L57–57
- `SchemeValidator.validate(self, scheme)` — L58–89
- `SchemeValidator.validate.visit(node_id)` — L80–85
- `SchemeValidator.preview(self, scheme)` — L90–98
- `SchemeRunner.__init__(self, runtime, events, evidence_writer=None, clock=time.monotonic)` — L102–104
- `SchemeRunner._resolve(value, outputs)` — L106–110
- `SchemeRunner.stop(self)` — L111–115
- `SchemeRunner.run(self, scheme, task_id='task.tray_to_groove', binding=None)` — L116–163
- `SchemeRunner.run.prepare(node_id)` — L124–128
- `SchemeRunner.run.eligible(node, keys)` — L129–129
- `compile_runtime_package(scheme, registry, parameters, provider_revision, performance)` — L166–176

## src/ares_r/task_studio.py

SHA256 `098d02c0481afb06b71799afae94876afe969b34a19b11f2408485d00a20bdea`

- `TaskStudio.__init__(self, root='.')` — L18–21
- `TaskStudio.skill_list(self)` — L22–22
- `TaskStudio.skill_show(self, skill_id)` — L23–23
- `TaskStudio.scheme_list(self)` — L24–24
- `TaskStudio.scheme_show(self, scheme_id)` — L25–25
- `TaskStudio.scheme_clone(self, source, new_id)` — L26–26
- `TaskStudio.scheme_validate(self, scheme_or_id)` — L27–29
- `TaskStudio.scheme_preview(self, scheme_or_id)` — L30–32
- `TaskStudio.scheme_save_draft(self, value)` — L33–36
- `TaskStudio.task_list(self)` — L37–41
- `TaskStudio.task_show(self, task_id)` — L42–45
- `TaskStudio.prepare(self, task_id)` — L46–56
- `TaskStudio.replay(self, task_id, failures=None)` — L57–69
- `TaskStudio.start_replay(self, task_id)` — L70–78
- `TaskStudio.start_replay.target()` — L73–76
- `TaskStudio.status(self)` — L79–81
- `TaskStudio.stop(self)` — L82–84

## src/ares_r/terminal.py

SHA256 `dbbdc6abdc2c9d974097d87d0cf9806c366d8faf8c4c9e2c584205960e5a905a`

- `_allowed_in_jaka_readonly(args)` — L200–223
- `_demo_path(controller, value)` — L226–234
- `_pop_delay(args)` — L237–263
- `_pose_speed(route, value=None)` — L266–278
- `_allowed_in_hardware(args)` — L281–315
- `_allowed_in_calibration_scope(args)` — L318–327
- `setup_command_history(repository: Path)` — L330–353
- `setup_command_history.save_history()` — L347–351
- `render(controller: TaskController)` — L356–392
- `run_terminal(controller: TaskController)` — L395–1266
- `run_terminal.direct_progress(report)` — L1172–1176

## src/ares_r/webui/roundtrip_panel.js

SHA256 `4900805ea90c8c8dbba524b31bfd1479529ec4fdbafc2fa4211af1f2ffdd0239`


C++/JS检查位置：
- L9: `<button id="roundtripStart" disabled style="background:#1c684f;margin-top:12px">一键开始完整抓放（实机）</button>`
- L16: `if(!container)return;container.prepend(panel);`
- L21: `const response=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});`
- L22: `const value=await response.json();if(!response.ok)throw Error(value.error||response.status);return value;`
- L26: `if(lastDigest&&lastDigest!==value.contract_sha256)checkbox.checked=false;`
- L33: `if(value.blockers.length)find('roundtripError').textContent=value.blockers.join('\n');`
- L34: `else if(value.failure_message)find('roundtripError').textContent=value.failure_message;`
- L35: `start.disabled=pending||value.running||!value.can_start||!checkbox.checked;`
- L36: `checkbox.disabled=pending||value.running;`
- L37: `if(value.running)checkbox.checked=false;`
- L40: `catch(error){start.disabled=true;find('roundtripError').textContent='后台状态不可用：'+error.message;}}`
- L41: `checkbox.addEventListener('change',()=>{if(current)paint(current);});`
- L43: `if(pending||!checkbox.checked||!current||current.running)return;`
- L44: `pending=true;start.disabled=true;checkbox.disabled=true;find('roundtripError').textContent='';`

## src/ares_r/webui/server.py

SHA256 `b498a28fb8f1864a81d48a9a45a4fea9d896e8df0a268863c3e03a6c1116fbab`

- `scene_payload(dispatcher)` — L30–72
- `system_status(dispatcher)` — L75–89
- `_ws_frame(payload)` — L92–98
- `Handler._json(self, value, status=200)` — L104–107
- `Handler._body(self)` — L109–111
- `Handler._websocket(self, payload_fn)` — L113–122
- `Handler.do_GET(self)` — L124–164
- `Handler.do_POST(self)` — L166–210
- `Handler.log_message(self, pattern, *args)` — L212–213
- `main()` — L216–226

## src/ares_r/world/scene_compiler.py

SHA256 `dca8dd4aa13b3f4348e16b472c9508de46db4f44c93a6062c8270b5e98b3cc0a`

- `_matrix(value: Sequence[Sequence[float]], label: str)` — L13–19
- `transform_body_aabb(center_m, dimensions_m, T_arm_body)` — L22–32
- `_quaternion_wxyz(rotation)` — L35–47
- `transform_body_cuboid(center_m, dimensions_m, T_arm_body)` — L50–53
- `compile_snapshot(snapshot, arm: str, T_body_model, planning_scope='DEMO_OFFLINE_ONLY', target_policy='HARD')` — L56–102

## src/ares_r/world_geometry.py

SHA256 `4dc53275702930c93b7fca275c76f44a96dd9be74431b401bf4f79b1dff098e1`

- `load_world_geometry(path: Path)` — L20–21
- `base_tcp_to_world(base: Dict[str, object], tcp_mm_rad: Sequence[float])` — L24–40
- `central_tcp_exclusion(side: str, world_y_m: float)` — L43–52
- `_wrap_pi(value: float)` — L55–56
- `_matmul(left, right)` — L59–61
- `_rx(value)` — L64–67
- `_rz(value)` — L70–73
- `_translate(x=0.0, z=0.0)` — L76–77
- `joint_points_base_m(model: Dict[str, object], joints_rad: Sequence[float])` — L80–95
- `_point_base_to_world(base: Dict[str, object], point: Sequence[float])` — L98–103
- `_display_model_to_controller(base: Dict[str, object], point: Sequence[float])` — L106–111
- `world_snapshot(config: Dict[str, object], diagnostics: Dict[str, Dict[str, object]])` — L114–140
- `_projection(snapshot: Dict[str, object], axes: Tuple[int, int], title: str, horizontal: str, vertical: str, reverse_horizontal: bool=False)` — L143–233
- `_projection.cell(point)` — L163–169
- `_projection.draw_line(start, end, mark)` — L171–188
- `_projection.column_for_y(value)` — L191–195
- `render_world(snapshot: Dict[str, object], detailed: bool=False)` — L236–272

