from __future__ import annotations

from collections.abc import Iterator, Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from furnace_winter.interface.commands import CommandRequest, ErrorCode
from furnace_winter.interface.feedback import CommandResult, FeedbackItem
from furnace_winter.models import (
    GameState,
    RandomState,
    encode_game_state,
    snapshot_json,
)


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


def _snapshot_mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a JSON object")
    snapshot = snapshot_json(value)
    if not isinstance(snapshot, dict):
        raise TypeError(f"{name} must be a JSON object")
    return snapshot


def _validate_sequence(value: Any, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _snapshot_log_entry(entry: LogEntry) -> LogEntry:
    return LogEntry(
        sequence=entry.sequence,
        category=entry.category,
        code=entry.code,
        payload=_snapshot_mapping(entry.payload, "log payload"),
    )


def _snapshot_request(request: CommandRequest) -> CommandRequest:
    return CommandRequest(
        command_id=request.command_id,
        name=request.name,
        arguments=_snapshot_mapping(request.arguments, "request arguments"),
        expected_state_sequence=request.expected_state_sequence,
    )


def _snapshot_feedback(item: FeedbackItem) -> FeedbackItem:
    return FeedbackItem(
        level=item.level,
        text_id=item.text_id,
        data=_snapshot_mapping(item.data, "feedback data"),
    )


def _snapshot_result(result: CommandResult) -> CommandResult:
    return CommandResult(
        command_id=result.command_id,
        accepted=result.accepted,
        code=result.code,
        state_changed=result.state_changed,
        state_sequence=result.state_sequence,
        feedback=tuple(_snapshot_feedback(item) for item in result.feedback),
        data=_snapshot_mapping(result.data, "result data"),
    )


class EventLog:
    """Append-only ordered log interface shared by execution and replay."""

    def __init__(self) -> None:
        self._entries: list[LogEntry] = []

    def append(self, entry: LogEntry) -> None:
        snapshot = _snapshot_log_entry(entry)
        _validate_sequence(snapshot.sequence, "log sequence")
        if self._entries and snapshot.sequence <= self._entries[-1].sequence:
            raise ValueError("log sequence must be strictly increasing")
        self._entries.append(snapshot)

    def entries(self) -> tuple[LogEntry, ...]:
        return deepcopy(tuple(self._entries))


@dataclass(frozen=True, slots=True)
class ReplayEntry:
    sequence: int
    request: CommandRequest
    result: CommandResult
    random_before: RandomState
    random_after: RandomState
    logs: tuple[LogEntry, ...] = ()


def _snapshot_replay_entry(entry: ReplayEntry) -> ReplayEntry:
    return ReplayEntry(
        sequence=entry.sequence,
        request=_snapshot_request(entry.request),
        result=_snapshot_result(entry.result),
        random_before=entry.random_before,
        random_after=entry.random_after,
        logs=tuple(_snapshot_log_entry(item) for item in entry.logs),
    )


@dataclass(frozen=True, slots=True)
class ReplayDocument:
    format_version: int
    initial_state: Mapping[str, Any]
    entries: tuple[ReplayEntry, ...]


class ReplayLog:
    """Append-only deterministic record; deliberately has no wall-clock field."""

    def __init__(self, initial_state: GameState) -> None:
        self._initial_state = _snapshot_mapping(
            encode_game_state(initial_state), "initial state"
        )
        self._entries: list[ReplayEntry] = []

    def append(self, entry: ReplayEntry) -> None:
        snapshot = _snapshot_replay_entry(entry)
        _validate_sequence(snapshot.sequence, "replay sequence")
        if self._entries and snapshot.sequence <= self._entries[-1].sequence:
            raise ValueError("replay sequence must be strictly increasing")
        if snapshot.result.command_id != snapshot.request.command_id:
            raise ValueError("replay result does not match request command_id")
        self._entries.append(snapshot)

    def __iter__(self) -> Iterator[ReplayEntry]:
        return iter(self.entries())

    def entries(self) -> tuple[ReplayEntry, ...]:
        return deepcopy(tuple(self._entries))

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
