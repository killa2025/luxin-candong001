from __future__ import annotations

from copy import deepcopy
from dataclasses import fields
from typing import Any

from furnace_winter.config import (
    BuildingRules,
    LawRules,
    SurvivalRules,
    TechnologyRules,
)
from furnace_winter.gameplay.end_day import EndDayContext, EndDayEngine, EndDayStage
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
from furnace_winter.models import GameState, SaveDataError, validate_game_state


RESEARCH_COMMAND = "game.research"
CANCEL_RESEARCH_COMMAND = "game.cancel_research"
SET_OVERLOAD_COMMAND = "game.set_overload"


def build_technology_catalog(rules: TechnologyRules) -> CommandCatalog:
    catalog = CommandCatalog()
    catalog.register(
        CommandSpec(
            name=RESEARCH_COMMAND,
            required_arguments={"tech_id": ArgumentKind.STRING},
            argument_options={"tech_id": tuple(sorted(rules.technologies))},
        )
    )
    catalog.register(CommandSpec(name=CANCEL_RESEARCH_COMMAND))
    catalog.register(
        CommandSpec(
            name=SET_OVERLOAD_COMMAND,
            required_arguments={"level": ArgumentKind.INTEGER},
        )
    )
    return catalog


class TechnologySystem:
    """Patch 006 deterministic research queue and confirmed technology effects."""

    def __init__(
        self,
        rules: TechnologyRules,
        building_rules: BuildingRules,
        survival_rules: SurvivalRules,
        law_rules: LawRules | None = None,
    ) -> None:
        self.rules = rules
        self.building_rules = building_rules
        self.survival_rules = survival_rules
        self.law_rules = law_rules
        referenced_tech_ids = {
            tech_id
            for rule in building_rules.buildings.values()
            for tech_id in rule.required_tech_ids
        }
        referenced_tech_ids.update(
            upgrade.required_tech_id for upgrade in building_rules.upgrades.values()
        )
        referenced_tech_ids.add(building_rules.heat.enhancement_tech_id)
        unknown_references = sorted(
            referenced_tech_ids - set(rules.technologies)
        )
        if unknown_references:
            raise ValueError(
                f"building rules reference unknown technologies: {unknown_references}"
            )
        self._catalog = build_technology_catalog(rules)
        self._validator = CommandValidator(self._catalog)

    def command_specs(self) -> tuple[CommandSpec, ...]:
        return self._catalog.specs()

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
            return self._error(command_id, sequence, "input_state_validation", exc)
        validation = self._validator.validate(request, state, self._legality)
        if not validation.is_valid:
            return self._rejected(command_id, sequence, validation)

        working = deepcopy(state)
        try:
            handlers = {
                RESEARCH_COMMAND: self._start_research,
                CANCEL_RESEARCH_COMMAND: self._cancel_research,
                SET_OVERLOAD_COMMAND: self._set_overload,
            }
            data = handlers[request.name](working, request)
            working.command_sequence += 1
            self.validate_state(working)
        except (KeyError, SaveDataError, TypeError, ValueError) as exc:
            return self._error(command_id, sequence, "result_state_validation", exc)

        for item in fields(GameState):
            setattr(state, item.name, deepcopy(getattr(working, item.name)))
        return CommandResult(
            command_id=command_id,
            accepted=True,
            code=ErrorCode.OK,
            state_changed=True,
            state_sequence=state.command_sequence,
            feedback=(FeedbackItem(FeedbackLevel.INFO, data=data),),
            data=data,
        )

    def _legality(
        self, state: GameState, request: CommandRequest
    ) -> CommandValidation:
        if state.calendar.is_day_locked or state.final_result.is_finalized:
            return self._illegal("day_not_open_for_planning")
        if request.name == RESEARCH_COMMAND:
            return self._research_legality(state, request)
        if request.name == CANCEL_RESEARCH_COMMAND:
            if state.technologies.active_research_id is None:
                return self._illegal("no_active_research")
            return CommandValidation.valid()
        return self._overload_legality(state, request)

    def _research_legality(
        self, state: GameState, request: CommandRequest
    ) -> CommandValidation:
        tech_id = str(request.arguments["tech_id"])
        rule = self.rules.technologies[tech_id]
        completed = set(state.technologies.researched_tech_ids)
        if state.technologies.active_research_id is not None:
            return self._illegal(
                "research_queue_occupied",
                active_research_id=state.technologies.active_research_id,
            )
        if tech_id in completed:
            return self._illegal("technology_already_researched")
        missing = sorted(set(rule.prerequisite_tech_ids) - completed)
        tier_unlock = self.rules.tier_unlock_tech_id(rule.tier)
        if tier_unlock is not None and tier_unlock not in completed:
            missing.append(tier_unlock)
        if missing:
            return self._illegal(
                "technology_prerequisite_missing",
                missing_tech_ids=sorted(set(missing)),
            )
        if not self._staffed_research_institutes(state, require_operational=False):
            return self._illegal("staffed_research_institute_required")
        missing_resources: dict[str, int] = {}
        if state.resources.wood < rule.wood_cost:
            missing_resources["wood"] = rule.wood_cost - state.resources.wood
        if state.resources.steel < rule.steel_cost:
            missing_resources["steel"] = rule.steel_cost - state.resources.steel
        if missing_resources:
            return self._illegal(
                "insufficient_resources", missing_resources=missing_resources
            )
        return CommandValidation.valid()

    def _overload_legality(
        self, state: GameState, request: CommandRequest
    ) -> CommandValidation:
        level = int(request.arguments["level"])
        if level not in self.rules.overload.levels:
            return self._illegal("invalid_overload_level", allowed_levels=[0, 1, 2])
        if level == state.furnace.overload_level:
            return self._illegal("overload_level_already_selected")
        if level > 0 and not state.furnace.is_active:
            return self._illegal("furnace_must_be_active")
        required = self.rules.overload.levels[level].required_tech_id
        if required and required not in state.technologies.researched_tech_ids:
            return self._illegal(
                "technology_prerequisite_missing", missing_tech_ids=[required]
            )
        return CommandValidation.valid()

    def _start_research(
        self, state: GameState, request: CommandRequest
    ) -> dict[str, Any]:
        tech_id = str(request.arguments["tech_id"])
        rule = self.rules.technologies[tech_id]
        required_units = rule.research_days * self.rules.research.progress_units_per_day
        state.resources.wood -= rule.wood_cost
        state.resources.steel -= rule.steel_cost
        state.technologies.active_research_id = tech_id
        state.technologies.research_progress_units = 0
        state.technologies.research_required_units = required_units
        return {
            "tech_id": tech_id,
            "wood_paid": rule.wood_cost,
            "steel_paid": rule.steel_cost,
            "research_required_units": required_units,
            "payment_timing": "on_start",
        }

    @staticmethod
    def _cancel_research(
        state: GameState, _request: CommandRequest
    ) -> dict[str, Any]:
        tech_id = state.technologies.active_research_id
        state.technologies.active_research_id = None
        state.technologies.research_progress_units = 0
        state.technologies.research_required_units = 0
        return {"tech_id": tech_id, "refund": {"wood": 0, "steel": 0}}

    @staticmethod
    def _set_overload(
        state: GameState, request: CommandRequest
    ) -> dict[str, Any]:
        level = int(request.arguments["level"])
        state.furnace.overload_level = level
        return {"overload_level": level, "payment_timing": "end_day"}

    def install(self, engine: EndDayEngine) -> None:
        engine.register_state_validator(self.validate_state)
        engine.register_stage_handler(
            EndDayStage.ADVANCE_AND_COMMIT_RESEARCH,
            self.advance_and_commit_research,
        )

    def validate_state(self, state: GameState) -> None:
        validate_game_state(
            state,
            self.building_rules,
            self.survival_rules,
            self.rules,
        )
        known = set(self.rules.technologies)
        completed_list = state.technologies.researched_tech_ids
        completed = set(completed_list)
        if len(completed) != len(completed_list):
            raise SaveDataError("researched technology ids must be unique")
        if completed - known:
            raise SaveDataError("state contains unknown researched technologies")
        for tech_id in completed:
            rule = self.rules.technologies[tech_id]
            if not set(rule.prerequisite_tech_ids).issubset(completed):
                raise SaveDataError("researched technology is missing a prerequisite")
            tier_unlock = self.rules.tier_unlock_tech_id(rule.tier)
            if tier_unlock is not None and tier_unlock not in completed:
                raise SaveDataError("researched technology tier is not unlocked")

        active = state.technologies.active_research_id
        if active is not None:
            if active not in known:
                raise SaveDataError("active research id is unknown")
            rule = self.rules.technologies[active]
            if not set(rule.prerequisite_tech_ids).issubset(completed):
                raise SaveDataError("active research is missing a prerequisite")
            tier_unlock = self.rules.tier_unlock_tech_id(rule.tier)
            if tier_unlock is not None and tier_unlock not in completed:
                raise SaveDataError("active research tier is not unlocked")
            required = rule.research_days * self.rules.research.progress_units_per_day
            if state.technologies.research_required_units != required:
                raise SaveDataError("active research duration does not match technology rules")

        overload_rule = self.rules.overload.levels[state.furnace.overload_level]
        if (
            overload_rule.required_tech_id is not None
            and overload_rule.required_tech_id not in completed
        ):
            raise SaveDataError("selected overload level is not unlocked")
        if state.furnace.pressure_redline_warned != (
            state.furnace.pressure >= self.rules.overload.redline_threshold
        ):
            raise SaveDataError("redline warning must match configured pressure threshold")

    def advance_and_commit_research(self, context: EndDayContext) -> None:
        state = context.state
        tech_id = state.technologies.active_research_id
        if tech_id is None:
            context.emit("technology.research.idle")
            return
        institutes = self._staffed_research_institutes(
            state, require_operational=True
        )
        if not institutes:
            context.emit(
                "technology.research.paused",
                {"tech_id": tech_id, "reason": "no_operational_engineer_staffed_institute"},
            )
            return

        progress = self.rules.research.progress_units_per_day
        if len(institutes) >= 2:
            progress = (
                progress * self.rules.research.second_center_speed_numerator
                // self.rules.research.second_center_speed_denominator
            )
        overtime_id = state.social_policy.overtime_building_id
        if overtime_id in {item.building_id for item in institutes}:
            numerator, denominator = self._overtime_progress_multiplier()
            progress = progress * numerator // denominator
        state.technologies.research_progress_units += progress

        completed = (
            state.technologies.research_progress_units
            >= state.technologies.research_required_units
        )
        context.emit(
            "technology.research.advanced",
            {
                "tech_id": tech_id,
                "progress_added": progress,
                "progress_units": state.technologies.research_progress_units,
                "required_units": state.technologies.research_required_units,
                "completed": completed,
                "research_institute_count": len(institutes),
            },
        )
        if not completed:
            return

        state.technologies.researched_tech_ids.append(tech_id)
        state.technologies.active_research_id = None
        state.technologies.research_progress_units = 0
        state.technologies.research_required_units = 0
        if tech_id == "tech_storage_expansion":
            warehouse_count = sum(
                building.building_type == "small_warehouse"
                for building in state.buildings.values()
            )
            state.resources.storage_capacity += 300 * warehouse_count
        context.emit("technology.research.completed", {"tech_id": tech_id})

    def view(self, state: GameState) -> tuple[dict[str, Any], ...]:
        completed = set(state.technologies.researched_tech_ids)
        result: list[dict[str, Any]] = []
        for tech_id, rule in sorted(self.rules.technologies.items()):
            missing = sorted(set(rule.prerequisite_tech_ids) - completed)
            tier_unlock = self.rules.tier_unlock_tech_id(rule.tier)
            if tier_unlock is not None and tier_unlock not in completed:
                missing.append(tier_unlock)
            if tech_id in completed:
                status = "completed"
            elif tech_id == state.technologies.active_research_id:
                status = "researching"
            elif missing:
                status = "locked"
            else:
                status = "available"
            result.append(
                {
                    "tech_id": tech_id,
                    "display_name": rule.display_name,
                    "tier": rule.tier,
                    "status": status,
                    "missing_tech_ids": sorted(set(missing)),
                    "wood_cost": rule.wood_cost,
                    "steel_cost": rule.steel_cost,
                    "research_days": rule.research_days,
                    "effect_status": rule.effect_status,
                }
            )
        return tuple(result)

    @staticmethod
    def _staffed_research_institutes(
        state: GameState, *, require_operational: bool
    ) -> list[Any]:
        return sorted(
            (
                building
                for building in state.buildings.values()
                if building.building_type == "research_institute"
                and building.is_built
                and building.assigned_engineers >= 1
                and (building.is_operational or not require_operational)
            ),
            key=lambda item: item.building_id,
        )

    def _overtime_progress_multiplier(self) -> tuple[int, int]:
        if self.law_rules is None:
            return 100, 100
        return (
            self.law_rules.worktime.overtime_medical_research_numerator,
            self.law_rules.worktime.overtime_medical_research_denominator,
        )

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
