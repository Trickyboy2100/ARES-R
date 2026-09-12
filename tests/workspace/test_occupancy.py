import unittest

from ares_r.workspace import Container, Occupancy, ResourceGraph, Slot, Station, Tool


class OccupancyTests(unittest.TestCase):
    def resources(self):
        return (Station("s", "station"),
                Slot("slot", "slot", "s", accepts_occupant_types=("Container",)),
                Container("v1", "vial 1"), Container("v2", "vial 2"), Tool("t", "tool"))

    def test_collision(self):
        with self.assertRaisesRegex(ValueError, "collision"):
            ResourceGraph.create(self.resources(), occupancies=(
                Occupancy("slot", "v1"), Occupancy("slot", "v2")))

    def test_incompatible_placement(self):
        with self.assertRaisesRegex(ValueError, "incompatible"):
            ResourceGraph.create(self.resources(), occupancies=(Occupancy("slot", "t"),))

    def test_valid_occupancy(self):
        graph = ResourceGraph.create(self.resources(), occupancies=(Occupancy("slot", "v1"),))
        self.assertEqual(graph.occupant("slot").resource_id, "v1")
