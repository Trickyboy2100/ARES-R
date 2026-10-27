# 优化与适配代码位置

| 层/机制 | 真实函数/行 | 文件SHA256 |
|---|---|---|
| CPU dense FK/world | `src/ares_r/motion/independent_path_validation.py:66-188` `validate_dense_world` | `a46f4e9bd74069532d29cabd07fe928cb65489c341e8b4c2b3bd2e6d438d9fda` |
| Double precision native SDF | `src/ares_r/motion/cpu_distance.py:42-58` `distances` | `199f8a656024320666d40940fcc4701222516d023ad82c4f99f7d04540e22c21` |
| Indexed inclusive query | `src/ares_r/manipulation/observed_contact_geometry.py:24-36` `_bounded_cloud` | `bfe34e9400fbbcb3b406bfc1e513abafc3f91b056a269166a0197cbc1690ab0a` |
| Contact artifact | `src/ares_r/manipulation/observed_contact_geometry.py:37-87` `build_observed_contact_geometry` | `bfe34e9400fbbcb3b406bfc1e513abafc3f91b056a269166a0197cbc1690ab0a` |
| Thin SVD | `src/ares_r/manipulation/collision_refinement.py:33-88` `observed_obb` | `e97d6854ebefe2b9d3ed74ef71ba0523baa626d15268365774c8f200ab51f56d` |
| Persistent ownership/cancel | `src/ares_r/motion/persistent_planner_service.py:40-58` `runtime_key` | `09e0cd51c358abfd0ab257738fa26b7a213656c021938fded9daa169c032af69` |
| Native retiming | `src/ares_r/motion/native_execution_package.py:60-186` `package_native_preview` | `1d98a23a3689cf40df58b89e920380618bd23de0c15ef1915c0ddd5172ba4548` |
| Locked-joint extraction fix | `src/ares_r/motion/planner_joint_mapping.py:11-20` `extract_arm_joint_positions` | `3016833712e6c4f5585f19d587e9f077415142296ca134a3aacd848d69d3d38a` |

CPU与query本轮同输入等价收据见runlogs。历史三项不重复相加，见LATENCY_METHOD_AUDIT。gpu effective_config同时绑定worker SHA。未改生产安全限幅。
输入/输出散列：CPU original request/result、query output_hash、RASC CAMERA/BODY散列均在各JSON；完整路径/敏感原日志只在本地私有运行目录。
