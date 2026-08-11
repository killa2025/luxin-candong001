from __future__ import annotations

from copy import deepcopy
from dataclasses import fields
from typing import Any

from furnace_winter.interface import (
    ArgumentKind,
    CommandCatalog,
    CommandRequest,
    CommandResult,
    CommandSpec,
    CommandValidation,
    CommandValidator,
    ErrorCode,
    FeedbackItem,
    FeedbackLevel,
)
from furnace_winter.models import (
    CURRENT_ENDING_REPORT_FORMAT_VERSION,
    FINAL_DAY,
    GameState,
    RunState,
    SaveDataError,
    TerminationReason,
    validate_game_state,
)
from furnace_winter.models.state import (
    ENDING_BODY_POOL_TEXT_IDS,
)
from furnace_winter.models.ending_selection import (
    canonical_report_body_text_ids,
    canonical_report_pending_text_ids,
    canonical_report_title_text_id,
    legacy_report_pending_text_ids,
    report_template_values,
)
from furnace_winter.text import (
    PendingRegistry,
    TextRegistry,
    build_ending_pending_registry,
    build_ending_text_registry,
)


END_RUN_COMMAND = "game.end_run"


def build_ending_report_catalog() -> CommandCatalog:
    catalog = CommandCatalog()
    catalog.register(
        CommandSpec(
            name=END_RUN_COMMAND,
            required_arguments={"confirm": ArgumentKind.BOOLEAN},
        )
    )
    return catalog


def _limiting_factor_ids(state: GameState) -> list[str]:
    return ["wood_supply_locked"] if state.final_frost.wood_supply_locked else []


class EndingReportSystem:
    """Patch 010 deterministic report selection and run termination."""

    def __init__(
        self,
        text_registry: TextRegistry | None = None,
        pending_registry: PendingRegistry | None = None,
    ) -> None:
        self.text_registry = text_registry or build_ending_text_registry()
        self.pending_registry = (
            pending_registry or build_ending_pending_registry()
        )
        self._catalog = build_ending_report_catalog()
        self._validator = CommandValidator(self._catalog)

    def command_specs(self) -> tuple[CommandSpec, ...]:
        return self._catalog.specs()

    def generate(self, state: GameState) -> None:
        """Persist a report selection after canonical terminal finalization."""

        final = state.final_result
        if final.report.is_generated:
            self.validate_state(state)
            return
        if not final.is_finalized:
            raise ValueError("ending report requires a completed result")
        if final.hard_fail_type is not None:
            if final.ending_id != "hard_fail":
                raise ValueError("hard-fail report requires a canonical result")
        else:
            if (
                state.final_frost.final_score_day != FINAL_DAY
                or final.ending_id not in ENDING_BODY_POOL_TEXT_IDS
            ):
                raise ValueError(
                    "survival report requires a completed D55 score"
                )
        report = final.report
        report.format_version = CURRENT_ENDING_REPORT_FORMAT_VERSION
        report.is_generated = True
        report.generated_day = state.calendar.current_day
        report.ending_state = final.ending_id
        report.display_result_id = final.ending_id
        report.title_text_id = canonical_report_title_text_id(state)
        report.body_text_ids = canonical_report_body_text_ids(state)
        report.pending_text_ids = canonical_report_pending_text_ids(state)
        report.hidden_achievement_ids = sorted(
            set(state.events.hidden_achievements_unlocked)
        )
        report.limiting_factor_ids = _limiting_factor_ids(state)

    def execute(self, state: GameState, request: CommandRequest) -> CommandResult:
        command_id = (
            request.command_id
            if isinstance(request, CommandRequest)
            and isinstance(request.command_id, str)
            else ""
        )
        sequence = (
            state.command_sequence
            if isinstance(state, GameState)
            and isinstance(state.command_sequence, int)
            and not isinstance(state.command_sequence, bool)
            else 0
        )
        validation = self._validator.validate(request)
        if not validation.is_valid:
            return self._rejected(command_id, sequence, validation)
        try:
            self.validate_state(state)
        except (SaveDataError, TypeError, ValueError) as exc:
            return self._error(
                command_id, sequence, "input_state_validation", exc
            )
        validation = self._validator.validate(
            request, state, self._legality
        )
        if not validation.is_valid:
            return self._rejected(command_id, sequence, validation)

        working = deepcopy(state)
        final = working.final_result
        final.run_state = RunState.ENDED
        final.termination_reason = TerminationReason.PLAYER_ENDED
        final.termination_day = FINAL_DAY
        final.termination_command_sequence = working.command_sequence + 1
        final.report.format_version = CURRENT_ENDING_REPORT_FORMAT_VERSION
        final.report.display_result_id = TerminationReason.PLAYER_ENDED.value
        final.report.title_text_id = canonical_report_title_text_id(working)
        final.report.body_text_ids = canonical_report_body_text_ids(working)
        final.report.pending_text_ids = canonical_report_pending_text_ids(
            working
        )
        working.command_sequence += 1
        try:
            self.validate_state(working)
        except (SaveDataError, TypeError, ValueError) as exc:
            return self._error(
                command_id, sequence, "result_state_validation", exc
            )

        for item in fields(GameState):
            setattr(state, item.name, deepcopy(getattr(working, item.name)))
        data = self.observe(state)
        return CommandResult(
            command_id=command_id,
            accepted=True,
            code=ErrorCode.OK,
            state_changed=True,
            state_sequence=state.command_sequence,
            feedback=(FeedbackItem(FeedbackLevel.INFO, data=data),),
            data=data,
        )

    def validate_state(self, state: GameState) -> None:
        validate_game_state(state)
        report = state.final_result.report
        if not report.is_generated:
            return
        for text_id in [report.title_text_id, *report.body_text_ids]:
            if text_id is None:
                raise ValueError("generated report text ids must not be null")
            self.text_registry.require(text_id)
        pending_ids = {
            entry.entry_id for entry in self.pending_registry.entries()
        }
        pending_ids.update(legacy_report_pending_text_ids(state))
        if set(report.pending_text_ids) - pending_ids:
            raise ValueError("ending report contains an unknown pending text id")

    def observe(self, state: GameState) -> dict[str, Any]:
        self.validate_state(state)
        final = state.final_result
        report = final.report
        if not report.is_generated:
            return {
                "available": False,
                "content_status": "not_generated",
                "body_complete": False,
                "pending_text_count": 0,
                "run_state": final.run_state.value,
                "termination_reason": (
                    final.termination_reason.value
                    if final.termination_reason is not None
                    else None
                ),
            }
        title = self.text_registry.require(str(report.title_text_id))
        template_values = report_template_values(state)
        body = []
        for text_id in report.body_text_ids:
            text = self.text_registry.require(text_id).text
            body.append(
                {
                    "text_id": text_id,
                    "text": text.format_map(template_values),
                }
            )
        return {
            "available": True,
            "content_status": (
                "partial_pending_text"
                if report.pending_text_ids
                else "complete"
            ),
            "body_complete": not report.pending_text_ids,
            "pending_text_count": len(report.pending_text_ids),
            "generated_day": report.generated_day,
            "run_state": final.run_state.value,
            "termination_reason": (
                final.termination_reason.value
                if final.termination_reason is not None
                else None
            ),
            "ending_state": report.ending_state,
            "display_result_id": report.display_result_id,
            "title": {"text_id": title.text_id, "text": title.text},
            "body": body,
            "pending_text_ids": list(report.pending_text_ids),
            "system_scores": dict(final.system_scores),
            "total_score": final.total_score,
            "major_tags": list(final.major_tags),
            "defining_tags": list(final.defining_tags),
            "ending_tags": list(final.ending_tags),
            "hidden_achievement_ids": list(
                report.hidden_achievement_ids
            ),
            "limiting_factor_ids": list(report.limiting_factor_ids),
        }

    @staticmethod
    def _legality(
        state: GameState, request: CommandRequest
    ) -> CommandValidation:
        final = state.final_result
        if final.run_state is RunState.ENDED:
            return EndingReportSystem._illegal("already_ended")
        if request.arguments.get("confirm") is not True:
            return EndingReportSystem._illegal("confirmation_required")
        if final.hard_fail_type is not None:
            return EndingReportSystem._illegal("hard_fail_cannot_be_overwritten")
        if state.calendar.current_day != FINAL_DAY:
            return EndingReportSystem._illegal("d55_not_reached")
        if (
            state.daily_survival.settled_day != FINAL_DAY
            or state.final_frost.final_score_day != FINAL_DAY
            or not final.is_finalized
            or final.ending_id not in ENDING_BODY_POOL_TEXT_IDS
            or not final.report.is_generated
        ):
            return EndingReportSystem._illegal(
                "d55_final_settlement_incomplete"
            )
        return CommandValidation.valid()

    @staticmethod
    def _illegal(reason: str, **details: Any) -> CommandValidation:
        return CommandValidation(
            False,
            ErrorCode.ILLEGAL_COMMAND,
            {"reason": reason, **details},
        )

    @staticmethod
    def _rejected(
        command_id: str, sequence: int, validation: CommandValidation
    ) -> CommandResult:
        data = dict(validation.details)
        return CommandResult(
            command_id=command_id,
            accepted=False,
            code=validation.code,
            state_changed=False,
            state_sequence=sequence,
            feedback=(FeedbackItem(FeedbackLevel.ERROR, data=data),),
            data=data,
        )

    @staticmethod
    def _error(
        command_id: str, sequence: int, stage: str, exc: Exception
    ) -> CommandResult:
        data = {"failed_stage": stage, "exception_type": type(exc).__name__}
        return CommandResult(
            command_id=command_id,
            accepted=False,
            code=ErrorCode.INTERNAL_ERROR,
            state_changed=False,
            state_sequence=sequence,
            feedback=(FeedbackItem(FeedbackLevel.ERROR, data=data),),
            data=data,
        )
