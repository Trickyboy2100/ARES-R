import json
from pathlib import Path
import unittest

from ares_r.motion.base_motion_observer import (
    BaseMotionObserver, BaseMotionTimeout, BaseObservation)


class _Clock:
    def __init__(self): self.value = 0.0
    def __call__(self): return self.value
    def sleep(self, seconds): self.value += seconds


def obs(x, y=0.0, yaw=0.0, log=1, queue=1):
    return BaseObservation(0.0, x, y, yaw, log, queue)


class BaseMotionObserverTest(unittest.TestCase):
    def config(self):
        return dict(revision="test-v1", poll_interval_s=.5, timeout_s=10,
                    motion_translation_m=.02, motion_yaw_deg=1,
                    minimum_observed_motion_s=.5, stable_samples=3,
                    settle_translation_m=.01, settle_yaw_deg=.2)

    def observer(self, values):
        clock = _Clock(); iterator = iter(values)
        return BaseMotionObserver(lambda: next(iterator), self.config(),
                                  sleep=clock.sleep, clock=clock)

    def test_acceptance_without_observed_motion_never_settles(self):
        observer = self.observer([obs(0)] * 30)
        with self.assertRaises((BaseMotionTimeout, StopIteration)):
            observer.wait(obs(0), timeout_s=2, expected_translation_m=.3)

    def test_motion_then_stable_window_settles_even_if_controller_label_is_absent(self):
        values = [obs(.03, log=2, queue=2), obs(.15, log=2, queue=2),
                  obs(.29, log=2, queue=2), obs(.300, log=3, queue=2),
                  obs(.301, log=3, queue=2), obs(.301, log=3, queue=2),
                  obs(.301, log=3, queue=2)]
        result = self.observer(values).wait(obs(0), expected_translation_m=.3)
        self.assertEqual(result["result"], "SETTLED")
        self.assertGreaterEqual(result["stable_samples"], 3)

    def test_partial_motion_then_pause_does_not_settle(self):
        values = [obs(.03,log=2,queue=2),obs(.07,log=2,queue=2),
                  obs(.07,log=2,queue=2),obs(.07,log=2,queue=2),obs(.07,log=2,queue=2)]
        observer=self.observer(values)
        with self.assertRaises((BaseMotionTimeout,StopIteration)):
            observer.wait(obs(0),expected_translation_m=.20)

    def test_explicit_completion_marker_allows_localization_disagreement(self):
        clock=_Clock();values=iter([
            BaseObservation(0,.03,0,0,2,2,motion_status="RelativeMove running"),
            BaseObservation(0,.07,0,0,2,2,motion_status="任务【RelativeMove】已完成"),
            BaseObservation(0,.07,0,0,2,2,motion_status="任务【RelativeMove】已完成"),
            BaseObservation(0,.07,0,0,2,2,motion_status="任务【RelativeMove】已完成"),
            BaseObservation(0,.07,0,0,2,2,motion_status="任务【RelativeMove】已完成")])
        result=BaseMotionObserver(lambda:next(values),self.config(),sleep=clock.sleep,
                                  clock=clock).wait(obs(0),expected_translation_m=.20)
        self.assertEqual(result["result"],"SETTLED")

    def test_yaw_only_motion_is_observed(self):
        values = [obs(0, yaw=-3), obs(0, yaw=-20), obs(0, yaw=-30),
                  obs(0, yaw=-30.05), obs(0, yaw=-30.05), obs(0, yaw=-30.05)]
        result = self.observer(values).wait(obs(0), expected_yaw_deg=-30)
        self.assertEqual(result["phase"], "SETTLED")

    def test_replay_p38a_pick_and_place_logs(self):
        root = (Path(__file__).resolve().parents[1] /
                "worklog/evidence/2026-09-24-p3-8a-system-audit")
        for name in ("pick_base_move_v2.json", "place_base_move.json"):
            payload = json.loads((root / name).read_text())
            motion_rows=list(payload["samples"])
            raw = motion_rows + list(payload["stationarity"]["samples"])
            rows = [BaseObservation(
                float(item.get("t", item.get("at_unix"))),
                float(item.get("x", item.get("x_m"))),
                float(item.get("y", item.get("y_m"))),
                float(item.get("yaw", item.get("yaw_deg"))),
                item.get("log_id", item.get("motion_log_id")),
                item.get("queue_id", item.get("motion_queue_id")),
                motion_status=("RelativeMove completed" if index>=len(motion_rows) else ""))
                    for index,item in enumerate(raw)]
            # The archived audit stopped recording immediately after its own
            # stationarity check. Repeat the final settled observation so the
            # production observer can prove its full five-sample window.
            rows.append(rows[-1])
            now = [float(payload["started_at_unix"])]
            iterator = iter(rows)
            def sample():
                value = next(iterator)
                now[0] = value.captured_at_unix
                return value
            before = payload.get("before_status", payload.get("before"))[-1]
            baseline = BaseObservation(before["t"], before["x"], before["y"], before["yaw"],
                                       before["log_id"], before["queue_id"])
            observer = BaseMotionObserver(sample, {
                "revision": "p38a-replay-v1", "poll_interval_s": .01,
                "timeout_s": 120, "stable_samples": 5,
                "settle_translation_m": .04, "settle_yaw_deg": 1.5,
                "minimum_observed_motion_s": 1.5},
                sleep=lambda _value: None, clock=lambda: now[0])
            result = observer.wait(baseline, expected_translation_m=.3)
            self.assertEqual(result["result"], "SETTLED", name)


if __name__ == "__main__":
    unittest.main()
