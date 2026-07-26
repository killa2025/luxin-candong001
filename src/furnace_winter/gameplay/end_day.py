from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping
from copy import deepcopy
from dataclasses import dataclass, field, fields
from enum import StrEnum
from hashlib import sha256
from typing import Any

from furnace_winter.interface import (
    ArgumentKind,
    CommandCatalog,
    CommandRequest,
    CommandResult,
    CommandSpec,
    CommandValidator,
    ErrorCode,
    FeedbackItem,
    FeedbackLevel,
    LogCategory,
    LogEntry,
)
from furnace_winter.models import (
    DeterministicRandom,
    FINAL_DAY,
    GameState,
    RandomState,
    dumps,
    encode_game_state,
    snapshot_json,
    validate_game_state,
)


END_DAY_COMMAND = "game.end_day"
CONFIRM_END_DAY_COMMAND = "game.confirm_end_day"
AUTOSAVE_END_DAY_SLOT = "autosave_end_day"
CONFIRMATION_TOKEN_ARGUMENT = "confirmation_token"
CONFIRMATION_STATE_SEQUENCE_ARGUMENT = "state_sequence"
CONFIRMATION_WARNING_SIGNATURE_ARGUMENT = "warning_signature"
_IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]*$")


class RiskWarningLevel(StrEnum):
    A_INFO = "A_INFO"
    B_STRONG = "B_STRONG"
    C_HARD_BLOCK = "C_HARD_BLOCK"


@dataclass(frozen=True, slots=True)
class RiskWarning:
    warning_id: str
    level: RiskWarningLevel
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not _IDENTIFIER_PATTERN.fullmatch(self.warning_id):
            raise ValueError(f"invalid warning_id: {self.warning_id!r}")
        if not isinstance(self.level, RiskWarningLevel):
            raise TypeError("warning level must be RiskWarningLevel")
        object.__setattr__(self, "details", _snapshot_object(self.details, "details"))


class EndDayStage(StrEnum):
    LOCK_INPUT = "lock_input"
    VALIDATE_HARD_BLOCKS = "validate_hard_blocks"
    READ_FINAL_PLAN = "read_final_plan"
    PAY_HEATING_AND_OVERLOAD = "pay_heating_and_overload"
    RESOLVE_ACTUAL_HEATING = "resolve_actual_heating"
    UPDATE_FURNACE_PRESSURE = "update_furnace_pressure"
    CALCULATE_ZONE_TEMPERATURE = "calculate_zone_temperature"
    CALCULATE_BUILDING_TEMPERATURE = "calculate_building_temperature"
    RESOLVE_BUILDING_OPERATION = "resolve_building_operation"
    RESOLVE_COLLECTION_AND_PRODUCTION = "resolve_collection_and_production"
    RESOLVE_FOOD_CHAIN = "resolve_food_chain"
    RESOLVE_MEDICAL_DISEASE_AND_DEATH = "resolve_medical_disease_and_death"
    RESOLVE_HOUSING_COLD_AND_HUNGER = "resolve_housing_cold_and_hunger"
    RESOLVE_TRUST_AND_PANIC = "resolve_trust_and_panic"
    CLOSE_ACTION_EFFECTS = "close_action_effects"
    ADVANCE_AND_COMMIT_RESEARCH = "advance_and_commit_research"
    UPDATE_PROMISE_TARGETS = "update_promise_targets"
    CHECK_HARD_FAILS = "check_hard_fails"
    CHECK_HIDDEN_ACHIEVEMENTS = "check_hidden_achievements"
    RECORD_DAILY_LOG_AND_ENDING_TAGS = "record_daily_log_and_ending_tags"
    CLOSE_DAILY_EFFECTS = "close_daily_effects"
    WRITE_AUTOSAVE = "write_autosave"
    ADVANCE_DAY = "advance_day"


END_DAY_STAGES = tuple(EndDayStage)
_RESERVED_STAGES = frozenset(
    {
        EndDayStage.LOCK_INPUT,
        EndDayStage.VALIDATE_HARD_BLOCKS,
        EndDayStage.WRITE_AUTOSAVE,
        EndDayStage.ADVANCE_DAY,
    }
)


@dataclass(frozen=True, slots=True)
class AutosaveRecord:
    slot: str
    settled_day: int
    state: Mapping[str, Any]
    logs: tuple[LogEntry, ...]
    resume_stage: str

    def __post_init__(self) -> None:
        if self.slot != AUTOSAVE_END_DAY_SLOT:
            raise ValueError(f"autosave slot must be {AUTOSAVE_END_DAY_SLOT!r}")
        if (
            not isinstance(self.settled_day, int)
            or isinstance(self.settled_day, bool)
            or self.settled_day < 1
        ):
            raise ValueError("settled_day must be a positive integer")
        object.__setattr__(self, "state", _snapshot_object(self.state, "state"))
        object.__setattr__(self, "logs", deepcopy(tuple(self.logs)))
        if not isinstance(self.resume_stage, str) or not self.resume_stage.strip():
            raise ValueError("resume_stage must be a non-empty string")


@dataclass(frozen=True, slots=True)
class EndDayExecution:
    result: CommandResult
    warnings: tuple[RiskWarning, ...]
    logs: tuple[LogEntry, ...]
    random_before: RandomState
    random_after: RandomState
    autosave: AutosaveRecord | None = None


@dataclass(frozen=True, slots=True)
class EndDayConfirmation:
    token: str
    state_sequence: int
    warning_signature: str
    state_signature: str

    def as_data(self) -> dict[str, Any]:
        return {
            CONFIRMATION_TOKEN_ARGUMENT: self.token,
            CONFIRMATION_STATE_SEQUENCE_ARGUMENT: self.state_sequence,
            CONFIRMATION_WARNING_SIGNATURE_ARGUMENT: self.warning_signature,
        }


class EndDayAbort(RuntimeError):
    def __init__(
        self,
        code: ErrorCode = ErrorCode.END_DAY_BLOCKED,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        if code is ErrorCode.OK:
            raise ValueError("abort code cannot be OK")
        super().__init__(code.value)
        self.code = code
        self.details = _snapshot_object(details or {}, "abort details")


@dataclass(slots=True)
class EndDayContext:
    state: GameState
    random: DeterministicRandom
    settled_day: int
    stage: EndDayStage
    _emit: Callable[[str, Mapping[str, Any]], None] = field(repr=False)

    def emit(self, code: str, payload: Mapping[str, Any] | None = None) -> None:
        if not _IDENTIFIER_PATTERN.fullmatch(code):
            raise ValueError(f"invalid settlement log code: {code!r}")
        self._emit(code, payload or {})

    def abort(
        self,
        code: ErrorCode = ErrorCode.END_DAY_BLOCKED,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        raise EndDayAbort(code, details)


RiskEvaluator = Callable[[GameState], Iterable[RiskWarning]]
StageHandler = Callable[[EndDayContext], None]
AutosaveSink = Callable[[AutosaveRecord], None]
StateValidator = Callable[[GameState], None]
NewDayHandler = Callable[[GameState], None]


def _snapshot_object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be an object")
    snapshot = snapshot_json(value)
    if not isinstance(snapshot, dict):
        raise TypeError(f"{name} must be an object")
    return snapshot


def _warning_data(warnings: tuple[RiskWarning, ...]) -> list[dict[str, Any]]:
    return [
        {
            "warning_id": warning.warning_id,
            "level": warning.level.value,
            "details": _snapshot_object(warning.details, "warning details"),
        }
        for warning in warnings
    ]


def _warning_signature(warnings: tuple[RiskWarning, ...]) -> str:
    normalized = sorted(
        _warning_data(warnings),
        key=lambda item: (item["warning_id"], item["level"]),
    )
    return sha256(dumps(normalized).encode("utf-8")).hexdigest()


def _state_signature(state: GameState) -> str:
    return sha256(dumps(encode_game_state(state)).encode("utf-8")).hexdigest()


def _replace_state(target: GameState, source: GameState) -> None:
    for item in fields(GameState):
        setattr(target, item.name, deepcopy(getattr(source, item.name)))


def _result_command_id(request: Any) -> str:
    if isinstance(request, CommandRequest) and isinstance(request.command_id, str):
        return request.command_id
    return ""


def _safe_state_sequence(state: Any) -> int:
    value = getattr(state, "command_sequence", 0)
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return 0


def _safe_random_state(state: Any) -> RandomState:
    value = getattr(state, "random", None)
    return value if isinstance(value, RandomState) else RandomState.initial(0)


def build_end_day_catalog() -> CommandCatalog:
    catalog = CommandCatalog()
    catalog.register(CommandSpec(name=END_DAY_COMMAND))
    catalog.register(
        CommandSpec(
            name=CONFIRM_END_DAY_COMMAND,
            required_arguments={
                CONFIRMATION_TOKEN_ARGUMENT: ArgumentKind.STRING,
                CONFIRMATION_STATE_SEQUENCE_ARGUMENT: ArgumentKind.INTEGER,
                CONFIRMATION_WARNING_SIGNATURE_ARGUMENT: ArgumentKind.STRING,
            },
        )
    )
    return catalog


class EndDayEngine:
    """Deterministic Patch 002 orchestration; later patches supply stage rules."""

    def __init__(self, autosave_sink: AutosaveSink | None = None) -> None:
        self._catalog = build_end_day_catalog()
        self._validator = CommandValidator(self._catalog)
        self._risk_evaluators: list[RiskEvaluator] = []
        self._stage_handlers: dict[EndDayStage, list[StageHandler]] = {
            stage: [] for stage in END_DAY_STAGES
        }
        self._state_validators: list[StateValidator] = []
        self._new_day_handlers: list[NewDayHandler] = []
        self._autosave_sink = autosave_sink
        self._last_autosave: AutosaveRecord | None = None
        self._pending_confirmation: EndDayConfirmation | None = None

    def command_specs(self) -> tuple[CommandSpec, ...]:
        return self._catalog.specs()

    def register_risk_evaluator(self, evaluator: RiskEvaluator) -> None:
        if not callable(evaluator):
            raise TypeError("risk evaluator must be callable")
        self._risk_evaluators.append(evaluator)

    def register_stage_handler(
        self, stage: EndDayStage, handler: StageHandler
    ) -> None:
        if not isinstance(stage, EndDayStage):
            raise TypeError("stage must be EndDayStage")
        if stage in _RESERVED_STAGES:
            raise ValueError(f"stage {stage.value!r} is owned by the end_day engine")
        if not callable(handler):
            raise TypeError("stage handler must be callable")
        self._stage_handlers[stage].append(handler)

    def register_state_validator(self, validator: StateValidator) -> None:
        if not callable(validator):
            raise TypeError("state validator must be callable")
        self._state_validators.append(validator)

    def register_new_day_handler(self, handler: NewDayHandler) -> None:
        """Run deterministic new-day work after the calendar advances.

        Patch 007 uses this boundary for promise settlement and event generation;
        failures still roll back the entire end-day transaction.
        """

        if not callable(handler):
            raise TypeError("new day handler must be callable")
        self._new_day_handlers.append(handler)

    def last_autosave(self) -> AutosaveRecord | None:
        return deepcopy(self._last_autosave)

    def execute(self, state: GameState, request: CommandRequest) -> EndDayExecution:
        random_before = _safe_random_state(state)
        validation = self._validator.validate(request)
        if not validation.is_valid:
            return self._rejected(
                state,
                request,
                validation.code,
                (),
                validation.details,
                random_before,
            )
        try:
            self._validate_state(state)
        except Exception as exc:  # registered validators are extension boundaries
            self._pending_confirmation = None
            return self._rejected(
                state,
                request,
                ErrorCode.INTERNAL_ERROR,
                (),
                {
                    "failed_stage": "input_state_validation",
                    "exception_type": type(exc).__name__,
                },
                random_before,
            )
        validation = self._validator.validate(request, state)
        if not validation.is_valid:
            if isinstance(request, CommandRequest) and request.name == CONFIRM_END_DAY_COMMAND:
                self._pending_confirmation = None
            return self._rejected(
                state,
                request,
                validation.code,
                (),
                validation.details,
                random_before,
            )
        if state.calendar.is_day_locked or state.final_result.is_finalized:
            self._pending_confirmation = None
            return self._rejected(
                state,
                request,
                ErrorCode.ILLEGAL_COMMAND,
                (),
                {"reason": "day_not_open_for_planning"},
                random_before,
            )
        if state.final_result.hard_fail_type is not None:
            self._pending_confirmation = None
            return self._rejected(
                state,
                request,
                ErrorCode.ILLEGAL_COMMAND,
                (),
                {"reason": "game_already_failed"},
                random_before,
            )

        try:
            warnings = self._evaluate_warnings(state)
        except Exception as exc:  # evaluator is an extension boundary
            self._pending_confirmation = None
            return self._rejected(
                state,
                request,
                ErrorCode.INTERNAL_ERROR,
                (),
                {"failed_stage": "risk_evaluation", "exception_type": type(exc).__name__},
                random_before,
            )

        hard_blocks = tuple(
            warning
            for warning in warnings
            if warning.level is RiskWarningLevel.C_HARD_BLOCK
        )
        if hard_blocks:
            self._pending_confirmation = None
            return self._rejected(
                state,
                request,
                ErrorCode.END_DAY_BLOCKED,
                warnings,
                {"hard_block_ids": [item.warning_id for item in hard_blocks]},
                random_before,
            )

        strong_warnings = tuple(
            warning
            for warning in warnings
            if warning.level is RiskWarningLevel.B_STRONG
        )
        if request.name == END_DAY_COMMAND and strong_warnings:
            confirmation = self._create_confirmation(state, request, warnings)
            self._pending_confirmation = confirmation
            return self._rejected(
                state,
                request,
                ErrorCode.END_DAY_CONFIRMATION_REQUIRED,
                warnings,
                {
                    "strong_warning_ids": [item.warning_id for item in strong_warnings],
                    "confirmation": confirmation.as_data(),
                },
                random_before,
            )

        warning_signature = _warning_signature(warnings)
        if request.name == CONFIRM_END_DAY_COMMAND:
            confirmation = self._pending_confirmation
            if confirmation is None:
                return self._rejected(
                    state,
                    request,
                    ErrorCode.ILLEGAL_COMMAND,
                    warnings,
                    {"reason": "end_day_preview_required"},
                    random_before,
                )
            supplied = request.arguments
            if (
                supplied[CONFIRMATION_TOKEN_ARGUMENT] != confirmation.token
                or supplied[CONFIRMATION_STATE_SEQUENCE_ARGUMENT]
                != confirmation.state_sequence
                or supplied[CONFIRMATION_WARNING_SIGNATURE_ARGUMENT]
                != confirmation.warning_signature
            ):
                self._pending_confirmation = None
                return self._rejected(
                    state,
                    request,
                    ErrorCode.STALE_STATE,
                    warnings,
                    {"reason": "confirmation_mismatch"},
                    random_before,
                )
            if state.command_sequence != confirmation.state_sequence:
                self._pending_confirmation = None
                return self._rejected(
                    state,
                    request,
                    ErrorCode.STALE_STATE,
                    warnings,
                    {"reason": "confirmation_state_changed"},
                    random_before,
                )
            if _state_signature(state) != confirmation.state_signature:
                self._pending_confirmation = None
                return self._rejected(
                    state,
                    request,
                    ErrorCode.STALE_STATE,
                    warnings,
                    {"reason": "confirmation_state_changed"},
                    random_before,
                )
            if warning_signature != confirmation.warning_signature or not strong_warnings:
                self._pending_confirmation = None
                return self._rejected(
                    state,
                    request,
                    ErrorCode.STALE_STATE,
                    warnings,
                    {"reason": "confirmation_risks_changed"},
                    random_before,
                )
        else:
            self._pending_confirmation = None

        self._pending_confirmation = None
        return self._settle(
            state,
            request,
            warnings,
            warning_signature,
            random_before,
        )

    @staticmethod
    def _create_confirmation(
        state: GameState,
        request: CommandRequest,
        warnings: tuple[RiskWarning, ...],
    ) -> EndDayConfirmation:
        warning_signature = _warning_signature(warnings)
        state_signature = _state_signature(state)
        token_material = {
            "command_id": request.command_id,
            "state_sequence": state.command_sequence,
            "state_signature": state_signature,
            "warning_signature": warning_signature,
        }
        token = sha256(dumps(token_material).encode("utf-8")).hexdigest()
        return EndDayConfirmation(
            token=token,
            state_sequence=state.command_sequence,
            warning_signature=warning_signature,
            state_signature=state_signature,
        )

    def _evaluate_warnings(self, state: GameState) -> tuple[RiskWarning, ...]:
        warnings: list[RiskWarning] = []
        seen: set[str] = set()
        for evaluator in self._risk_evaluators:
            evaluated = evaluator(deepcopy(state))
            for warning in evaluated:
                if not isinstance(warning, RiskWarning):
                    raise TypeError("risk evaluator must return RiskWarning items")
                if warning.warning_id in seen:
                    raise ValueError(f"duplicate warning_id: {warning.warning_id}")
                seen.add(warning.warning_id)
                warnings.append(warning)
        return tuple(warnings)

    def _settle(
        self,
        state: GameState,
        request: CommandRequest,
        warnings: tuple[RiskWarning, ...],
        expected_warning_signature: str,
        random_before: RandomState,
    ) -> EndDayExecution:
        working = deepcopy(state)
        random = DeterministicRandom.from_state(working.random)
        settled_day = working.calendar.current_day
        logs: list[LogEntry] = []
        pending_autosave: AutosaveRecord | None = None
        current_stage = EndDayStage.LOCK_INPUT

        def append_log(code: str, payload: Mapping[str, Any]) -> None:
            logs.append(
                LogEntry(
                    sequence=len(logs) + 1,
                    category=LogCategory.SYSTEM,
                    code=code,
                    payload=_snapshot_object(payload, "settlement log payload"),
                )
            )

        try:
            for current_stage in END_DAY_STAGES:
                append_log(
                    f"end_day.stage.{current_stage.value}",
                    {"day": settled_day, "stage_index": END_DAY_STAGES.index(current_stage)},
                )
                if current_stage is EndDayStage.LOCK_INPUT:
                    working.calendar.is_day_locked = True
                    working.calendar.is_end_day_confirmed = True
                elif current_stage is EndDayStage.VALIDATE_HARD_BLOCKS:
                    rechecked_warnings = self._evaluate_warnings(working)
                    hard_blocks = tuple(
                        warning
                        for warning in rechecked_warnings
                        if warning.level is RiskWarningLevel.C_HARD_BLOCK
                    )
                    if hard_blocks:
                        raise EndDayAbort(
                            ErrorCode.END_DAY_BLOCKED,
                            {
                                "reason": "hard_block_after_input_lock",
                                "hard_block_ids": [
                                    warning.warning_id for warning in hard_blocks
                                ],
                            },
                        )
                    if (
                        _warning_signature(rechecked_warnings)
                        != expected_warning_signature
                    ):
                        raise EndDayAbort(
                            ErrorCode.STALE_STATE,
                            {"reason": "risks_changed_after_input_lock"},
                        )
                    warnings = rechecked_warnings
                elif current_stage is EndDayStage.WRITE_AUTOSAVE:
                    if working.calendar.current_day != settled_day:
                        raise RuntimeError("stage handler changed current_day")
                    if working.calendar.max_day != FINAL_DAY:
                        raise RuntimeError("stage handler changed max_day")
                    if working.command_sequence != state.command_sequence:
                        raise RuntimeError("stage handler changed command_sequence")
                    working.calendar.is_day_locked = True
                    working.calendar.is_end_day_confirmed = True
                    working.random = random.snapshot()
                    working.command_sequence = state.command_sequence + 1
                    self._validate_state(working)
                    resume_stage = (
                        "terminal_state"
                        if working.final_result.hard_fail_type is not None
                        else "final_settlement"
                        if settled_day == FINAL_DAY
                        else EndDayStage.ADVANCE_DAY.value
                    )
                    pending_autosave = AutosaveRecord(
                        slot=AUTOSAVE_END_DAY_SLOT,
                        settled_day=settled_day,
                        state=encode_game_state(working),
                        logs=tuple(logs),
                        resume_stage=resume_stage,
                    )
                elif current_stage is EndDayStage.ADVANCE_DAY:
                    self._advance_after_settlement(working)
                    if working.calendar.current_day != settled_day:
                        for handler in self._new_day_handlers:
                            handler(working)
                else:
                    context = EndDayContext(
                        state=working,
                        random=random,
                        settled_day=settled_day,
                        stage=current_stage,
                        _emit=append_log,
                    )
                    for handler in self._stage_handlers[current_stage]:
                        handler(context)
        except EndDayAbort as exc:
            return self._rejected(
                state,
                request,
                exc.code,
                warnings,
                {**exc.details, "failed_stage": current_stage.value},
                random_before,
                tuple(logs),
            )
        except Exception as exc:  # handlers are extension boundaries
            return self._rejected(
                state,
                request,
                ErrorCode.INTERNAL_ERROR,
                warnings,
                {
                    "failed_stage": current_stage.value,
                    "exception_type": type(exc).__name__,
                },
                random_before,
                tuple(logs),
            )

        working.random = random.snapshot()
        try:
            self._validate_state(working)
        except Exception as exc:  # registered validators are extension boundaries
            return self._rejected(
                state,
                request,
                ErrorCode.INTERNAL_ERROR,
                warnings,
                {
                    "failed_stage": "commit_state_validation",
                    "exception_type": type(exc).__name__,
                },
                random_before,
                tuple(logs),
            )
        if self._autosave_sink is not None:
            try:
                if pending_autosave is None:
                    raise RuntimeError("autosave record was not created")
                self._autosave_sink(deepcopy(pending_autosave))
            except Exception as exc:  # sink is an extension boundary
                return self._rejected(
                    state,
                    request,
                    ErrorCode.INTERNAL_ERROR,
                    warnings,
                    {
                        "failed_stage": EndDayStage.WRITE_AUTOSAVE.value,
                        "exception_type": type(exc).__name__,
                    },
                    random_before,
                    tuple(logs),
                )
        _replace_state(state, working)
        self._last_autosave = deepcopy(pending_autosave)
        transition = (
            "hard_fail"
            if state.final_result.hard_fail_type is not None
            else "final_settlement"
            if settled_day == FINAL_DAY
            else "next_day"
        )
        result = CommandResult(
            command_id=_result_command_id(request),
            accepted=True,
            code=ErrorCode.OK,
            state_changed=True,
            state_sequence=_safe_state_sequence(state),
            feedback=(
                FeedbackItem(
                    FeedbackLevel.INFO,
                    data={"settled_day": settled_day, "transition": transition},
                ),
            ),
            data={
                "settled_day": settled_day,
                "transition": transition,
                "warnings": _warning_data(warnings),
                "completed_stages": [stage.value for stage in END_DAY_STAGES],
                "autosave_slot": AUTOSAVE_END_DAY_SLOT,
            },
        )
        return EndDayExecution(
            result=result,
            warnings=warnings,
            logs=tuple(logs),
            random_before=random_before,
            random_after=state.random,
            autosave=deepcopy(pending_autosave),
        )

    def _validate_state(self, state: GameState) -> None:
        validate_game_state(state)
        for validator in self._state_validators:
            validator(deepcopy(state))

    @staticmethod
    def _advance_after_settlement(state: GameState) -> None:
        if state.final_result.hard_fail_type is not None:
            return
        if state.calendar.current_day >= FINAL_DAY:
            return
        state.calendar.current_day += 1
        state.calendar.is_day_locked = False
        state.calendar.is_end_day_confirmed = False

    @staticmethod
    def _rejected(
        state: GameState,
        request: CommandRequest,
        code: ErrorCode,
        warnings: tuple[RiskWarning, ...],
        details: Mapping[str, Any],
        random_before: RandomState,
        logs: tuple[LogEntry, ...] = (),
    ) -> EndDayExecution:
        result = CommandResult(
            command_id=_result_command_id(request),
            accepted=False,
            code=code,
            state_changed=False,
            state_sequence=_safe_state_sequence(state),
            feedback=(
                FeedbackItem(
                    FeedbackLevel.ERROR
                    if code not in {ErrorCode.END_DAY_CONFIRMATION_REQUIRED}
                    else FeedbackLevel.WARNING,
                    data=_snapshot_object(details, "result details"),
                ),
            ),
            data={**_snapshot_object(details, "details"), "warnings": _warning_data(warnings)},
        )
        return EndDayExecution(
            result=result,
            warnings=warnings,
            logs=deepcopy(logs),
            random_before=random_before,
            random_after=_safe_random_state(state),
        )
