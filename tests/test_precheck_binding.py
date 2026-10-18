import unittest
from ares_r.manipulation.first_pick_package import bound_contact_lift,_sha
class BranchBindingTests(unittest.TestCase):
    def test_selected_ik_paths_are_immutable_and_same_branch(self):
        branch={'observation_id':'OBS','prechecked_paths':{'contact':[[.1]*6]*26,'lift':[[.1]*6]*51}}
        branch['branch_sha256']=_sha(branch)
        plan={'selected_goal_candidate_metadata':branch,'trajectory_points_rad':[[0]*6,[.1]*6]}
        contact,lift,bound=bound_contact_lift(plan,{},'OBS')
        self.assertEqual(contact,branch['prechecked_paths']['contact'])
        plan['trajectory_points_rad'][-1]=[.2]*6
        with self.assertRaisesRegex(ValueError,'SEAM'):bound_contact_lift(plan,{},'OBS')
        plan['trajectory_points_rad'][-1]=[.1]*6
        branch['prechecked_paths']['lift'][0]=[.11]*6
        with self.assertRaisesRegex(ValueError,'DIGEST'):bound_contact_lift(plan,{},'OBS')
