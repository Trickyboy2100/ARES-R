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

    def test_yaw_only_motion_is_observed(self):
        values = [obs(0, yaw=-3), obs(0, yaw=-20), obs(0, yaw=-30),
                  obs(0, yaw=-30.05), obs(0, yaw=-30.05), obs(0, yaw=-30.05)]
        result = self.observer(values).wait(obs(0), expected_yaw_deg=-30)
        self.assertEqual(result["phase"], "SETTLED")


if __name__ == "__main__":
    unittest.main()
