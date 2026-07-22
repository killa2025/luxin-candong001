from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import fields
from typing import Any

from furnace_winter.config import BuildingRules, EventRules, SurvivalRules, TechnologyRules
from furnace_winter.gameplay.end_day import (
    EndDayContext,
    EndDayEngine,
    EndDayStage,
    RiskWarning,
    RiskWarningLevel,
)
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
    EventRecord,
    EventResolutionRecord,
    GameState,
    PromiseRecord,
    PromiseSettlementRecord,
    SaveDataError,
    validate_game_state,
)


RESOLVE_EVENT_COMMAND = "game.resolve_event"
EVENT_ID_ARGUMENT = "event_id"
OPTION_ID_ARGUMENT = "option_id"

_FIXED_WARNING_EVENTS = {
    34: "black_frost_echo",
    42: "final_preparation_window",
    46: "city_night_terror",
    49: "seventh_frost_start",
}
_FROST_STAGE_BY_DAY = {
    34: "day34",
    42: "day42",
    46: "day46",
    48: "day48",
    49: "day49",
}
_TODO_BODY_EVENTS = {
    "long_shift_collapse",
    "overtime_empty_post",
    "seventh_frost_start",
    "arrival_day6",
    "arrival_day19",
    "arrival_day37",
}
_FOLLOWUP_COMMANDS = {
    "adjust_ration_prompt": "game.set_ration",
    "medical_ration_prompt": "game.medical_ration",
    "memorial_prompt": "game.memorial",
    "adjust_furnace_prompt": "game.set_furnace",
    "overload_off_prompt": "game.set_overload",
    "increase_furnace_prompt": "game.set_furnace",
}
_EVENT_OPTIONS: dict[str, tuple[str, ...]] = {
    "empty_pot": ("promise_food", "maintain_ration", "adjust_ration_prompt"),
    "raw_food_dispute": ("promise_food", "continue_raw_food", "prioritize_children"),
    "medical_beds_emergency": ("promise_medical", "temporary_beds", "maintain"),
    "severe_case_backlog": ("medical_ration_prompt", "promise_medical", "accept_current"),
    "first_body": ("public_memorial", "quiet_handling", "postpone"),
    "bodies_under_snow": ("promise_body", "memorial_prompt", "continue_postponing"),
    "children_request": ("promise_children", "maintain", "fireside_tasks"),
    "red_frozen_hands": ("suspend_high_risk", "cold_care", "continue"),
    "long_shift_collapse": ("suspend_long_shift", "food_compensation", "continue"),
    "overtime_empty_post": ("promise_labor", "food_compensation", "continue"),
    "coal_bottom": ("promise_coal", "adjust_furnace_prompt", "maintain"),
    "furnace_redline": ("overload_off_prompt", "promise_furnace", "maintain_overload"),
    "cold_house_night": ("promise_housing", "increase_furnace_prompt", "maintain"),
    "trust_crack": ("promise_trust", "public_explanation", "avoid_questions"),
    "city_unrest": ("promise_panic", "calm_and_explain", "suppress_unrest"),
    "black_frost_echo": ("publish_warning", "management_only", "delay_announcement"),
    "final_preparation_window": ("publish_checklist", "management_only", "suppress_panic"),
    "city_night_terror": ("final_mobilization", "maintain_order", "tell_the_truth"),
    "seventh_frost_start": ("acknowledge",),
}


def build_event_catalog() -> CommandCatalog:
    catalog = CommandCatalog()
    catalog.register(
        CommandSpec(
            name=RESOLVE_EVENT_COMMAND,
            required_arguments={
                EVENT_ID_ARGUMENT: ArgumentKind.STRING,
                OPTION_ID_ARGUMENT: ArgumentKind.STRING,
            },
        )
    )
    return catalog


class EventSystem:
    """Patch 007 event queue, promises, fixed arrivals, and warning nodes."""

    def __init__(
        self,
        rules: EventRules,
        building_rules: BuildingRules,
        survival_rules: SurvivalRules,
        technology_rules: TechnologyRules | None = None,
    ) -> None:
        self.rules = rules
        self.building_rules = building_rules
        self.survival_rules = survival_rules
        self.technology_rules = technology_rules
        self._catalog = build_event_catalog()
        self._validator = CommandValidator(self._catalog)

    def command_specs(self) -> tuple[CommandSpec, ...]:
        return self._catalog.specs()

    def active_event_views(self, state: GameState) -> tuple[dict[str, Any], ...]:
        """Return deterministic, machine-readable event panels for an AI client."""

        self.validate_state(state)
        views: list[dict[str, Any]] = []
        for event in sorted(
            state.events.active_events.values(),
            key=lambda item: (item.priority, item.event_id),
        ):
            available = set(self._available_options(state, event.event_id))
            canonical = (
                tuple(self.rules.fixed_arrivals[event.event_id].options)
                if event.event_id in self.rules.fixed_arrivals
                else _EVENT_OPTIONS[event.event_id]
            )
            option_views: list[dict[str, Any]] = []
            unavailable_views: list[dict[str, Any]] = []
            for option_id in canonical:
                is_available = (
                    option_id in event.option_ids and option_id in available
                )
                if not is_available:
                    unavailable_views.append(
                        {
                            "option_id": option_id,
                            "text_id": self._option_text_id(
                                event.event_id, option_id, canonical
                            ),
                            "reason": self._option_unavailable_reason(
                                state, event.event_id, option_id
                            ),
                        }
                    )
                    continue
                preview: dict[str, Any] | None = None
                preview_state = deepcopy(state)
                preview = self._resolve(
                    preview_state, event.event_id, option_id
                )
                option_views.append(
                    {
                        "option_id": option_id,
                        "text_id": self._option_text_id(
                            event.event_id, option_id, canonical
                        ),
                        "available": True,
                        "followup_command": _FOLLOWUP_COMMANDS.get(option_id),
                        "preview": preview,
                    }
                )
            title_id, body_id = self._event_text_ids(event.event_id)
            views.append(
                {
                    "event_id": event.event_id,
                    "event_type": event.event_type,
                    "is_blocking": event.is_blocking,
                    "trigger_day": event.trigger_day,
                    "trigger_reason_ids": list(event.trigger_reason_ids),
                    "priority": event.priority,
                    "title_text_id": title_id,
                    "body_text_id": body_id,
                    "body_status": (
                        "TODO_TEXT"
                        if event.event_id in _TODO_BODY_EVENTS
                        else "AVAILABLE"
                    ),
                    "status_summary": self._event_status_snapshot(state),
                    "options": option_views,
                    "unavailable_extra_options": unavailable_views,
                }
            )
        return tuple(views)

    def active_promise_views(self, state: GameState) -> tuple[dict[str, Any], ...]:
        """Return targets and exact settlement directions without strategy hints."""

        self.validate_state(state)
        views: list[dict[str, Any]] = []
        for promise in sorted(
            state.promises.active_promises.values(),
            key=lambda item: item.promise_id,
        ):
            effect = self.rules.promise.effects[promise.severity]
            views.append(
                {
                    "promise_id": promise.promise_id,
                    "promise_type": promise.promise_type,
                    "name_text_id": f"promise.{promise.promise_type}.name",
                    "source_event_id": promise.source_event_id,
                    "created_day": promise.created_day,
                    "deadline_day": promise.deadline_day,
                    "days_remaining": max(
                        promise.deadline_day - state.calendar.current_day, 0
                    ),
                    "deadline_day_is_usable": True,
                    "target_id": f"promise.{promise.promise_type}.target",
                    "target_met_now": self._promise_succeeded(state, promise),
                    "severity": promise.severity,
                    "success_effect": {
                        "trust": effect.success_trust,
                        "panic": effect.success_panic,
                    },
                    "failure_effect": {
                        "trust": effect.failure_trust,
                        "panic": effect.failure_panic,
                    },
                }
            )
        return tuple(views)

    def install(self, engine: EndDayEngine) -> None:
        engine.register_state_validator(self.validate_state)
        engine.register_risk_evaluator(self.evaluate_risks)
        engine.register_stage_handler(
            EndDayStage.UPDATE_PROMISE_TARGETS, self.capture_daily_metrics
        )
        engine.register_stage_handler(
            EndDayStage.CHECK_HIDDEN_ACHIEVEMENTS,
            self.check_hidden_achievements,
        )
        engine.register_new_day_handler(self.begin_new_day)

    def initialize_day(self, state: GameState) -> None:
        """Generate the current day once, including a fresh game's day 1."""

        self.validate_state(state)
        if state.events.generated_for_day is None:
            self._prepare_day(state)
        self.validate_state(state)

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
            event_id = request.arguments[EVENT_ID_ARGUMENT]
            option_id = request.arguments[OPTION_ID_ARGUMENT]
            assert isinstance(event_id, str) and isinstance(option_id, str)
            data = self._resolve(working, event_id, option_id)
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
        event_id = request.arguments.get(EVENT_ID_ARGUMENT)
        option_id = request.arguments.get(OPTION_ID_ARGUMENT)
        event = state.events.active_events.get(event_id)
        if event is None:
            return self._illegal("event_not_active", event_id=event_id)
        if option_id not in event.option_ids:
            return self._illegal(
                "event_option_unavailable",
                event_id=event_id,
                option_id=option_id,
                available_option_ids=list(event.option_ids),
                unavailable_reason=self._option_unavailable_reason(
                    state, event_id, option_id
                ),
            )
        if option_id not in self._available_options(state, event_id):
            return self._illegal(
                "event_option_prerequisite_changed",
                event_id=event_id,
                option_id=option_id,
                unavailable_reason=self._option_unavailable_reason(
                    state, event_id, option_id
                ),
            )
        return CommandValidation.valid()

    def _resolve(
        self, state: GameState, event_id: str, option_id: str
    ) -> dict[str, Any]:
        event = state.events.active_events[event_id]
        trust_before = state.trust_panic.trust
        panic_before = state.trust_panic.panic
        population_before = state.population.population_alive
        resources_before = {
            name: getattr(state.resources, name)
            for name in ("coal", "wood", "steel", "raw_food", "cooked_food")
        }
        promise_id: str | None = None

        if event_id in self.rules.fixed_arrivals:
            self._apply_arrival(state, event_id, option_id)
        else:
            promise_type = self._promise_type_for_option(event_id, option_id)
            if promise_type is not None:
                promise_id = self._create_promise(state, event_id, promise_type)
            self._apply_event_effect(state, event_id, option_id)

        del state.events.active_events[event_id]
        if event_id not in state.events.resolved_event_ids:
            state.events.resolved_event_ids.append(event_id)
        data = {
            "event_id": event_id,
            "option_id": option_id,
            "event_type": event.event_type,
            "promise_id": promise_id,
            "trust_change": self._delta(trust_before, state.trust_panic.trust),
            "panic_change": self._delta(panic_before, state.trust_panic.panic),
            "population_added": state.population.population_alive - population_before,
            "resource_changes": {
                name: getattr(state.resources, name) - before
                for name, before in resources_before.items()
            },
            "risk_preview": self.arrival_risk_preview(state)
            if event_id in self.rules.fixed_arrivals
            else None,
        }
        state.events.resolution_history.append(
            EventResolutionRecord(
                event_id=event_id,
                option_id=option_id,
                event_type=event.event_type,
                resolved_day=state.calendar.current_day,
                trust_change=data["trust_change"],
                panic_change=data["panic_change"],
                population_added=data["population_added"],
                resource_changes=dict(data["resource_changes"]),
            )
        )
        return data

    def _create_promise(
        self, state: GameState, source_event_id: str, promise_type: str
    ) -> str:
        if len(state.promises.active_promises) >= self.rules.promise.max_active:
            raise SaveDataError("promise slots are full")
        if any(
            item.promise_type == promise_type
            for item in state.promises.active_promises.values()
        ):
            raise SaveDataError("a promise of this type is already active")
        if state.calendar.current_day >= self.rules.promise.disabled_from_day:
            raise SaveDataError("normal promises are disabled during frostfall")
        duration = self.rules.promise.deadlines[promise_type]
        deadline = state.calendar.current_day + duration
        if state.calendar.current_day >= self.rules.promise.deadline_cap_start_day:
            deadline = min(deadline, self.rules.promise.deadline_cap_day)
        if deadline < state.calendar.current_day:
            raise SaveDataError("no valid promise deadline remains")
        rule = self.rules.events[source_event_id]
        severity = rule.promise_severity
        if severity is None:
            raise SaveDataError("source event does not define promise severity")
        if (
            promise_type == "furnace"
            and state.furnace.pressure
            >= self.rules.thresholds["furnace_pressure_forced"]
        ):
            severity = "critical"
        elif (
            promise_type == "housing"
            and state.events.active_events[source_event_id].event_type == "major"
        ):
            severity = "serious"
        promise_id = f"promise-{state.promises.next_sequence:04d}"
        state.promises.next_sequence += 1
        state.promises.active_promises[promise_id] = PromiseRecord(
            promise_id=promise_id,
            promise_type=promise_type,
            source_event_id=source_event_id,
            created_day=state.calendar.current_day,
            deadline_day=deadline,
            severity=severity,
            target={
                "trust_at_creation": state.trust_panic.trust or 0,
                "panic_at_creation": state.trust_panic.panic or 0,
            },
        )
        return promise_id

    def begin_new_day(self, state: GameState) -> None:
        self._settle_promises(state)
        self._prepare_day(state)

    def _settle_promises(self, state: GameState) -> None:
        for promise_id in list(state.promises.active_promises):
            promise = state.promises.active_promises[promise_id]
            succeeded = self._promise_succeeded(state, promise)
            if not succeeded and state.calendar.current_day <= promise.deadline_day:
                continue
            effect = self.rules.promise.effects[promise.severity]
            if succeeded:
                self._change_morale(
                    state, effect.success_trust, effect.success_panic
                )
                state.promises.completed_promise_ids.append(promise_id)
                outcome = "success"
                trust_change = effect.success_trust
                panic_change = effect.success_panic
            else:
                self._change_morale(
                    state, effect.failure_trust, effect.failure_panic
                )
                state.promises.failed_promise_ids.append(promise_id)
                outcome = "failure"
                trust_change = effect.failure_trust
                panic_change = effect.failure_panic
                chain_key = f"chain_{promise.promise_type}_stage"
                state.events.metrics[chain_key] = min(
                    state.events.metrics.get(chain_key, 1) + 1, 3
                )
            state.promises.settlement_history.append(
                PromiseSettlementRecord(
                    promise_id=promise_id,
                    promise_type=promise.promise_type,
                    settled_day=state.calendar.current_day,
                    outcome=outcome,
                    severity=promise.severity,
                    trust_change=trust_change,
                    panic_change=panic_change,
                )
            )
            del state.promises.active_promises[promise_id]

    def _promise_succeeded(self, state: GameState, promise: PromiseRecord) -> bool:
        kind = promise.promise_type
        alive = state.population.population_alive
        if kind == "food":
            edible = state.resources.raw_food + state.resources.cooked_food
            if edible < alive * 2:
                return False
            if state.resources.cooked_food >= alive:
                return True
            processing_capacity = sum(
                (
                    80
                    if "tech_canteen_process_improvement"
                    in state.technologies.researched_tech_ids
                    else self.building_rules.buildings[
                        item.building_type
                    ].raw_food_processing_cap
                )
                for item in state.buildings.values()
                if item.building_type == "canteen" and item.is_operational
            )
            cooked_shortfall = alive - state.resources.cooked_food
            return min(state.resources.raw_food, processing_capacity) >= cooked_shortfall
        if kind == "medical":
            patients = state.population.sick_population + state.population.critical_population
            has_operational_medical = any(
                item.building_type in {"medical_station", "hospital"}
                and item.is_operational
                for item in state.buildings.values()
            )
            return (
                has_operational_medical
                and state.medical.effective_capacity >= patients
            )
        if kind == "housing":
            return state.population.homeless_population == 0
        if kind == "body":
            return state.social_policy.unhandled_bodies == 0
        if kind == "children":
            return self._unprotected_children(state) == 0
        if kind == "labor":
            first_recent_day = state.calendar.current_day - 2
            last_recent_day = state.calendar.current_day - 1
            return (
                not any(
                    first_recent_day <= day <= last_recent_day
                    for day in state.events.recent_overtime_days
                )
                and (
                    state.social_policy.current_worktime_mode == "normal"
                    or state.events.metrics.get("long_shift_suspended_until_day")
                    == state.calendar.current_day
                )
                and state.daily_survival.worktime_sick_added == 0
            )
        if kind == "coal":
            base_cost = self.survival_rules.furnace_levels[
                self._current_furnace_level(state)
            ].coal_cost
            if base_cost == 0:
                base_cost = self.survival_rules.furnace_levels[1].coal_cost
            return state.resources.coal >= base_cost * 2
        if kind == "furnace":
            return state.furnace.pressure <= 70 and state.furnace.overload_level == 0
        if kind == "trust":
            trust = state.trust_panic.trust or 0
            return trust >= 40 or trust >= promise.target["trust_at_creation"] + 8
        if kind == "panic":
            panic = state.trust_panic.panic or 0
            return panic <= 60 or panic <= promise.target["panic_at_creation"] - 8
        raise SaveDataError(f"unsupported promise type: {kind}")

    def _prepare_day(self, state: GameState) -> None:
        day = state.calendar.current_day
        state.events.active_events.clear()
        state.events.suppressed_event_ids_today.clear()
        state.events.generated_for_day = day
        state.events.seventh_frostfall_active = day >= 49
        state.events.frostfall_warning_stage = "none"
        for warning_day, stage in sorted(_FROST_STAGE_BY_DAY.items()):
            if day >= warning_day:
                state.events.frostfall_warning_stage = stage
        if day == 48:
            state.events.frostfall_eve_status_shown = True
        if day >= state.old_city.trigger_day and not state.old_city.is_unlocked:
            state.old_city.activation_pending = True
        state.events.status_ids = self._status_ids(state)
        if day == 48:
            self._add_unique(state.events.status_ids, "event.frost_eve")

        major: list[str] = []
        normal: list[str] = []
        arrival = next(
            (
                item.event_id
                for item in self.rules.fixed_arrivals.values()
                if item.day == day and item.event_id not in state.events.fixed_arrival_choices
            ),
            None,
        )
        if arrival is not None:
            major.append(arrival)
        warning = _FIXED_WARNING_EVENTS.get(day)
        if warning is not None and self._eligible(state, warning):
            major.append(warning)
        for event_id, event_type in self._condition_candidates(state):
            if self._eligible(state, event_id):
                (major if event_type == "major" else normal).append(event_id)

        major.sort(key=self._priority_key)
        normal.sort(key=self._priority_key)
        selected_major = major[: self.rules.queue.max_major_per_day]
        normal_limit = (
            self.rules.queue.max_normal_with_major
            if selected_major
            else self.rules.queue.max_normal_without_major
        )
        selected_normal = normal[:normal_limit]
        suppressed = major[len(selected_major):] + normal[len(selected_normal):]
        state.events.suppressed_event_ids_today.extend(suppressed)
        for event_id in suppressed:
            self._add_unique(state.events.status_ids, f"event.suppressed.{event_id}")
        for event_id in selected_major:
            self._activate(state, event_id, "major")
        for event_id in selected_normal:
            self._activate(state, event_id, "normal")

    def _condition_candidates(self, state: GameState) -> list[tuple[str, str]]:
        if state.calendar.current_day >= 49:
            return []
        candidates: list[tuple[str, str]] = []
        thresholds = self.rules.thresholds
        food_days_x10 = self._food_days_x10(state)
        if food_days_x10 < thresholds["empty_pot_days_x10"] and state.events.metrics.get("food_warning_streak", 0) >= 1:
            candidates.append(("empty_pot", "normal"))
        if (
            len(self._recent_raw_food_days(state)) >= thresholds["raw_food_days"]
            or self._has_recent_consecutive_canteen_outage(state)
        ):
            candidates.append(("raw_food_dispute", "normal"))
        patients = state.population.sick_population + state.population.critical_population
        gap = max(patients - state.medical.effective_capacity, 0)
        if gap >= thresholds["medical_gap_event"]:
            major = gap >= thresholds["medical_gap_major"] or (state.medical.effective_capacity == 0 and patients >= 5)
            candidates.append(("medical_beds_emergency", "major" if major else "normal"))
        if (
            state.population.critical_population >= thresholds["severe_patients"]
            or state.events.metrics.get("persistent_severe_days", 0)
            >= thresholds["persistent_severe_days"]
        ):
            candidates.append(("severe_case_backlog", "normal"))
        if state.population.population_dead > 0:
            candidates.append(("first_body", "major"))
        bodies = state.social_policy.unhandled_bodies
        if bodies >= thresholds["unhandled_body_event"]:
            candidates.append(("bodies_under_snow", "major" if bodies >= thresholds["unhandled_body_major"] else "normal"))
        if state.calendar.current_day >= thresholds["children_request_day_min"] and self._unprotected_children(state) >= thresholds["unprotected_children"]:
            candidates.append(("children_request", "normal"))
        child_labor_active = bool(
            {
                "child_labor_low_risk_law",
                "child_labor_all_jobs_law",
            }
            & set(state.laws.signed_law_ids)
        )
        if child_labor_active and (
            state.events.metrics.get("child_labor_risk_points", 0)
            >= thresholds["child_labor_risk_points"]
            or state.events.metrics.get("child_harm_from_work_today", 0)
            >= thresholds["child_harm_from_work"]
        ):
            candidates.append(("red_frozen_hands", "major"))
        if (
            state.social_policy.consecutive_long_shift_days
            >= thresholds["long_shift_days"]
            or state.events.metrics.get("long_shift_risk_points", 0)
            >= thresholds["long_shift_risk_points"]
        ):
            candidates.append(("long_shift_collapse", "normal"))
        recent_overtime = [
            day for day in state.events.recent_overtime_days
            if day >= state.calendar.current_day - thresholds["overtime_window_days"]
        ]
        if (
            len(recent_overtime) >= thresholds["overtime_uses"]
            or state.events.metrics.get("overtime_harm_today", 0) >= 1
        ):
            candidates.append(("overtime_empty_post", "major"))
        coal_days_x10 = self._coal_days_x10(state)
        if coal_days_x10 < thresholds["coal_event_days_x10"]:
            coal_major = (
                state.calendar.current_day >= 34
                and coal_days_x10
                < thresholds["coal_major_days_x10_after_black_frost"]
            )
            candidates.append(("coal_bottom", "major" if coal_major else "normal"))
        pressure = state.furnace.pressure
        if pressure >= thresholds["furnace_pressure_event"]:
            candidates.append(("furnace_redline", "major"))
        exposure_level = state.events.metrics.get("cold_exposure_level", 0)
        if (
            state.calendar.current_day >= thresholds["cold_house_day_min"]
            and state.population.homeless_population >= thresholds["homeless_event"]
            and exposure_level >= thresholds["cold_exposure_event_level"]
            and (
                state.calendar.current_day >= 34
                or state.events.metrics.get("cold_exposure_warning_streak", 0)
                >= thresholds["cold_exposure_status_delay_days"]
            )
        ):
            major = (
                state.population.homeless_population >= thresholds["homeless_major"]
                or exposure_level >= thresholds["cold_exposure_major_level"]
            )
            candidates.append(("cold_house_night", "major" if major else "normal"))
        trust = state.trust_panic.trust
        if trust is not None and trust <= thresholds["trust_event"]:
            candidates.append(("trust_crack", "major" if trust <= thresholds["trust_major"] else "normal"))
        panic = state.trust_panic.panic
        if panic is not None and panic >= thresholds["panic_event"]:
            candidates.append(("city_unrest", "major" if panic >= thresholds["panic_major"] else "normal"))
        return candidates

    def _activate(self, state: GameState, event_id: str, event_type: str) -> None:
        options = self._available_options(state, event_id)
        if not options:
            raise SaveDataError("an active event must retain an executable option")
        priority = (
            1
            if event_id in self.rules.fixed_arrivals
            else self.rules.events[event_id].priority
        )
        state.events.active_events[event_id] = EventRecord(
            event_id=event_id,
            event_type=event_type,
            trigger_day=state.calendar.current_day,
            priority=priority,
            trigger_reason_ids=list(self._trigger_reason_ids(state, event_id)),
            option_ids=list(options),
            is_blocking=event_type == "major",
        )
        state.events.occurrence_counts[event_id] = (
            state.events.occurrence_counts.get(event_id, 0) + 1
        )
        cooldown = self.rules.events.get(event_id)
        if cooldown is not None and cooldown.cooldown_days:
            state.events.cooldown_until_day[event_id] = (
                state.calendar.current_day + cooldown.cooldown_days
            )
        if (
            event_id == "furnace_redline"
            and state.furnace.pressure
            >= self.rules.thresholds["furnace_pressure_forced"]
        ):
            state.events.metrics["furnace_forced_redline_shown"] = 1

    def _available_options(self, state: GameState, event_id: str) -> tuple[str, ...]:
        if event_id in self.rules.fixed_arrivals:
            return tuple(self.rules.fixed_arrivals[event_id].options)
        available: list[str] = []
        for option_id in _EVENT_OPTIONS[event_id]:
            promise_type = self._promise_type_for_option(event_id, option_id)
            if promise_type is not None and not self._can_create_promise(state, promise_type):
                continue
            if option_id == "prioritize_children" and (
                state.population.children == 0 or state.resources.cooked_food == 0
            ):
                continue
            if option_id == "temporary_beds" and not (
                "basic_medical_law" in state.laws.signed_law_ids
                or any(item.building_type in {"medical_station", "hospital"} and item.is_operational for item in state.buildings.values())
            ):
                continue
            if option_id == "medical_ration_prompt" and not (
                "medical_ration_law" in state.laws.signed_law_ids
                and state.resources.cooked_food >= 3
                and state.calendar.current_day
                >= state.laws.cooldowns.get("medical_ration", 1)
            ):
                continue
            if option_id == "memorial_prompt" and not (
                "memorial_law" in state.laws.signed_law_ids
                and any(
                    item.building_type == "cemetery" and item.is_built
                    for item in state.buildings.values()
                )
                and state.calendar.current_day
                >= state.laws.cooldowns.get("memorial", 1)
            ):
                continue
            if option_id == "overload_off_prompt" and state.furnace.overload_level == 0:
                continue
            food_cost = self._event_food_cost(state, event_id, option_id)
            if food_cost is not None and state.resources.cooked_food < food_cost:
                continue
            available.append(option_id)
        return tuple(available)

    def _trigger_reason_ids(
        self, state: GameState, event_id: str
    ) -> tuple[str, ...]:
        if event_id in self.rules.fixed_arrivals:
            return ("fixed_arrival_day",)
        if event_id in _FIXED_WARNING_EVENTS.values():
            return ("fixed_frost_warning_day",)
        thresholds = self.rules.thresholds
        reasons: list[str] = []
        if event_id == "empty_pot":
            reasons.append("food_reserve_below_threshold")
        elif event_id == "raw_food_dispute":
            if len(self._recent_raw_food_days(state)) >= thresholds["raw_food_days"]:
                reasons.append("recent_raw_food_days_reached")
            if self._has_recent_consecutive_canteen_outage(state):
                reasons.append("recent_canteen_outage_days_reached")
        elif event_id == "medical_beds_emergency":
            reasons.append("medical_capacity_gap_reached")
        elif event_id == "severe_case_backlog":
            if state.population.critical_population >= thresholds["severe_patients"]:
                reasons.append("critical_patient_count_reached")
            if state.events.metrics.get("persistent_severe_days", 0) >= thresholds["persistent_severe_days"]:
                reasons.append("persistent_severe_days_reached")
        elif event_id == "first_body":
            reasons.append("first_death_recorded")
        elif event_id == "bodies_under_snow":
            reasons.append("unhandled_body_count_reached")
        elif event_id == "children_request":
            reasons.append("unprotected_child_count_reached")
        elif event_id == "red_frozen_hands":
            if state.events.metrics.get("child_labor_risk_points", 0) >= thresholds["child_labor_risk_points"]:
                reasons.append("child_labor_risk_points_reached")
            if state.events.metrics.get("child_harm_from_work_today", 0) >= thresholds["child_harm_from_work"]:
                reasons.append("child_work_harm_recorded")
        elif event_id == "long_shift_collapse":
            if state.social_policy.consecutive_long_shift_days >= thresholds["long_shift_days"]:
                reasons.append("consecutive_long_shift_days_reached")
            if state.events.metrics.get("long_shift_risk_points", 0) >= thresholds["long_shift_risk_points"]:
                reasons.append("long_shift_harm_points_reached")
        elif event_id == "overtime_empty_post":
            recent = [
                day
                for day in state.events.recent_overtime_days
                if day >= state.calendar.current_day - thresholds["overtime_window_days"]
            ]
            if len(recent) >= thresholds["overtime_uses"]:
                reasons.append("recent_overtime_uses_reached")
            if state.events.metrics.get("overtime_harm_today", 0) >= 1:
                reasons.append("overtime_harm_recorded")
        elif event_id == "coal_bottom":
            reasons.append("coal_reserve_below_threshold")
        elif event_id == "furnace_redline":
            reasons.append("furnace_pressure_reached")
        elif event_id == "cold_house_night":
            reasons.extend(("homeless_count_reached", "cold_exposure_reached"))
        elif event_id == "trust_crack":
            reasons.append("trust_below_threshold")
        elif event_id == "city_unrest":
            reasons.append("panic_above_threshold")
        if not reasons:
            raise SaveDataError("event activation has no matching trigger reason")
        return tuple(reasons)

    def _option_unavailable_reason(
        self, state: GameState, event_id: str, option_id: str
    ) -> str:
        """Return a stable machine reason without recommending an option."""

        canonical = (
            tuple(self.rules.fixed_arrivals[event_id].options)
            if event_id in self.rules.fixed_arrivals
            else _EVENT_OPTIONS.get(event_id, ())
        )
        if option_id not in canonical:
            return "unknown_option"
        promise_type = self._promise_type_for_option(event_id, option_id)
        if promise_type is not None:
            if state.calendar.current_day >= self.rules.promise.disabled_from_day:
                return "promises_disabled_from_day_49"
            if len(state.promises.active_promises) >= self.rules.promise.max_active:
                return "active_promise_limit_reached"
            if any(
                item.promise_type == promise_type
                for item in state.promises.active_promises.values()
            ):
                return "same_promise_type_already_active"
        if option_id == "prioritize_children":
            if state.population.children == 0:
                return "no_children"
            if state.resources.cooked_food == 0:
                return "insufficient_cooked_food"
        if option_id == "temporary_beds" and not (
            "basic_medical_law" in state.laws.signed_law_ids
            or any(
                item.building_type in {"medical_station", "hospital"}
                and item.is_operational
                for item in state.buildings.values()
            )
        ):
            return "medical_prerequisite_missing"
        if option_id == "medical_ration_prompt":
            if "medical_ration_law" not in state.laws.signed_law_ids:
                return "medical_ration_law_not_signed"
            if state.resources.cooked_food < 3:
                return "insufficient_cooked_food"
            if state.calendar.current_day < state.laws.cooldowns.get(
                "medical_ration", 1
            ):
                return "medical_ration_on_cooldown"
        if option_id == "memorial_prompt":
            if "memorial_law" not in state.laws.signed_law_ids:
                return "memorial_law_not_signed"
            if not any(
                item.building_type == "cemetery" and item.is_built
                for item in state.buildings.values()
            ):
                return "cemetery_not_built"
            if state.calendar.current_day < state.laws.cooldowns.get(
                "memorial", 1
            ):
                return "memorial_on_cooldown"
        if option_id == "overload_off_prompt" and state.furnace.overload_level == 0:
            return "overload_already_off"
        food_cost = self._event_food_cost(state, event_id, option_id)
        if food_cost is not None and state.resources.cooked_food < food_cost:
            return "insufficient_cooked_food"
        return "option_not_offered_when_event_activated"

    def _can_create_promise(self, state: GameState, promise_type: str) -> bool:
        return (
            state.calendar.current_day < self.rules.promise.disabled_from_day
            and len(state.promises.active_promises) < self.rules.promise.max_active
            and all(item.promise_type != promise_type for item in state.promises.active_promises.values())
        )

    def _eligible(self, state: GameState, event_id: str) -> bool:
        rule = self.rules.events[event_id]
        count = state.events.occurrence_counts.get(event_id, 0)
        if rule.max_per_game and count >= rule.max_per_game:
            return False
        if (
            event_id == "furnace_redline"
            and state.furnace.pressure
            >= self.rules.thresholds["furnace_pressure_forced"]
            and not state.events.metrics.get("furnace_forced_redline_shown", 0)
        ):
            return True
        return state.calendar.current_day >= state.events.cooldown_until_day.get(event_id, 0)

    def _priority_key(self, event_id: str) -> tuple[int, str]:
        if event_id in self.rules.fixed_arrivals:
            return 1, event_id
        return self.rules.events[event_id].priority, event_id

    def _promise_type_for_option(self, event_id: str, option_id: str) -> str | None:
        if not option_id.startswith("promise_"):
            return None
        promise_type = option_id.removeprefix("promise_")
        rule = self.rules.events[event_id]
        if rule.promise_type != promise_type:
            raise SaveDataError("event promise option disagrees with its configured type")
        return promise_type

    def _apply_event_effect(self, state: GameState, event_id: str, option_id: str) -> None:
        effects: dict[tuple[str, str], tuple[int, int]] = {
            ("empty_pot", "maintain_ration"): (-1, 1),
            ("empty_pot", "adjust_ration_prompt"): (-2, 1),
            ("raw_food_dispute", "continue_raw_food"): (-1, 2),
            ("raw_food_dispute", "prioritize_children"): (1, -1),
            ("medical_beds_emergency", "temporary_beds"): (1, -1),
            ("medical_beds_emergency", "maintain"): (-2, 2),
            ("severe_case_backlog", "accept_current"): (-3, 3),
            ("first_body", "public_memorial"): (1, -1),
            ("first_body", "quiet_handling"): (0, 1),
            ("first_body", "postpone"): (-2, 2),
            ("bodies_under_snow", "continue_postponing"): (-3, 3),
            ("children_request", "maintain"): (-1, 1),
            ("children_request", "fireside_tasks"): (0, -1),
            ("red_frozen_hands", "suspend_high_risk"): (2, -1),
            ("red_frozen_hands", "cold_care"): (1, -1),
            ("red_frozen_hands", "continue"): (-3, 3),
            ("long_shift_collapse", "suspend_long_shift"): (1, -1),
            ("long_shift_collapse", "food_compensation"): (1, -1),
            ("long_shift_collapse", "continue"): (-2, 2),
            ("overtime_empty_post", "food_compensation"): (1, -1),
            ("overtime_empty_post", "continue"): (-3, 3),
            ("coal_bottom", "adjust_furnace_prompt"): (0, -1),
            ("coal_bottom", "maintain"): (-2, 3),
            ("furnace_redline", "overload_off_prompt"): (0, -1),
            ("furnace_redline", "maintain_overload"): (-4, 5),
            ("cold_house_night", "maintain"): (-3, 3),
            ("trust_crack", "public_explanation"): (1, 1),
            ("trust_crack", "avoid_questions"): (-3, 2),
            ("city_unrest", "calm_and_explain"): (0, -2),
            ("city_unrest", "suppress_unrest"): (-2, -1),
        }
        trust, panic = effects.get((event_id, option_id), (0, 0))
        self._change_morale(state, trust, panic)
        if (event_id, option_id) == ("raw_food_dispute", "prioritize_children"):
            state.resources.cooked_food -= min(state.population.children, state.resources.cooked_food)
            state.events.metrics["child_food_priority_until_day"] = state.calendar.current_day
        elif (event_id, option_id) == ("medical_beds_emergency", "temporary_beds"):
            state.events.metrics["temporary_medical_risk_reduction_until_day"] = state.calendar.current_day
            state.events.metrics["temporary_medical_risk_numerator"] = 80
            state.events.metrics["temporary_medical_risk_denominator"] = 100
        elif (event_id, option_id) == ("red_frozen_hands", "suspend_high_risk"):
            state.events.metrics["child_high_risk_work_suspended_until_day"] = state.calendar.current_day + 1
        elif (event_id, option_id) == ("red_frozen_hands", "cold_care"):
            cost = self._event_food_cost(state, event_id, option_id)
            assert cost is not None
            state.resources.cooked_food -= cost
            state.events.metrics["child_cold_risk_reduction_until_day"] = state.calendar.current_day
            state.events.metrics["child_cold_risk_numerator"] = 50
            state.events.metrics["child_cold_risk_denominator"] = 100
        elif (event_id, option_id) == ("long_shift_collapse", "suspend_long_shift"):
            state.events.metrics["long_shift_suspended_until_day"] = state.calendar.current_day + 1
        elif option_id == "food_compensation":
            cost = self._event_food_cost(state, event_id, option_id)
            assert cost is not None
            state.resources.cooked_food -= cost

    def _apply_arrival(self, state: GameState, event_id: str, option_id: str) -> None:
        effect = self.rules.fixed_arrivals[event_id].options[option_id]
        population = state.population
        healthy = effect.total - effect.sick - effect.critical - effect.disabled
        population.population_total += effect.total
        population.population_alive += effect.total
        population.workers += effect.workers
        population.engineers += effect.engineers
        population.children += effect.children
        population.healthy_population += healthy
        population.sick_population += effect.sick
        population.critical_population += effect.critical
        population.disabled_population += effect.disabled
        population.housed_population = min(population.population_alive, state.housing.capacity)
        population.homeless_population = population.population_alive - population.housed_population
        state.medical.medical_pressure = max(
            population.sick_population
            + population.critical_population
            - state.medical.effective_capacity,
            0,
        )
        self._change_morale(state, effect.trust, effect.panic)
        state.events.fixed_arrival_choices[event_id] = option_id
        # Patch 007 exposes the day-37 delta but Patch 008 owns the faction count.
        if state.old_city.is_unlocked and effect.old_city:
            state.events.metrics["pending_old_city_arrival_delta"] = effect.old_city

    def arrival_risk_preview(self, state: GameState) -> dict[str, Any]:
        alive = state.population.population_alive
        food = state.resources.raw_food + state.resources.cooked_food
        return {
            "population_after_event": alive,
            "housing_capacity": state.housing.capacity,
            "homeless_after_event": state.population.homeless_population,
            "food_days_x10_after_event": (food * 10) // alive if alive else 0,
            "medical_capacity": state.medical.effective_capacity,
            "medical_gap_after_event": state.medical.medical_pressure,
            "sick_after_event": state.population.sick_population,
            "critical_after_event": state.population.critical_population,
            "disabled_after_event": state.population.disabled_population,
            "children_after_event": state.population.children,
            "trust_after_event": state.trust_panic.trust,
            "panic_after_event": state.trust_panic.panic,
            "old_city_delta_pending": state.events.metrics.get("pending_old_city_arrival_delta", 0),
        }

    def evaluate_risks(self, state: GameState) -> tuple[RiskWarning, ...]:
        warnings: list[RiskWarning] = []
        for event in state.events.active_events.values():
            if event.is_blocking:
                warnings.append(
                    RiskWarning(
                        f"events.major_pending.{event.event_id}",
                        RiskWarningLevel.C_HARD_BLOCK,
                        {"event_id": event.event_id, "trigger_day": event.trigger_day},
                    )
                )
        for status_id in state.events.status_ids:
            safe_id = status_id.replace("_", "-")
            warnings.append(
                RiskWarning(
                    f"events.status.{safe_id}",
                    RiskWarningLevel.A_INFO,
                    {"status_id": status_id},
                )
            )
        return tuple(warnings)

    def capture_daily_metrics(self, context: EndDayContext) -> None:
        state = context.state
        day = context.settled_day
        if state.daily_survival.raw_food_eaten > state.daily_survival.cooked_food_eaten:
            state.events.recent_raw_food_days.append(day)
        if not any(
            item.building_type == "canteen" and item.is_operational
            for item in state.buildings.values()
        ):
            state.events.recent_canteen_outage_days.append(day)
        if state.social_policy.overtime_building_id is not None:
            state.events.recent_overtime_days.append(day)
        critical = state.population.critical_population
        previous_critical = state.events.metrics.get("previous_critical_patients")
        if critical >= self.rules.thresholds["persistent_severe_patients"] and (
            previous_critical is None or critical >= previous_critical
        ):
            state.events.metrics["persistent_severe_days"] = (
                state.events.metrics.get("persistent_severe_days", 0) + 1
            )
        else:
            state.events.metrics["persistent_severe_days"] = 0
        state.events.metrics["previous_critical_patients"] = critical
        raw_window = self.rules.thresholds["raw_food_window_days"]
        canteen_window = self.rules.thresholds["canteen_outage_days"]
        state.events.recent_raw_food_days = [
            item
            for item in state.events.recent_raw_food_days
            if item >= day - raw_window + 1
        ]
        state.events.recent_canteen_outage_days = [
            item
            for item in state.events.recent_canteen_outage_days
            if item >= day - canteen_window + 1
        ]
        state.events.recent_overtime_days = [item for item in state.events.recent_overtime_days if item >= day - 4]
        if self._food_days_x10(state) < self.rules.thresholds["food_warning_days_x10"]:
            state.events.metrics["food_warning_streak"] = state.events.metrics.get("food_warning_streak", 0) + 1
        else:
            state.events.metrics["food_warning_streak"] = 0
        if (
            state.population.homeless_population
            >= self.rules.thresholds["homeless_event"]
            and state.events.metrics.get("cold_exposure_level", 0)
            >= self.rules.thresholds["cold_exposure_event_level"]
        ):
            state.events.metrics["cold_exposure_warning_streak"] = (
                state.events.metrics.get("cold_exposure_warning_streak", 0) + 1
            )
        else:
            state.events.metrics["cold_exposure_warning_streak"] = 0

    def check_hidden_achievements(self, context: EndDayContext) -> None:
        state = context.state
        cold_deaths = state.events.deaths_today_by_cause.get("cold_exposure", 0) + state.events.deaths_today_by_cause.get("freezing", 0)
        if (
            "cold_death_solution" not in state.events.hidden_achievements_unlocked
            and state.daily_survival.effective_furnace_level == 0
            and cold_deaths > 0
            and state.events.cold_exposure_deaths_total == 0
        ):
            state.events.hidden_achievements_unlocked.append("cold_death_solution")
            state.events.hidden_achievement_popup_queue.append("cold_death_solution")
            context.emit(
                "events.achievement.unlocked",
                {"achievement_id": "cold_death_solution", "trigger_day": context.settled_day},
            )
        state.events.cold_exposure_deaths_total += cold_deaths
        state.events.deaths_today_by_cause.clear()

    def validate_state(self, state: GameState) -> None:
        validate_game_state(
            state,
            self.building_rules,
            self.survival_rules,
            self.technology_rules,
        )
        known = set(self.rules.events) | set(self.rules.fixed_arrivals)
        if set(state.events.active_events) - known:
            raise SaveDataError("state contains an unknown active event")
        if set(state.events.resolved_event_ids) - known:
            raise SaveDataError("state contains an unknown resolved event")
        if set(state.events.suppressed_event_ids_today) - known:
            raise SaveDataError("state contains an unknown suppressed event")
        if set(state.events.occurrence_counts) - known:
            raise SaveDataError("state contains an unknown event occurrence counter")
        if set(state.events.cooldown_until_day) - set(self.rules.events):
            raise SaveDataError("state contains an unknown event cooldown")
        for event_id, event in state.events.active_events.items():
            canonical_options = (
                tuple(self.rules.fixed_arrivals[event_id].options)
                if event_id in self.rules.fixed_arrivals
                else _EVENT_OPTIONS[event_id]
            )
            if not set(event.option_ids).issubset(canonical_options):
                raise SaveDataError("active event contains an unknown option")
            if not event.trigger_reason_ids or len(event.trigger_reason_ids) != len(
                set(event.trigger_reason_ids)
            ):
                raise SaveDataError("active event trigger reasons must be non-empty and unique")
            expected_priority = 1 if event_id in self.rules.fixed_arrivals else self.rules.events[event_id].priority
            if event.priority != expected_priority:
                raise SaveDataError("active event priority does not match event rules")
            if event_id in self.rules.fixed_arrivals:
                if (
                    event.event_type != "major"
                    or event.trigger_day != self.rules.fixed_arrivals[event_id].day
                ):
                    raise SaveDataError("fixed arrival event has an invalid day or type")
            if event_id in _FIXED_WARNING_EVENTS.values() and event.event_type != "major":
                raise SaveDataError("fixed frost warning events must be major")
        for event_id, count in state.events.occurrence_counts.items():
            if event_id in self.rules.fixed_arrivals:
                maximum = 1
            else:
                maximum = self.rules.events[event_id].max_per_game
            if maximum and count > maximum:
                raise SaveDataError("event occurrence count exceeds its configured maximum")
        for resolution in state.events.resolution_history:
            if resolution.event_id not in known:
                raise SaveDataError("event history contains an unknown event")
            canonical_options = (
                tuple(self.rules.fixed_arrivals[resolution.event_id].options)
                if resolution.event_id in self.rules.fixed_arrivals
                else _EVENT_OPTIONS[resolution.event_id]
            )
            if resolution.option_id not in canonical_options:
                raise SaveDataError("event history contains an unknown option")
        for event_id, choice in state.events.fixed_arrival_choices.items():
            if choice not in self.rules.fixed_arrivals[event_id].options:
                raise SaveDataError("fixed arrival choice does not match event rules")
            if self.rules.fixed_arrivals[event_id].day > state.calendar.current_day:
                raise SaveDataError("fixed arrival choice cannot come from a future day")
        self._validate_fixed_arrival_history(state)
        expected_frost_stage = "none"
        for day, stage in sorted(_FROST_STAGE_BY_DAY.items()):
            if state.calendar.current_day >= day:
                expected_frost_stage = stage
        if (
            state.events.generated_for_day is not None
            and state.events.frostfall_warning_stage != expected_frost_stage
        ):
            raise SaveDataError("frostfall warning stage does not match the calendar")
        if (
            state.events.generated_for_day is not None
            and state.calendar.current_day >= state.old_city.trigger_day
            and not state.old_city.is_unlocked
            and not state.old_city.activation_pending
        ):
            raise SaveDataError("old city activation interface is missing after day 24")
        known_promise_types = set(self.rules.promise.deadlines)
        for promise in state.promises.active_promises.values():
            if promise.promise_type not in known_promise_types:
                raise SaveDataError("state contains an unknown promise type")
            if promise.source_event_id not in self.rules.events:
                raise SaveDataError("promise source event is unknown")
            if promise.severity not in self.rules.promise.effects:
                raise SaveDataError("promise severity is unknown")
            if set(promise.target) != {"trust_at_creation", "panic_at_creation"}:
                raise SaveDataError("promise target snapshot is incomplete")
            expected_deadline = promise.created_day + self.rules.promise.deadlines[promise.promise_type]
            if promise.created_day >= self.rules.promise.deadline_cap_start_day:
                expected_deadline = min(expected_deadline, self.rules.promise.deadline_cap_day)
            if promise.deadline_day != expected_deadline:
                raise SaveDataError("promise deadline does not match event rules")
        for settlement in state.promises.settlement_history:
            if settlement.promise_type not in known_promise_types:
                raise SaveDataError("promise history contains an unknown type")
            effect = self.rules.promise.effects.get(settlement.severity)
            if effect is None:
                raise SaveDataError("promise history contains an unknown severity")
            expected_effect = (
                (effect.success_trust, effect.success_panic)
                if settlement.outcome == "success"
                else (effect.failure_trust, effect.failure_panic)
            )
            if (settlement.trust_change, settlement.panic_change) != expected_effect:
                raise SaveDataError("promise history effect does not match event rules")

    def _status_ids(self, state: GameState) -> list[str]:
        statuses: list[str] = []
        t = self.rules.thresholds
        if self._food_days_x10(state) < t["food_warning_days_x10"]:
            statuses.append("event.food_warning")
        if state.medical.medical_pressure >= t["medical_gap_warning"]:
            statuses.append("event.medical_warning")
        if state.population.homeless_population >= t["homeless_warning"]:
            statuses.append("event.housing_warning")
        if self._coal_days_x10(state) < t["coal_warning_days_x10"]:
            statuses.append("event.coal_warning")
        if state.furnace.pressure >= t["furnace_pressure_warning"]:
            statuses.append("event.furnace_pressure_warning")
        if state.trust_panic.trust is not None and state.trust_panic.trust <= t["trust_warning"]:
            statuses.append("event.trust_warning")
        if state.trust_panic.panic is not None and state.trust_panic.panic >= t["panic_warning"]:
            statuses.append("event.panic_warning")
        if state.calendar.current_day >= 34:
            statuses.append("frost.warning.preparation")
        if state.old_city.activation_pending:
            statuses.append("old_city.activation_pending")
        return statuses

    def _food_days_x10(self, state: GameState) -> int:
        alive = state.population.population_alive
        if alive == 0:
            return 0
        return ((state.resources.raw_food + state.resources.cooked_food) * 10) // alive

    def _coal_days_x10(self, state: GameState) -> int:
        cost = self.survival_rules.furnace_levels[self._current_furnace_level(state)].coal_cost
        return (state.resources.coal * 10) // cost if cost else 10_000

    def _recent_raw_food_days(self, state: GameState) -> list[int]:
        first_day = (
            state.calendar.current_day
            - self.rules.thresholds["raw_food_window_days"]
        )
        last_day = state.calendar.current_day - 1
        return [
            day
            for day in state.events.recent_raw_food_days
            if first_day <= day <= last_day
        ]

    def _has_recent_consecutive_canteen_outage(self, state: GameState) -> bool:
        required = self.rules.thresholds["canteen_outage_days"]
        last_day = state.calendar.current_day - 1
        first_day = last_day - required + 1
        return all(
            day in state.events.recent_canteen_outage_days
            for day in range(first_day, last_day + 1)
        )

    @staticmethod
    def _event_food_cost(
        state: GameState, event_id: str, option_id: str
    ) -> int | None:
        if (event_id, option_id) == ("red_frozen_hands", "cold_care"):
            return min(state.population.children, 20)
        if option_id == "food_compensation":
            workers = state.population.workers + state.population.engineers
            return min(workers, 60 if event_id == "overtime_empty_post" else 40)
        return None

    def _validate_fixed_arrival_history(self, state: GameState) -> None:
        for event_id, rule in self.rules.fixed_arrivals.items():
            choice = state.events.fixed_arrival_choices.get(event_id)
            histories = [
                item
                for item in state.events.resolution_history
                if item.event_id == event_id
            ]
            resolved = event_id in state.events.resolved_event_ids
            active = event_id in state.events.active_events
            count = state.events.occurrence_counts.get(event_id, 0)
            if active:
                if (
                    state.calendar.current_day != rule.day
                    or choice is not None
                    or resolved
                    or histories
                    or count != 1
                ):
                    raise SaveDataError("active fixed arrival state is inconsistent")
                continue
            if choice is not None:
                if (
                    not resolved
                    or count != 1
                    or len(histories) != 1
                    or histories[0].option_id != choice
                    or histories[0].event_type != "major"
                    or histories[0].resolved_day != rule.day
                ):
                    raise SaveDataError(
                        "fixed arrival choice, history, and resolution disagree"
                    )
                continue
            if resolved or histories or count or state.calendar.current_day > rule.day:
                raise SaveDataError("a past fixed arrival cannot be skipped")
            if (
                state.calendar.current_day == rule.day
                and state.events.generated_for_day == rule.day
                and not active
            ):
                raise SaveDataError("today's fixed arrival must remain active or resolved")

    @staticmethod
    def _current_furnace_level(state: GameState) -> int:
        if not state.furnace.is_active:
            return 0
        try:
            return int(state.furnace.mode_id.rsplit("_", 1)[1])
        except (IndexError, ValueError):
            return 1

    @staticmethod
    def _unprotected_children(state: GameState) -> int:
        if any(
            item.building_type in {"child_shelter", "school"}
            and item.is_operational
            for item in state.buildings.values()
        ):
            return 0
        apprentices = (
            state.population.medical_apprentices
            + state.population.engineering_apprentices
        )
        return max(state.population.children - apprentices, 0)

    @staticmethod
    def _change_morale(state: GameState, trust: int, panic: int) -> None:
        if state.trust_panic.trust is not None:
            state.trust_panic.trust = min(max(state.trust_panic.trust + trust, 0), 100)
        if state.trust_panic.panic is not None:
            state.trust_panic.panic = min(max(state.trust_panic.panic + panic, 0), 100)

    @staticmethod
    def _delta(before: int | None, after: int | None) -> int | None:
        return None if before is None or after is None else after - before

    @staticmethod
    def _add_unique(items: list[str], value: str) -> None:
        if value not in items:
            items.append(value)

    @staticmethod
    def _event_text_ids(event_id: str) -> tuple[str, str]:
        if event_id.startswith("arrival_day"):
            day = event_id.removeprefix("arrival_day")
            return f"arrival.day{day}.title", f"arrival.day{day}.body"
        if event_id == "furnace_redline":
            return "event.furnace_redline.title", "event.furnace_redline.warning"
        return f"event.{event_id}.title", f"event.{event_id}.body"

    @staticmethod
    def _option_text_id(
        event_id: str, option_id: str, canonical: tuple[str, ...]
    ) -> str:
        if event_id.startswith("arrival_day"):
            return f"arrival.option.{option_id}"
        letter = "abc"[canonical.index(option_id)]
        return f"event.{event_id}.option_{letter}"

    def _event_status_snapshot(self, state: GameState) -> dict[str, int | None]:
        return {
            "current_day": state.calendar.current_day,
            "food_days_x10": self._food_days_x10(state),
            "coal_days_x10": self._coal_days_x10(state),
            "medical_gap": state.medical.medical_pressure,
            "unhandled_bodies": state.social_policy.unhandled_bodies,
            "unprotected_children": self._unprotected_children(state),
            "homeless_population": state.population.homeless_population,
            "cold_exposure_level": state.events.metrics.get(
                "cold_exposure_level", 0
            ),
            "furnace_pressure": state.furnace.pressure,
            "trust": state.trust_panic.trust,
            "panic": state.trust_panic.panic,
        }

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
        return CommandResult(
            command_id=command_id,
            accepted=False,
            code=validation.code,
            state_sequence=sequence,
            feedback=(FeedbackItem(FeedbackLevel.ERROR, data=validation.details),),
            data=validation.details,
        )

    @staticmethod
    def _error(
        command_id: str, sequence: int, stage: str, exc: Exception
    ) -> CommandResult:
        details = {"failed_stage": stage, "exception_type": type(exc).__name__}
        return CommandResult(
            command_id=command_id,
            accepted=False,
            code=ErrorCode.INTERNAL_ERROR,
            state_sequence=sequence,
            feedback=(FeedbackItem(FeedbackLevel.ERROR, data=details),),
            data=details,
        )
