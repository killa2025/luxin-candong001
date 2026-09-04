from __future__ import annotations

import math
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any

from furnace_winter.models import GameState


COMMAND_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]*$")


def invalid_command_format_details() -> dict[str, Any]:
    """Return stable syntax guidance without recommending a game action."""

    request_shape = {
        "command_id": "STRING",
        "name": "COMMAND_NAME_STRING",
        "arguments": "OBJECT",
        "expected_state_sequence": "INTEGER_OR_NULL",
    }
    return {
        "reason": "invalid_command_format",
        "accepted_envelope_shapes": (
            {
                "type": "command",
                "request": dict(request_shape),
            },
            dict(request_shape),
        ),
        "request_shape": dict(request_shape),
        "request_fields": {
            "required": ["name"],
            "optional": [
                "command_id",
                "arguments",
                "expected_state_sequence",
            ],
        },
        "request_defaults": {
            "command_id": "SESSION_ASSIGNED_STRING",
            "arguments": {},
            "expected_state_sequence": "CURRENT_STATE_SEQUENCE",
        },
        "unsupported_field_aliases": {
            "command": "name",
        },
    }


def invalid_arguments_format_details(arguments: Any) -> dict[str, Any]:
    """Return protocol guidance when the arguments container is not an object."""

    if isinstance(arguments, Mapping):
        actual_kind = "OBJECT"
    elif isinstance(arguments, list):
        actual_kind = "ARRAY"
    elif arguments is None:
        actual_kind = "NULL"
    elif isinstance(arguments, bool):
        actual_kind = "BOOLEAN"
    elif isinstance(arguments, str):
        actual_kind = "STRING"
    elif isinstance(arguments, (int, float)):
        actual_kind = "NUMBER"
    else:
        actual_kind = "NON_JSON"
    details = invalid_command_format_details()
    details["field_errors"] = {
        "arguments": {
            "required_kind": "OBJECT",
            "actual_kind": actual_kind,
        }
    }
    return details


class ErrorCode(StrEnum):
    OK = "OK"
    INVALID_COMMAND_FORMAT = "INVALID_COMMAND_FORMAT"
    COMMAND_NOT_REGISTERED = "COMMAND_NOT_REGISTERED"
    INVALID_ARGUMENTS = "INVALID_ARGUMENTS"
    STALE_STATE = "STALE_STATE"
    ILLEGAL_COMMAND = "ILLEGAL_COMMAND"
    END_DAY_CONFIRMATION_REQUIRED = "END_DAY_CONFIRMATION_REQUIRED"
    END_DAY_BLOCKED = "END_DAY_BLOCKED"
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
    command_exists: bool = field(default=True, kw_only=True)
    executable: bool = field(default=True, kw_only=True)
    unavailable_reason: str | None = field(default=None, kw_only=True)
    required_arguments: Mapping[str, ArgumentKind] = field(default_factory=dict)
    optional_arguments: Mapping[str, ArgumentKind] = field(default_factory=dict)
    argument_options: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    allow_extra_arguments: bool = False
    argument_semantics: Mapping[str, str] = field(default_factory=dict)
    # Discovery metadata; existing command-specific legality keeps its priority.
    argument_minimums: Mapping[str, int] = field(default_factory=dict)
    related_rule_sections: tuple[str, ...] = ()
    related_protocol_contracts: tuple[str, ...] = ()
    pre_execution_text_id: str | None = None
    pre_execution_text_template: str | None = None
    pre_execution_text_parameters: Mapping[str, str] = field(default_factory=dict)


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
    """Holds machine-readable command schemas without strategy metadata."""

    def __init__(self) -> None:
        self._specs: dict[str, CommandSpec] = {}

    def register(self, spec: CommandSpec) -> None:
        if not COMMAND_NAME_PATTERN.fullmatch(spec.name):
            raise ValueError(f"invalid command name: {spec.name!r}")
        if spec.name in self._specs:
            raise ValueError(f"duplicate command spec: {spec.name}")
        if type(spec.command_exists) is not bool:
            raise ValueError("command exists must be a boolean")
        if type(spec.executable) is not bool:
            raise ValueError("command executable state must be a boolean")
        if not spec.command_exists:
            raise ValueError("registered command specs must exist")
        if spec.executable and spec.unavailable_reason is not None:
            raise ValueError("executable commands cannot have an unavailable reason")
        if not spec.executable and (
            not isinstance(spec.unavailable_reason, str)
            or not COMMAND_NAME_PATTERN.fullmatch(spec.unavailable_reason)
        ):
            raise ValueError(
                "unavailable commands require a stable unavailable reason"
            )
        overlap = set(spec.required_arguments) & set(spec.optional_arguments)
        if overlap:
            raise ValueError(f"arguments cannot be both required and optional: {overlap}")
        known_arguments = set(spec.required_arguments) | set(spec.optional_arguments)
        unknown_options = set(spec.argument_options) - known_arguments
        for argument, minimum in spec.argument_minimums.items():
            kind = spec.required_arguments.get(
                argument, spec.optional_arguments.get(argument)
            )
            if kind != ArgumentKind.INTEGER or type(minimum) is not int:
                raise ValueError("argument minimums require integer arguments and bounds")
        if unknown_options:
            raise ValueError(f"argument options reference unknown arguments: {unknown_options}")
        unknown_semantics = set(spec.argument_semantics) - known_arguments
        if unknown_semantics:
            raise ValueError(
                "argument semantics reference unknown arguments: "
                f"{unknown_semantics}"
            )
        for argument, options in spec.argument_options.items():
            if not options or any(
                not isinstance(option, str)
                or not option.strip()
                or option != option.strip()
                for option in options
            ):
                raise ValueError(f"argument options must be normalized strings: {argument}")
        for argument, semantic in spec.argument_semantics.items():
            if (
                not isinstance(semantic, str)
                or not COMMAND_NAME_PATTERN.fullmatch(semantic)
            ):
                raise ValueError(
                    f"argument semantics must use stable normalized ids: {argument}"
                )
        if any(
            not isinstance(section, str)
            or not COMMAND_NAME_PATTERN.fullmatch(section)
            for section in spec.related_rule_sections
        ):
            raise ValueError("related rule sections must use stable normalized ids")
        if len(set(spec.related_rule_sections)) != len(spec.related_rule_sections):
            raise ValueError("related rule sections must be unique")
        if any(
            not isinstance(contract, str)
            or not COMMAND_NAME_PATTERN.fullmatch(contract)
            for contract in spec.related_protocol_contracts
        ):
            raise ValueError(
                "related protocol contracts must use stable normalized ids"
            )
        if len(set(spec.related_protocol_contracts)) != len(
            spec.related_protocol_contracts
        ):
            raise ValueError("related protocol contracts must be unique")
        if (spec.pre_execution_text_id is None) != (
            spec.pre_execution_text_template is None
        ):
            raise ValueError(
                "pre-execution text id and template must be provided together"
            )
        if spec.pre_execution_text_id is not None and (
            not COMMAND_NAME_PATTERN.fullmatch(spec.pre_execution_text_id)
            or not spec.pre_execution_text_template
            or spec.pre_execution_text_template != spec.pre_execution_text_template.strip()
        ):
            raise ValueError("pre-execution text must be normalized and non-blank")
        if spec.pre_execution_text_id is None and spec.pre_execution_text_parameters:
            raise ValueError("pre-execution parameters require registered text")
        if any(
            not COMMAND_NAME_PATTERN.fullmatch(parameter)
            or not isinstance(source, str)
            or not source.strip()
            or source != source.strip()
            for parameter, source in spec.pre_execution_text_parameters.items()
        ):
            raise ValueError("pre-execution text parameters must be normalized")
        if "confirm" in known_arguments and "confirm" not in spec.argument_semantics:
            spec = replace(
                spec,
                argument_semantics={
                    **spec.argument_semantics,
                    "confirm": "explicit_true_only_never_preview",
                },
            )
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
            return CommandValidation(
                False,
                ErrorCode.INVALID_COMMAND_FORMAT,
                invalid_command_format_details(),
            )
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
                invalid_command_format_details(),
            )
        if request.expected_state_sequence is not None and (
            not isinstance(request.expected_state_sequence, int)
            or isinstance(request.expected_state_sequence, bool)
            or request.expected_state_sequence < 0
        ):
            return CommandValidation(
                False,
                ErrorCode.INVALID_COMMAND_FORMAT,
                invalid_command_format_details(),
            )
        if not isinstance(request.arguments, Mapping):
            return CommandValidation(
                False,
                ErrorCode.INVALID_COMMAND_FORMAT,
                invalid_arguments_format_details(request.arguments),
            )
        if not _is_json_value(request.arguments):
            return CommandValidation(
                False,
                ErrorCode.INVALID_ARGUMENTS,
                {"reason": "arguments_contains_non_json_value"},
            )

        spec = self._catalog.get(request.name)
        if spec is None:
            return CommandValidation(False, ErrorCode.COMMAND_NOT_REGISTERED)

        known_arguments = set(spec.required_arguments) | set(
            spec.optional_arguments
        )
        if (
            "confirm" in known_arguments
            and request.arguments.get("confirm") is False
        ):
            return CommandValidation(
                False,
                ErrorCode.ILLEGAL_COMMAND,
                {
                    "reason": "confirm_false_is_not_preview",
                    "required_confirmation_value": True,
                    "state_will_change": False,
                },
            )

        if state is not None and request.expected_state_sequence is not None:
            if request.expected_state_sequence != state.command_sequence:
                return CommandValidation(
                    False,
                    ErrorCode.STALE_STATE,
                    {
                        "expected": request.expected_state_sequence,
                        "actual": state.command_sequence,
                        "reason": "state_sequence_mismatch",
                        "current_state_sequence": state.command_sequence,
                        "requires_fresh_observation": True,
                        "retry_expected_state_sequence": state.command_sequence,
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

        invalid_options = sorted(
            name
            for name, options in spec.argument_options.items()
            if name in request.arguments
            and request.arguments[name] not in options
        )
        if invalid_options:
            return CommandValidation(
                False,
                ErrorCode.INVALID_ARGUMENTS,
                {
                    "invalid_options": invalid_options,
                    "allowed_options": {
                        name: list(spec.argument_options[name])
                        for name in invalid_options
                    },
                },
            )

        if state is not None and legality_check is not None:
            legality = legality_check(state, request)
            if not legality.is_valid:
                return legality
        return CommandValidation.valid()
