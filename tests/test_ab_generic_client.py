import unittest

from ares_r.motion.ab_client import ABDemoClient


class Service:
    def __init__(self): self.requests = [];self.local_scene=None
    def plan(self, request):
        self.requests.append(request)
        return {"plan_id": "generic"}


class ABGenericClientTests(unittest.TestCase):
    def test_client_only_supplies_goal_and_constraints(self):
        service = Service()
        result = ABDemoClient(service).plan("A")
        request = service.requests[0]
        self.assertEqual(result["plan_id"], "generic")
        self.assertEqual(request.request_label, "AB_DEMO_TO_A")
        self.assertFalse(hasattr(request, "obstacle_ids"))
        self.assertFalse(hasattr(request, "clearance_gate_m"))

    def test_only_endpoint_selection_remains_in_demo_client(self):
        service=Service();client=ABDemoClient(service)
        self.assertEqual(client.next_destination(client.contract["A_joints_rad"]),"B")
        self.assertEqual(client.next_destination(client.contract["B_joints_rad"]),"A")


if __name__ == "__main__": unittest.main()
