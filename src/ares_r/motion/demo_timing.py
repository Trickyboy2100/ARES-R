"""Right-demo timing profile; independent of SDK and shared site configuration."""
import math

SPEED_SCALE = 3.0
SAMPLE_PERIOD_S = .08
MAX_JOINT_SPEED_DEG_S = 3.0
# Preserve the commissioned site acceleration ceiling, not 9 * the old gate.
MAX_JOINT_ACCEL_DEG_S2 = math.degrees(.2)
MAX_TCP_SPEED_M_S = .06


def sample_count_at_scale(point_count, legacy_dt):
    """Compress the previous profile by 3, rounded UP to full 80 ms periods."""
    if point_count < 2 or not math.isfinite(legacy_dt) or legacy_dt <= 0:
        raise ValueError("invalid legacy timing")
    legacy_intervals = math.ceil((point_count - 1) * legacy_dt / SAMPLE_PERIOD_S)
    return math.ceil(legacy_intervals / SPEED_SCALE) + 1, legacy_intervals * SAMPLE_PERIOD_S
