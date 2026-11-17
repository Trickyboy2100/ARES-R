#!/usr/bin/env python3
"""Preserve a stale owned planner socket before a managed service starts."""
import argparse
import os
from pathlib import Path
import socket
import stat
import time


def prepare(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        return
    metadata = path.lstat()
    if metadata.st_uid != os.getuid() or not stat.S_ISSOCK(metadata.st_mode):
        raise RuntimeError("planner path is not an owned socket")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(2)
        try:
            client.connect(str(path))
        except ConnectionRefusedError:
            path.rename(path.with_name("planner-stale-" + str(time.time_ns()) + ".sock"))
            return
        except FileNotFoundError:
            return
    raise RuntimeError("planner socket already has a live listener")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("socket_path", type=Path)
    prepare(parser.parse_args().socket_path)
