# Source delivery validation — 2026-10-18

- Canonical and alternate files are byte-preserved from the source trees listed
  in SOURCE_MANIFEST.json; all 423 source/variant SHA256 entries matched locally.
- Golden first-pick hashes remain unchanged.
- No real device calls, GPU solve, service startup or execute command was used.
- Mac Python is 3.14. `test_roundtrip*.py` discovery ran 13 entries: 12 tests
  passed; test_roundtrip_launcher failed to import because NumPy is not installed
  in this interpreter. This is **not** a full test-suite PASS or GPU validation.
- No environment packages were installed just to publish source. Ubuntu must use
  the pinned compatible offline environment and rerun tests/replays.
- Existing frozen audit snapshots and exact unified diffs retain their original
  whitespace; they are not reformatted to satisfy diff whitespace checks.
- This upload excludes raw pointclouds, private site logs, credentials and vendor
  binaries. Original source working trees were not staged, reset or changed.
