"""Right-demo timing profile; independent of SDK and shared site configuration."""
import math

SPEED_SCALE = 3.0
RECOVERY_SPEED_SCALE = 2.0
SUPPORTED_SPEED_SCALES = (RECOVERY_SPEED_SCALE, SPEED_SCALE)
SAMPLE_PERIOD_S = .08
MAX_JOINT_SPEED_DEG_S = 3.0
# Preserve the commissioned site acceleration ceiling, not 9 * the old gate.
MAX_JOINT_ACCEL_DEG_S2 = math.degrees(.2)
MAX_TCP_SPEED_M_S = .06


def sample_count_at_scale(point_count, legacy_dt, speed_scale=SPEED_SCALE):
    """Compress a profile by an approved scale, rounded up to 80 ms periods."""
    if point_count < 2 or not math.isfinite(legacy_dt) or legacy_dt <= 0:
        raise ValueError("invalid legacy timing")
    if speed_scale not in SUPPORTED_SPEED_SCALES:
        raise ValueError("unsupported demo speed scale")
    legacy_intervals = math.ceil((point_count - 1) * legacy_dt / SAMPLE_PERIOD_S)
    return math.ceil(legacy_intervals / speed_scale) + 1, legacy_intervals * SAMPLE_PERIOD_S
