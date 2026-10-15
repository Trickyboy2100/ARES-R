#!/usr/bin/env bash
set -euo pipefail

EXPECTED="69c10d90cdcc5483c70409404bb80bb50bf9ee00700d677ecbe9b138b49c8964"
ARCHIVE="${1:-}"

if [[ -z "$ARCHIVE" || ! -f "$ARCHIVE" ]]; then
  echo "usage: $0 /path/to/ARES-R_2026-10-12_Preland_Planning_Records_REAL_ALIGNED.tar.gz" >&2
  exit 2
fi

if command -v sha256sum >/dev/null 2>&1; then
  ACTUAL="$(sha256sum "$ARCHIVE" | awk '{print $1}')"
else
  ACTUAL="$(shasum -a 256 "$ARCHIVE" | awk '{print $1}')"
fi

if [[ "$ACTUAL" != "$EXPECTED" ]]; then
  echo "archive SHA256 mismatch: expected=$EXPECTED actual=$ACTUAL" >&2
  exit 1
fi

gzip -t "$ARCHIVE"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
tar -xzf "$ARCHIVE" -C "$TMP_DIR"
ROOT="$TMP_DIR/ARES-R_2026-10-12_Preland_Planning_Records"

if [[ ! -f "$ROOT/real_aligned_sources/SHA256SUMS.txt" ]]; then
  echo "missing real_aligned_sources/SHA256SUMS.txt" >&2
  exit 1
fi

if command -v sha256sum >/dev/null 2>&1; then
  (cd "$ROOT" && sha256sum -c real_aligned_sources/SHA256SUMS.txt)
else
  (cd "$ROOT" && shasum -a 256 -c real_aligned_sources/SHA256SUMS.txt)
fi

echo "ARES-R real-aligned archive verification: PASS"
