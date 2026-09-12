"""Canonical, finite JSON serialization for persistent skill contracts."""

from dataclasses import fields, is_dataclass
from enum import Enum
import hashlib
import json
import math
from typing import Any, Mapping, Tuple


def freeze(value: Any) -> Any:
    """Convert JSON-like data into an immutable, deterministically ordered value."""
    if isinstance(value, Enum):
        return value
    if is_dataclass(value):
        return value
    if isinstance(value, Mapping):
        return tuple(sorted((str(key), freeze(item)) for key, item in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(freeze(item) for item in value)
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("non-finite values are not persistable")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError("unsupported persistent value: %s" % type(value).__name__)


def _is_pair_sequence(value: Any) -> bool:
    return isinstance(value, tuple) and all(
        isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str)
        for item in value
    )


def plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {field.name: plain(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): plain(item) for key, item in sorted(value.items())}
    if _is_pair_sequence(value):
        return {key: plain(item) for key, item in value}
    if isinstance(value, (tuple, list)):
        return [plain(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("non-finite values are not serializable")
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(plain(value), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


_HEX = frozenset("0123456789abcdef")


def require_digest(value: str, label: str) -> str:
    value = str(value).lower()
    if len(value) != 64 or any(char not in _HEX for char in value):
        raise ValueError("%s must be a SHA-256 digest" % label)
    return value


def pairs(value: Any, label: str) -> Tuple[Tuple[str, Any], ...]:
    """Freeze a mapping/pair iterable while rejecting duplicate or empty keys."""
    items = value.items() if isinstance(value, Mapping) else value
    result = tuple(sorted((str(key), freeze(item)) for key, item in items))
    if any(not key for key, _ in result) or len(dict(result)) != len(result):
        raise ValueError("%s keys must be unique and non-empty" % label)
    return result
