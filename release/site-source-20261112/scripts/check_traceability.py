#!/usr/bin/env python3
"""Fail when implementation changes have no corresponding work record."""

import argparse
import subprocess
import sys


def changed_files(mode: str):
    command = ["git", "diff", "--name-only", "--cached"] if mode == "staged" else ["git", "diff", "--name-only", "origin/main...HEAD"]
    return [line for line in subprocess.check_output(command, text=True).splitlines() if line]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["staged", "branch"], default="staged")
    args = parser.parse_args()
    files = changed_files(args.mode)
    implementation = any(path.startswith(("src/", "config/", "scripts/", "tests/", "ros_ws/")) for path in files)
    trace = any(path.startswith(("worklog/daily/", "docs/adr/")) for path in files)
    if implementation and not trace:
        print("Traceability check failed: implementation changed without a worklog/daily or docs/adr entry.")
        return 1
    print("Traceability check passed (%d changed files)." % len(files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
