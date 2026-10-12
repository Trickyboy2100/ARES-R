"""Strict planning-only evidence adapter for ARES-R archived cuRobo runs.

This script DOES NOT infer Skill transition success, contact success or RL viability.
It intentionally distinguishes planner results from physical execution labels.
Python 3.8+; standard library only.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rounded_vector(values: Any, digits: int = 4):
    if not isinstance(values, (list, tuple)):
        return None
    try:
        return tuple(round(float(x), digits) for x in values)
    except (TypeError, ValueError):
        return None


def read_record(request_path: Path, root: Path) -> dict:
    plan_path = request_path.with_name('planning.json')
    request = json.loads(request_path.read_text(encoding='utf-8'))
    result = json.loads(plan_path.read_text(encoding='utf-8'))
    if not isinstance(request, dict) or not isinstance(result, dict):
        raise ValueError('request/result must be JSON objects')
    scene_req = request.get('scene_snapshot_id')
    scene_res = result.get('scene_snapshot_id')
    status = result.get('observed_result')
    trajectory = result.get('trajectory_points_rad') or []
    orientation = result.get('orientation_validation') or {}
    dense = result.get('independent_dense_validation') or {}
    clearance = result.get('clearance_m') or {}
    planning_time = result.get('timing_s') or {}
    goal = request.get('runtime_motion_goal') or result.get('runtime_motion_goal') or {}
    goal_pos = _rounded_vector(goal.get('position_m')) if isinstance(goal, dict) else None
    start = _rounded_vector(request.get('start_rad'))
    # Correlated repeated scenarios are NOT independent training examples.
    context = {'scene': scene_req, 'start_rad': start,
               'goal_position_m': goal_pos,
               'goal_orientation': goal.get('orientation') if isinstance(goal, dict) else None,
               'goal_yaw': goal.get('yaw_target_rad') if isinstance(goal, dict) else None,
               'goal_rad': _rounded_vector(request.get('goal_rad')),
               'motion_constraints': request.get('motion_constraints')}
    context_id = hashlib.sha256(json.dumps(context, sort_keys=True, default=str).encode()).hexdigest()[:16]
    return {
        'source': str(plan_path.relative_to(root)),
        'request_sha256': sha256_file(request_path),
        'result_sha256': sha256_file(plan_path),
        'scene_snapshot_id': scene_req,
        'scene_binding_matches': bool(scene_req and scene_res and scene_req == scene_res),
        'context_id': context_id,
        'observed_result': status,
        'trajectory_samples': len(trajectory),
        'planner_success_with_trajectory': status == 'SUCCESS' and len(trajectory) >= 2,
        'independent_dense_collision_free': dense.get('collision_free'),
        'orientation_validation_passed': orientation.get('passed'),
        'minimum_modeled_clearance_m': clearance.get('planned_path'),
        'planner_time_s': planning_time.get('planning_reported_total'),
        'goal_position_m': list(goal_pos) if goal_pos else None,
        'start_rad': list(start) if start else None,
        'execution_eligible': False,
        'downstream_skill_success': None,
        'contact_success': None,
        'label_level': 'FROZEN_PLANNING_ONLY',
    }


def audit_tree(root: Path):
    root = root.resolve()
    if not root.is_dir():
        raise ValueError('input must be an existing directory')
    records, errors = [], []
    for request_path in sorted(root.rglob('planner_request.json')):
        if request_path.with_name('planning.json').is_file():
            try:
                records.append(read_record(request_path, root))
            except (OSError, ValueError, TypeError, KeyError) as exc:
                errors.append({'source': str(request_path.relative_to(root)), 'error': str(exc)})
    by_context = defaultdict(list)
    for row in records:
        by_context[row['context_id']].append(row)
    # These are PLANNER statuses, not downstream task outcomes.
    summary = {
        'schema_version': 1,
        'data_kind': 'ARES_R_PLANNING_AUDIT_NOT_RL_DATASET',
        'records': len(records),
        'status_counts': dict(sorted(Counter(str(r['observed_result']) for r in records).items())),
        'paired_context_count': sum(len(rows) > 1 for rows in by_context.values()),
        'distinct_contexts': len(by_context),
        'verified_planning_success_count': sum(r['planner_success_with_trajectory']
            and r['scene_binding_matches']
            and r['independent_dense_collision_free'] is True
            and r['orientation_validation_passed'] is not False for r in records),
        'known_downstream_transition_labels': sum(r['downstream_skill_success'] is not None for r in records),
        'scientific_rl_viability_proven': False,
        'warnings': [
            'Nonrandom debugging traces; no valid train/test split for skill RL.',
            'Correlated repeats must stay in the same split group.',
            'Planner SUCCESS is neither native execution eligibility nor task success.',
            'Need controlled candidate sweeps and downstream execution labels.',
        ],
        'parse_errors': errors,
    }
    return records, summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    records, summary = audit_tree(args.input)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output/'planner_records.jsonl').write_text(
        ''.join(json.dumps(r, sort_keys=True)+'\n' for r in records), encoding='utf-8')
    (args.output/'summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if records and not summary['parse_errors'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
