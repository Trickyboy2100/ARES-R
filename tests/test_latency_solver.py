import unittest
from unittest.mock import Mock
from ares_r.motion.latency_solver import validate_solver_policy, solve_single_pass, orientation_runtime_key


class LatencySolverTests(unittest.TestCase):
    def test_legacy_and_invalid(self):
        self.assertIsNone(validate_solver_policy(None))
        for p in ({'mode':'UNSAFE'}, {'mode':'FAST_SINGLE_PASS_V1','initial_iters':0},
                  {'mode':'FAST_SINGLE_PASS_V1','initial_iters':True},
                  {'mode':'FAST_SINGLE_PASS_V1','max_goal_candidates':50}):
            with self.assertRaises(ValueError):validate_solver_policy(p)

    def test_single_curobo_pass_not_interpolation(self):
        planner=Mock()
        result=solve_single_pass(planner,'goal','start',
            {'mode':'FAST_SINGLE_PASS_V1','initial_iters':25})
        planner.trajopt_solver.solve_cspace.assert_called_once_with(
            'goal','start',seed_traj=None,finetune_attempts=0,initial_iters=25,finetune_dt_scale=1.0)
        self.assertIs(result,planner.trajopt_solver.solve_cspace.return_value)

    def test_target_rotation_does_not_rebuild_runtime_but_criteria_does(self):
        a={'policy':'FIXED_ROTATION_V1','target_R_body_tcp':[[1]],'weight_scale':1}
        b=dict(a,target_R_body_tcp=[[2]])
        self.assertEqual(orientation_runtime_key(a),orientation_runtime_key(b))
        self.assertNotEqual(orientation_runtime_key(a),orientation_runtime_key(dict(a,weight_scale=2)))

    def test_existing_task_requests_remain_quality(self):
        from ares_r.motion.scene_aware_motion import MotionRequest,MotionGoal,OrientationMode
        from ares_r.motion.scene_aware_planner import apply_latency_profile
        p={'num_trajopt_seeds':8,'use_cuda_graph':False}
        self.assertEqual(apply_latency_profile(p,MotionRequest('right',[0]*6)),(None,None))
        self.assertEqual(p['num_trajopt_seeds'],8)
        request=MotionRequest('right',goal=MotionGoal([.6,-.2,1],orientation=OrientationMode.LEVEL_YAW_TARGET,
            yaw_target_rad=0),planning_mode='FAST')
        policy,contract=apply_latency_profile(p,request)
        self.assertEqual(policy['initial_iters'],50)
        self.assertFalse(contract['automatic_quality_fallback'])
        self.assertEqual(contract['result_deadline_s'],4)

    def test_fast_request_never_cold_starts_slow_worker(self):
        from unittest.mock import patch
        from ares_r.motion.planner_service_client import plan
        with patch('ares_r.motion.planner_service_client._call',side_effect=FileNotFoundError), \
             patch('ares_r.motion.planner_service_client.subprocess.Popen') as process:
            with self.assertRaisesRegex(RuntimeError,'NOT_READY'):
                plan('/unused','/unused','request','output','log',2,autostart=False)
            process.assert_not_called()


class CollisionLaunchBudgetTests(unittest.TestCase):
    def test_preallocation_bound_preserves_normal_world_and_guards_int32(self):
        from ares_r.motion.latency_solver import bounded_interpolation_buffer
        normal,proof=bounded_interpolation_buffer(5000,2,360,512)
        self.assertEqual(normal,5000)
        large,proof=bounded_interpolation_buffer(5000,2,360,768)
        self.assertLess(large,5000);self.assertLess(proof['dense_kernel_extent_upper_bound'],2**31)
        self.assertFalse(proof['path_truncation_allowed'])
        site,proof=bounded_interpolation_buffer(5000,2,1727,768)
        self.assertGreaterEqual(site,64);self.assertLess(proof['dense_kernel_extent_upper_bound'],2**31)
        with self.assertRaisesRegex(RuntimeError,'BUDGET_EXCEEDED'):bounded_interpolation_buffer(5000,200,1727,768)
