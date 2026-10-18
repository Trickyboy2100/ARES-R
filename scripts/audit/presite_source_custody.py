"""Read-only source custody; no ARES imports, hardware APIs or network access.

Writes only beneath --output. Private tar files MUST NOT be published to GitHub.
"""
import argparse
from collections import Counter
import datetime
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tarfile


def git(root, *args, binary=False):
    p = subprocess.run(['git', '-C', str(root), *args], capture_output=True,
                       env=dict(os.environ, GIT_OPTIONAL_LOCKS='0'))
    if p.returncode:
        raise RuntimeError(p.stderr.decode(errors='replace'))
    return p.stdout if binary else p.stdout.decode(errors='surrogateescape')


def digest_file(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        while True:
            b = f.read(4 * 1024 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def bucket(rel):
    parts = Path(rel).parts
    if any(p in ('worklog', 'logs', 'capture_output', 'capture_output_fast',
                 'pointclouds', 'evidence', 'runtime', 'state') for p in parts):
        return 'data'
    if any(p in ('vendor', '.venv', 'venv', '__pycache__', '.pytest_cache',
                 'node_modules', '.mypy_cache') for p in parts):
        return 'dependencies_generated'
    return 'source'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--roots', nargs='+', required=True, type=Path)
    p.add_argument('--archive', action='store_true')
    a = p.parse_args()
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(out, 0o700)
    manifest = {'schema_version': 1, 'collected_at': datetime.datetime.now(
        datetime.timezone.utc).isoformat(), 'hardware_access': False,
        'scope': 'Supplied Mac roots; excludes .git internals (git bundles instead); '
                 'does not follow symlinks; no ARES code imports', 'repositories': []}
    for root in a.roots:
        root = root.resolve()
        ident = ('downloads-' if '/Downloads/' in str(root) else 'local-') + root.name
        tracked = set(git(root, 'ls-files', '-z').split('\0')) - {''}
        ignored = set(git(root, 'ls-files', '--others', '--ignored',
                          '--exclude-standard', '-z').split('\0')) - {''}
        changes = git(root, 'status', '--porcelain=v1', '-z', '--untracked-files=all')
        modified = set(git(root, 'diff', '--name-only', '-z', 'HEAD').split('\0')) - {''}
        repo = {'id': ident, 'root': str(root),
                'head': git(root, 'rev-parse', 'HEAD').strip(),
                'branch': git(root, 'branch', '--show-current').strip(),
                'worktrees': git(root, 'worktree', 'list', '--porcelain'),
                'status_porcelain': changes.replace('\0', '\n'),
                'files': [], 'errors': []}
        # Git remote URLs may contain credentials: retain private, not printed.
        d = out / 'git' / ident
        d.mkdir(parents=True, exist_ok=True)
        (d / 'remotes.private.txt').write_text(git(root, 'remote', '-v'))
        (d / 'worktree.patch').write_bytes(git(root, 'diff', '--binary', binary=True))
        (d / 'index.patch').write_bytes(git(root, 'diff', '--cached', '--binary', binary=True))
        (d / 'index_entries.txt').write_text(git(root, 'ls-files', '--stage'))
        # Bundle preserves committed refs, patches/tars preserve dirty bytes.
        if a.archive:
            bundle = d / 'all-refs.bundle'
            result = subprocess.run(['git', '-C', str(root), 'bundle', 'create',
                                     str(bundle), '--all'], capture_output=True)
            repo['git_bundle_ok'] = result.returncode == 0
            if result.returncode:
                repo['errors'].append('bundle: ' + result.stderr.decode(errors='replace'))
        archives = {}
        if a.archive:
            for kind in ('source', 'data', 'dependencies_generated'):
                dest = out / 'bundles' / (ident + '.' + kind + '.tar.gz')
                dest.parent.mkdir(exist_ok=True)
                archives[kind] = tarfile.open(dest, 'w:gz', compresslevel=1)
        try:
            for parent, dirs, files in os.walk(root, followlinks=False):
                dirs[:] = sorted(x for x in dirs if x != '.git')
                # Preserve directory symlinks without traversing their targets.
                links = [x for x in dirs if (Path(parent) / x).is_symlink()]
                dirs[:] = [x for x in dirs if x not in links]
                for name in sorted(files + links):
                    if name == '.git':
                        continue
                    path = Path(parent) / name
                    rel = str(path.relative_to(root))
                    row = {'path': rel, 'classification': ('TRACKED_MODIFIED' if rel in modified
                           else 'TRACKED' if rel in tracked else 'IGNORED' if rel in ignored
                           else 'UNTRACKED'), 'bundle': bucket(rel)}
                    try:
                        before = path.lstat()
                        row.update(size=before.st_size, mtime_ns=before.st_mtime_ns,
                                   mode=stat.S_IMODE(before.st_mode))
                        if getattr(before, 'st_flags', 0) & 0x40000000:
                            row.update(type='dataless_placeholder',
                                       error='iCloud/provider bytes not resident; not hydrated or guessed')
                            repo['errors'].append(rel + ': NONRESIDENT_BYTES')
                        elif path.is_symlink():
                            row.update(type='symlink', target=os.readlink(path))
                            row['sha256'] = hashlib.sha256(os.fsencode(row['target'])).hexdigest()
                        elif path.is_file():
                            row.update(type='file', sha256=digest_file(path))
                        else:
                            row['type'] = 'special_not_archived'
                        if a.archive and row['type'] in ('file', 'symlink'):
                            archives[row['bundle']].add(path, arcname=rel, recursive=False)
                        after = path.lstat()
                        row['stable_during_capture'] = (
                            before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
                    except Exception as exc:
                        row['error'] = str(exc)
                        repo['errors'].append(rel + ': ' + str(exc))
                    repo['files'].append(row)
        finally:
            for arc in archives.values():
                arc.close()
        present = {r['path'] for r in repo['files']}
        repo['tracked_missing'] = sorted(tracked - present)
        repo['counts'] = dict(Counter(x['classification'] for x in repo['files']))
        manifest['repositories'].append(repo)
        save(out / 'SOURCE_CUSTODY_MANIFEST.json', manifest)
        print(ident, repo['head'][:12], len(repo['files']), repo['counts'], flush=True)
    # Derive exact remote SHA256 from Git blob bytes, never from Git SHA1 alone.
    for branch in ('integration', 'audit'):
        tree_file = out / 'remote' / (branch + '_tree.json')
        if not tree_file.exists():
            continue
        tree = json.loads(tree_file.read_text())
        blobs = {r['sha'] for r in tree['tree'] if r['type'] == 'blob'}
        resolved = {}
        for root in a.roots:
            remaining = sorted(blobs - resolved.keys())
            if not remaining:
                break
            inp = ('\n'.join(remaining) + '\n').encode()
            check = subprocess.run(['git', '-C', str(root), 'cat-file', '--batch-check'],
                                   input=inp, capture_output=True).stdout.decode().splitlines()
            available = [line.split()[0] for line in check if ' blob ' in line]
            if not available:
                continue
            proc = subprocess.Popen(['git', '-C', str(root), 'cat-file', '--batch'],
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            for sha in available:
                proc.stdin.write((sha + '\n').encode()); proc.stdin.flush()
                header = proc.stdout.readline().decode().split()
                size = int(header[2]); data = proc.stdout.read(size); proc.stdout.read(1)
                resolved[sha] = hashlib.sha256(data).hexdigest()
            proc.stdin.close(); proc.wait()
        # Audit source snapshots exist locally, even if their git objects do not.
        by_blob = {}
        for repo in manifest['repositories']:
            for row in repo['files']:
                if row.get('type') != 'file' or row.get('size', 0) > 8 * 1024 * 1024:
                    continue
                data = (Path(repo['root']) / row['path']).read_bytes()
                sha = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
                if sha in blobs and sha not in resolved:
                    by_blob[sha] = row['sha256']
        resolved.update(by_blob)
        comparisons = []
        remote = {r['path']: resolved.get(r['sha']) for r in tree['tree'] if r['type'] == 'blob'}
        for repo in manifest['repositories']:
            for row in repo['files']:
                sha = remote.get(row['path'])
                comparisons.append({'repository': repo['id'], 'path': row['path'],
                    'local_sha256': row.get('sha256'), 'remote_sha256': sha,
                    'comparison': ('ABSENT_REMOTE' if row['path'] not in remote else
                                   'REMOTE_BYTES_UNAVAILABLE' if sha is None else
                                   'IDENTICAL' if sha == row.get('sha256') else 'DIFFERENT')})
            local = {r['path'] for r in repo['files']}
            for path in remote.keys() - local:
                comparisons.append({'repository': repo['id'], 'path': path,
                                    'remote_sha256': remote[path], 'comparison': 'ABSENT_LOCAL'})
        save(out / 'remote' / (branch + '_sha256.json'), {'head': tree['head'],
             'paths': remote, 'unresolved_blobs': sorted(blobs - resolved.keys())})
        save(out / (branch.upper() + '_FILE_COMPARISON.json'), comparisons)
        print(branch, 'resolved blobs', len(resolved), '/', len(blobs), flush=True)
    checks = []
    for folder in ('bundles', 'git'):
        for path in sorted((out / folder).rglob('*')):
            if path.is_file():
                checks.append(digest_file(path) + '  ' + str(path.relative_to(out)))
    (out / 'PRIVATE_ARCHIVE_SHA256SUMS').write_text('\n'.join(checks) + '\n')
    print('COMPLETE', out, flush=True)


if __name__ == '__main__':
    main()
