"""Verify private archives against original byte hashes, without extraction."""
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile

ROOT = Path('/Users/andyee/Documents/ChatGPT/local/presite-20261018-private')


def main():
    m = json.loads((ROOT / 'SOURCE_CUSTODY_MANIFEST.json').read_text())
    result = {'hardware_access': False, 'archives': [], 'bundles': [],
              'errors': [], 'original_tree_changed_paths': []}
    for repo in m['repositories']:
        for kind in ('source', 'data', 'dependencies_generated'):
            path = ROOT / 'bundles' / (repo['id'] + '.' + kind + '.tar.gz')
            expected = {f['path']: f for f in repo['files']
                        if f.get('type') in ('file', 'symlink') and f['bundle'] == kind}
            seen = set()
            with tarfile.open(path, 'r:gz') as archive:
                for member in archive:
                    row = expected.get(member.name)
                    if row is None:
                        result['errors'].append('unexpected member ' + member.name)
                        continue
                    h = hashlib.sha256()
                    if member.issym():
                        h.update(member.linkname.encode())
                    else:
                        stream = archive.extractfile(member)
                        while True:
                            data = stream.read(4 * 1024 * 1024)
                            if not data:
                                break
                            h.update(data)
                    if h.hexdigest() != row['sha256']:
                        result['errors'].append(repo['id'] + '/' + member.name + ': sha mismatch')
                    seen.add(member.name)
            if seen != set(expected):
                result['errors'].append(str(path) + ': member count mismatch')
            result['archives'].append({'path': str(path), 'verified_members': len(seen)})
        bundle = ROOT / 'git' / repo['id'] / 'all-refs.bundle'
        if bundle.exists():
            p = subprocess.run(['git', '-C', repo['root'], 'bundle', 'verify', str(bundle)],
                               capture_output=True)
            result['bundles'].append({'repository': repo['id'], 'verified': p.returncode == 0})
            if p.returncode:
                result['errors'].append(repo['id'] + ': bundle verification failed')
        # Compare original status (no imports, no task run) to custody snapshot.
        p = subprocess.run(['git', '-C', repo['root'], 'status', '--porcelain=v1',
                            '-z', '--untracked-files=all'], capture_output=True,
                            env={'PATH': '/usr/bin:/bin', 'GIT_OPTIONAL_LOCKS': '0'})
        if p.stdout.decode(errors='surrogateescape').replace('\0', '\n') != repo['status_porcelain']:
            result['original_tree_changed_paths'].append(repo['id'])
    result['pass'] = not result['errors'] and not result['original_tree_changed_paths']
    (ROOT / 'CUSTODY_VERIFICATION.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'pass': result['pass'], 'archives': len(result['archives']),
        'bundles': len(result['bundles']), 'members': sum(x['verified_members'] for x in result['archives']),
        'errors': result['errors'], 'changed_trees': result['original_tree_changed_paths']}))
    if not result['pass']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
