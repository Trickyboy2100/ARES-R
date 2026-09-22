"""Planning-only A/B demo lifecycle; hardware execution is intentionally locked."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math


def classify_reference_corridor(gaps_by_object, endpoint_gap_m):
    """Classify a full-robot swept reference chord, never a TCP-only line."""
    if not gaps_by_object or not math.isfinite(endpoint_gap_m):
        return "SCENE_INVALID", []
    if not all(math.isfinite(value) for value in gaps_by_object.values()):
        return "SCENE_INVALID", []
    if endpoint_gap_m <= 0:
        return "SCENE_INVALID", []
    hits = sorted(name for name, value in gaps_by_object.items() if value <= 0)
    return ("STRAIGHT_BLOCKED" if hits else "STRAIGHT_CLEAR"), hits


def validate_curobo_only_policy(contract):
    """Enforce the latest user override: no explicit A/B waypoint."""
    if contract.get("motion_policy") != "CUROBO_ONLY_FOR_EVERY_POINT_TO_POINT_LEG":
        raise ValueError("every P3.2 point-to-point leg must use cuRobo")
    if contract.get("planner_mode") != "CUROBO_DIRECT":
        raise ValueError("P3.2 demo uses one cuRobo request from start to goal")
    if contract.get("explicit_waypoints") != [] or "waypoint_joints_rad" in contract:
        raise ValueError("explicit waypoints are forbidden by the latest user override")


class ABState(str, Enum):
    IDLE = "AB_DEMO_IDLE"
    AT_A = "AB_AT_A"
    AT_B = "AB_AT_B"
    SCANNING = "SCANNING"
    SCENE_READY = "SCENE_READY"
    STRAIGHT_CLEAR = "STRAIGHT_CLEAR"
    BYPASS_REQUIRED = "BYPASS_REQUIRED"
    PLANNED = "PLANNED"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    EXECUTING = "EXECUTING"
    ARRIVED = "ARRIVED"
    STOPPED = "STOPPED"
    FAULT = "FAULT"


@dataclass
class ABPlanningSession:
    state: ABState = ABState.IDLE
    endpoint: str | None = None
    scene_snapshot_id: str | None = None
    trajectory_id: str | None = None
    tool_tcp_physical_semantics_unresolved: bool = True

    def at_endpoint(self, endpoint: str):
        if endpoint not in ("A", "B"):
            raise ValueError("endpoint must be A or B")
        self.invalidate()
        self.endpoint = endpoint
        self.state = ABState.AT_A if endpoint == "A" else ABState.AT_B

    def begin_scan(self):
        if self.state not in (ABState.AT_A, ABState.AT_B):
            raise ValueError("fresh scan requires verified endpoint state")
        self.invalidate()
        self.state = ABState.SCANNING

    def scene_ready(self, snapshot_id: str):
        if self.state != ABState.SCANNING or not snapshot_id:
            raise ValueError("fresh snapshot required")
        self.scene_snapshot_id = snapshot_id
        self.state = ABState.SCENE_READY

    def classified(self, classification: str):
        if self.state != ABState.SCENE_READY:
            raise ValueError("scene not ready")
        if classification == "STRAIGHT_CLEAR":
            self.state = ABState.STRAIGHT_CLEAR
        elif classification == "STRAIGHT_BLOCKED":
            self.state = ABState.BYPASS_REQUIRED
        elif classification == "SCENE_INVALID":
            self.fault()
        else:
            raise ValueError("unknown classifier result")

    def planned(self, trajectory_id: str, snapshot_id: str):
        if self.state not in (ABState.STRAIGHT_CLEAR, ABState.BYPASS_REQUIRED):
            raise ValueError("classification required")
        if not trajectory_id or snapshot_id != self.scene_snapshot_id:
            raise ValueError("stale/mismatched scene binding")
        self.trajectory_id = trajectory_id
        self.state = ABState.PLANNED

    def preview(self):
        if self.state != ABState.PLANNED:
            raise ValueError("no fresh plan")
        self.state = ABState.AWAITING_CONFIRMATION

    def execute_next(self):
        # This method must remain a hard gate in P3.2 even with a valid plan.
        raise PermissionError("P3.2 is planning-only; TOOL_TCP_PHYSICAL_SEMANTICS_UNRESOLVED=YES")

    def observed_arrival(self, endpoint: str):
        # For future controlled adapter integration only; no P3.2 caller should
        # synthesize an arrival from a planning result.
        if self.state != ABState.EXECUTING:
            raise ValueError("arrival requires real execution feedback")
        self.invalidate()
        self.endpoint = endpoint
        self.state = ABState.ARRIVED

    def stop(self):
        self.invalidate()
        self.state = ABState.STOPPED

    def fault(self):
        self.invalidate()
        self.state = ABState.FAULT

    def invalidate(self):
        self.scene_snapshot_id = None
        self.trajectory_id = None
