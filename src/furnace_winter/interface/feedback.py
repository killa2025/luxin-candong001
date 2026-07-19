from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from furnace_winter.interface.commands import ErrorCode


class FeedbackLevel(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass(frozen=True, slots=True)
class FeedbackItem:
    level: FeedbackLevel
    text_id: str | None = None
    data: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CommandResult:
    command_id: str
    accepted: bool
    code: ErrorCode
    state_changed: bool = False
    state_sequence: int = 0
    feedback: tuple[FeedbackItem, ...] = ()
    data: Mapping[str, Any] = field(default_factory=dict)
