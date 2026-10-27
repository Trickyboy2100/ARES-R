"""Select commanded arm axes from named solver outputs, retaining locked DOFs.

cuRobo may return a full joint vector including locked gripper joints. The
number of arm commands must never be inferred by reshaping that full vector.
"""
import numpy as np

ARM_NAMES = tuple('joint%d' % i for i in range(1, 7))


def extract_arm_joint_positions(positions, joint_names):
    names = tuple(joint_names)
    if len(set(names)) != len(names) or any(name not in names for name in ARM_NAMES):
        raise ValueError('solver output must uniquely name all six arm joints')
    values = np.asarray(positions, dtype=float)
    if values.ndim < 2 or values.shape[-1] != len(names) or not values.size:
        raise ValueError('solver output shape does not match named joints')
    if not np.isfinite(values).all():
        raise ValueError('solver output contains nonfinite joints')
    return values.reshape(-1, len(names))[:, [names.index(name) for name in ARM_NAMES]]
