from __future__ import annotations

import math
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from furnace_winter.models import GameState


COMMAND_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]*$")


class ErrorCode(StrEnum):
    OK = "OK"
    INVALID_COMMAND_FORMAT = "INVALID_COMMAND_FORMAT"
    COMMAND_NOT_REGISTERED = "COMMAND_NOT_REGISTERED"
    INVALID_ARGUMENTS = "INVALID_ARGUMENTS"
    STALE_STATE = "STALE_STATE"
    ILLEGAL_COMMAND = "ILLEGAL_COMMAND"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ArgumentKind(StrEnum):
    STRING = "STRING"
    INTEGER = "INTEGER"
    NUMBER = "NUMBER"
    BOOLEAN = "BOOLEAN"
    ARRAY = "ARRAY"
    OBJECT = "OBJECT"


@dataclass(frozen=True, slots=True)
class CommandRequest:
    command_id: str
    name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    expected_state_sequence: int | None = None


@dataclass(frozen=True, slots=True)
class CommandSpec:
    name: str
    required_arguments: Mapping[str, ArgumentKind] = field(default_factory=dict)
    optional_arguments: Mapping[str, ArgumentKind] = field(default_factory=dict)
    allow_extra_arguments: bool = False


@dataclass(frozen=True, slots=True)
class CommandValidation:
    is_valid: bool
    code: ErrorCode
    details: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def valid(cls) -> CommandValidation:
        return cls(is_valid=True, code=ErrorCode.OK)


LegalityCheck = Callable[[GameState, CommandRequest], CommandValidation]


class CommandCatalog:
    """Holds schemas only; Patch 001 registers no gameplay commands."""

    def __init__(self) -> None:
        self._specs: dict[str, CommandSpec] = {}

    def register(self, spec: CommandSpec) -> None:
        if not COMMAND_NAME_PATTERN.fullmatch(spec.name):
            raise ValueError(f"invalid command name: {spec.name!r}")
        if spec.name in self._specs:
            raise ValueError(f"duplicate command spec: {spec.name}")
        overlap = set(spec.required_arguments) & set(spec.optional_arguments)
        if overlap:
            raise ValueError(f"arguments cannot be both required and optional: {overlap}")
        self._specs[spec.name] = spec

    def get(self, name: str) -> CommandSpec | None:
        return self._specs.get(name)

    def specs(self) -> tuple[CommandSpec, ...]:
        return tuple(self._specs[name] for name in sorted(self._specs))


def _is_json_value(value: Any) -> bool:
    if value is None or isinstance(value, (str, bool, int)):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(_is_json_value(child) for child in value)
    if isinstance(value, Mapping):
        return all(
            isinstance(key, str) and _is_json_value(child)
            for key, child in value.items()
        )
    return False


def _matches_kind(value: Any, kind: ArgumentKind) -> bool:
    if kind is ArgumentKind.STRING:
        return isinstance(value, str)
    if kind is ArgumentKind.INTEGER:
        return isinstance(value, int) and not isinstance(value, bool)
    if kind is ArgumentKind.NUMBER:
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and (not isinstance(value, float) or math.isfinite(value))
        )
    if kind is ArgumentKind.BOOLEAN:
        return isinstance(value, bool)
    if kind is ArgumentKind.ARRAY:
        return isinstance(value, list)
    if kind is ArgumentKind.OBJECT:
        return isinstance(value, Mapping)
    return False


class CommandValidator:
    def __init__(self, catalog: CommandCatalog) -> None:
        self._catalog = catalog

    def validate(
        self,
        request: CommandRequest,
        state: GameState | None = None,
        legality_check: LegalityCheck | None = None,
    ) -> CommandValidation:
        if not isinstance(request, CommandRequest):
            return CommandValidation(False, ErrorCode.INVALID_COMMAND_FORMAT)
        if (
            not isinstance(request.command_id, str)
            or not request.command_id.strip()
            or request.command_id != request.command_id.strip()
            or not isinstance(request.name, str)
            or not COMMAND_NAME_PATTERN.fullmatch(request.name)
        ):
            return CommandValidation(
                False,
                ErrorCode.INVALID_COMMAND_FORMAT,
            )
        if request.expected_state_sequence is not None and (
            not isinstance(request.expected_state_sequence, int)
            or isinstance(request.expected_state_sequence, bool)
            or request.expected_state_sequence < 0
        ):
            return CommandValidation(False, ErrorCode.INVALID_COMMAND_FORMAT)
        if not isinstance(request.arguments, Mapping) or not _is_json_value(request.arguments):
            return CommandValidation(False, ErrorCode.INVALID_ARGUMENTS)

        spec = self._catalog.get(request.name)
        if spec is None:
            return CommandValidation(False, ErrorCode.COMMAND_NOT_REGISTERED)

        if state is not None and request.expected_state_sequence is not None:
            if request.expected_state_sequence != state.command_sequence:
                return CommandValidation(
                    False,
                    ErrorCode.STALE_STATE,
                    {
                        "expected": request.expected_state_sequence,
                        "actual": state.command_sequence,
                    },
                )

        provided = set(request.arguments)
        required = set(spec.required_arguments)
        allowed = required | set(spec.optional_arguments)
        missing = sorted(required - provided)
        unexpected = sorted(provided - allowed) if not spec.allow_extra_arguments else []
        if missing or unexpected:
            return CommandValidation(
                False,
                ErrorCode.INVALID_ARGUMENTS,
                {"missing": missing, "unexpected": unexpected},
            )

        kinds = dict(spec.optional_arguments)
        kinds.update(spec.required_arguments)
        wrong_types = sorted(
            name
            for name, value in request.arguments.items()
            if name in kinds and not _matches_kind(value, kinds[name])
        )
        if wrong_types:
            return CommandValidation(
                False,
                ErrorCode.INVALID_ARGUMENTS,
                {"wrong_types": wrong_types},
            )

        if state is not None and legality_check is not None:
            legality = legality_check(state, request)
            if not legality.is_valid:
                return legality
        return CommandValidation.valid()
