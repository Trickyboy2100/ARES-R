#!/usr/bin/env python3
"""Supervised AMR in-place rotation probe.

Sends ONE relative move through the real commissioned adapter path and watches
`/openapi/robot/status` while it runs, so an observed rotation can be attributed
to the command and not to the map-pose drift this robot is known to have
(localization confidence sits near 40%).

Dry-run by default.  Moving the base additionally requires ``--enable-hardware``
and the exact confirmation phrase printed on screen, mirroring the Terminal
guard, and ``GET /control/stop`` is sent as soon as the observed rotation
exceeds ``--abort-deg``.

    PYTHONPATH=src python3 scripts/probe_amr_rotation.py --yaw-deg -30
    PYTHONPATH=src python3 scripts/probe_amr_rotation.py --yaw-deg -30 \\
        --enable-hardware --confirm "PROBE AMR ROTATION -30"

Evidence: `docs/AMR_MOTION_ROTATION_COMMISSIONING_2026-09-21.md`.
"""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from unittest.mock import patch

import ares_r.adapters.amr_http as amr_http
from ares_r.adapters.amr_http import AmrHttpBase

REPOSITORY = Path(__file__).resolve().parents[1]
POLL_S = 0.25


class _Capture:
    """Stands in for urlopen so dry-run prints the exact payload on the wire."""

    status = 200

    def __init__(self):
        self.request = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return b'{"status":3}'


def _pose(base):
    info = base._request("GET", "/robot/status")["info"]
    return float(info["x"]), float(info["y"]), float(info["yawNumber"])


def _phrase(args):
    return "PROBE AMR ROTATION %g" % args.yaw_deg


def _dry_run(base, args):
    capture = _Capture()
    with patch.object(amr_http, "urlopen", side_effect=lambda request, timeout: capture) as opened:
        try:
            base.move_relative(args.x_m, args.y_m, args.yaw_deg, args.linear_mps,
                               args.angular_radps, args.timeout_s)
        except ValueError as exc:
            print("DRY RUN: rejected by the configured envelope -> %s" % exc)
            return 1
        capture.request = opened.call_args.args[0]
    print("DRY RUN: nothing was sent.")
    print("  method : POST")
    print("  url    : %s" % capture.request.full_url)
    print("  body   : %s" % capture.request.data.decode())
    print("  boundary: |delta yaw| > %.1f deg triggers GET /control/stop" % args.abort_deg)
    print("  to execute: --enable-hardware --confirm \"%s\"" % _phrase(args))
    return 0


def _run(base, args):
    if args.confirm != _phrase(args):
        print("Refusing to move: type --confirm \"%s\" exactly." % _phrase(args))
        return 2

    before = []
    started = time.time()
    while time.time() - started < args.baseline_s:
        before.append(_pose(base))
        time.sleep(POLL_S)
    yaw0 = statistics.median([item[2] for item in before[-8:]])

    response = base.move_relative(args.x_m, args.y_m, args.yaw_deg, args.linear_mps,
                                  args.angular_radps, args.timeout_s)
    print("accepted: %s" % json.dumps(response))

    after = []
    aborted = False
    started = time.time()
    while time.time() - started < args.max_wait_s:
        after.append(_pose(base))
        delta = after[-1][2] - yaw0
        if abs(delta) > args.abort_deg:
            aborted = True
            break
        time.sleep(POLL_S)
    stop = base.stop()

    deltas = [item[2] - yaw0 for item in after]
    evidence = {
        "requested_yaw_deg": args.yaw_deg,
        "x_m": args.x_m, "y_m": args.y_m,
        "baseline_yaw_deg": yaw0,
        "observed_peak_delta_deg": max(deltas, key=abs) if deltas else None,
        "observed_settled_delta_deg": statistics.median(deltas[-4:]) if deltas else None,
        "abort_tripped": aborted,
        "stop_response": stop,
        "samples": len(after),
    }
    path = REPOSITORY / "logs" / ("amr_rotation_probe_%s.json" % time.strftime("%Y%m%d-%H%M%S"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence, indent=2, sort_keys=True))
    print("RESULT %s" % json.dumps(evidence, sort_keys=True))
    print("evidence: %s" % path)
    return 1 if aborted else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--yaw-deg", type=float, required=True,
                        help="degrees; negative is clockwise (measured 2026-09-21)")
    parser.add_argument("--x-m", type=float, default=0.0)
    parser.add_argument("--y-m", type=float, default=0.0)
    parser.add_argument("--linear-mps", type=float, default=0.2)
    parser.add_argument("--angular-radps", type=float, default=0.2, help="rad/s, not degrees")
    parser.add_argument("--timeout-s", type=float, default=60.0)
    parser.add_argument("--abort-deg", type=float, default=35.0)
    parser.add_argument("--baseline-s", type=float, default=8.0)
    parser.add_argument("--max-wait-s", type=float, default=40.0)
    parser.add_argument("--enable-hardware", action="store_true")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()

    config = json.loads((REPOSITORY / "config" / "system.json").read_text())
    base = AmrHttpBase(config["base"])
    return _dry_run(base, args) if not args.enable_hardware else _run(base, args)


if __name__ == "__main__":
    sys.exit(main())
