"""Pregrasp worker geometry: FK, geometric Jacobian and the central-slab model."""

import math
import unittest

import numpy as np

from ares_r.motion.pregrasp_worker import (FORBIDDEN_HALF_WIDTH_M, WALL_FACE_OFFSET_M,
                                           central_margin, central_wall, chain_kinematics,
                                           cuboid_clearance, densify, matrix_quaternion_wxyz,
                                           quaternion_matrix_wxyz, rigid_transform,
                                           wall_corners_body)


def planar_chain(lengths, axis_offset=0.05):
    """Origins of revolute joints about z, each spaced along its own x axis."""
    return [rigid_transform([length, 0.0, 0.0], [0.0, 0.0, 0.0]) for length in lengths]


def full_chain(origins, joint_angles, tool_offset_m):
    """Independent scalar implementation used as the finite-difference oracle."""
    transform = np.eye(4)
    for origin, angle in zip(origins, joint_angles):
        spin = np.eye(4)
        spin[0, 0] = math.cos(angle)
        spin[0, 1] = -math.sin(angle)
        spin[1, 0] = math.sin(angle)
        spin[1, 1] = math.cos(angle)
        transform = transform @ origin @ spin
    return transform[:3, :3] @ np.asarray(tool_offset_m, dtype=float) + transform[:3, 3]


class RigidTransformTest(unittest.TestCase):
    def test_translation_only(self):
        matrix = rigid_transform([0.1, -0.2, 0.3], [0.0, 0.0, 0.0])
        self.assertTrue(np.allclose(matrix[:3, :3], np.eye(3)))
        self.assertTrue(np.allclose(matrix[:3, 3], [0.1, -0.2, 0.3]))

    def test_yaw_rotation_follows_the_documented_convention(self):
        matrix = rigid_transform([0.0, 0.0, 0.0], [0.0, 0.0, math.pi / 2])
        self.assertTrue(np.allclose(matrix[:3, :3] @ [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], atol=1e-12))

    def test_quaternion_order_is_wxyz(self):
        identity = matrix_quaternion_wxyz(np.eye(3))
        self.assertTrue(np.allclose(identity, [1.0, 0.0, 0.0, 0.0]))
        yaw = matrix_quaternion_wxyz(rigid_transform([0, 0, 0], [0, 0, math.pi / 2])[:3, :3])
        self.assertAlmostEqual(yaw[0], math.cos(math.pi / 4), places=12)
        self.assertAlmostEqual(yaw[3], math.sin(math.pi / 4), places=12)


class ChainKinematicsTest(unittest.TestCase):
    def test_two_joint_chain_matches_the_scalar_oracle(self):
        origins = planar_chain([0.0, 0.3])
        offset = [0.0, 0.0, 0.12]
        samples = [[0.0, 0.0], [0.4, -0.9], [math.pi / 2, math.pi / 2]]
        tcp, jacobian, links = chain_kinematics(samples, origins, offset)
        self.assertEqual(jacobian.shape, (3, 6, 2))
        self.assertEqual(links.shape, (3, 4, 3))
        for index, joints in enumerate(samples):
            self.assertTrue(np.allclose(tcp[index], full_chain(origins, joints, offset), atol=1e-12))
            # The reported link chain is the base, J1, J2 and the TCP.
            self.assertTrue(np.allclose(links[index][0], [0.0, 0.0, 0.0]))
            self.assertTrue(np.allclose(links[index][-1], tcp[index]))

    def test_jacobian_matches_central_finite_differences(self):
        origins = planar_chain([0.0, 0.25, 0.2])
        offset = [0.03, -0.02, 0.1]
        samples = np.array([[0.0] * 3, [0.3, -0.6, 0.9], [-1.1, 0.4, 0.2]])
        _, jacobian, _ = chain_kinematics(samples, origins, offset)
        epsilon = 1e-6
        for index, joints in enumerate(samples):
            for joint in range(3):
                step = np.zeros(3)
                step[joint] = epsilon
                plus = full_chain(origins, joints + step, offset)
                minus = full_chain(origins, joints - step, offset)
                finite_difference = (plus - minus) / (2 * epsilon)
                self.assertTrue(np.allclose(jacobian[index][:3, joint], finite_difference, atol=1e-7),
                                "linear column %d of sample %d" % (joint, index))
                # A revolute joint about z contributes a unit z rotation column.
                self.assertTrue(np.allclose(jacobian[index][3:, joint], [0.0, 0.0, 1.0], atol=1e-12))

    def test_joint_count_must_match_the_chain(self):
        origins = planar_chain([0.0, 0.3])
        with self.assertRaises(ValueError):
            chain_kinematics([[0.0, 0.0, 0.0]], origins, [0.0, 0.0, 0.1])


class DensifyTest(unittest.TestCase):
    def test_subsampling_keeps_every_planner_point(self):
        points = [[0.0] * 6, [1.0] * 6, [2.0] * 6]
        dense = densify(points, 4)
        self.assertEqual(len(dense), 2 * 4 + 1)
        self.assertTrue(np.allclose(dense[0], points[0]))
        self.assertTrue(np.allclose(dense[4], points[1]))
        self.assertTrue(np.allclose(dense[-1], points[-1]))
        self.assertTrue(np.allclose(dense[::4], points))

    def test_rejects_degenerate_subsampling(self):
        with self.assertRaises(ValueError):
            densify([[0.0] * 6, [1.0] * 6], 0)


class CentralSlabTest(unittest.TestCase):
    def test_right_wall_near_face_sits_inside_the_hard_boundary(self):
        model_from_body = np.eye(4)
        wall = central_wall(model_from_body, "right")
        near_face = wall["pose"][1] - wall["dims"][1] / 2.0
        self.assertAlmostEqual(near_face, -WALL_FACE_OFFSET_M, places=12)
        # The wall body extends away from the arm on the illegal side.
        self.assertGreater(wall["pose"][1], 0.0)

    def test_left_wall_is_the_mirror_of_the_right_wall(self):
        wall = central_wall(np.eye(4), "left")
        near_face = wall["pose"][1] + wall["dims"][1] / 2.0
        self.assertAlmostEqual(near_face, WALL_FACE_OFFSET_M, places=12)
        self.assertLess(wall["pose"][1], 0.0)

    def test_margin_is_positive_only_outside_the_slab(self):
        right = central_margin([-0.2, -0.07, -0.01, 0.2], "right")
        self.assertGreater(right[0], 0.0)
        self.assertAlmostEqual(right[1], 0.0)
        self.assertLess(right[2], 0.0)
        left = central_margin([0.2, FORBIDDEN_HALF_WIDTH_M, 0.01, -0.2], "left")
        self.assertGreater(left[0], 0.0)
        self.assertAlmostEqual(left[1], 0.0)
        self.assertLess(left[2], 0.0)

    def test_wall_is_rotated_with_the_base_frame(self):
        body_rotation = rigid_transform([0.0, 0.0, 0.0], [0.0, 0.0, math.pi / 2])
        wall = central_wall(body_rotation, "left")
        quaternion = np.asarray(wall["pose"][3:])
        self.assertAlmostEqual(float(np.linalg.norm(quaternion)), 1.0, places=12)
        self.assertAlmostEqual(quaternion[0], math.cos(math.pi / 4), places=12)

    def test_quaternion_encoding_round_trips_through_the_matrix_form(self):
        for angles in ([0.0, 0.0, 0.0], [0.0, 0.0, 0.3], [0.2, -0.4, 1.0]):
            matrix = rigid_transform([1.0, 2.0, 3.0], angles)[:3, :3]
            restored = quaternion_matrix_wxyz(matrix_quaternion_wxyz(matrix))
            self.assertTrue(np.allclose(matrix, restored, atol=1e-9), angles)
        with self.assertRaises(ValueError):
            quaternion_matrix_wxyz([0.0, 0.0, 0.0, 0.0])


class CuboidClearanceTest(unittest.TestCase):
    def test_axis_aligned_box_reduces_to_the_plain_distance(self):
        box = dict(dims=[1.0, 1.0, 1.0], pose=[0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0])
        # A sphere of radius 0.2 at x = 1.0 clears the x face at 0.5 by 0.3.
        self.assertAlmostEqual(cuboid_clearance([[1.0, 0.0, 0.0]], [0.2], box)[0], 0.3, places=12)
        # Straight through the centre is a deep penetration of half the box.
        self.assertAlmostEqual(cuboid_clearance([[0.0, 0.0, 0.0]], [0.0], box)[0], -0.5, places=12)

    def test_yawed_box_is_measured_in_its_own_frame(self):
        # The central wall is yawed with the arm base. Measuring it as if it were
        # axis aligned around its centre reported a false half-metre penetration
        # during the offline end-to-end check; this pins the correction.
        rotation = rigid_transform([0.0, 0.0, 0.0], [0.0, 0.0, math.pi / 4])[:3, :3]
        box = dict(dims=[10.0, 10.0, 10.0],
                   pose=[0.0, 0.0, 0.0] + matrix_quaternion_wxyz(rotation))
        on_face = rotation @ [0.0, 5.0, 0.0]
        self.assertAlmostEqual(cuboid_clearance([on_face], [0.0], box)[0], 0.0, places=9)
        one_metre_out = rotation @ [0.0, 6.0, 0.0]
        self.assertAlmostEqual(cuboid_clearance([one_metre_out], [0.0], box)[0], 1.0, places=9)
        # The same face point carrying a real radius is a real conflict.
        self.assertLess(cuboid_clearance([on_face], [0.1], box)[0], 0.0)
        # The naive axis-aligned distance from the box centre, which the first
        # implementation used, would have called that face point deeply inside.
        offset = np.abs(np.asarray(on_face) - np.asarray(box["pose"][:3]))
        naive = float(np.linalg.norm(np.maximum(offset - 5.0, 0.0))
                      + min(float(np.max(offset - 5.0)), 0.0))
        self.assertLess(naive, -1.0)

    def test_wall_corners_land_exactly_on_the_intended_near_face(self):
        body = rigid_transform([0.0, -0.2, 1.2], [0.0, 0.0, math.pi / 4])
        model_from_body = np.linalg.inv(body)
        wall = central_wall(model_from_body, "right")
        corners = wall_corners_body(wall, model_from_body, body)
        self.assertAlmostEqual(float(corners[:, 1].min()), -WALL_FACE_OFFSET_M, places=9)
        self.assertAlmostEqual(float(corners[:, 1].max()), 5.0, places=9)
        self.assertAlmostEqual(float(corners[:, 2].min()), 0.0, places=9)
        self.assertAlmostEqual(float(corners[:, 2].max()), 5.0, places=9)
        # The offset face has to sit strictly inside the 14 cm hard boundary so a
        # sphere is pushed further out than the operator's link-centre check.
        self.assertGreater(-WALL_FACE_OFFSET_M, -FORBIDDEN_HALF_WIDTH_M)


if __name__ == "__main__":
    unittest.main()
