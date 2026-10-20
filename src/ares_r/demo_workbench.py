"""Offline preparation shared by ART and WebUI. No device adapter imports."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[2]
PAGE = Path(__file__).with_name("webui") / "workbench.html"
SLOTS = tuple(f"{level}_{side}" for level in ("lower", "upper")
              for side in ("left", "middle", "right"))


def load(path):
    return json.loads(Path(path).read_text())


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def station_catalog(root=ROOT):
    """Aliases reference the current route, never the historical September move."""
    root = Path(root)
    route = load(root / "config/grasp_place_base_route.json")
    return {
        "schema_version": 1, "revision": digest(route),
        "stations": [
            {"id": "SCALE_FRONT", "name": "称前站", "alias": "GRASP", "slam_pose": None},
            {"id": "DRYER_FRONT", "name": "烘干机前站", "alias": "PLACE", "slam_pose": None}],
        "routes": copy.deepcopy(route["routes"]),
        "source_revision": route["revision"],
        "historical_registry": "config/manipulation_stations.json",
        "historical_registry_migrated": False,
        "execution_enabled": False,
    }


def task_draft(direction, slots, occupancy, root=ROOT):
    """Build reviewable intent only; never assume observed or reserved state."""
    if direction not in ("SCALE_TO_DRYER", "DRYER_TO_SCALE"):
        raise ValueError("unknown transfer direction")
    if not slots or len(slots) > 6 or len(set(slots)) != len(slots):
        raise ValueError("select one to six distinct slots")
    if any(s not in SLOTS for s in slots):
        raise ValueError("unknown slot")
    required = "EMPTY" if direction == "SCALE_TO_DRYER" else "OCCUPIED"
    blockers, transfers = [], []
    for slot in slots:
        if occupancy.get(slot, "UNKNOWN") != required:
            blockers.append(f"{slot}: requires {required}; currently {occupancy.get(slot, 'UNKNOWN')}")
        transfers.append({
            "source_station": "SCALE_FRONT" if direction == "SCALE_TO_DRYER" else "DRYER_FRONT",
            "destination_station": "DRYER_FRONT" if direction == "SCALE_TO_DRYER" else "SCALE_FRONT",
            "slot_id": slot,
            "operation": "PLACE" if direction == "SCALE_TO_DRYER" else "PICK",
            "requires_reservation": True, "requires_fresh_observation": True,
            "requires_verified_completion": True,
            "requires_scale_source_replenishment": direction == "SCALE_TO_DRYER",
            "requires_scale_destination_clear": direction == "DRYER_TO_SCALE",
        })
    result = {
        "schema_version": 1, "kind": "TRANSFER_INTENT_DRAFT",
        "direction": direction, "transfers": transfers,
        "station_revision": station_catalog(root)["revision"],
        "occupancy_assertions": dict(occupancy),
        "occupancy_blockers": blockers,
        "execution_enabled": False,
        "not_a_runtime_scheme": True,
        "required_runtime_integration": [
            "OperationsRegistry reserve/complete/cancel with evidence",
            "fresh source/destination profiles and slot calibration",
            "SceneAwareMotion and task-scoped payload preparation",
            "verified scale replenishment or clearance between cycles",
        ],
    }
    result["draft_digest"] = digest(result)
    return result


def timing_report(events):
    """Attempt/stage intervals overlap; report critical wall time, never sum both."""
    starts, rows, errors = {}, [], []
    for event in events:
        stage, state = event.get("stage"), event.get("state")
        detail = event.get("detail") or {}
        attempt = detail.get("attempt") if stage == "PLANNING_ATTEMPT" else None
        key = (stage, attempt)
        at = event.get("monotonic_s", event.get("at_unix"))
        if not isinstance(at, (int, float)) or not math.isfinite(at):
            errors.append(f"{stage}: missing finite timestamp")
            continue
        # Never mix monotonic and wall-clock timestamps within an interval.
        clock = "monotonic" if "monotonic_s" in event else "wall"
        if state == "START":
            if key in starts:
                errors.append(f"{stage}: duplicate unmatched START")
            starts[key] = (at, detail, clock)
        elif state in ("PASS", "FAILED", "FAULT", "COMPLETE"):
            if key not in starts:
                continue
            start, original, old_clock = starts.pop(key)
            if clock != old_clock or at < start:
                errors.append(f"{stage}: inconsistent clock")
                continue
            rows.append({"stage": stage, "attempt": attempt,
                         "mode": original.get("mode"), "state": state,
                         "elapsed_s": at - start, "error": detail.get("error"),
                         "clock": clock})
    return {"intervals": rows, "errors": errors,
            "unfinished": [{"stage": k[0], "attempt": k[1]} for k in starts],
            "nested_intervals_not_additive": True,
            "solve_time_inferred_from_stage_time": False}


def snapshot(root=ROOT):
    root = Path(root)
    p = load(root / "demos/right_arm_grasp_place_roundtrip_v1/parameters.json")
    route = load(root / p["base_route"])
    from .manipulation.roundtrip_demo import recipe
    stages = recipe(p, route)
    docs = root / "docs/golden/2026-10-19"
    return {"mode": "OFFLINE_REVIEW_NO_MOTION", "parameters": p,
            "reproduction_inputs": load(docs / "reproduction-inputs.json"),
            "stages": stages, "stations": station_catalog(root), "slots": SLOTS,
            "custody": load(docs / "custody.json"),
            "gaps": load(docs / "prepared-artifact-gaps.json"),
            "recovery_timing": timing_report(load(docs / "evidence/v17-place-recovery-completed/events.json")),
            "golden_source_unchanged": True}


class ReviewHandler(BaseHTTPRequestHandler):
    root = ROOT

    def do_GET(self):
        if self.path == "/api/workbench":
            data, content = json.dumps(snapshot(self.root), ensure_ascii=False).encode(), "application/json"
        elif self.path in ("/", "/workbench"):
            data, content = PAGE.read_bytes(), "text/html; charset=utf-8"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if self.path != "/api/workbench/draft":
            self.send_error(405, "Offline review has no device or mutation endpoint")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 16384:
                raise ValueError("invalid request size")
            body = json.loads(self.rfile.read(length))
            result = task_draft(body["direction"], body["slots"], {}, self.root)
            data = json.dumps(result, ensure_ascii=False).encode()
        except (ValueError, KeyError, TypeError) as exc:
            self.send_error(400, str(exc))
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["status", "serve", "timings", "draft"])
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--port", type=int, default=8788)
    parser.add_argument("--events", type=Path)
    parser.add_argument("--direction", default="SCALE_TO_DRYER")
    parser.add_argument("--slots", nargs="+", default=["lower_middle"])
    args = parser.parse_args()
    if args.command == "serve":
        ReviewHandler.root = args.root
        print(f"Offline review: http://127.0.0.1:{args.port}/workbench", flush=True)
        ThreadingHTTPServer(("127.0.0.1", args.port), ReviewHandler).serve_forever()
    elif args.command == "timings":
        if not args.events:
            parser.error("--events required")
        print(json.dumps(timing_report(load(args.events)), ensure_ascii=False, indent=2))
    elif args.command == "draft":
        print(json.dumps(task_draft(args.direction, args.slots, {}, args.root), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(snapshot(args.root), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
