"""Versioned registry of semantic SkillDefinition data."""

from typing import Dict, Optional, Tuple

from .contracts import SkillDefinition
from .maturity import SkillMaturity


class SkillRegistry:
    def __init__(self) -> None:
        self._definitions = {}  # type: Dict[Tuple[str, str], SkillDefinition]

    def register(self, definition: SkillDefinition) -> None:
        key = (definition.skill_id, definition.implementation_version)
        if key in self._definitions:
            raise ValueError("duplicate skill registration: %s@%s" % key)
        self._definitions[key] = definition

    def get(self, skill_id: str, implementation_version: Optional[str] = None) -> SkillDefinition:
        if implementation_version is not None:
            item = self._definitions.get((skill_id, implementation_version))
            if item is None:
                raise KeyError("unknown skill/version: %s@%s" % (skill_id, implementation_version))
            return item
        matches = [item for key, item in self._definitions.items() if key[0] == skill_id]
        if len(matches) != 1:
            raise KeyError("skill requires an unambiguous implementation version: %s" % skill_id)
        return matches[0]

    def definitions(self, maximum_maturity: Optional[SkillMaturity] = None) -> Tuple[SkillDefinition, ...]:
        values = self._definitions.values()
        if maximum_maturity is not None:
            ceiling = SkillMaturity(maximum_maturity)
            values = [item for item in values if item.maturity <= ceiling]
        return tuple(sorted(values, key=lambda item: (item.skill_id, item.implementation_version)))
