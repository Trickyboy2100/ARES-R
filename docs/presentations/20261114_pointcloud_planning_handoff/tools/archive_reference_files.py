#!/usr/bin/env python3
"""Byte-exact reference-file archiving. No network, Git, PPT rewriting or device I/O.

This tool was written during a broken-runtime handoff and has NOT been executed
there. Run test_archive_reference_files.py before archiving production sources.
A .part file is not a standalone PowerPoint; unpack restores the exact original.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import BinaryIO, Any

BLOCK = 1024 * 1024


def safe_name(value: Any) -> str:
    if not isinstance(value, str) or not value or value in {'.', '..'}:
        raise ValueError('Invalid filename')
    if '/' in value or '\\' in value or '\x00' in value:
        raise ValueError('Manifest filename must be a basename')
    return value


def digest_ok(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def pack(source: Path, dest: Path, chunk_mib: int) -> None:
    source = source.resolve(strict=True)
    if not source.is_file():
        raise ValueError('Source must be a regular file')
    if not 1 <= chunk_mib <= 48:
        raise ValueError('Use a chunk size from 1 to 48 MiB')
    before = source.stat()
    if before.st_size == 0:
        raise ValueError('Refusing an empty source file')
    # Never replace an existing archive, and never modify the source.
    dest.mkdir(parents=True, exist_ok=False)
    all_hash = hashlib.sha256()
    parts: list[dict[str, Any]] = []
    total = 0
    with source.open('rb') as stream:
        number = 0
        while True:
            data = stream.read(chunk_mib * BLOCK)
            if not data:
                break
            number += 1
            name = f'part-{number:05d}.bin'
            with (dest / name).open('xb') as out:
                out.write(data)
            all_hash.update(data)
            total += len(data)
            parts.append({'file': name, 'size_bytes': len(data),
                          'sha256': hashlib.sha256(data).hexdigest()})
    after = source.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError('Source changed during read; archive is incomplete')
    if total != before.st_size:
        raise RuntimeError('Source byte count changed; archive is incomplete')
    manifest = {
        'schema_version': 1,
        'archive_type': 'byte_exact_parts',
        'original_filename': source.name,
        'size_bytes': total,
        'sha256': all_hash.hexdigest(),
        'chunk_mib': chunk_mib,
        'parts': parts,
        'note': 'Reassemble before opening. No masters, media or notes were rewritten.'
    }
    with (dest / 'manifest.json').open('x', encoding='utf-8') as out:
        json.dump(manifest, out, ensure_ascii=False, indent=2)
        out.write('\n')
    verify(dest)


def load_manifest(archive: Path) -> dict[str, Any]:
    with (archive / 'manifest.json').open(encoding='utf-8') as src:
        obj = json.load(src)
    if obj.get('schema_version') != 1 or obj.get('archive_type') != 'byte_exact_parts':
        raise ValueError('Unsupported archive schema')
    safe_name(obj.get('original_filename'))
    if not digest_ok(obj.get('sha256')):
        raise ValueError('Invalid overall SHA256')
    if not isinstance(obj.get('size_bytes'), int) or obj['size_bytes'] <= 0:
        raise ValueError('Invalid overall size')
    parts = obj.get('parts')
    if not isinstance(parts, list) or not parts:
        raise ValueError('No archive parts')
    seen: set[str] = set()
    for part in parts:
        if not isinstance(part, dict):
            raise ValueError('Invalid part record')
        name = safe_name(part.get('file'))
        if name in seen:
            raise ValueError('Duplicate part filename')
        seen.add(name)
        if not digest_ok(part.get('sha256')):
            raise ValueError('Invalid part SHA256')
        if not isinstance(part.get('size_bytes'), int) or part['size_bytes'] <= 0:
            raise ValueError('Invalid part size')
    return obj


def scan(archive: Path, obj: dict[str, Any], sink: BinaryIO | None = None) -> None:
    all_hash = hashlib.sha256()
    total = 0
    for part in obj['parts']:
        path = archive / part['file']
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'Missing or symlinked part: {part["file"]}')
        part_hash = hashlib.sha256()
        count = 0
        with path.open('rb') as src:
            while True:
                data = src.read(BLOCK)
                if not data:
                    break
                part_hash.update(data)
                all_hash.update(data)
                count += len(data)
                total += len(data)
                if sink is not None:
                    sink.write(data)
        if count != part['size_bytes'] or part_hash.hexdigest() != part['sha256']:
            raise ValueError(f'Corrupt archive part: {part["file"]}')
    if total != obj['size_bytes'] or all_hash.hexdigest() != obj['sha256']:
        raise ValueError('Overall checksum or byte count mismatch')


def verify(archive: Path) -> None:
    obj = load_manifest(archive)
    scan(archive, obj)
    print(f'VERIFIED {obj["original_filename"]}: {obj["size_bytes"]} bytes; SHA256={obj["sha256"]}')


def unpack(archive: Path, output: Path) -> None:
    obj = load_manifest(archive)
    output.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        with output.open('xb') as sink:
            created = True
            scan(archive, obj, sink)
    except Exception:
        # Only remove a partial output created by this invocation.
        if created:
            output.unlink(missing_ok=True)
        raise
    print(f'RESTORED {output}; SHA256={obj["sha256"]}')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('pack')
    p.add_argument('source', type=Path)
    p.add_argument('archive', type=Path)
    p.add_argument('--chunk-mib', type=int, default=40)
    p = sub.add_parser('verify')
    p.add_argument('archive', type=Path)
    p = sub.add_parser('unpack')
    p.add_argument('archive', type=Path)
    p.add_argument('output', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'pack':
            pack(args.source, args.archive, args.chunk_mib)
        elif args.command == 'verify':
            verify(args.archive)
        else:
            unpack(args.archive, args.output)
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
