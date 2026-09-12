"""Evidence-gated skill maturity."""

from dataclasses import dataclass
from enum import IntEnum
from typing import Dict, Optional, Tuple

from .serialization import require_digest


class SkillMaturity(IntEnum):
    SPECIFIED = 0
    MOCK_VERIFIED = 1
    SIM_VERIFIED = 2
    REAL_DRYRUN = 3
    REAL_COMMISSIONED = 4


@dataclass(frozen=True)
class MaturityEvidenceKey:
    skill_id: str
    implementation_version: str
    provider_family: str
    robot_revision: str
    tool_revision: str
    config_revision: str

    def __post_init__(self) -> None:
        if not all((self.skill_id, self.implementation_version, self.provider_family,
                    self.robot_revision, self.tool_revision, self.config_revision)):
            raise ValueError("complete maturity evidence scope is required")


@dataclass(frozen=True)
class MaturityEvidence:
    key: MaturityEvidenceKey
    maturity: SkillMaturity
    evidence_digest: str
    recorded_at_unix_ns: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "maturity", SkillMaturity(self.maturity))
        object.__setattr__(self, "evidence_digest", require_digest(self.evidence_digest, "evidence_digest"))
        if self.recorded_at_unix_ns <= 0:
            raise ValueError("maturity evidence timestamp must be positive")


class MaturityEvidenceRegistry:
    """Read-only lookup view. Promotion workflow is intentionally absent."""
    def __init__(self, evidence: Tuple[MaturityEvidence, ...] = ()) -> None:
        index = {item.key: item for item in evidence}
        if len(index) != len(evidence):
            raise ValueError("duplicate maturity evidence scope")
        self._index = index  # type: Dict[MaturityEvidenceKey, MaturityEvidence]

    def lookup(self, key: MaturityEvidenceKey) -> Optional[MaturityEvidence]:
        return self._index.get(key)
