"""Produce offline custody reports from hashes only; never import robot code."""
import difflib
import hashlib
import json
from pathlib import Path

BASE = Path('/Users/andyee/Documents/ChatGPT/local')
PRIVATE = BASE / 'presite-20261018-private'
RELEASE = BASE / 'ARES-R-release-candidate-20261018'


def main():
    m = json.loads((PRIVATE / 'SOURCE_CUSTODY_MANIFEST.json').read_text())
    roots = {r['id']: r for r in m['repositories']}
    maps = {r['id']: {f['path']: f for f in r['files']} for r in m['repositories']}
    for name in ('production_scene_worker.py', 'latency_solver.py',
                 'persistent_planner_service.py', 'planner_service_client.py',
                 'independent_path_validation.py'):
        rel = 'src/ares_r/motion/' + name
        a = BASE / 'ARES-R-offsets-20261016' / rel
        b = BASE / 'ARES-R-operations-20261015' / rel
        diff = ''.join(difflib.unified_diff(a.read_text().splitlines(True),
                   b.read_text().splitlines(True), fromfile='offsets/' + rel,
                   tofile='operations/' + rel))
        dest = PRIVATE / 'diffs' / (name + '.diff')
        dest.parent.mkdir(exist_ok=True)
        dest.write_text(diff)
    canonical = json.loads((PRIVATE / 'remote/integration_sha256.json').read_text())
    audit = json.loads((PRIVATE / 'remote/audit_sha256.json').read_text())
    paths = [
        'src/ares_r/webui/index.html', 'src/ares_r/webui/operations.html',
        'src/ares_r/webui/operations.js', 'src/ares_r/webui/roundtrip_panel.js',
        'src/ares_r/webui/server.py', 'src/ares_r/canonical_backend.py',
        'src/ares_r/demos/roundtrip_launcher.py',
        'src/ares_r/manipulation/roundtrip_demo.py',
        'scripts/run_grasp_place_roundtrip.py',
        'scripts/build_first_pick_execution_package.py',
        'scripts/prepare_authorized_first_pick.py',
        'scripts/verify_authorized_first_pick.py',
        'scripts/resume_confirmed_grasp_lift.py', 'scripts/finish_confirmed_lift_hold.py',
        'config/grasp_place_base_route.json', 'config/planner_latency_profiles.json',
        'demos/right_arm_grasp_place_roundtrip_v1/demo.json',
        'demos/right_arm_grasp_place_roundtrip_v1/parameters.json',
        'src/ares_r/motion/production_scene_worker.py',
        'src/ares_r/motion/latency_solver.py', 'src/ares_r/motion/cpu_distance.py',
        'src/ares_r/motion/native_execution_package.py',
        'src/ares_r/motion/native_demo.py',
        'src/ares_r/motion/planner_service_client.py',
        'src/ares_r/motion/persistent_planner_service.py',
        'scripts/jaka_right_demo.cpp', 'tests/test_roundtrip_demo.py',
        'tests/test_roundtrip_launcher.py', 'tests/test_latency_solver.py',
        'deploy/systemd/ares-r-backend.service', 'deploy/systemd/ares-r-webui.service',
        'scripts/run_first_pick_demo.py', 'demos/right_arm_epic_pick_lift_v1/demo.json',
        'pyproject.toml', 'config/system.json', 'config/robot_collision_model.json',
        'config/jaka_tools.site.json', 'config/jaka_mini2_motion.site.json']
    critical = []
    for path in paths:
        row = {'path': path, 'mac': {}, 'integration_sha256': canonical['paths'].get(path),
               'audit_root_sha256': audit['paths'].get(path),
               'audit_snapshot_sha256': audit['paths'].get(
                   'worklog/audits/2026-10-17-roundtrip-offline/source_snapshot/' + path),
               'site_effective_sha256': None}
        for key, lookup in maps.items():
            if path in lookup:
                f = lookup[path]
                row['mac'][key] = {k: f.get(k) for k in ('sha256', 'classification', 'type', 'size')}
        critical.append(row)
    (PRIVATE / 'CRITICAL_RUNTIME_FILE_MATRIX.json').write_text(json.dumps(critical, indent=2) + '\n')
    lines = ['# Mac worktree custody / diff report', '',
             '2026-10-18. Source custody only; not a runnable release or deployed build.', '',
             '| Worktree | HEAD | tracked modified | untracked | ignored | nonresident |',
             '|---|---|---:|---:|---:|---:|']
    for r in m['repositories']:
        c = r['counts']
        lines.append('| %s | `%s` | %d | %d | %d | %d |' % (r['id'], r['head'][:12],
            c.get('TRACKED_MODIFIED', 0), c.get('UNTRACKED', 0), c.get('IGNORED', 0),
            sum(x.get('type') == 'dataless_placeholder' for x in r['files'])))
    lines += ['', '## Remote byte SHA256 coverage', '']
    for key in ('integration', 'audit'):
        v = json.loads((PRIVATE / 'remote' / (key + '_sha256.json')).read_text())
        lines.append('- %s `%s`: %d paths; %d unresolved blobs.' % (
            key, v['head'], len(v['paths']), len(v['unresolved_blobs'])))
    lines += ['', '## Critical runtime bytes', '',
              'Full hashes and all worktrees: private CRITICAL_RUNTIME_FILE_MATRIX.json.', '',
              '| Path | offsets | operations | GitHub integration | audit snapshot |',
              '|---|---|---|---|---|']
    for row in critical:
        def short(value):
            return '`' + value[:12] + '`' if value else 'MISSING'
        lines.append('| `%s` | %s | %s | %s | %s |' % (row['path'],
            short(row['mac'].get('local-ARES-R-offsets-20261016', {}).get('sha256')),
            short(row['mac'].get('local-ARES-R-operations-20261015', {}).get('sha256')),
            short(row['integration_sha256']), short(row['audit_snapshot_sha256'])))
    lines += ['', '## Exact FAST differences', '',
        '- offsets worker keeps cuboid_capacity buckets in runtime cache key; operations does not.',
        '- operations parses solver_policy, uses solve_single_pass, caps goal candidates, uses native CPU distance and skips FAST baseline diagnostics.',
        '- operations latency_contract is evaluated after solve; this is not active cancellation.',
        '- both still contain warmup and benchmark_runs loops; effective request values must be verified.',
        '- no source was selected or merged in this custody phase; neither filename nor HEAD proves site-loaded bytes.',
        '- exact patches for five planner modules are retained privately, with both full source archives.', '',
        '## Custody boundaries', '',
        'Private tar archives are partitioned into source / data / dependencies_generated. Git bundles and both index/worktree patches preserve committed and dirty histories. Nonresident placeholders are inventoried but bytes are not claimed. No owner attribution is inferred from dirty status. No production sources edited, no motion, no public raw uploads.',
        'Search scope: 12 repositories discovered beneath Documents/ChatGPT/local and Downloads; no PSSD mounted and no .codex/worktrees Git checkout found. Parent local/.git is unborn, not an ARES runtime repository. Newly created RC checkout is an output, not an input.',
        'Sparse archive checkout may have skip-worktree entries absent on disk; git bundle preserves committed objects. tracked_missing does not by itself mean user deletion.']
    (PRIVATE / 'MAC_WORKTREE_DIFF_REPORT.md').write_text('\n'.join(lines) + '\n')
    unknown = ['# Unresolved file origins', '',
        '- Site effective scripts, loaded Python module SHAs, systemd install bytes and native/SDK binaries: NOT RETRIEVED.',
        '- Dirty file author cannot be established from Git status. Coworker AMR edits not merged or attributed.',
        '- .32 Oct16 per-request worker revision cannot be inferred from local file names.',
        '- 41 offsets duplicate files were nonresident at capture (see exact manifest); no guessed hashes.',
        '- Existing September/Oct12 pointclouds are not substituted for Oct16 pick/post-grasp scenes.',
        '- Legacy site config/asset pins do not prove currently installed package versions.', '']
    for r in m['repositories']:
        for f in r['files']:
            if f.get('type') == 'dataless_placeholder':
                unknown.append('- NONRESIDENT `%s/%s`' % (r['id'], f['path']))
    (PRIVATE / 'UNRESOLVED_FILE_ORIGINS.md').write_text('\n'.join(unknown) + '\n')
    # Search every inventoried filename, rather than only a preferred folder.
    tokens = ['web_1792140369955017446', 'web_1792141460049419632',
              'web_1792142393480633163', 'confirmed_lift_', 'finish_hold_',
              'PLAN_998c1812d2ff462e934e5872c1079a3c',
              'PLAN_5fac3267121c41dba683bc9b043823b5',
              'PLAN_b570ced607b64a5e981b15c67ab9d68b']
    matches = {token: [{'repository': r['id'], 'path': f['path'], 'sha256': f.get('sha256')}
                       for r in m['repositories'] for f in r['files'] if token in f['path']]
               for token in tokens}
    (PRIVATE / 'OCT16_RAW_PATH_SEARCH.json').write_text(json.dumps(matches, indent=2) + '\n')
    print('reports generated', len(critical), 'critical paths',
          sum(len(v) for v in matches.values()), 'raw path matches')


if __name__ == '__main__':
    main()
