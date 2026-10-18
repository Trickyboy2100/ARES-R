#!/usr/bin/env python3
"""One-shot read/write for the configured right Inspire gripper, no pyserial."""

import argparse
import json
import os
from pathlib import Path
import select
import struct
import termios
import time

ROOT = Path(__file__).resolve().parents[1]


def frame(device_id, command, data=b""):
    body = bytes([device_id, len(data) + 1, command]) + data
    return b"\xeb\x90" + body + bytes([sum(body) & 0xff])


def exchange(port, payload, expected):
    fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        attrs = termios.tcgetattr(fd)
        attrs[0] = attrs[1] = attrs[3] = 0
        attrs[2] = termios.CS8 | termios.CLOCAL | termios.CREAD
        attrs[4] = attrs[5] = termios.B115200
        attrs[6][termios.VMIN] = 0; attrs[6][termios.VTIME] = 0
        termios.tcsetattr(fd, termios.TCSANOW, attrs); termios.tcflush(fd, termios.TCIOFLUSH)
        os.write(fd, payload); response = b""; deadline = time.monotonic() + 1.0
        while len(response) < expected and time.monotonic() < deadline:
            ready, _, _ = select.select([fd], [], [], max(0, deadline - time.monotonic()))
            if ready:
                response += os.read(fd, expected - len(response))
        if len(response) != expected:
            raise RuntimeError("gripper response length %d expected %d" % (len(response), expected))
        return response
    finally:
        os.close(fd)


def main():
    p = argparse.ArgumentParser(); p.add_argument("action", choices=("read", "move"))
    p.add_argument("--raw", type=int); a = p.parse_args()
    cfg = json.loads((ROOT / "config/system.json").read_text())["grippers"]["right"]
    port = cfg["port"]; device = int(cfg.get("device_id", 1))
    if a.action == "move":
        if a.raw is None or not int(cfg["min_position"]) <= a.raw <= int(cfg["max_position"]):
            raise ValueError("valid --raw required")
        response = exchange(port, frame(device, 0x54, struct.pack("<H", a.raw)), 7)
        time.sleep(.3)
    else:
        response = None
    readback = exchange(port, frame(device, 0xD9), 8)
    position = (readback[-2] << 8) | readback[-3]
    print(json.dumps({"action": a.action, "command_raw": a.raw,
                      "position_raw": position,
                      "response_hex": response.hex() if response else None,
                      "readback_hex": readback.hex()}))


if __name__ == "__main__":
    main()
