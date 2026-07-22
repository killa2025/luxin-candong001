from __future__ import annotations

from copy import deepcopy
from dataclasses import fields
from typing import Any

from furnace_winter.config import BuildingRules, LawRules, SurvivalRules, TechnologyRules
from furnace_winter.gameplay.end_day import EndDayContext, EndDayEngine, EndDayStage, RiskWarning, RiskWarningLevel
from furnace_winter.gameplay.survival import is_building_expected_operational
from furnace_winter.interface import (
    ArgumentKind, CommandCatalog, CommandRequest, CommandResult, CommandSpec,
    CommandValidation, CommandValidator, ErrorCode, FeedbackItem, FeedbackLevel,
)
from furnace_winter.models import (
    OVERTIME_BUILDING_TYPES,
    GameState,
    SaveDataError,
    validate_game_state,
)


SIGN_LAW_COMMAND = "game.sign_law"
SET_RATION_COMMAND = "game.set_ration"
SET_WORKTIME_COMMAND = "game.set_worktime"
OVERTIME_COMMAND = "game.overtime"
MEDICAL_RATION_COMMAND = "game.medical_ration"
TRIAGE_COMMAND = "game.triage"
MEMORIAL_COMMAND = "game.memorial"

_LAW_COOLDOWN = "ordinary_law"
_EMERGENCY_COOLDOWN = "emergency_ration"
_MEDICAL_COOLDOWN = "medical_ration"
_TRIAGE_COOLDOWN = "triage"
_MEMORIAL_COOLDOWN = "memorial"
_LONG_SHIFT_EXCLUDED_TYPES = frozenset({
    "child_shelter", "school", "small_tavern", "grand_casino",
    "basic_residence", "improved_residence", "advanced_residence",
    "small_warehouse", "cemetery", "cold_pit", "furnace_hall",
    "patrol_station", "hot_spring_bath", "gathering_shelter",
})


def build_law_catalog(rules: LawRules | None = None) -> CommandCatalog:
    catalog = CommandCatalog()
    law_ids = tuple(sorted(rules.laws)) if rules else ()
    ration_ids = tuple(sorted(rules.rations)) if rules else (
        "normal", "coarse_soup", "rice_porridge", "emergency",
    )
    catalog.register(CommandSpec(
        name=SIGN_LAW_COMMAND,
        required_arguments={"law_id": ArgumentKind.STRING},
        optional_arguments={"confirm": ArgumentKind.BOOLEAN},
        argument_options={"law_id": law_ids} if law_ids else {},
    ))
    catalog.register(CommandSpec(
        name=SET_RATION_COMMAND,
        required_arguments={"mode": ArgumentKind.STRING},
        optional_arguments={"confirm": ArgumentKind.BOOLEAN},
        argument_options={"mode": ration_ids},
    ))
    catalog.register(CommandSpec(
        name=SET_WORKTIME_COMMAND,
        required_arguments={"mode": ArgumentKind.STRING},
        argument_options={"mode": ("normal", "long_shift")},
    ))
    catalog.register(CommandSpec(
        name=OVERTIME_COMMAND,
        required_arguments={"building_id": ArgumentKind.STRING, "confirm": ArgumentKind.BOOLEAN},
    ))
    catalog.register(CommandSpec(
        name=MEDICAL_RATION_COMMAND,
        required_arguments={"confirm": ArgumentKind.BOOLEAN},
    ))
    catalog.register(CommandSpec(
        name=TRIAGE_COMMAND,
        required_arguments={"building_id": ArgumentKind.STRING, "confirm": ArgumentKind.BOOLEAN},
    ))
    catalog.register(CommandSpec(name=MEMORIAL_COMMAND))
    return catalog


class LawSystem:
    """Patch 005 006A signing, modes, actions, and deterministic daily hooks."""

    def __init__(
        self,
        rules: LawRules,
        building_rules: BuildingRules,
        survival_rules: SurvivalRules,
        technology_rules: TechnologyRules | None = None,
    ) -> None:
        self.rules = rules
        self.building_rules = building_rules
        self.survival_rules = survival_rules
        self.technology_rules = technology_rules
        self._catalog = build_law_catalog(rules)
        self._validator = CommandValidator(self._catalog)

    def command_specs(self) -> tuple[CommandSpec, ...]:
        return self._catalog.specs()

    def execute(self, state: GameState, request: CommandRequest) -> CommandResult:
        command_id = request.command_id if isinstance(request, CommandRequest) and isinstance(request.command_id, str) else ""
        sequence = state.command_sequence if isinstance(state, GameState) and isinstance(state.command_sequence, int) and not isinstance(state.command_sequence, bool) else 0
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
                SIGN_LAW_COMMAND: self._sign_law,
                SET_RATION_COMMAND: self._set_ration,
                SET_WORKTIME_COMMAND: self._set_worktime,
                OVERTIME_COMMAND: self._overtime,
                MEDICAL_RATION_COMMAND: self._medical_ration,
                TRIAGE_COMMAND: self._triage,
                MEMORIAL_COMMAND: self._memorial,
            }
            data = handlers[request.name](working, request)
            working.command_sequence += 1
            self.validate_state(working)
        except (KeyError, SaveDataError, TypeError, ValueError) as exc:
            return self._error(command_id, sequence, "result_state_validation", exc)
        for item in fields(GameState):
            setattr(state, item.name, deepcopy(getattr(working, item.name)))
        return CommandResult(
            command_id=command_id, accepted=True, code=ErrorCode.OK,
            state_changed=True, state_sequence=state.command_sequence,
            feedback=(FeedbackItem(FeedbackLevel.INFO, data=data),), data=data,
        )

    def _legality(self, state: GameState, request: CommandRequest) -> CommandValidation:
        if state.calendar.is_day_locked or state.final_result.is_finalized:
            return self._illegal("day_not_open_for_planning")
        checks = {
            SIGN_LAW_COMMAND: self._sign_legality,
            SET_RATION_COMMAND: self._ration_legality,
            SET_WORKTIME_COMMAND: self._worktime_legality,
            OVERTIME_COMMAND: self._overtime_legality,
            MEDICAL_RATION_COMMAND: self._medical_ration_legality,
            TRIAGE_COMMAND: self._triage_legality,
            MEMORIAL_COMMAND: self._memorial_legality,
        }
        return checks[request.name](state, request)

    def _sign_legality(self, state: GameState, request: CommandRequest) -> CommandValidation:
        law_id = str(request.arguments["law_id"])
        rule = self.rules.laws[law_id]
        signed = set(state.laws.signed_law_ids)
        if law_id in signed:
            return self._illegal("law_already_signed")
        next_day = state.laws.cooldowns.get(_LAW_COOLDOWN, 1)
        if state.calendar.current_day < next_day:
            return self._illegal("law_cooldown_active", next_available_day=next_day)
        missing_all = sorted(set(rule.required_all) - signed)
        missing_any = bool(rule.required_any) and not (set(rule.required_any) & signed)
        if missing_all or missing_any:
            return self._illegal(
                "law_prerequisite_missing", missing_all=missing_all,
                required_any=list(rule.required_any) if missing_any else [],
            )
        conflicts = sorted(set(rule.mutually_exclusive) & signed)
        if conflicts:
            return self._illegal("law_route_locked", conflicting_law_ids=conflicts)
        if rule.confirmation_required and request.arguments.get("confirm") is not True:
            return self._illegal("confirmation_required")
        return CommandValidation.valid()

    def _ration_legality(self, state: GameState, request: CommandRequest) -> CommandValidation:
        mode = str(request.arguments["mode"])
        ration = self.rules.rations[mode]
        if state.social_policy.current_ration_mode == mode:
            return self._illegal("ration_mode_already_active")
        if state.social_policy.current_ration_mode == "emergency":
            return self._illegal("emergency_ration_cannot_be_replaced_today")
        if ration.required_law_id and ration.required_law_id not in state.laws.signed_law_ids:
            return self._illegal("law_prerequisite_missing", missing_law_ids=[ration.required_law_id])
        if mode == "emergency":
            if request.arguments.get("confirm") is not True:
                return self._illegal("confirmation_required")
            next_day = state.laws.cooldowns.get(_EMERGENCY_COOLDOWN, 1)
            if state.calendar.current_day < next_day:
                return self._illegal("action_cooldown_active", next_available_day=next_day)
            if not self._has_operational_canteen(state):
                return self._illegal("canteen_unavailable")
        return CommandValidation.valid()

    def _worktime_legality(self, state: GameState, request: CommandRequest) -> CommandValidation:
        mode = str(request.arguments["mode"])
        if state.social_policy.current_worktime_mode == mode:
            return self._illegal("worktime_mode_already_active")
        if mode == "long_shift" and "long_shift_law" not in state.laws.signed_law_ids:
            return self._illegal("law_prerequisite_missing", missing_law_ids=["long_shift_law"])
        return CommandValidation.valid()

    def _overtime_legality(self, state: GameState, request: CommandRequest) -> CommandValidation:
        if "overtime_law" not in state.laws.signed_law_ids:
            return self._illegal("law_prerequisite_missing", missing_law_ids=["overtime_law"])
        if request.arguments.get("confirm") is not True:
            return self._illegal("confirmation_required")
        if state.social_policy.overtime_building_id is not None:
            return self._illegal("overtime_daily_limit_reached")
        building = state.buildings.get(str(request.arguments["building_id"]))
        if building is None:
            return self._illegal("unknown_building")
        if building.building_type not in OVERTIME_BUILDING_TYPES:
            return self._illegal("building_cannot_overtime")
        if self._assigned_total(building) <= 0:
            return self._illegal("building_has_no_staff")
        if not self._is_expected_operational(state, building):
            return self._illegal("building_not_operational")
        return CommandValidation.valid()

    def _medical_ration_legality(self, state: GameState, request: CommandRequest) -> CommandValidation:
        if "medical_ration_law" not in state.laws.signed_law_ids:
            return self._illegal("law_prerequisite_missing", missing_law_ids=["medical_ration_law"])
        if request.arguments.get("confirm") is not True:
            return self._illegal("confirmation_required")
        next_day = state.laws.cooldowns.get(_MEDICAL_COOLDOWN, 1)
        if state.calendar.current_day < next_day:
            return self._illegal("action_cooldown_active", next_available_day=next_day)
        if state.population.sick_population + state.population.critical_population == 0:
            return self._illegal("no_treatable_patients")
        if state.resources.cooked_food < self.rules.medical.medical_ration_food_per_patient:
            return self._illegal("insufficient_cooked_food")
        if self._current_medical_capacity(state) == 0:
            return self._illegal("no_operational_medical_system")
        return CommandValidation.valid()

    def _triage_legality(self, state: GameState, request: CommandRequest) -> CommandValidation:
        if "triage_law" not in state.laws.signed_law_ids:
            return self._illegal("law_prerequisite_missing", missing_law_ids=["triage_law"])
        if request.arguments.get("confirm") is not True:
            return self._illegal("confirmation_required")
        building = state.buildings.get(str(request.arguments["building_id"]))
        if building is None:
            return self._illegal("unknown_building")
        if building.building_type not in {"medical_station", "hospital"}:
            return self._illegal("invalid_triage_target")
        if not self._is_expected_operational(state, building):
            return self._illegal("medical_building_not_operational")
        if state.medical.medical_pressure <= 0:
            return self._illegal("medical_system_not_overloaded")
        if self.rules.medical.triage_cooldown_days is None:
            return self._illegal("triage_balance_not_sealed")
        next_day = state.laws.cooldowns.get(_TRIAGE_COOLDOWN, 1)
        if state.calendar.current_day < next_day:
            return self._illegal("action_cooldown_active", next_available_day=next_day)
        return CommandValidation.valid()

    def _memorial_legality(self, state: GameState, _request: CommandRequest) -> CommandValidation:
        if "memorial_law" not in state.laws.signed_law_ids:
            return self._illegal("law_prerequisite_missing", missing_law_ids=["memorial_law"])
        if state.population.population_dead <= 0:
            return self._illegal("no_deaths_to_memorialize")
        if not self._has_built_type(state, "cemetery"):
            return self._illegal("cemetery_not_built")
        next_day = state.laws.cooldowns.get(_MEMORIAL_COOLDOWN, 1)
        if state.calendar.current_day < next_day:
            return self._illegal("action_cooldown_active", next_available_day=next_day)
        return CommandValidation.valid()

    def _sign_law(self, state: GameState, request: CommandRequest) -> dict[str, Any]:
        law_id = str(request.arguments["law_id"])
        rule = self.rules.laws[law_id]
        state.laws.signed_law_ids.append(law_id)
        state.laws.cooldowns[_LAW_COOLDOWN] = state.calendar.current_day + self.rules.ordinary_cooldown_days
        self._change_emotion(state, trust=rule.trust_change or 0, panic=rule.panic_change or 0)
        if "firepit" in rule.auto_enable:
            state.social_policy.firepit_enabled = True
        if law_id == "cemetery_law":
            state.social_policy.death_path = "cemetery"
        elif law_id == "cold_pit_law":
            state.social_policy.death_path = "cold_pit"
        runtime_buildings = [
            item for item in rule.unlock_buildings if item in self.building_rules.buildings
        ]
        deferred_buildings = [
            item for item in rule.unlock_buildings if item not in self.building_rules.buildings
        ]
        return {
            "law_id": law_id,
            "next_ordinary_law_day": state.laws.cooldowns[_LAW_COOLDOWN],
            "unlocked_building_ids": runtime_buildings,
            "deferred_building_ids": deferred_buildings,
            "unlocked_action_ids": list(rule.unlock_actions),
            "unlocked_mode_ids": list(rule.unlock_modes),
            "auto_enabled_ids": list(rule.auto_enable),
            "trust_change": rule.trust_change, "panic_change": rule.panic_change,
        }

    def _set_ration(self, state: GameState, request: CommandRequest) -> dict[str, Any]:
        mode = str(request.arguments["mode"])
        previous = state.social_policy.current_ration_mode
        if mode == "emergency":
            state.social_policy.previous_ration_mode = previous
            state.social_policy.previous_ration_days = state.social_policy.consecutive_ration_days
            state.laws.cooldowns[_EMERGENCY_COOLDOWN] = state.calendar.current_day + self.rules.actions.emergency_ration_cooldown_days
            self._change_emotion(
                state,
                trust=self.rules.actions.emergency_ration_trust_change,
                panic=self.rules.actions.emergency_ration_panic_change,
            )
        state.social_policy.current_ration_mode = mode
        ration = self.rules.rations[mode]
        state.social_policy.ration_food_numerator = ration.food_numerator
        state.social_policy.ration_food_denominator = ration.food_denominator
        return {
            "ration_mode": mode, "previous_mode": previous,
            "active_duration": "current_day_only" if mode == "emergency" else "until_changed",
            "next_available_day": state.laws.cooldowns.get(_EMERGENCY_COOLDOWN),
        }

    def _set_worktime(self, state: GameState, request: CommandRequest) -> dict[str, Any]:
        mode = str(request.arguments["mode"])
        state.social_policy.current_worktime_mode = mode
        if mode == "normal":
            state.social_policy.worktime_output_numerator = 100
            state.social_policy.worktime_output_denominator = 100
        else:
            state.social_policy.worktime_output_numerator = self.rules.worktime.long_shift_output_numerator
            state.social_policy.worktime_output_denominator = self.rules.worktime.long_shift_output_denominator
        return {"worktime_mode": mode, "active_duration": "until_changed"}

    def _overtime(self, state: GameState, request: CommandRequest) -> dict[str, Any]:
        building_id = str(request.arguments["building_id"])
        building = state.buildings[building_id]
        state.social_policy.overtime_building_id = building_id
        state.social_policy.overtime_output_numerator = self.rules.worktime.overtime_output_numerator
        state.social_policy.overtime_output_denominator = self.rules.worktime.overtime_output_denominator
        self._change_emotion(
            state, trust=self.rules.worktime.overtime_trust_change,
            panic=self.rules.worktime.overtime_panic_change,
        )
        progress_numerator, progress_denominator = self.overtime_progress_multiplier(
            state, building_id
        )
        return {
            "building_id": building_id,
            "active_duration": "current_day_only",
            "cannot_cancel": True,
            "progress_multiplier_numerator": progress_numerator,
            "progress_multiplier_denominator": progress_denominator,
            "progress_multiplier_applies_to": (
                "medical"
                if building.building_type in {"medical_station", "hospital"}
                else "research"
                if building.building_type == "research_institute"
                else None
            ),
        }

    def _medical_ration(self, state: GameState, _request: CommandRequest) -> dict[str, Any]:
        rule = self.rules.medical
        self._sync_medical_capacity(state)
        affected = min(
            state.population.sick_population + state.population.critical_population,
            rule.medical_ration_max_patients,
            state.resources.cooked_food // rule.medical_ration_food_per_patient,
        )
        sick_cured = min(state.population.sick_population, affected)
        critical_progressed = min(state.population.critical_population, affected - sick_cured)
        food_paid = affected * rule.medical_ration_food_per_patient
        state.resources.cooked_food -= food_paid
        state.population.sick_population -= sick_cured
        state.population.healthy_population += sick_cured
        state.medical.critical_treatment_progress += critical_progressed
        state.medical.medical_ration_sick_cured_today = sick_cured
        state.medical.medical_ration_critical_progress_today = critical_progressed
        state.medical.medical_pressure = max(
            state.population.sick_population + state.population.critical_population - state.medical.effective_capacity, 0
        )
        state.laws.cooldowns[_MEDICAL_COOLDOWN] = state.calendar.current_day + rule.medical_ration_cooldown_days
        return {
            "affected_patients": affected, "sick_cured": sick_cured,
            "critical_treatment_progressed": critical_progressed,
            "cooked_food_paid": food_paid,
            "next_available_day": state.laws.cooldowns[_MEDICAL_COOLDOWN],
            "balance_status": "TEST_NUMERIC",
        }

    def _triage(self, state: GameState, request: CommandRequest) -> dict[str, Any]:
        building_id = str(request.arguments["building_id"])
        assert self.rules.medical.triage_cooldown_days is not None
        state.social_policy.triage_building_id = building_id
        state.social_policy.triage_used_ever = True
        state.laws.cooldowns[_TRIAGE_COOLDOWN] = state.calendar.current_day + self.rules.medical.triage_cooldown_days
        self._add_tag(state, "triage_used")
        return {"building_id": building_id, "active_duration": "current_day_only"}

    def _memorial(self, state: GameState, _request: CommandRequest) -> dict[str, Any]:
        self._change_emotion(
            state, trust=self.rules.actions.memorial_trust_change,
            panic=self.rules.actions.memorial_panic_change,
        )
        state.laws.cooldowns[_MEMORIAL_COOLDOWN] = state.calendar.current_day + self.rules.actions.memorial_cooldown_days
        return {
            "trust_change": self.rules.actions.memorial_trust_change,
            "panic_change": self.rules.actions.memorial_panic_change,
            "next_available_day": state.laws.cooldowns[_MEMORIAL_COOLDOWN],
            "bodies_processed": 0,
        }

    def install(self, engine: EndDayEngine) -> None:
        engine.register_state_validator(self.validate_state)
        engine.register_risk_evaluator(self.evaluate_risks)
        engine.register_stage_handler(
            EndDayStage.READ_FINAL_PLAN, self.prepare_daily_modes
        )
        engine.register_stage_handler(EndDayStage.RESOLVE_MEDICAL_DISEASE_AND_DEATH, self.resolve_medical_disease_and_death)
        engine.register_stage_handler(EndDayStage.RESOLVE_TRUST_AND_PANIC, self.resolve_trust_and_panic)
        engine.register_stage_handler(EndDayStage.CLOSE_ACTION_EFFECTS, self.close_action_effects)
        engine.register_stage_handler(EndDayStage.CLOSE_DAILY_EFFECTS, self.close_daily_effects)

    def validate_state(self, state: GameState) -> None:
        validate_game_state(
            state,
            self.building_rules,
            self.survival_rules,
            self.technology_rules,
        )
        signed_list = state.laws.signed_law_ids
        signed = set(signed_list)
        if len(signed) != len(signed_list):
            raise SaveDataError("signed law ids must be unique")
        if signed - set(self.rules.laws):
            raise SaveDataError("state contains unknown signed laws")
        for law_id in signed:
            rule = self.rules.laws[law_id]
            if not set(rule.required_all).issubset(signed):
                raise SaveDataError("signed law is missing an all-of prerequisite")
            if rule.required_any and not (set(rule.required_any) & signed):
                raise SaveDataError("signed law is missing an any-of prerequisite")
            if set(rule.mutually_exclusive) & signed:
                raise SaveDataError("mutually exclusive laws cannot both be signed")
        ration = self.rules.rations[state.social_policy.current_ration_mode]
        if ration.required_law_id and ration.required_law_id not in signed:
            raise SaveDataError("active ration mode is not unlocked")
        if state.social_policy.current_ration_mode == "emergency":
            previous_mode = state.social_policy.previous_ration_mode
            assert previous_mode is not None
            previous_ration = self.rules.rations[previous_mode]
            if (
                previous_ration.required_law_id
                and previous_ration.required_law_id not in signed
            ):
                raise SaveDataError("restored ration mode is not unlocked")
        if (
            state.social_policy.ration_food_numerator != ration.food_numerator
            or state.social_policy.ration_food_denominator != ration.food_denominator
        ):
            raise SaveDataError("active ration ratio must match law rules")
        if state.social_policy.current_worktime_mode == "long_shift" and "long_shift_law" not in signed:
            raise SaveDataError("long shift mode is not unlocked")
        expected_worktime_ratio = (
            (
                self.rules.worktime.long_shift_output_numerator,
                self.rules.worktime.long_shift_output_denominator,
            )
            if state.social_policy.current_worktime_mode == "long_shift"
            else (100, 100)
        )
        if (
            state.social_policy.worktime_output_numerator,
            state.social_policy.worktime_output_denominator,
        ) != expected_worktime_ratio:
            raise SaveDataError("worktime output ratio must match law rules")
        overtime_id = state.social_policy.overtime_building_id
        if overtime_id is not None:
            if "overtime_law" not in signed:
                raise SaveDataError("overtime target requires the overtime law")
            overtime_target = state.buildings[overtime_id]
            if overtime_target.building_type not in OVERTIME_BUILDING_TYPES:
                raise SaveDataError("overtime target building type is not allowed")
            if self._assigned_total(overtime_target) <= 0:
                raise SaveDataError("overtime target must retain assigned staff")
            if (
                state.social_policy.overtime_output_numerator,
                state.social_policy.overtime_output_denominator,
            ) != (
                self.rules.worktime.overtime_output_numerator,
                self.rules.worktime.overtime_output_denominator,
            ):
                raise SaveDataError("overtime output ratio must match law rules")
        if state.social_policy.firepit_enabled != ("firepit_law" in signed):
            raise SaveDataError("firepit enabled state must match signed law")
        expected_path = "cemetery" if "cemetery_law" in signed else "cold_pit" if "cold_pit_law" in signed else "none"
        if state.social_policy.death_path != expected_path:
            raise SaveDataError("death path must match signed laws")

    def evaluate_risks(self, state: GameState) -> tuple[RiskWarning, ...]:
        warnings: list[RiskWarning] = []
        effective_capacity = self._current_medical_capacity(state)
        medical_pressure = max(
            state.population.sick_population + state.population.critical_population - effective_capacity,
            0,
        )
        if state.social_policy.current_worktime_mode == "long_shift":
            warnings.append(RiskWarning("laws.long_shift_active", RiskWarningLevel.A_INFO, {"consecutive_days": state.social_policy.consecutive_long_shift_days}))
        if state.social_policy.overtime_building_id:
            warnings.append(RiskWarning("laws.overtime_active", RiskWarningLevel.B_STRONG, {"building_id": state.social_policy.overtime_building_id}))
        if state.social_policy.current_ration_mode != "normal":
            warnings.append(RiskWarning("laws.nonstandard_ration_active", RiskWarningLevel.A_INFO, {"mode": state.social_policy.current_ration_mode}))
        if medical_pressure > 0:
            warnings.append(RiskWarning("laws.medical_overload", RiskWarningLevel.B_STRONG, {"medical_pressure": medical_pressure, "effective_capacity": effective_capacity}))
        if state.calendar.current_day >= 4 and self._current_medical_capacity(state) == 0 and state.population.sick_population + state.population.critical_population > 0:
            warnings.append(RiskWarning("laws.day4_medical_gap", RiskWarningLevel.B_STRONG, {"current_day": state.calendar.current_day}))
        if state.social_policy.unhandled_bodies > 0:
            warnings.append(RiskWarning("laws.unhandled_bodies", RiskWarningLevel.B_STRONG, {"count": state.social_policy.unhandled_bodies}))
        return tuple(warnings)

    def prepare_daily_modes(self, context: EndDayContext) -> None:
        state = context.state
        ration_mode = self._effective_ration_mode(state)
        if state.social_policy.current_ration_mode == "emergency":
            ration_day = 1 if ration_mode == "emergency" else 0
        elif ration_mode == "normal":
            ration_day = 0
            state.social_policy.consecutive_ration_days = 0
            state.social_policy.consecutive_ration_mode = "normal"
        elif state.social_policy.consecutive_ration_mode == ration_mode:
            ration_day = state.social_policy.consecutive_ration_days + 1
            state.social_policy.consecutive_ration_days = ration_day
        else:
            ration_day = 1
            state.social_policy.consecutive_ration_days = 1
            state.social_policy.consecutive_ration_mode = ration_mode
        context.emit(
            "laws.daily_modes.prepared",
            {"ration_mode": ration_mode, "ration_day": ration_day},
        )

    def resolve_medical_disease_and_death(self, context: EndDayContext) -> None:
        state = context.state
        temporary = self.rules.medical.temporary_capacity if context.settled_day <= self.rules.medical.temporary_capacity_through_day else 0
        building_capacity = self._building_medical_capacity(state, expected=False)
        state.medical.temporary_capacity = temporary
        state.medical.building_capacity = building_capacity
        state.medical.effective_capacity = temporary + building_capacity
        ration_mode = self._effective_ration_mode(state)
        ration = self.rules.rations[ration_mode]
        ration_day = (
            1
            if ration_mode == "emergency"
            else state.social_policy.consecutive_ration_days
            if ration_mode != "normal"
            else 0
        )
        ration_sick = 0
        if ration.sick_after_days is not None and ration_day >= ration.sick_after_days and ration.sick_population_divisor:
            ration_sick = min(state.population.healthy_population, state.population.population_alive // ration.sick_population_divisor)
        state.population.healthy_population -= ration_sick
        state.population.sick_population += ration_sick
        requested_worktime_sick, accident_risk_points, worktime_details = (
            self._worktime_health_effects(state)
        )
        worktime_sick = min(
            state.population.healthy_population, requested_worktime_sick
        )
        state.population.healthy_population -= worktime_sick
        state.population.sick_population += worktime_sick
        state.daily_survival.worktime_sick_added = worktime_sick
        state.daily_survival.overtime_accident_risk_points = accident_risk_points
        accounted = state.social_policy.unhandled_bodies + state.social_policy.buried_bodies + state.social_policy.stored_bodies
        new_bodies = max(state.population.population_dead - accounted, 0)
        state.social_policy.unhandled_bodies += new_bodies
        if self._has_built_type(state, "cemetery"):
            state.social_policy.buried_bodies += state.social_policy.unhandled_bodies
            state.social_policy.unhandled_bodies = 0
        elif self._has_built_type(state, "cold_pit"):
            state.social_policy.stored_bodies += state.social_policy.unhandled_bodies
            state.social_policy.unhandled_bodies = 0
        state.medical.medical_pressure = max(
            state.population.sick_population + state.population.critical_population - state.medical.effective_capacity, 0
        )
        context.emit("laws.medical_and_death.resolved", {
            "temporary_capacity": temporary, "building_capacity": building_capacity,
            "effective_capacity": state.medical.effective_capacity,
            "medical_pressure": state.medical.medical_pressure,
            "ration_mode_used": ration_mode,
            "ration_sick_added": ration_sick,
            "worktime_sick_added": worktime_sick,
            "overtime_accident_risk_points": accident_risk_points,
            "accident_resolution": "risk_points_only_result_not_sealed",
            "worktime_details": worktime_details,
            "new_bodies": new_bodies, "unhandled_bodies": state.social_policy.unhandled_bodies,
        })

    def resolve_trust_and_panic(self, context: EndDayContext) -> None:
        state = context.state
        ration_mode = self._effective_ration_mode(state)
        ration = self.rules.rations[ration_mode]
        ration_day = (
            1
            if ration_mode == "emergency"
            else state.social_policy.consecutive_ration_days
            if ration_mode != "normal"
            else 0
        )
        trust_change = ration.daily_trust_change
        panic_change = ration.daily_panic_change
        if ration_mode == "rice_porridge" and ration_day % 2 == 0:
            trust_change -= 1
            panic_change += 1
        if ration_mode == "coarse_soup" and ration_day >= 6:
            panic_change += 1
        if state.social_policy.current_worktime_mode == "long_shift":
            long_day = state.social_policy.consecutive_long_shift_days + 1
            trust_change += self.rules.worktime.long_shift_daily_trust_change
            panic_change += self.rules.worktime.long_shift_daily_panic_change
            if long_day >= 3:
                panic_change += self.rules.worktime.long_shift_day_3_extra_panic
            if long_day >= 5:
                trust_change += self.rules.worktime.long_shift_day_5_extra_trust
            state.social_policy.consecutive_long_shift_days = long_day
        else:
            state.social_policy.consecutive_long_shift_days = 0
        if state.social_policy.firepit_enabled and state.daily_survival.effective_furnace_level > 0 and not state.daily_survival.heating_shortfall:
            panic_change += self.rules.actions.firepit_daily_panic_change
        units = state.social_policy.unhandled_bodies // self.rules.actions.unhandled_body_unit
        trust_change += units * self.rules.actions.unhandled_body_trust_change
        panic_change += units * self.rules.actions.unhandled_body_panic_change
        if state.social_policy.unhandled_bodies >= self.rules.actions.unhandled_body_crisis_threshold:
            panic_change += self.rules.actions.unhandled_body_crisis_extra_panic
            self._add_tag(state, "unhandled_bodies_crisis")
        self._change_emotion(state, trust=trust_change, panic=panic_change)
        context.emit("laws.trust_and_panic.resolved", {
            "trust_change": trust_change, "panic_change": panic_change,
            "ration_mode_used": ration_mode,
            "ration_days": ration_day,
            "long_shift_days": state.social_policy.consecutive_long_shift_days,
            "unhandled_bodies": state.social_policy.unhandled_bodies,
        })

    def close_action_effects(self, context: EndDayContext) -> None:
        state = context.state
        restored = None
        if state.social_policy.current_ration_mode == "emergency":
            restored = state.social_policy.previous_ration_mode
            assert restored is not None
            state.social_policy.current_ration_mode = restored
            previous_rule = self.rules.rations[restored]
            state.social_policy.ration_food_numerator = previous_rule.food_numerator
            state.social_policy.ration_food_denominator = previous_rule.food_denominator
            state.social_policy.previous_ration_mode = None
            state.social_policy.consecutive_ration_days = state.social_policy.previous_ration_days
            state.social_policy.previous_ration_days = 0
        state.social_policy.triage_building_id = None
        context.emit("laws.action_effects.closed", {"restored_ration_mode": restored, "triage_reset": True})

    @staticmethod
    def close_daily_effects(context: EndDayContext) -> None:
        state = context.state
        state.social_policy.overtime_building_id = None
        state.social_policy.overtime_output_numerator = 100
        state.social_policy.overtime_output_denominator = 100
        state.medical.medical_ration_sick_cured_today = 0
        state.medical.medical_ration_critical_progress_today = 0
        context.emit("laws.daily_effects.closed", {"overtime_reset": True, "medical_action_summary_reset": True})

    def observe(self, state: GameState) -> dict[str, Any]:
        self.validate_state(state)
        signed = set(state.laws.signed_law_ids)
        available: list[str] = []
        locked: dict[str, Any] = {}
        for law_id, rule in self.rules.laws.items():
            if law_id in signed:
                continue
            missing_all = sorted(set(rule.required_all) - signed)
            missing_any = bool(rule.required_any) and not (set(rule.required_any) & signed)
            conflicts = sorted(set(rule.mutually_exclusive) & signed)
            if not missing_all and not missing_any and not conflicts:
                available.append(law_id)
            else:
                locked[law_id] = {"missing_all": missing_all, "required_any": list(rule.required_any) if missing_any else [], "conflicts": conflicts}
        all_building_unlocks = {
            item for law_id in signed for item in self.rules.laws[law_id].unlock_buildings
        }
        unlocked_buildings = sorted(
            item for item in all_building_unlocks if item in self.building_rules.buildings
        )
        deferred_buildings = sorted(
            item for item in all_building_unlocks if item not in self.building_rules.buildings
        )
        unlocked_actions = sorted({item for law_id in signed for item in self.rules.laws[law_id].unlock_actions})
        overtime_building_id = state.social_policy.overtime_building_id
        progress_numerator, progress_denominator = (
            self.overtime_progress_multiplier(state, overtime_building_id)
            if overtime_building_id is not None
            else (100, 100)
        )
        return {
            "signed_law_ids": list(state.laws.signed_law_ids),
            "available_law_ids": sorted(available), "locked_laws": locked,
            "next_ordinary_law_day": state.laws.cooldowns.get(_LAW_COOLDOWN, 1),
            "unlocked_building_ids": unlocked_buildings,
            "deferred_building_ids": deferred_buildings,
            "unlocked_action_ids": unlocked_actions,
            "ration_mode": state.social_policy.current_ration_mode,
            "worktime_mode": state.social_policy.current_worktime_mode,
            "overtime_progress_multiplier": {
                "building_id": overtime_building_id,
                "numerator": progress_numerator,
                "denominator": progress_denominator,
            },
            "death_path": state.social_policy.death_path,
            "firepit_enabled": state.social_policy.firepit_enabled,
            "medical_capacity": self._current_medical_capacity(state),
            "medical_pressure": max(
                state.population.sick_population + state.population.critical_population
                - self._current_medical_capacity(state),
                0,
            ),
            "action_next_available_days": {k: v for k, v in state.laws.cooldowns.items() if k != _LAW_COOLDOWN},
        }

    def overtime_progress_multiplier(
        self, state: GameState, building_id: str
    ) -> tuple[int, int]:
        """Return the exact treatment/research progress multiplier for a building."""

        building = state.buildings.get(building_id)
        if (
            state.social_policy.overtime_building_id == building_id
            and building is not None
            and building.building_type
            in {"medical_station", "hospital", "research_institute"}
        ):
            return (
                self.rules.worktime.overtime_medical_research_numerator,
                self.rules.worktime.overtime_medical_research_denominator,
            )
        return 100, 100

    def _current_medical_capacity(self, state: GameState) -> int:
        temporary = self.rules.medical.temporary_capacity if state.calendar.current_day <= self.rules.medical.temporary_capacity_through_day else 0
        return temporary + self._building_medical_capacity(state, expected=True)

    def _sync_medical_capacity(self, state: GameState) -> None:
        temporary = self.rules.medical.temporary_capacity if state.calendar.current_day <= self.rules.medical.temporary_capacity_through_day else 0
        building = self._building_medical_capacity(state, expected=True)
        state.medical.temporary_capacity = temporary
        state.medical.building_capacity = building
        state.medical.effective_capacity = temporary + building
        state.medical.medical_pressure = max(
            state.population.sick_population + state.population.critical_population
            - state.medical.effective_capacity,
            0,
        )

    def _building_medical_capacity(
        self, state: GameState, *, expected: bool
    ) -> int:
        capacity = 0
        for building in state.buildings.values():
            operational = (
                self._is_expected_operational(state, building)
                if expected
                else building.is_operational
            )
            if not operational:
                continue
            staff = self._assigned_total(building)
            if building.building_type == "medical_station":
                full_capacity = (
                    12
                    if "tech_medical_tools_improvement"
                    in state.technologies.researched_tech_ids
                    else 10
                )
                capacity += (full_capacity * staff) // 5
            elif building.building_type == "hospital":
                capacity += (30 * staff) // 10
        return capacity

    def _has_operational_canteen(self, state: GameState) -> bool:
        return any(
            building.building_type == "canteen"
            and self._is_expected_operational(state, building)
            for building in state.buildings.values()
        )

    def _is_expected_operational(self, state: GameState, building: Any) -> bool:
        return is_building_expected_operational(
            state,
            building,
            self.building_rules,
            self.survival_rules,
            self.technology_rules,
        )

    def _effective_ration_mode(self, state: GameState) -> str:
        if (
            state.daily_survival.settled_day == state.calendar.current_day
            and state.daily_survival.ration_mode_used in self.rules.rations
        ):
            return state.daily_survival.ration_mode_used
        if (
            state.social_policy.current_ration_mode != "normal"
            and not self._has_operational_canteen(state)
        ):
            return "normal"
        return state.social_policy.current_ration_mode

    def _worktime_health_effects(
        self, state: GameState
    ) -> tuple[int, int, dict[str, Any]]:
        overtime_sick = 0
        overtime_cold_sick = 0
        accident_risk_points = 0
        overtime_staff = 0
        overtime_id = state.social_policy.overtime_building_id
        if overtime_id is not None:
            target = state.buildings[overtime_id]
            overtime_staff = self._assigned_total(target)
            overtime_sick = overtime_staff // self.rules.worktime.overtime_sick_divisor
            if overtime_staff > 0:
                overtime_sick = max(
                    overtime_sick,
                    self.rules.worktime.overtime_sick_minimum_if_staffed,
                )
                accident_divisor = self.rules.worktime.overtime_accident_risk_divisor
                accident_risk_points = (
                    overtime_staff + accident_divisor - 1
                ) // accident_divisor
            if self._is_severe_cold_work(target):
                overtime_cold_sick = (
                    overtime_staff
                    // self.rules.worktime.overtime_cold_extra_sick_divisor
                )

        long_shift_sick = 0
        long_shift_cold_sick = 0
        long_shift_staff = 0
        long_shift_cold_staff = 0
        if state.social_policy.current_worktime_mode == "long_shift":
            affected = [
                building
                for building in state.buildings.values()
                if building.is_operational
                and building.building_type not in _LONG_SHIFT_EXCLUDED_TYPES
                and self._assigned_total(building) > 0
            ]
            long_shift_staff = sum(self._assigned_total(item) for item in affected)
            long_shift_cold_staff = sum(
                self._assigned_total(item)
                for item in affected
                if self._is_severe_cold_work(item)
            )
            long_shift_day = state.social_policy.consecutive_long_shift_days + 1
            divisor = (
                self.rules.worktime.long_shift_first_day_sick_divisor
                if long_shift_day == 1
                else self.rules.worktime.long_shift_consecutive_sick_divisor
            )
            long_shift_sick = long_shift_staff // divisor
            long_shift_cold_sick = (
                long_shift_cold_staff
                // self.rules.worktime.long_shift_cold_extra_sick_divisor
            )

        total_sick = (
            overtime_sick
            + overtime_cold_sick
            + long_shift_sick
            + long_shift_cold_sick
        )
        return total_sick, accident_risk_points, {
            "overtime_staff": overtime_staff,
            "overtime_sick_added": overtime_sick,
            "overtime_cold_extra_sick": overtime_cold_sick,
            "long_shift_staff": long_shift_staff,
            "long_shift_cold_staff": long_shift_cold_staff,
            "long_shift_sick_added": long_shift_sick,
            "long_shift_cold_extra_sick": long_shift_cold_sick,
        }

    @staticmethod
    def _is_severe_cold_work(building: Any) -> bool:
        return building.effective_temperature <= -46

    @staticmethod
    def _has_built_type(state: GameState, building_type: str) -> bool:
        return any(building.building_type == building_type and building.is_built for building in state.buildings.values())

    @staticmethod
    def _assigned_total(building: Any) -> int:
        return sum((
            building.assigned_workers, building.assigned_engineers,
            building.assigned_children, building.assigned_medical_apprentices,
            building.assigned_engineering_apprentices,
        ))

    @staticmethod
    def _change_emotion(state: GameState, *, trust: int = 0, panic: int = 0) -> None:
        if state.trust_panic.trust is not None:
            state.trust_panic.trust = min(max(state.trust_panic.trust + trust, 0), 100)
        if state.trust_panic.panic is not None:
            state.trust_panic.panic = min(max(state.trust_panic.panic + panic, 0), 100)

    @staticmethod
    def _add_tag(state: GameState, tag: str) -> None:
        if tag not in state.social_policy.ending_tag_candidates:
            state.social_policy.ending_tag_candidates.append(tag)

    @staticmethod
    def _illegal(reason: str, **details: Any) -> CommandValidation:
        return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": reason, **details})

    @staticmethod
    def _rejected(command_id: str, sequence: int, validation: CommandValidation) -> CommandResult:
        data = dict(validation.details)
        return CommandResult(
            command_id=command_id, accepted=False, code=validation.code,
            state_changed=False, state_sequence=sequence,
            feedback=(FeedbackItem(FeedbackLevel.ERROR, data=data),), data=data,
        )

    @staticmethod
    def _error(command_id: str, sequence: int, stage: str, exc: Exception) -> CommandResult:
        data = {"failed_stage": stage, "exception_type": type(exc).__name__}
        return CommandResult(
            command_id=command_id, accepted=False, code=ErrorCode.INTERNAL_ERROR,
            state_changed=False, state_sequence=sequence,
            feedback=(FeedbackItem(FeedbackLevel.ERROR, data=data),), data=data,
        )
