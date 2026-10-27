#!/usr/bin/env python3
"""Export and authenticate user-authorized GRASP archives, without checkout/merge."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import tarfile

COMMIT = 'dc70016a8fc95d8d0e6efb52ef935d5cec9d408e'
DIRECTORY = 'worklog/evidence/2026-10-21-grasp-source-data/'

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    def export(name):
        content = subprocess.check_output(['git', 'show', COMMIT + ':' + DIRECTORY + name])
        target = args.output / name
        if target.exists() and target.read_bytes() != content:
            raise RuntimeError('Refusing to replace different source: ' + str(target))
        target.write_bytes(content)
        return target
    for name in ['README.md', 'PUBLICATION.md', 'SHA256SUMS', 'DATA_INDEX.json']:
        export(name)
    index = json.loads((args.output / 'DATA_INDEX.json').read_text())
    receipt = {'source_commit': COMMIT, 'archives': [], 'no_hardware_access': True}
    for item in index['archives']:
        target = export(item['name'])
        assert target.stat().st_size == item['bytes']
        assert hashlib.sha256(target.read_bytes()).hexdigest() == item['sha256']
        with tarfile.open(target) as archive:
            for member in archive.getmembers():
                path = PurePosixPath(member.name)
                assert not path.is_absolute() and '..' not in path.parts
                assert member.isfile() or member.isdir()
            # Source export is deterministic; never overwrite existing extracted files.
            unpacked = args.output / 'unpacked'
            for member in archive.getmembers():
                if member.isfile() and (unpacked / member.name).exists():
                    assert (unpacked / member.name).read_bytes() == archive.extractfile(member).read()
            archive.extractall(unpacked, filter='data')
        receipt['archives'].append({**item, 'verified': True})
    (args.output / 'RECEIPT.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))

if __name__ == '__main__':
    main()
