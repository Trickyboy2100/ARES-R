import unittest

from ares_r.adapters.serial_gripper import SerialGripper


class SerialGripperTest(unittest.TestCase):
    def setUp(self):
        self.gripper = SerialGripper("right", {"port": "/dev/null", "device_id": 1, "min_position": 0, "max_position": 1000})

    def test_read_position_frame(self):
        self.assertEqual(self.gripper._frame(0xD9).hex(), "eb900101d9db")

    def test_move_position_frame_is_little_endian(self):
        self.assertEqual(self.gripper._frame(0x54, bytes([0xF4, 0x01])).hex(), "eb90010354f4014d")

    def test_position_range(self):
        with self.assertRaises(ValueError):
            self.gripper.move_to(1001)


if __name__ == "__main__":
    unittest.main()
