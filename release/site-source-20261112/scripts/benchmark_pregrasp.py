#!/usr/bin/env python3
"""Run the section 8.6 pregrasp planning matrix and print the result table.

Planning only: this script never imports a hardware adapter and never sends a
motion command. One arm is planned per case, and the reviewed profile list comes
from ares_r.motion.curobo_params so ad-hoc parameter edits cannot leak in.

    scripts/benchmark_pregrasp.py right_S0_to_pregrasp_A right_S1_to_pregrasp_A
"""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ares_r.motion.curobo_params import PROFILES
from ares_r.motion.pregrasp import plan_case

SUMMARY_NAME = "matrix.json"
TABLE_NAME = "matrix.md"


def load_config(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def row_from_result(result, directory, case_id, profile):
    payload = json.loads((Path(directory) / "trajectory.json").read_text(encoding="utf-8"))
    geometry = payload.get("pregrasp", {})
    singularity = payload.get("singularity_summary", {})
    return dict(
        case_id=case_id, arm=result["arm"], profile=profile, success=True,
        directory=str(directory), random_seed=payload.get("random_seed"),
        points=result["points"], duration_s=result["duration_s"],
        orchestration_wall_s=result["orchestration_wall_s"],
        plan_cspace_wall_ms=result["plan_cspace_wall_ms"],
        curobo_total_time_s=result["curobo_total_time_s"],
        curobo_solve_time_s=result["curobo_solve_time_s"],
        min_sigma_min_scaled=singularity.get("min_sigma_min_scaled"),
        max_condition_number_scaled=singularity.get("max_condition_number_scaled"),
        min_abs_sin_j5=singularity.get("min_abs_sin_j5"),
        levels=singularity.get("levels"),
        min_model_clearance_m=geometry.get("min_model_clearance_m"),
        min_central_margin_m=geometry.get("min_central_margin_m"),
        min_soft_limit_margin_rad=geometry.get("min_soft_limit_margin_rad"),
        joint_path_length_rad_total=geometry.get("joint_path_length_rad_total"),
        tcp_path_length_m=geometry.get("tcp_path_length_m"),
        tcp_frame_check_deviation_m=geometry.get("tcp_frame_check_deviation_m"),
    )


def failure_row(case_id, profile, stage, error):
    return dict(case_id=case_id, profile=profile, success=False, stage=stage, error=error)


def format_table(rows):
    header = ("| case | arm | profile | ok | wall s | plan ms | solve s | sigma min | cond max "
              "| clearance m | limit margin rad | joints rad | tcp m | points |")
    rule = "|" + "---|" * 15
    lines = [header, rule]

    def cell(value, digits=4):
        if value is None:
            return "-"
        if isinstance(value, float):
            return ("%%.%df" % digits) % value
        return str(value)

    for row in rows:
        if not row.get("success"):
            lines.append("| %s | - | %s | FAIL | - | - | - | - | - | - | - | - | - | %s |"
                         % (row["case_id"], row["profile"], row.get("stage", "?")))
            continue
        lines.append("| %s | %s | %s | ok | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            row["case_id"], row["arm"], row["profile"], cell(row["orchestration_wall_s"], 2),
            cell(row["plan_cspace_wall_ms"], 0), cell(row["curobo_solve_time_s"], 4),
            cell(row["min_sigma_min_scaled"], 5), cell(row["max_condition_number_scaled"], 3),
            cell(row["min_model_clearance_m"], 4), cell(row["min_soft_limit_margin_rad"], 5),
            cell(row["joint_path_length_rad_total"], 3), cell(row["tcp_path_length_m"], 4),
            cell(row["points"], 0)))
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("cases", nargs="+", help="case ids with a captured start and manifest")
    parser.add_argument("--config", default="config/system.json")
    parser.add_argument("--profiles", default=",".join(sorted(PROFILES)))
    parser.add_argument("--output-root", type=Path, default=Path("logs/pregrasp_matrix"))
    args = parser.parse_args()

    profiles = [name.strip() for name in args.profiles.split(",") if name.strip()]
    unknown = [name for name in profiles if name not in PROFILES]
    if unknown:
        raise SystemExit("unknown profiles %s; reviewed profiles are %s"
                         % (unknown, ", ".join(sorted(PROFILES))))
    if not profiles:
        raise SystemExit("at least one profile is required")

    config = load_config(args.config)
    rows = []
    failures = []
    for case_id in args.cases:
        for profile in profiles:
            try:
                directory, result = plan_case(config, case_id, profile)
            except (RuntimeError, ValueError, OSError) as exc:
                row = failure_row(case_id, profile, type(exc).__name__, str(exc))
                rows.append(row)
                failures.append(row)
                print("FAILED %s %s: %s" % (case_id, profile, exc), file=sys.stderr)
                continue
            row = row_from_result(result, directory, case_id, profile)
            rows.append(row)
            print("OK %s %s: points=%d duration=%.2fs sigma_min=%.5f" % (
                case_id, profile, row["points"], row["duration_s"], row["min_sigma_min_scaled"]))

    args.output_root.mkdir(parents=True, exist_ok=True)
    summary = dict(schema_version=1, cases=list(args.cases), profiles=profiles,
                   planning_only=True, rows=rows, failures=failures,
                   note=("Planning-only matrix. Failures are kept and never overwritten by a later "
                         "success; each run has its own directory and run id."))
    (args.output_root / SUMMARY_NAME).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    table = format_table(rows)
    (args.output_root / TABLE_NAME).write_text(table + "\n", encoding="utf-8")
    print()
    print(table)
    print()
    print("Matrix summary: %s" % (args.output_root / SUMMARY_NAME))
    print("Result table:   %s" % (args.output_root / TABLE_NAME))
    if failures:
        print("%d of %d runs failed; inspect their planner.log before retrying with a new run id."
              % (len(failures), len(rows)))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
