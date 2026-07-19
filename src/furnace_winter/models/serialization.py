from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any


def to_primitive(value: Any) -> Any:
    """Convert state/interface dataclasses to deterministic JSON values."""

    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: to_primitive(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): to_primitive(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_primitive(child) for child in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"value is not JSON serializable: {type(value).__name__}")


def dumps(value: Any) -> str:
    return json.dumps(
        to_primitive(value),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
