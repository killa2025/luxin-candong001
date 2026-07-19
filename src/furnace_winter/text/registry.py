from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from furnace_winter.config import ConfigStatus


class TextVisibility(StrEnum):
    PLAYER_VISIBLE = "PLAYER_VISIBLE"
    COMMON = "COMMON"
    SYSTEM_INTERNAL = "SYSTEM_INTERNAL"
    UNDECIDED = "UNDECIDED"


@dataclass(frozen=True, slots=True)
class TextEntry:
    text_id: str
    text: str
    status: ConfigStatus
    visibility: TextVisibility
    source: str


@dataclass(frozen=True, slots=True)
class MissingTextReport:
    required_ids: tuple[str, ...]
    missing_ids: tuple[str, ...]

    @property
    def is_complete(self) -> bool:
        return not self.missing_ids


class TextRegistryError(ValueError):
    pass


class MissingTextError(KeyError):
    def __init__(self, text_id: str) -> None:
        self.text_id = text_id
        super().__init__(text_id)


def _validate_normalized_id(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be blank")
    if value != value.strip():
        raise ValueError(f"{name} must not have leading or trailing whitespace")
    return value


class TextRegistry:
    """Runtime-only registry for confirmed, non-internal player text."""

    def __init__(self) -> None:
        self._entries: dict[str, TextEntry] = {}

    def register(self, entry: TextEntry) -> None:
        try:
            _validate_normalized_id(entry.text_id, "text_id")
        except ValueError as exc:
            raise TextRegistryError(str(exc)) from exc
        if not isinstance(entry.text, str) or not entry.text.strip():
            raise TextRegistryError("runtime text must not be blank")
        if not isinstance(entry.status, ConfigStatus):
            raise TextRegistryError("text status must be a ConfigStatus")
        if not entry.status.is_runtime:
            raise TextRegistryError(f"non-runtime status is excluded: {entry.status}")
        if entry.visibility not in {
            TextVisibility.PLAYER_VISIBLE,
            TextVisibility.COMMON,
        }:
            raise TextRegistryError(
                f"visibility is excluded from TextRegistry: {entry.visibility}"
            )
        if entry.text_id in self._entries:
            raise TextRegistryError(f"duplicate text_id: {entry.text_id}")
        self._entries[entry.text_id] = entry

    def get(self, text_id: str) -> TextEntry | None:
        return self._entries.get(text_id)

    def require(self, text_id: str) -> TextEntry:
        entry = self.get(text_id)
        if entry is None:
            raise MissingTextError(text_id)
        return entry

    def report_missing(self, required_ids: list[str] | tuple[str, ...]) -> MissingTextReport:
        required = tuple(dict.fromkeys(required_ids))
        missing = tuple(text_id for text_id in required if text_id not in self._entries)
        return MissingTextReport(required_ids=required, missing_ids=missing)

    def entries(self) -> tuple[TextEntry, ...]:
        return tuple(self._entries[text_id] for text_id in sorted(self._entries))


@dataclass(frozen=True, slots=True)
class PendingEntry:
    entry_id: str
    status: ConfigStatus
    source: str
    note: str = ""


class PendingRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, PendingEntry] = {}

    def register(self, entry: PendingEntry) -> None:
        _validate_normalized_id(entry.entry_id, "entry_id")
        if entry.status not in {ConfigStatus.PENDING, ConfigStatus.TODO_TEXT}:
            raise ValueError("PendingRegistry only accepts PENDING or TODO_TEXT")
        if entry.entry_id in self._entries:
            raise ValueError(f"duplicate pending entry: {entry.entry_id}")
        self._entries[entry.entry_id] = entry

    def entries(self) -> tuple[PendingEntry, ...]:
        return tuple(self._entries[key] for key in sorted(self._entries))

    def todo_text_ids(self) -> tuple[str, ...]:
        return tuple(
            entry.entry_id
            for entry in self.entries()
            if entry.status is ConfigStatus.TODO_TEXT
        )


@dataclass(frozen=True, slots=True)
class DeprecatedEntry:
    entry_id: str
    source: str
    replacement_id: str | None = None


class DeprecatedRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, DeprecatedEntry] = {}

    def register(self, entry: DeprecatedEntry) -> None:
        _validate_normalized_id(entry.entry_id, "entry_id")
        if entry.replacement_id is not None:
            _validate_normalized_id(entry.replacement_id, "replacement_id")
        if entry.entry_id in self._entries:
            raise ValueError(f"duplicate deprecated entry: {entry.entry_id}")
        self._entries[entry.entry_id] = entry

    def contains(self, entry_id: str) -> bool:
        return entry_id in self._entries

    def entries(self) -> tuple[DeprecatedEntry, ...]:
        return tuple(self._entries[key] for key in sorted(self._entries))
