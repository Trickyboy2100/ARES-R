#!/usr/bin/env python3
"""Offline source inventory only: never imports ARES services or opens sockets.

Generates audit artifacts from local files; no production files are modified.
The static call inventory is not a proven dynamic call graph.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
CRITICAL = {
    'src/ares_r/canonical_backend.py', 'src/ares_r/scene_aware_dispatch.py',
    'src/ares_r/operations.py', 'src/ares_r/offset_frames.py',
    'src/ares_r/demos/roundtrip_launcher.py', 'src/ares_r/manipulation/roundtrip_demo.py',
    'src/ares_r/manipulation/observation_transaction.py',
    'src/ares_r/manipulation/observation_transaction_v2.py',
    'src/ares_r/manipulation/grasp_verification.py', 'src/ares_r/manipulation/contact_bypass.py',
    'src/ares_r/manipulation/attached_collision.py', 'src/ares_r/manipulation/first_pick_package.py',
    'src/ares_r/motion/planner_service_client.py', 'src/ares_r/motion/persistent_planner_service.py',
    'src/ares_r/motion/production_scene_worker.py', 'src/ares_r/motion/scene_aware_planner.py',
    'src/ares_r/motion/scene_aware_motion.py', 'src/ares_r/motion/scene_aware_execution.py',
    'src/ares_r/motion/runtime_goal_ik.py', 'src/ares_r/motion/latency_solver.py',
    'src/ares_r/motion/native_execution_package.py', 'src/ares_r/motion/native_demo.py',
    'src/ares_r/motion/live_scene.py', 'src/ares_r/motion/live_state.py',
    'src/ares_r/motion/local_scene_service.py', 'src/ares_r/motion/tcp_orientation.py',
    'src/ares_r/motion/execution_tool_envelope.py', 'src/ares_r/motion/safety_kernel.py',
    'src/ares_r/motion/base_motion_observer.py', 'src/ares_r/motion/execution_candidate.py',
    'src/ares_r/perception/body_pointcloud.py', 'src/ares_r/perception/robot_collision.py',
    'src/ares_r/perception/robot_owned_filter.py', 'src/ares_r/perception/residual_cloud.py',
    'src/ares_r/perception/support_decomposition.py', 'src/ares_r/world/scene_compiler.py',
    'src/ares_r/adapters/epic.py', 'src/ares_r/adapters/epic_5700.py',
    'src/ares_r/adapters/jaka_sdk.py', 'src/ares_r/adapters/amr_http.py',
    'src/ares_r/webui/server.py', 'src/ares_r/webui/roundtrip_panel.js',
    'scripts/run_grasp_place_roundtrip.py', 'scripts/prepare_authorized_first_pick.py',
    'scripts/build_first_pick_execution_package.py', 'scripts/capture_manipulation_observation.py',
    'scripts/verify_authorized_first_pick.py', 'scripts/gripper_direct_once.py',
    'scripts/resume_confirmed_grasp_lift.py', 'scripts/finish_confirmed_lift_hold.py',
    'scripts/jaka_right_demo.cpp', 'scripts/p32_scan_scene.py',
    'scripts/build_p3_production_scene.py', 'scripts/audit_curobo_fk.py',
    'scripts/run_first_pick_demo.py', 'scripts/test_grasp_place_base_roundtrip.py',
    'src/ares_r/epic_pointcloud.py', 'scripts/epic_capture_service.py',
    'src/ares_r/adapters/epic_profiles.py', 'src/ares_r/adapters/epic_protocol.py',
    'src/ares_r/world_geometry.py', 'scripts/run_scene_aware_supervised.py',
    'src/ares_r/terminal.py', 'src/ares_r/cli.py', 'src/ares_r/task_runtime.py',
    'src/ares_r/task_studio.py', 'src/ares_r/demos/registry.py',
}


def text(node):
    return ast.unparse(node)


class Inventory(ast.NodeVisitor):
    def __init__(self, path):
        self.path = path
        self.scope = []
        self.symbols = []
        self.conditions = []
        self.raises = []
        self.waits = []

    def visit_ClassDef(self, node):
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node):
        name = '.'.join(self.scope + [node.name])
        self.symbols.append(dict(name=name, line=node.lineno, end_line=node.end_lineno,
                                 signature=text(node.args),
                                 calls=sorted(set(text(n.func) for n in ast.walk(node)
                                                  if isinstance(n, ast.Call)))))
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def record(self, target, node, expression):
        target.append(dict(symbol='.'.join(self.scope) or '<module>',
                           line=node.lineno, expression=expression))

    def visit_If(self, node):
        self.record(self.conditions, node, text(node.test))
        self.generic_visit(node)

    def visit_Raise(self, node):
        self.record(self.raises, node, text(node))
        self.generic_visit(node)

    def visit_Call(self, node):
        name = text(node.func)
        if (name.endswith(('sleep', 'wait', 'wait_for', 'urlopen', 'settimeout', 'flock'))
                or any(k.arg in ('timeout', 'timeout_s', 'max_nfev', 'deadline') for k in node.keywords)):
            self.record(self.waits, node, text(node))
        self.generic_visit(node)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.relative_to(ROOT / 'worklog')
    output.mkdir(parents=True, exist_ok=False)
    paths = set((ROOT / 'src/ares_r').rglob('*.py')) | set((ROOT / 'scripts').glob('*.py'))
    paths |= set((ROOT / 'scripts').glob('*.cpp')) | set((ROOT / 'src/ares_r/webui').glob('*.js'))
    paths |= set((ROOT / 'config').glob('*.json'))
    paths |= set((ROOT / 'demos/right_arm_grasp_place_roundtrip_v1').glob('*.json'))
    rows = []
    for path in sorted(paths):
        if ' 2.' in path.name or '__pycache__' in path.parts:
            continue
        rel = path.relative_to(ROOT).as_posix()
        raw = path.read_bytes()
        row = dict(path=rel, sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw),
                   critical=rel in CRITICAL)
        source = raw.decode('utf-8')
        if path.suffix == '.py':
            try:
                parsed = ast.parse(source)
                inv = Inventory(rel); inv.visit(parsed)
                row.update(symbols=inv.symbols, branch_conditions=inv.conditions,
                           explicit_raises=inv.raises, wait_and_timeout_calls=inv.waits)
                row['assignments'] = [dict(line=n.lineno, expression=text(n))
                    for n in parsed.body if isinstance(n, (ast.Assign, ast.AnnAssign))]
                row['imports'] = [dict(line=n.lineno, expression=text(n))
                    for n in ast.walk(parsed) if isinstance(n, (ast.Import, ast.ImportFrom))]
            except SyntaxError as exc:
                row['parse_error'] = str(exc)
        elif path.suffix in ('.cpp', '.js'):
            row['review_lines'] = [dict(line=i, expression=line.strip())
                for i, line in enumerate(source.splitlines(), 1)
                if re.search(r'throw |if\s*\(|sleep|deadline|servo_j|flock|fetch\(|disabled', line)]
        if row['critical']:
            snapshot = output / 'source_snapshot' / rel
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            snapshot.write_bytes(raw)
        rows.append(row)
    git = lambda *a: subprocess.check_output(['git', *a], cwd=ROOT, text=True).strip()
    data = dict(schema_version=1, audit_date='2026-10-17', network_access=False,
                source='LOCAL_WORKTREE_NOT_A_FRESH_DOT32_SNAPSHOT',
                git_head=git('rev-parse', 'HEAD'), branch=git('branch', '--show-current'),
                tracked_dirty=git('status', '--short', '--untracked-files=no').splitlines(),
                static_analysis_limit='Calls/conditions are candidates, not a dynamically proven execution graph.',
                files=rows)
    (output / 'source_inventory.json').write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
    catalog = ['# 本地代码函数和限制索引', '',
               '离线AST索引。每项分支不等于实际运行的安全门；仅critical文件进入冻结源码副本。', '']
    for row in rows:
        if not row['critical']:
            continue
        catalog += [f"## {row['path']}", '', f"SHA256 `{row['sha256']}`", '']
        for symbol in row.get('symbols', []):
            catalog.append(f"- `{symbol['name']}({symbol['signature']})` — L{symbol['line']}–{symbol['end_line']}")
        if row.get('review_lines'):
            catalog += ['', 'C++/JS检查位置：']
            catalog += [f"- L{x['line']}: `{x['expression'].replace('`', chr(39))}`" for x in row['review_lines']]
        catalog += ['']
    (output / 'FUNCTION_INDEX.md').write_text('\n'.join(catalog)+'\n')
    hashes = [f"{r['sha256']}  {r['path']}" for r in rows]
    (output / 'SOURCE_SHA256SUMS').write_text('\n'.join(hashes)+'\n')
    print(json.dumps(dict(files=len(rows), critical=sum(r['critical'] for r in rows),
                         functions=sum(len(r.get('symbols', [])) for r in rows),
                         conditions=sum(len(r.get('branch_conditions', [])) for r in rows),
                         raises=sum(len(r.get('explicit_raises', [])) for r in rows),
                         waits=sum(len(r.get('wait_and_timeout_calls', [])) for r in rows),
                         output=str(output)), ensure_ascii=False))


if __name__ == '__main__':
    main()
