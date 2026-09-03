import json
import tempfile
import unittest
from pathlib import Path

from ares_r.factory import build_controller
from ares_r.models import TaskState


class ControllerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config = {
            "epic": {},
            "motion": {"approach_m": 0.03, "lift_m": 0.08},
            "base": {"pick_station": "pick", "place_station": "dryer"},
            "logging": {"directory": self.tmp.name},
        }
        self.controller = build_controller(self.config, "mock")

    def tearDown(self):
        self.tmp.cleanup()

    def test_complete_cycle(self):
        self.controller.cycle(2)
        self.assertEqual(self.controller.state, TaskState.COMPLETED)
        self.assertFalse(self.controller.carrying)
        self.assertEqual(self.controller.base.station(), "dryer")

    def test_pick_requires_detection(self):
        with self.assertRaises(RuntimeError):
            self.controller.pick()

    def test_stop_requires_reset(self):
        self.controller.stop_all()
        with self.assertRaises(RuntimeError):
            self.controller.detect_pick()
        self.controller.reset_mock()
        self.assertEqual(self.controller.state, TaskState.IDLE)

    def test_dock_range_is_validated(self):
        with self.assertRaises(ValueError):
            self.controller.detect_place(7)


if __name__ == "__main__":
    unittest.main()
