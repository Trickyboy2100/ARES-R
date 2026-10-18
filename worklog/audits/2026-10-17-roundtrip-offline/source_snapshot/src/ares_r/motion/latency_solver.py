"""Bounded cuRobo optimizer policy, independent of collision/physical limits."""


def orientation_runtime_key(lock):
    """Only solver-construction knobs; target rotations live in each goal buffer."""
    if lock is None:return None
    return {key:lock[key] for key in ('policy','criteria_rpy','weight_scale',
                                    'non_terminal_orientation_cost') if key in lock}


def validate_solver_policy(value):
    if value is None: return None
    if value.get('mode') != 'FAST_SINGLE_PASS_V1':
        raise ValueError('unknown bounded cuRobo solver policy')
    iters = value.get('initial_iters', 25)
    candidates = value.get('max_goal_candidates', 1)
    if isinstance(iters, bool) or not isinstance(iters, int) or iters not in (25,50,75,100):
        raise ValueError('pinned optimizer initial_iters must be 25/50/75/100 (inner_iters=25)')
    if isinstance(candidates, bool) or not isinstance(candidates, int) or not 1 <= candidates <= 4:
        raise ValueError('max_goal_candidates must be integer 1..4')
    if value.get('distance_backend') not in (None,'NATIVE_CPU_V1'):
        raise ValueError('unknown distance backend')
    return dict(value, initial_iters=iters, max_goal_candidates=candidates)


def solve_single_pass(planner, goal, start, policy, seed=None):
    """cuRobo-generated seeds and optimization, never direct interpolation/MoveJ."""
    policy = validate_solver_policy(policy)
    return planner.trajopt_solver.solve_cspace(goal, start, seed_traj=seed,
        finetune_attempts=0, initial_iters=policy['initial_iters'], finetune_dt_scale=1.0)
