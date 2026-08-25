from __future__ import annotations

from collections.abc import Iterator, Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from furnace_winter.interface.commands import (
    COMMAND_NAME_PATTERN,
    CommandRequest,
    ErrorCode,
)
from furnace_winter.interface.feedback import (
    CommandResult,
    FeedbackItem,
    FeedbackLevel,
)
from furnace_winter.models import (
    DeterministicRandom,
    GameState,
    RandomState,
    decode_game_state,
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


def _require_fields(
    value: Any,
    expected_fields: frozenset[str],
    name: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a JSON object")
    if set(value) != expected_fields:
        raise ValueError(f"{name} has invalid fields")
    return value


def _decode_random_state(value: Any, name: str) -> RandomState:
    document = _require_fields(
        value,
        frozenset({"seed", "internal_state", "draws", "algorithm"}),
        name,
    )
    state = RandomState(
        seed=document["seed"],
        internal_state=document["internal_state"],
        draws=document["draws"],
        algorithm=document["algorithm"],
    )
    DeterministicRandom.from_state(state)
    return state


def _decode_request(value: Any) -> CommandRequest:
    document = _require_fields(
        value,
        frozenset(
            {
                "command_id",
                "name",
                "arguments",
                "expected_state_sequence",
            }
        ),
        "replay request",
    )
    command_id = document["command_id"]
    name = document["name"]
    expected_state_sequence = document["expected_state_sequence"]
    if (
        not isinstance(command_id, str)
        or not command_id.strip()
        or command_id != command_id.strip()
        or not isinstance(name, str)
        or not COMMAND_NAME_PATTERN.fullmatch(name)
        or (
            expected_state_sequence is not None
            and (
                not isinstance(expected_state_sequence, int)
                or isinstance(expected_state_sequence, bool)
                or expected_state_sequence < 0
            )
        )
    ):
        raise ValueError("replay request identity is invalid")
    return CommandRequest(
        command_id=command_id,
        name=name,
        arguments=_snapshot_mapping(
            document["arguments"],
            "replay request arguments",
        ),
        expected_state_sequence=expected_state_sequence,
    )


def _decode_feedback(value: Any) -> FeedbackItem:
    document = _require_fields(
        value,
        frozenset({"level", "text_id", "data"}),
        "replay feedback",
    )
    text_id = document["text_id"]
    if text_id is not None and (
        not isinstance(text_id, str)
        or not text_id.strip()
        or text_id != text_id.strip()
    ):
        raise ValueError("replay feedback text_id is invalid")
    return FeedbackItem(
        level=FeedbackLevel(document["level"]),
        text_id=text_id,
        data=_snapshot_mapping(document["data"], "replay feedback data"),
    )


def _decode_result(value: Any) -> CommandResult:
    document = _require_fields(
        value,
        frozenset(
            {
                "command_id",
                "accepted",
                "code",
                "state_changed",
                "state_sequence",
                "feedback",
                "data",
            }
        ),
        "replay result",
    )
    command_id = document["command_id"]
    accepted = document["accepted"]
    state_changed = document["state_changed"]
    state_sequence = document["state_sequence"]
    feedback = document["feedback"]
    if (
        not isinstance(command_id, str)
        or not command_id.strip()
        or command_id != command_id.strip()
        or not isinstance(accepted, bool)
        or not isinstance(state_changed, bool)
        or not isinstance(state_sequence, int)
        or isinstance(state_sequence, bool)
        or state_sequence < 0
        or not isinstance(feedback, list)
    ):
        raise ValueError("replay result is invalid")
    code = ErrorCode(document["code"])
    if accepted != (code is ErrorCode.OK):
        raise ValueError("replay result acceptance and code are inconsistent")
    if not accepted and state_changed:
        raise ValueError("rejected replay result cannot change state")
    return CommandResult(
        command_id=command_id,
        accepted=accepted,
        code=code,
        state_changed=state_changed,
        state_sequence=state_sequence,
        feedback=tuple(_decode_feedback(item) for item in feedback),
        data=_snapshot_mapping(document["data"], "replay result data"),
    )


def _decode_log_entry(value: Any) -> LogEntry:
    document = _require_fields(
        value,
        frozenset({"sequence", "category", "code", "payload"}),
        "replay log entry",
    )
    code = document["code"]
    if (
        not isinstance(code, str)
        or not code.strip()
        or code != code.strip()
    ):
        raise ValueError("replay log code is invalid")
    return LogEntry(
        sequence=_validate_sequence(
            document["sequence"],
            "replay log sequence",
        ),
        category=LogCategory(document["category"]),
        code=code,
        payload=_snapshot_mapping(
            document["payload"],
            "replay log payload",
        ),
    )


def decode_log_entry(value: Any) -> LogEntry:
    """Strictly decode one persisted structured log entry."""

    return _decode_log_entry(value)


def _decode_replay_entry(value: Any) -> ReplayEntry:
    document = _require_fields(
        value,
        frozenset(
            {
                "sequence",
                "request",
                "result",
                "random_before",
                "random_after",
                "logs",
            }
        ),
        "replay entry",
    )
    logs = document["logs"]
    if not isinstance(logs, list):
        raise TypeError("replay entry logs must be an array")
    event_log = EventLog()
    for log_entry in logs:
        event_log.append(_decode_log_entry(log_entry))
    return ReplayEntry(
        sequence=_validate_sequence(
            document["sequence"],
            "replay sequence",
        ),
        request=_decode_request(document["request"]),
        result=_decode_result(document["result"]),
        random_before=_decode_random_state(
            document["random_before"],
            "replay random_before",
        ),
        random_after=_decode_random_state(
            document["random_after"],
            "replay random_after",
        ),
        logs=event_log.entries(),
    )


def decode_replay_document(value: Any) -> ReplayDocument:
    """Strictly decode a persisted replay before allowing replacement."""

    document = _require_fields(
        value,
        frozenset({"format_version", "initial_state", "entries"}),
        "replay document",
    )
    format_version = document["format_version"]
    entries = document["entries"]
    if (
        not isinstance(format_version, int)
        or isinstance(format_version, bool)
        or format_version != REPLAY_FORMAT_VERSION
    ):
        raise ValueError("unsupported replay format_version")
    if not isinstance(entries, list):
        raise TypeError("replay entries must be an array")
    initial_state = decode_game_state(document["initial_state"])
    replay = ReplayLog(initial_state)
    for entry in entries:
        replay.append(_decode_replay_entry(entry))
    return replay.document()


@dataclass(frozen=True, slots=True)
class ReplayVerification:
    matches: bool
    sequence: int | None = None
    expected_code: ErrorCode | None = None
    actual_code: ErrorCode | None = None
