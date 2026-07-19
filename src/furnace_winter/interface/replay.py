from __future__ import annotations

from collections.abc import Iterator, Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from furnace_winter.interface.commands import CommandRequest, ErrorCode
from furnace_winter.interface.feedback import CommandResult
from furnace_winter.models import GameState, RandomState, encode_game_state


REPLAY_FORMAT_VERSION = 1


class LogCategory(StrEnum):
    COMMAND = "COMMAND"
    VALIDATION = "VALIDATION"
    RESULT = "RESULT"
    STATE = "STATE"
    SYSTEM = "SYSTEM"


@dataclass(frozen=True, slots=True)
class LogEntry:
    sequence: int
    category: LogCategory
    code: str
    payload: Mapping[str, Any] = field(default_factory=dict)


class EventLog:
    """Append-only ordered log interface shared by execution and replay."""

    def __init__(self) -> None:
        self._entries: list[LogEntry] = []

    def append(self, entry: LogEntry) -> None:
        if entry.sequence < 0:
            raise ValueError("log sequence must not be negative")
        if self._entries and entry.sequence <= self._entries[-1].sequence:
            raise ValueError("log sequence must be strictly increasing")
        self._entries.append(entry)

    def entries(self) -> tuple[LogEntry, ...]:
        return tuple(self._entries)


@dataclass(frozen=True, slots=True)
class ReplayEntry:
    sequence: int
    request: CommandRequest
    result: CommandResult
    random_before: RandomState
    random_after: RandomState
    logs: tuple[LogEntry, ...] = ()


@dataclass(frozen=True, slots=True)
class ReplayDocument:
    format_version: int
    initial_state: Mapping[str, Any]
    entries: tuple[ReplayEntry, ...]


class ReplayLog:
    """Append-only deterministic record; deliberately has no wall-clock field."""

    def __init__(self, initial_state: GameState) -> None:
        self._initial_state = encode_game_state(initial_state)
        self._entries: list[ReplayEntry] = []

    def append(self, entry: ReplayEntry) -> None:
        if entry.sequence < 0:
            raise ValueError("replay sequence must not be negative")
        if self._entries and entry.sequence <= self._entries[-1].sequence:
            raise ValueError("replay sequence must be strictly increasing")
        if entry.result.command_id != entry.request.command_id:
            raise ValueError("replay result does not match request command_id")
        self._entries.append(entry)

    def __iter__(self) -> Iterator[ReplayEntry]:
        return iter(tuple(self._entries))

    def entries(self) -> tuple[ReplayEntry, ...]:
        return tuple(self._entries)

    def document(self) -> ReplayDocument:
        return ReplayDocument(
            format_version=REPLAY_FORMAT_VERSION,
            initial_state=deepcopy(self._initial_state),
            entries=self.entries(),
        )


@dataclass(frozen=True, slots=True)
class ReplayVerification:
    matches: bool
    sequence: int | None = None
    expected_code: ErrorCode | None = None
    actual_code: ErrorCode | None = None
