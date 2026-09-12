"""Evidence-gated skill maturity."""

from enum import IntEnum


class SkillMaturity(IntEnum):
    SPECIFIED = 0
    MOCK_VERIFIED = 1
    SIM_VERIFIED = 2
    REAL_DRYRUN = 3
    REAL_COMMISSIONED = 4
