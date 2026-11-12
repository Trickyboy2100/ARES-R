#!/usr/bin/env python3
"""Download pinned official cuRobo code/configs without unrelated large robot assets.

Every file is checked against its Git blob SHA. Dedicated destination only.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import time
import urllib.request

REVISION = "8e734f3ced1df898990bcd92de40abce475907db"


def read(url):
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=20) as response:
                return response.read()
        except Exception as exc:
            last = exc
            time.sleep(attempt + 1)
    raise last


def wanted(path):
    return (path in ("pyproject.toml", "setup.py", "README.md", "LICENSE", "LICENSE_ASSETS")
            or path.startswith("curobo/_src/") or path.startswith("curobo/content/configs/")
            or (path.startswith("curobo/content/") and path.endswith(".py"))
            or (path.startswith("curobo/") and path.count("/") == 1))


def blob_hash(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    root = args.directory.resolve()
    root.mkdir(parents=True, exist_ok=True)
    tree = json.loads(read("https://api.github.com/repos/NVlabs/curobo/git/trees/%s?recursive=1" % REVISION))
    if tree.get("truncated"):
        raise RuntimeError("GitHub tree truncated")
    files = [item for item in tree["tree"] if item["type"] == "blob" and wanted(item["path"])]
    def fetch(item):
        path = root / item["path"]
        if root not in path.resolve().parents:
            raise RuntimeError("invalid upstream path")
        if path.is_file() and blob_hash(path.read_bytes()) == item["sha"]:
            return
        data = read("https://raw.githubusercontent.com/NVlabs/curobo/%s/%s" % (REVISION, item["path"]))
        if blob_hash(data) != item["sha"]:
            raise RuntimeError("Git blob mismatch: %s" % item["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(fetch, item) for item in files]
        for count, future in enumerate(as_completed(futures), 1):
            future.result()
            if count % 25 == 0:
                print("Verified %d/%d files" % (count, len(files)), flush=True)
    (root / "ARES_R_SOURCE_MANIFEST.json").write_text(json.dumps({"commit": REVISION, "files": files}, indent=2))
    print("Verified source complete:", root, flush=True)


if __name__ == "__main__":
    main()
