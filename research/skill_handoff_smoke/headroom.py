"""Smoke-1 headroom gate: is there value in choosing a different terminal state?

Only accept independently labeled, controlled candidate sweeps. In-sample oracle
headroom is NOT a deployable learned policy and is NOT evidence RL will win.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path


def evaluate_headroom(rows):
    groups = defaultdict(lambda: defaultdict(list))
    for row in rows:
        if not all(k in row for k in
                   ('context_id', 'candidate_id', 'heuristic_rank', 'downstream_skill_success')):
            continue
        success = row['downstream_skill_success']
        if not isinstance(success, bool) or row.get('scene_binding_matches') is False:
            continue
        groups[str(row['context_id'])][str(row['candidate_id'])].append(row)
    comparisons = []
    for ctx, by_candidate in sorted(groups.items()):
        if len(by_candidate) < 2:
            continue
        choices = []
        for name, attempts in sorted(by_candidate.items()):
            rank = min(int(r['heuristic_rank']) for r in attempts)
            rate = sum(int(r['downstream_skill_success']) for r in attempts) / len(attempts)
            choices.append((name, rank, rate, len(attempts)))
        heuristic = min(choices, key=lambda a: (a[1], a[0]))
        oracle = max(choices, key=lambda a: (a[2], -a[1], a[0]))
        comparisons.append({
            'context_id': ctx, 'candidate_count': len(choices),
            'heuristic_candidate': heuristic[0],
            'heuristic_success_rate': heuristic[2],
            'oracle_candidate': oracle[0],
            'oracle_success_rate': oracle[2],
            'oracle_gap': oracle[2] - heuristic[2],
            'candidate_success_span': max(c[2] for c in choices) - min(c[2] for c in choices),
        })
    n = len(comparisons)
    return {
        'schema_version': 1,
        'eligible_contexts': n,
        'evaluated_attempts': sum(len(v) for g in groups.values() for v in g.values()),
        'oracle_advantage_mean': sum(x['oracle_gap'] for x in comparisons) / n if n else None,
        'any_candidate_choice_matters': sum(x['candidate_success_span'] > 0 for x in comparisons),
        'policy_evidence_ready': False,
        'ready_for_rl_comparison': n >= 12 and
            sum(x['candidate_success_span'] > 0 for x in comparisons) > 0,
        'warning': 'In-sample oracle is only an upper bound; test a learned policy on held-out task/scene groups.',
        'contexts': comparisons,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args(argv)
    rows = [json.loads(line) for line in args.input.read_text().splitlines() if line.strip()]
    result = evaluate_headroom(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({k:v for k,v in result.items() if k!='contexts'}, indent=2))
    return 0 if result['ready_for_rl_comparison'] else 3


if __name__ == '__main__':
    raise SystemExit(main())
