"""Observation-backed completion for asynchronous AMR requests.

The R300 accepts a relative-motion request before the chassis has moved and its
``state`` field can remain ``IDLE`` throughout motion.  Completion therefore
comes from a geometric observation stream, never from request acceptance or a
controller label by itself.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import time
from typing import Callable, Mapping, Optional


class BaseMotionTimeout(RuntimeError):
    pass


@dataclass(frozen=True)
class BaseObservation:
    captured_at_unix: float
    x_m: float
    y_m: float
    yaw_deg: float
    motion_log_id: Optional[object] = None
    motion_queue_id: Optional[object] = None
    scene_signature: Optional[str] = None
    arm_state_revision: Optional[str] = None

    @classmethod
    def from_robot_status(cls, value: Mapping[str, object], *, clock=time.time):
        info = value["info"]
        log = value.get("log") or {}
        return cls(clock(), float(info["x"]), float(info["y"]),
                   float(info["yawNumber"]), log.get("id"), log.get("queueId"))


def _yaw_delta_deg(first: float, second: float) -> float:
    return abs((float(second) - float(first) + 180.0) % 360.0 - 180.0)


def observation_delta(first: BaseObservation, second: BaseObservation) -> dict:
    return {
        "translation_m": math.hypot(second.x_m - first.x_m, second.y_m - first.y_m),
        "yaw_deg": _yaw_delta_deg(first.yaw_deg, second.yaw_deg),
        "scene_changed": (first.scene_signature is not None and
                          second.scene_signature is not None and
                          first.scene_signature != second.scene_signature),
        "arm_changed": (first.arm_state_revision is not None and
                        second.arm_state_revision is not None and
                        first.arm_state_revision != second.arm_state_revision),
        "marker_changed": ((first.motion_log_id, first.motion_queue_id) !=
                           (second.motion_log_id, second.motion_queue_id)),
    }


class BaseMotionObserver:
    """Wait for observed movement followed by a consecutive stable window."""

    def __init__(self, sample: Callable[[], BaseObservation], config: Mapping[str, object],
                 *, sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.time) -> None:
        self.sample = sample
        self.config = dict(config)
        self.sleep = sleep
        self.clock = clock

    def capture(self) -> BaseObservation:
        return self.sample()

    def wait(self, baseline: BaseObservation, *, timeout_s: Optional[float] = None,
             expected_translation_m: float = 0.0,
             expected_yaw_deg: float = 0.0) -> dict:
        poll = float(self.config.get("poll_interval_s", 0.5))
        timeout = float(timeout_s or self.config.get("timeout_s", 120.0))
        stable_required = int(self.config.get("stable_samples", 5))
        settle_translation = float(self.config.get("settle_translation_m", 0.04))
        settle_yaw = float(self.config.get("settle_yaw_deg", 1.5))
        min_elapsed = float(self.config.get("minimum_observed_motion_s", 1.5))
        configured_translation = float(self.config.get("motion_translation_m", 0.02))
        configured_yaw = float(self.config.get("motion_yaw_deg", 1.0))
        translation_trigger = min(configured_translation,
                                  max(abs(float(expected_translation_m)) * 0.20, 0.005))
        yaw_trigger = min(configured_yaw, max(abs(float(expected_yaw_deg)) * 0.20, 0.25))
        if poll <= 0 or timeout <= 0 or stable_required < 2:
            raise ValueError("invalid base completion-observer timing")

        started = self.clock()
        previous = baseline
        samples = []
        phase = "REQUESTED"
        motion_at = None
        stable = 0
        while self.clock() - started <= timeout:
            current = self.sample()
            from_start = observation_delta(baseline, current)
            from_previous = observation_delta(previous, current)
            elapsed = self.clock() - started
            moved = (from_start["translation_m"] >= translation_trigger or
                     from_start["yaw_deg"] >= yaw_trigger or
                     from_start["scene_changed"])
            if moved and phase == "REQUESTED":
                phase = "MOTION_OBSERVED"
                motion_at = elapsed
            locally_stable = (from_previous["translation_m"] <= settle_translation and
                              from_previous["yaw_deg"] <= settle_yaw and
                              not from_previous["scene_changed"] and
                              not from_previous["arm_changed"])
            if phase != "REQUESTED" and motion_at is not None and elapsed - motion_at >= min_elapsed:
                phase = "SETTLING"
                stable = stable + 1 if locally_stable else 0
            samples.append({
                "captured_at_unix": current.captured_at_unix,
                "x_m": current.x_m, "y_m": current.y_m, "yaw_deg": current.yaw_deg,
                "motion_log_id": current.motion_log_id,
                "motion_queue_id": current.motion_queue_id,
                "from_start": from_start, "from_previous": from_previous,
                "phase": phase, "stable_count": stable,
            })
            if stable >= stable_required:
                return {
                    "schema_version": 1,
                    "observer_revision": str(self.config.get("revision", "UNVERSIONED")),
                    "result": "SETTLED", "phase": "SETTLED",
                    "elapsed_s": elapsed, "motion_observed_at_s": motion_at,
                    "stable_samples": stable, "samples": samples,
                    "method": "geometric observation then consecutive stable window",
                }
            previous = current
            self.sleep(poll)
        raise BaseMotionTimeout(
            "AMR completion timeout: phase=%s samples=%d; request acceptance is not arrival"
            % (phase, len(samples)))


def amr_status_sampler(base, *, clock=time.time) -> Callable[[], BaseObservation]:
    def sample():
        return BaseObservation.from_robot_status(
            base._request("GET", "/robot/status"), clock=clock)
    return sample
