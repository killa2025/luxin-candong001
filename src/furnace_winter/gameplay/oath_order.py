from __future__ import annotations

from copy import deepcopy
from dataclasses import fields
from math import ceil, floor
from typing import Any

from furnace_winter.config import (
    BuildingRules,
    OathOrderRules,
    SurvivalRules,
    TechnologyRules,
)
from furnace_winter.gameplay.end_day import (
    EndDayContext,
    EndDayEngine,
    EndDayStage,
    RiskWarning,
    RiskWarningLevel,
)
from furnace_winter.gameplay.hunger import (
    remove_non_hunger_deaths_or_departures,
)
from furnace_winter.gameplay.survival import medical_building_capacity
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
    GameState,
    HardFailType,
    RouteFacilityState,
    SaveDataError,
    validate_game_state,
)


RESOLVE_OLD_CITY_COMMAND = "game.resolve_old_city_event"
SIGN_OATH_ORDER_LAW_COMMAND = "game.sign_oath_order_law"
STAFF_OATH_ORDER_FACILITY_COMMAND = "game.staff_oath_order_facility"
USE_OATH_ORDER_ACTION_COMMAND = "game.use_oath_order_action"

_ROUTE_ENTRY_LAWS = {"oath": "guard_oath", "iron": "city_patrol_order"}
_ROUTE_FACILITIES = {"oath": "oath_hall", "iron": "patrol_office"}
_TERMINAL_LAWS = {"final_oath", "highest_order"}
_CRITICAL_BUILDING_TYPES = frozenset(
    {
        "medical_station",
        "hospital",
        "canteen",
        "hunting_lodge",
        "greenhouse",
        "improved_greenhouse",
        "small_coal_miner",
    }
)
_NON_SURVIVAL_BUILDING_TYPES = frozenset(
    {
        "research_institute",
        "school",
        "child_shelter",
        "small_tavern",
        "grand_casino",
    }
)
_SECONDARY_BUILDING_TYPES = frozenset({"logging_camp", "small_steel_miner"})
_ASSIGNMENT_ATTRIBUTES = (
    "assigned_workers",
    "assigned_children",
    "assigned_medical_apprentices",
    "assigned_engineering_apprentices",
    "assigned_engineers",
)
_OLD_CITY_OPTIONS = {
    "southern_letter": ("publish", "suppress"),
    "rumors": ("public_explain", "ignore"),
    "public_gathering": ("public_explain", "strengthen_patrol", "ignore"),
    "countdown": ("promise_reduce_old_city", "do_not_stop", "ask_for_time"),
}


def build_oath_order_catalog(rules: OathOrderRules) -> CommandCatalog:
    catalog = CommandCatalog()
    catalog.register(
        CommandSpec(
            name=RESOLVE_OLD_CITY_COMMAND,
            required_arguments={
                "event_id": ArgumentKind.STRING,
                "option_id": ArgumentKind.STRING,
            },
            argument_options={
                "event_id": tuple(sorted(_OLD_CITY_OPTIONS)),
                "option_id": tuple(
                    sorted({item for values in _OLD_CITY_OPTIONS.values() for item in values})
                ),
            },
        )
    )
    catalog.register(
        CommandSpec(
            name=SIGN_OATH_ORDER_LAW_COMMAND,
            required_arguments={"law_id": ArgumentKind.STRING},
            optional_arguments={"confirm": ArgumentKind.BOOLEAN},
            argument_options={"law_id": tuple(sorted(rules.laws))},
        )
    )
    catalog.register(
        CommandSpec(
            name=STAFF_OATH_ORDER_FACILITY_COMMAND,
            required_arguments={
                "facility_id": ArgumentKind.STRING,
                "workers": ArgumentKind.INTEGER,
                "engineers": ArgumentKind.INTEGER,
            },
            argument_options={"facility_id": ("oath_hall", "patrol_office")},
            argument_semantics={
                "workers": "absolute_target_count",
                "engineers": "absolute_target_count",
            },
        )
    )
    catalog.register(
        CommandSpec(
            name=USE_OATH_ORDER_ACTION_COMMAND,
            required_arguments={"action_id": ArgumentKind.STRING},
            argument_options={"action_id": tuple(sorted(rules.actions))},
        )
    )
    return catalog


class OathOrderSystem:
    """Patch 008 old-city, 006C route, facility, action, and fail-axis rules."""

    def __init__(
        self,
        rules: OathOrderRules,
        building_rules: BuildingRules,
        survival_rules: SurvivalRules,
        technology_rules: TechnologyRules | None = None,
    ) -> None:
        self.rules = rules
        self.building_rules = building_rules
        self.survival_rules = survival_rules
        self.technology_rules = technology_rules
        self._catalog = build_oath_order_catalog(rules)
        self._validator = CommandValidator(self._catalog)

    def command_specs(self) -> tuple[CommandSpec, ...]:
        return self._catalog.specs()

    def execute(self, state: GameState, request: CommandRequest) -> CommandResult:
        command_id = (
            request.command_id
            if isinstance(request, CommandRequest) and isinstance(request.command_id, str)
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
            self._refresh_unlock(working)
            handlers = {
                RESOLVE_OLD_CITY_COMMAND: self._resolve_old_city,
                SIGN_OATH_ORDER_LAW_COMMAND: self._sign_law,
                STAFF_OATH_ORDER_FACILITY_COMMAND: self._staff_facility,
                USE_OATH_ORDER_ACTION_COMMAND: self._use_action,
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

    def _legality(self, state: GameState, request: CommandRequest) -> CommandValidation:
        if (
            state.calendar.is_day_locked
            or state.final_result.is_finalized
            or state.final_result.hard_fail_type is not None
        ):
            return self._illegal("day_not_open_for_planning")
        if request.name == RESOLVE_OLD_CITY_COMMAND:
            return self._old_city_legality(state, request)
        if request.name == SIGN_OATH_ORDER_LAW_COMMAND:
            return self._sign_legality(state, request)
        if request.name == STAFF_OATH_ORDER_FACILITY_COMMAND:
            return self._staff_legality(state, request)
        return self._action_legality(state, request)

    def _old_city_legality(
        self, state: GameState, request: CommandRequest
    ) -> CommandValidation:
        event_id = str(request.arguments["event_id"])
        option_id = str(request.arguments["option_id"])
        if state.old_city.pending_event_id != event_id:
            return self._illegal(
                "old_city_event_not_pending",
                pending_event_id=state.old_city.pending_event_id,
                available_option_ids=list(
                    self._available_old_city_options(state)
                ),
            )
        if option_id not in _OLD_CITY_OPTIONS[event_id]:
            return self._illegal(
                "old_city_option_unavailable",
                event_id=event_id,
                option_id=option_id,
                available_option_ids=list(
                    self._available_old_city_options(state, event_id)
                ),
            )
        unavailable_reason = self._old_city_option_unavailable_reason(
            state, event_id, option_id
        )
        if unavailable_reason is not None:
            return self._illegal(
                unavailable_reason,
                event_id=event_id,
                option_id=option_id,
                available_option_ids=list(
                    self._available_old_city_options(state, event_id)
                ),
            )
        return CommandValidation.valid()

    def _sign_legality(
        self, state: GameState, request: CommandRequest
    ) -> CommandValidation:
        law_id = str(request.arguments["law_id"])
        rule = self.rules.laws[law_id]
        signed = set(state.oath_order.signed_law_ids)
        if not self._is_page_available(state):
            return self._illegal("oath_order_page_locked")
        if law_id in signed:
            return self._illegal("law_already_signed")
        if state.calendar.current_day < state.oath_order.next_law_day:
            return self._illegal(
                "law_cooldown_active",
                next_available_day=state.oath_order.next_law_day,
            )
        if state.oath_order.selected_route not in {None, rule.route}:
            return self._illegal("law_route_locked")
        entry_law = _ROUTE_ENTRY_LAWS[rule.route]
        if state.oath_order.selected_route is None and law_id != entry_law:
            return self._illegal("route_entry_law_required", required_law_id=entry_law)
        if law_id == entry_law and request.arguments.get("confirm") is not True:
            return self._illegal("confirmation_required")
        missing = sorted(set(rule.requires) - signed)
        if missing:
            return self._illegal("law_prerequisite_missing", missing_law_ids=missing)
        if law_id in _TERMINAL_LAWS and not self._facility(state, rule.route).is_running:
            return self._illegal("route_facility_not_running")
        return CommandValidation.valid()

    def _staff_legality(
        self, state: GameState, request: CommandRequest
    ) -> CommandValidation:
        facility_id = str(request.arguments["facility_id"])
        workers = request.arguments["workers"]
        engineers = request.arguments["engineers"]
        assert isinstance(workers, int) and isinstance(engineers, int)
        if workers < 0 or engineers < 0:
            return self._illegal("staff_count_negative")
        expected = (
            _ROUTE_FACILITIES.get(state.oath_order.selected_route or "")
        )
        if facility_id != expected:
            return self._illegal("route_facility_unavailable")
        current = self._facility_by_id(state, facility_id)
        assigned_workers, assigned_engineers = self._assigned_adults(
            state, exclude=current
        )
        if assigned_workers + workers > state.population.workers:
            return self._illegal("insufficient_workers")
        if assigned_engineers + engineers > state.population.engineers:
            return self._illegal("insufficient_engineers")
        return CommandValidation.valid()

    def _action_legality(
        self, state: GameState, request: CommandRequest
    ) -> CommandValidation:
        action_id = str(request.arguments["action_id"])
        rule = self.rules.actions[action_id]
        if state.oath_order.selected_route != rule.route:
            return self._illegal("action_route_unavailable")
        if rule.required_law not in state.oath_order.signed_law_ids:
            return self._illegal(
                "law_prerequisite_missing", missing_law_ids=[rule.required_law]
            )
        if not self._facility(state, rule.route).is_running:
            return self._illegal("route_facility_not_running")
        next_day = state.oath_order.action_next_available_day.get(action_id, 1)
        if state.calendar.current_day < next_day:
            return self._illegal("action_cooldown_active", next_available_day=next_day)
        if action_id == "mourning_bell" and (
            state.population.population_dead <= 0
            and not state.events.deaths_today_by_cause
        ):
            return self._illegal("no_death_to_mourn")
        if rule.old_city < 0 and (
            not state.old_city.is_unlocked
            or state.old_city.resolved
            or state.old_city.member_count <= 0
        ):
            return self._illegal("old_city_not_active")
        if action_id == "shared_meal":
            cost = self._shared_meal_cost(state)
            if state.resources.cooked_food < cost:
                return self._illegal(
                    "insufficient_cooked_food", required=cost,
                    available=state.resources.cooked_food,
                )
        return CommandValidation.valid()

    def _resolve_old_city(
        self, state: GameState, request: CommandRequest
    ) -> dict[str, Any]:
        event_id = str(request.arguments["event_id"])
        option_id = str(request.arguments["option_id"])
        old = state.old_city
        trust = panic = count = 0
        if event_id == "southern_letter":
            base = max(
                self.rules.old_city.initial_minimum,
                ceil(old.reference_population * self.rules.old_city.initial_percent / 100),
            )
            if option_id == "publish":
                count, trust, panic = base + 2, 1, 2
            else:
                count, trust, panic = base, -2, 1
                old.hidden_growth_days_remaining = 3
        elif event_id == "rumors":
            if option_id == "public_explain":
                count, trust, panic = -3, 1, 1
            else:
                count, panic = 3, 1
        elif event_id == "public_gathering":
            if option_id == "public_explain":
                count, trust, panic = -4, 1, 1
            elif option_id == "strengthen_patrol":
                count, trust, panic = -4, -1, -1
            else:
                count, trust, panic = 5, -1, 2
        elif option_id == "promise_reduce_old_city":
            old.promise_active = True
            old.promise_created_day = state.calendar.current_day
            assert old.countdown_day is not None
            old.promise_deadline_day = old.countdown_day
            old.promise_target_count = (
                old.middle_threshold - 1
                if old.member_count >= old.middle_threshold
                else max(0, old.member_count - 8)
            )
        elif option_id == "ask_for_time":
            assert old.countdown_day is not None
            old.countdown_day = min(
                old.countdown_day + 2, self.rules.old_city.countdown_cap_day
            )
            panic = 2
        else:
            count, trust, panic = 3, -1, 2

        old.member_count = min(
            max(old.member_count + count, 0), state.population.population_alive
        )
        self._change_emotion(state, trust=trust, panic=panic)
        old.pending_event_id = None
        if event_id == "southern_letter":
            old.active_stage_id = "southern_letter"
        if event_id == "countdown" and option_id == "do_not_stop":
            settlement = self._settle_old_city(state)
        else:
            settlement = None
        return {
            "event_id": event_id,
            "option_id": option_id,
            "member_count": old.member_count,
            "trust_change": trust,
            "panic_change": panic,
            "countdown_day_after": old.countdown_day,
            "promise_active_after": old.promise_active,
            "promise_target_count": old.promise_target_count,
            "promise_deadline_day": old.promise_deadline_day,
            "settlement": settlement,
        }

    def _sign_law(
        self, state: GameState, request: CommandRequest
    ) -> dict[str, Any]:
        law_id = str(request.arguments["law_id"])
        rule = self.rules.laws[law_id]
        state.oath_order.page_unlocked = True
        if state.oath_order.selected_route is None:
            state.oath_order.selected_route = rule.route
            facility = self._facility(state, rule.route)
            facility.enabled = True
            facility.visible = True
        state.oath_order.signed_law_ids.append(law_id)
        state.oath_order.law_signed_days[law_id] = state.calendar.current_day
        state.oath_order.next_law_day = (
            state.calendar.current_day + self.rules.unlock.law_cooldown_days
        )
        if law_id == "final_oath":
            state.oath_order.final_oath_active = True
        elif law_id == "highest_order":
            state.oath_order.highest_order_active = True
        self._change_emotion(state, trust=rule.trust, panic=rule.panic)
        return {
            "law_id": law_id,
            "route": rule.route,
            "trust_change": rule.trust,
            "panic_change": rule.panic,
            "next_law_day": state.oath_order.next_law_day,
        }

    def _staff_facility(
        self, state: GameState, request: CommandRequest
    ) -> dict[str, Any]:
        facility_id = str(request.arguments["facility_id"])
        facility = self._facility_by_id(state, facility_id)
        facility.assigned_workers = int(request.arguments["workers"])
        facility.assigned_engineers = int(request.arguments["engineers"])
        facility.is_running = (
            facility.enabled
            and facility.assigned_workers + facility.assigned_engineers >= 1
        )
        return {
            "facility_id": facility_id,
            "slot_cost": 0,
            "assigned_workers": facility.assigned_workers,
            "assigned_engineers": facility.assigned_engineers,
            "is_running": facility.is_running,
        }

    def _use_action(
        self, state: GameState, request: CommandRequest
    ) -> dict[str, Any]:
        action_id = str(request.arguments["action_id"])
        rule = self.rules.actions[action_id]
        cooked_food_paid = 0
        if action_id == "shared_meal":
            cooked_food_paid = self._shared_meal_cost(state)
            state.resources.cooked_food -= cooked_food_paid
        if action_id == "mourning_bell":
            state.oath_order.death_panic_aftershock_halved_day = (
                state.calendar.current_day
            )
        if rule.old_city:
            state.old_city.member_count = min(
                max(state.old_city.member_count + rule.old_city, 0),
                state.population.population_alive,
            )
        self._change_emotion(state, trust=rule.trust, panic=rule.panic)
        state.oath_order.action_next_available_day[action_id] = (
            state.calendar.current_day + rule.cooldown_days
        )
        state.oath_order.action_last_used_day[action_id] = (
            state.calendar.current_day
        )
        return {
            "action_id": action_id,
            "trust_change": rule.trust,
            "panic_change": rule.panic,
            "old_city_change": rule.old_city,
            "cooked_food_paid": cooked_food_paid,
            "next_available_day": state.oath_order.action_next_available_day[action_id],
        }

    def install(self, engine: EndDayEngine) -> None:
        engine.register_state_validator(self.validate_state)
        engine.register_risk_evaluator(self.evaluate_risks)
        engine.register_stage_handler(
            EndDayStage.UPDATE_PROMISE_TARGETS, self.update_old_city
        )
        engine.register_stage_handler(EndDayStage.CHECK_HARD_FAILS, self.check_hard_fails)
        engine.register_new_day_context_handler(
            self.resolve_old_city_deadline_transition
        )
        engine.register_new_day_handler(self.prepare_new_day)

    def evaluate_risks(self, state: GameState) -> tuple[RiskWarning, ...]:
        if state.old_city.pending_event_id is None:
            return ()
        return (
            RiskWarning(
                f"old_city.{state.old_city.pending_event_id}",
                RiskWarningLevel.C_HARD_BLOCK,
                {"event_id": state.old_city.pending_event_id},
            ),
        )

    def prepare_new_day(self, state: GameState) -> None:
        self._refresh_unlock(state)
        if (
            state.calendar.current_day >= self.rules.old_city.trigger_day
            and not state.old_city.is_unlocked
        ):
            self._activate_old_city(state)

    def update_old_city(self, context: EndDayContext) -> None:
        state = context.state
        old = state.old_city
        if not old.is_unlocked or old.resolved or old.pending_event_id is not None:
            return

        pending_arrival = state.events.metrics.pop(
            "pending_old_city_arrival_delta", 0
        )
        trend = self.rules.old_city.daily_growth
        if old.hidden_growth_days_remaining:
            trend += 1
            old.hidden_growth_days_remaining -= 1
        trust = state.trust_panic.trust
        panic = state.trust_panic.panic
        if trust is not None:
            if trust < 40:
                trend += 1
            if trust < 25:
                trend += 1
        if panic is not None:
            if panic > 65:
                trend += 1
            if panic > 80:
                trend += 1
        alive = state.population.population_alive
        food_x10 = (
            (state.resources.raw_food + state.resources.cooked_food) * 10 // alive
            if alive else 0
        )
        if food_x10 < 15:
            trend += 1
        if state.population.homeless_population >= 20:
            trend += 1
        if state.medical.medical_pressure >= 5:
            trend += 1
        if state.social_policy.unhandled_bodies >= 6:
            trend += 1
        deaths_today = sum(state.events.deaths_today_by_cause.values())
        if deaths_today >= 3:
            trend += 1
            if context.settled_day not in old.recent_major_death_days:
                old.recent_major_death_days.append(context.settled_day)
        old.recent_major_death_days = [
            day
            for day in old.recent_major_death_days
            if context.settled_day - 2 <= day <= context.settled_day
        ]
        recent_failures = [
            item
            for item in state.promises.settlement_history
            if item.outcome == "failure"
            and context.settled_day - 2 <= item.settled_day <= context.settled_day
        ]
        failures_today = [
            item for item in recent_failures
            if item.settled_day == context.settled_day
        ]
        if failures_today:
            severity_delta = {"ordinary": 2, "serious": 4, "critical": 6}
            trend += max(severity_delta[item.severity] for item in failures_today)
        stable = (
            trust is not None and trust >= 60
            and panic is not None and panic <= 40
            and food_x10 >= 20
            and state.population.homeless_population == 0
            and state.medical.medical_pressure == 0
            and state.social_policy.unhandled_bodies == 0
        )
        if stable:
            recent_rejected_arrival = any(
                item.option_id == "reject"
                and context.settled_day - 2 <= item.resolved_day <= context.settled_day
                for item in state.events.resolution_history
                if item.event_id in {"arrival_day6", "arrival_day19", "arrival_day37"}
            )
            trend = (
                -2
                if (
                    not recent_failures
                    and not old.recent_major_death_days
                    and not recent_rejected_arrival
                )
                else -1
            )
        trend = min(max(trend, self.rules.old_city.daily_decline_cap), self.rules.old_city.daily_growth_cap)
        old.last_daily_trend = trend + pending_arrival
        old.member_count = min(max(old.member_count + trend + pending_arrival, 0), alive)

        self._advance_old_city_stage(state)
        if (
            context.settled_day >= self.rules.old_city.countdown_cap_day
            and old.countdown_day is None
            and not old.resolved
        ):
            self._settle_old_city(state)
        context.emit(
            "old_city.daily.updated",
            {
                "member_count": old.member_count,
                "trend": old.last_daily_trend,
                "stage_id": old.active_stage_id,
            },
        )

    def resolve_old_city_deadline_transition(
        self, context: EndDayContext
    ) -> bool:
        """Resolve Patch 008 promises and countdowns at the new-day boundary."""

        state = context.state
        old = state.old_city
        if not old.is_unlocked or old.resolved:
            return False
        countdown_due = (
            old.countdown_day is not None
            and context.settled_day >= old.countdown_day
        )
        if countdown_due:
            context.emit(
                "deadline_day_end_state",
                {
                    "deadline_day": old.countdown_day,
                    "settled_day": context.settled_day,
                    "new_day": state.calendar.current_day,
                    "member_count": old.member_count,
                    "trust": state.trust_panic.trust,
                    "panic": state.trust_panic.panic,
                },
            )
        promise_resolution = self._settle_old_city_promise(
            state, state.calendar.current_day
        )
        if countdown_due:
            context.emit(
                "promise_resolution",
                promise_resolution
                or {
                    "status": (
                        "already_settled"
                        if old.promise_settled
                        else "no_promise"
                    ),
                    "outcome": old.promise_outcome,
                    "settled_day": old.promise_settled_day,
                },
            )
            settlement = self._settle_old_city(
                state, settlement_day=context.settled_day
            )
            context.emit(
                "old_city_final_resolution",
                {
                    **settlement,
                    "deadline_day": old.countdown_day,
                    "settlement_day": old.settlement_day,
                },
            )
        return countdown_due or promise_resolution is not None

    def check_hard_fails(self, context: EndDayContext) -> None:
        state = context.state
        if state.final_result.hard_fail_type is not None:
            return
        if state.population.population_alive <= 0:
            state.final_result.hard_fail_type = HardFailType.POPULATION_ZERO
            return
        if state.trust_panic.trust == 0:
            if state.oath_order.final_oath_active:
                self._add_ending_tag(state, "oath_carried_zero_trust")
            else:
                state.final_result.hard_fail_type = HardFailType.TRUST_EXILE
                return
        if state.trust_panic.panic == 100:
            if state.oath_order.highest_order_active:
                self._add_ending_tag(state, "decree_carried_panic")
            else:
                state.final_result.hard_fail_type = HardFailType.PANIC_EXPELLED

    def validate_state(self, state: GameState) -> None:
        validate_game_state(
            state,
            self.building_rules,
            self.survival_rules,
            self.technology_rules,
        )
        signed = set(state.oath_order.signed_law_ids)
        if signed - set(self.rules.laws):
            raise SaveDataError("state contains an unknown oath/order law")
        routes = {self.rules.laws[item].route for item in signed}
        if len(routes) > 1:
            raise SaveDataError("oath and iron laws are permanently exclusive")
        if routes and state.oath_order.selected_route not in routes:
            raise SaveDataError("signed oath/order laws disagree with selected route")
        if state.oath_order.selected_route is not None and (
            _ROUTE_ENTRY_LAWS[state.oath_order.selected_route] not in signed
        ):
            raise SaveDataError("selected oath/order route lacks its entry law")
        for law_id in signed:
            if not set(self.rules.laws[law_id].requires).issubset(signed):
                raise SaveDataError("signed oath/order law lacks a prerequisite")
        if state.oath_order.final_oath_active != ("final_oath" in signed):
            raise SaveDataError("final oath activation must match its signed law")
        if state.oath_order.highest_order_active != ("highest_order" in signed):
            raise SaveDataError("highest order activation must match its signed law")
        if set(state.oath_order.action_next_available_day) - set(self.rules.actions):
            raise SaveDataError("state contains an unknown route action cooldown")
        if set(state.oath_order.action_last_used_day) - set(self.rules.actions):
            raise SaveDataError("state contains an unknown route action history")
        if set(state.oath_order.law_signed_days) != signed:
            raise SaveDataError("oath/order law history must match signed laws")
        signed_days = list(state.oath_order.law_signed_days.values())
        if (
            any(day > state.calendar.current_day or day < 1 for day in signed_days)
            or len(signed_days) != len(set(signed_days))
        ):
            raise SaveDataError("oath/order signing days must be past and unique")
        ordered_days = sorted(signed_days)
        if any(
            later - earlier < self.rules.unlock.law_cooldown_days
            for earlier, later in zip(ordered_days, ordered_days[1:])
        ):
            raise SaveDataError("oath/order signing history violates cooldown")
        if ordered_days:
            first_day = ordered_days[0]
            if first_day < self.rules.unlock.ordinary_day:
                raise SaveDataError("oath/order route was entered before day 30")
            if (
                first_day < self.rules.unlock.guaranteed_day
                and len(state.laws.signed_law_ids)
                < self.rules.unlock.ordinary_social_laws
            ):
                raise SaveDataError("early oath/order entry lacks eight social laws")
        for law_id, day in state.oath_order.law_signed_days.items():
            if any(
                state.oath_order.law_signed_days[required] >= day
                for required in self.rules.laws[law_id].requires
            ):
                raise SaveDataError("oath/order law history violates prerequisite order")
        expected_next_law_day = (
            max(signed_days) + self.rules.unlock.law_cooldown_days
            if signed_days else 1
        )
        if state.oath_order.next_law_day != expected_next_law_day:
            raise SaveDataError("oath/order cooldown disagrees with signing history")
        if set(state.oath_order.action_next_available_day) != set(
            state.oath_order.action_last_used_day
        ):
            raise SaveDataError("route action cooldowns and history must match")
        for action_id, used_day in state.oath_order.action_last_used_day.items():
            required_law = self.rules.actions[action_id].required_law
            if (
                used_day > state.calendar.current_day
                or required_law not in state.oath_order.law_signed_days
                or used_day < state.oath_order.law_signed_days[required_law]
                or state.oath_order.action_next_available_day[action_id]
                != used_day + self.rules.actions[action_id].cooldown_days
            ):
                raise SaveDataError("route action cooldown disagrees with usage history")
        if (
            state.oath_order.death_panic_aftershock_halved_day is not None
            and state.oath_order.action_last_used_day.get("mourning_bell")
            != state.oath_order.death_panic_aftershock_halved_day
        ):
            raise SaveDataError("mourning-bell modifier lacks its action history")
        if state.oath_order.page_unlocked and not (
            state.oath_order.selected_route is not None
            or state.calendar.current_day >= self.rules.unlock.guaranteed_day
            or (
                state.calendar.current_day >= self.rules.unlock.ordinary_day
                and len(state.laws.signed_law_ids)
                >= self.rules.unlock.ordinary_social_laws
            )
        ):
            raise SaveDataError("oath/order page was unlocked before its condition")
        old = state.old_city
        if old.is_unlocked:
            expected = self._old_city_thresholds(old.reference_population)
            if (
                old.low_threshold,
                old.middle_threshold,
                old.high_threshold,
            ) != expected:
                raise SaveDataError("old city thresholds do not match reference population")
        assigned_workers, assigned_engineers = self._assigned_adults(state)
        if assigned_workers > state.population.workers:
            raise SaveDataError("assigned workers exceed the population pool")
        if assigned_engineers > state.population.engineers:
            raise SaveDataError("assigned engineers exceed the population pool")

    def route_view(self, state: GameState) -> dict[str, Any]:
        self.validate_state(state)
        return {
            "page_unlocked": state.oath_order.page_unlocked or self._is_page_available(state),
            "selected_route": state.oath_order.selected_route,
            "signed_law_ids": list(state.oath_order.signed_law_ids),
            "next_law_day": state.oath_order.next_law_day,
            "entry_law_ids": dict(_ROUTE_ENTRY_LAWS),
            "law_rules": [
                {
                    "law_id": law_id,
                    "route": rule.route,
                    "required_law_ids": list(rule.requires),
                    "trust_change": rule.trust,
                    "panic_change": rule.panic,
                    "confirmation_required": (
                        law_id == _ROUTE_ENTRY_LAWS[rule.route]
                    ),
                    "terminal_law": law_id in _TERMINAL_LAWS,
                    "facility_required": law_id in _TERMINAL_LAWS,
                    "is_signed": law_id in state.oath_order.signed_law_ids,
                }
                for law_id, rule in sorted(self.rules.laws.items())
            ],
            "action_rules": [
                {
                    "action_id": action_id,
                    "route": rule.route,
                    "required_law_id": rule.required_law,
                    "cooldown_days": rule.cooldown_days,
                    "trust_change": rule.trust,
                    "panic_change": rule.panic,
                    "cooked_food_cost": rule.cooked_food,
                    "old_city_change": rule.old_city,
                }
                for action_id, rule in sorted(self.rules.actions.items())
            ],
            "facilities": {
                "oath_hall": self._facility_view(state.oath_order.oath_hall),
                "patrol_office": self._facility_view(state.oath_order.patrol_office),
            },
            "action_next_available_day": dict(
                state.oath_order.action_next_available_day
            ),
        }

    def old_city_view(self, state: GameState) -> dict[str, Any]:
        self.validate_state(state)
        old = state.old_city
        pending_event_id = old.pending_event_id
        available_option_ids = self._available_old_city_options(
            state, pending_event_id
        )
        option_previews = []
        for option_id in available_option_ids:
            preview_state = deepcopy(state)
            preview = self._resolve_old_city(
                preview_state,
                CommandRequest(
                    command_id="old-city-preview",
                    name=RESOLVE_OLD_CITY_COMMAND,
                    arguments={
                        "event_id": pending_event_id,
                        "option_id": option_id,
                    },
                ),
            )
            option_previews.append(
                {"option_id": option_id, "preview": preview}
            )
        unavailable_options = []
        if pending_event_id is not None:
            for option_id in _OLD_CITY_OPTIONS[pending_event_id]:
                reason = self._old_city_option_unavailable_reason(
                    state, pending_event_id, option_id
                )
                if reason is not None:
                    unavailable_options.append(
                        {"option_id": option_id, "reason": reason}
                    )
        return {
            "is_unlocked": old.is_unlocked,
            "member_count": old.member_count,
            "active_stage_id": old.active_stage_id,
            "pending_event_id": pending_event_id,
            "available_option_ids": list(available_option_ids),
            "option_previews": option_previews,
            "unavailable_options": unavailable_options,
            "thresholds": {
                "low": old.low_threshold,
                "middle": old.middle_threshold,
                "high": old.high_threshold,
            },
            "countdown_day": old.countdown_day,
            "promise_active": old.promise_active,
            "promise_created_day": old.promise_created_day,
            "promise_target_count": old.promise_target_count,
            "promise_deadline_day": old.promise_deadline_day,
            "promise_settled": old.promise_settled,
            "promise_outcome": old.promise_outcome,
            "promise_settled_day": old.promise_settled_day,
            "resolved": old.resolved,
            "result_id": old.result_id,
            "theoretical_departures": old.theoretical_departures,
            "actual_departures": old.actual_departures,
            "protected_jobs": dict(old.protected_jobs),
            "protected_engineers": old.protected_engineers,
            "reduction_reason": old.reduction_reason,
            "settlement_resource_losses": dict(
                old.settlement_resource_losses
            ),
        }

    def _available_old_city_options(
        self, state: GameState, event_id: str | None = None
    ) -> tuple[str, ...]:
        target_event_id = (
            state.old_city.pending_event_id
            if event_id is None
            else event_id
        )
        if (
            target_event_id is None
            or target_event_id != state.old_city.pending_event_id
            or target_event_id not in _OLD_CITY_OPTIONS
        ):
            return ()
        return tuple(
            option_id
            for option_id in _OLD_CITY_OPTIONS[target_event_id]
            if self._old_city_option_unavailable_reason(
                state, target_event_id, option_id
            )
            is None
        )

    @staticmethod
    def _old_city_option_unavailable_reason(
        state: GameState, event_id: str, option_id: str
    ) -> str | None:
        if (
            event_id == "countdown"
            and option_id == "promise_reduce_old_city"
            and (
                state.old_city.promise_active
                or state.old_city.promise_settled
            )
        ):
            return "old_city_promise_already_used"
        if event_id == "countdown" and option_id == "ask_for_time":
            trust = state.trust_panic.trust
            if (
                (trust is None or trust < 50)
                and state.oath_order.selected_route is None
            ):
                return "old_city_time_request_unavailable"
        return None

    def _activate_old_city(self, state: GameState) -> None:
        old = state.old_city
        old.is_unlocked = True
        old.activation_pending = False
        old.reference_population = state.population.population_alive
        (
            old.low_threshold,
            old.middle_threshold,
            old.high_threshold,
        ) = self._old_city_thresholds(old.reference_population)
        old.active_stage_id = "southern_letter"
        old.pending_event_id = "southern_letter"
        old.stage_events_seen.append("southern_letter")

    def _old_city_thresholds(self, reference: int) -> tuple[int, int, int]:
        rule = self.rules.old_city
        return (
            max(rule.low_minimum, ceil(reference * rule.low_percent / 100)),
            max(rule.middle_minimum, ceil(reference * rule.middle_percent / 100)),
            max(rule.high_minimum, ceil(reference * rule.high_percent / 100)),
        )

    def _advance_old_city_stage(self, state: GameState) -> None:
        old = state.old_city
        if old.resolved or old.pending_event_id is not None:
            return
        if (
            "rumors" not in old.stage_events_seen
            and old.member_count >= old.low_threshold
        ):
            stage = "rumors"
        elif (
            "public_gathering" not in old.stage_events_seen
            and old.member_count >= old.middle_threshold
        ):
            stage = "public_gathering"
        elif (
            "countdown" not in old.stage_events_seen
            and old.member_count >= old.high_threshold
        ):
            stage = "countdown"
        else:
            return
        old.active_stage_id = stage
        old.stage_events_seen.append(stage)
        old.pending_event_id = stage
        if stage == "countdown":
            old.countdown_day = min(
                state.calendar.current_day + self.rules.old_city.countdown_days,
                self.rules.old_city.countdown_cap_day,
            )

    def _settle_old_city_promise(
        self, state: GameState, current_day: int
    ) -> dict[str, Any] | None:
        old = state.old_city
        if not old.promise_active:
            return None
        assert old.promise_target_count is not None
        assert old.promise_deadline_day is not None
        if old.member_count <= old.promise_target_count:
            outcome, trust, panic, count = "success", 3, -2, -8
        elif current_day > old.promise_deadline_day:
            outcome, trust, panic, count = "failure", -8, 8, 6
        else:
            return None
        old.promise_active = False
        old.promise_settled = True
        old.promise_outcome = outcome
        old.promise_settled_day = current_day
        old.member_count = min(
            max(old.member_count + count, 0), state.population.population_alive
        )
        self._change_emotion(state, trust=trust, panic=panic)
        return {
            "status": "settled",
            "outcome": outcome,
            "settled_day": current_day,
            "deadline_day": old.promise_deadline_day,
            "member_count_change": count,
            "trust_change": trust,
            "panic_change": panic,
        }

    def _settle_old_city(
        self, state: GameState, *, settlement_day: int | None = None
    ) -> dict[str, Any]:
        old = state.old_city
        alive = state.population.population_alive
        settlement_member_count = old.member_count
        if old.member_count < old.low_threshold:
            result, leave, trust, panic = "scattered", 0, 3, -2
        elif old.member_count < old.high_threshold:
            result = "partial_exodus"
            leave = min(floor(old.member_count * 0.40), floor(alive * 0.12))
            trust, panic = -5, 5
        else:
            result = "large_exodus"
            leave = min(floor(old.member_count * 0.55), floor(alive * 0.22))
            trust, panic = -8, 8
        theoretical_departures = leave
        departure = self._remove_population(state, leave)
        leave = departure["actual_departures"]
        if result == "partial_exodus":
            theoretical_losses = {
                "cooked_food": leave,
                "coal": leave * 2,
                "wood": leave,
                "steel": floor(leave / 2),
            }
        elif result == "large_exodus":
            theoretical_losses = {
                "cooked_food": leave * 2,
                "coal": leave * 3,
                "wood": leave * 2,
                "steel": leave,
            }
        else:
            theoretical_losses = {
                "cooked_food": 0,
                "coal": 0,
                "wood": 0,
                "steel": 0,
            }
        losses = {
            resource: min(getattr(state.resources, resource), loss)
            for resource, loss in theoretical_losses.items()
        }
        for resource, loss in losses.items():
            setattr(
                state.resources,
                resource,
                getattr(state.resources, resource) - loss,
            )
        self._change_emotion(state, trust=trust, panic=panic)
        old.member_count = 0
        old.resolved = True
        old.result_id = result
        old.settlement_day = (
            state.calendar.current_day
            if settlement_day is None
            else settlement_day
        )
        old.settlement_member_count = settlement_member_count
        old.theoretical_departures = theoretical_departures
        old.actual_departures = leave
        old.protected_jobs = dict(departure["protected_jobs"])
        old.protected_engineers = departure["protected_engineers"]
        old.reduction_reason = departure["reduction_reason"]
        old.settlement_resource_losses = dict(losses)
        old.active_stage_id = None
        old.pending_event_id = None
        return {
            "result_id": result,
            "theoretical_departures": theoretical_departures,
            "actual_departures": leave,
            "protected_jobs": dict(old.protected_jobs),
            "protected_engineers": old.protected_engineers,
            "reduction_reason": old.reduction_reason,
            "resource_losses": losses,
            "trust_change": trust,
            "panic_change": panic,
        }

    def _remove_population(
        self, state: GameState, requested: int
    ) -> dict[str, Any]:
        if requested <= 0:
            return {
                "actual_departures": 0,
                "protected_jobs": {},
                "protected_engineers": 0,
                "reduction_reason": None,
            }
        population = state.population
        protected_engineers = min(population.engineers, 2)
        protected_assignments = self._protected_job_assignments(state)
        protected_jobs = {
            target_id: 1 for target_id in sorted(protected_assignments)
        }
        assigned = self._assignment_totals(state)
        categorized = population.workers + population.engineers + population.children
        uncategorized = max(population.population_alive - categorized, 0)
        remaining = requested

        from_uncategorized = min(remaining, uncategorized)
        remaining -= from_uncategorized

        def remove_unassigned(attribute: str, available: int) -> None:
            nonlocal remaining
            removed = min(remaining, max(available, 0))
            if removed <= 0:
                return
            if attribute == "workers":
                population.workers -= removed
            elif attribute == "engineers":
                population.engineers -= removed
            elif attribute == "children":
                population.children -= removed
            elif attribute == "medical_apprentices":
                population.medical_apprentices -= removed
                population.children -= removed
            elif attribute == "engineering_apprentices":
                population.engineering_apprentices -= removed
                population.children -= removed
            remaining -= removed

        remove_unassigned(
            "workers", population.workers - assigned["assigned_workers"]
        )
        ordinary_children = (
            population.children
            - population.medical_apprentices
            - population.engineering_apprentices
        )
        remove_unassigned(
            "children", ordinary_children - assigned["assigned_children"]
        )
        remove_unassigned(
            "medical_apprentices",
            population.medical_apprentices
            - assigned["assigned_medical_apprentices"],
        )
        remove_unassigned(
            "engineering_apprentices",
            population.engineering_apprentices
            - assigned["assigned_engineering_apprentices"],
        )
        remove_unassigned(
            "engineers",
            min(
                population.engineers - assigned["assigned_engineers"],
                population.engineers - protected_engineers,
            ),
        )

        for _tier, target_id, item, attribute in self._departure_assignments(state):
            if remaining <= 0:
                break
            value = getattr(item, attribute)
            protected_assignment = protected_assignments.get(target_id)
            protected = (
                1
                if (
                    protected_assignment is not None
                    and protected_assignment[0] is item
                    and protected_assignment[1] == attribute
                )
                else 0
            )
            removable = max(value - protected, 0)
            if attribute == "assigned_engineers":
                removable = min(
                    removable, population.engineers - protected_engineers
                )
            removed = min(remaining, removable)
            if removed <= 0:
                continue
            setattr(item, attribute, value - removed)
            if attribute == "assigned_workers":
                population.workers -= removed
            elif attribute == "assigned_engineers":
                population.engineers -= removed
            elif attribute == "assigned_children":
                population.children -= removed
            elif attribute == "assigned_medical_apprentices":
                population.medical_apprentices -= removed
                population.children -= removed
            elif attribute == "assigned_engineering_apprentices":
                population.engineering_apprentices -= removed
                population.children -= removed
            remaining -= removed

        actual = requested - remaining
        remove_non_hunger_deaths_or_departures(state, actual)
        health_remaining = actual
        for name in (
            "healthy_population", "sick_population",
            "critical_population", "disabled_population",
        ):
            value = getattr(population, name)
            removed = min(value, health_remaining)
            setattr(population, name, value - removed)
            health_remaining -= removed
        population.population_alive -= actual
        population.population_total -= actual
        population.housed_population = min(
            population.housed_population, population.population_alive
        )
        population.homeless_population = (
            population.population_alive - population.housed_population
        )
        state.medical.medical_pressure = max(
            population.sick_population
            + population.critical_population
            - state.medical.effective_capacity,
            0,
        )
        for building in state.buildings.values():
            if sum(
                getattr(building, attribute)
                for attribute in _ASSIGNMENT_ATTRIBUTES
            ) == 0:
                building.is_operational = False
        state.medical.building_capacity = medical_building_capacity(
            state, expected=False
        )
        state.medical.effective_capacity = (
            state.medical.temporary_capacity
            + state.medical.building_capacity
        )
        state.medical.medical_pressure = max(
            population.sick_population
            + population.critical_population
            - state.medical.effective_capacity,
            0,
        )
        for facility in (
            state.oath_order.oath_hall,
            state.oath_order.patrol_office,
        ):
            facility.is_running = (
                facility.enabled
                and facility.assigned_workers + facility.assigned_engineers >= 1
            )
        reduction_reason = None
        if actual < requested:
            job_limited = bool(protected_assignments)
            engineer_limited = (
                population.engineers <= protected_engineers
                and protected_engineers > 0
            )
            if job_limited and engineer_limited:
                reduction_reason = "critical_jobs_and_engineer_floor"
            elif job_limited:
                reduction_reason = "critical_job_protection"
            elif engineer_limited:
                reduction_reason = "engineer_floor"
            else:
                reduction_reason = "population_protection"
        return {
            "actual_departures": actual,
            "protected_jobs": protected_jobs,
            "protected_engineers": protected_engineers,
            "reduction_reason": reduction_reason,
        }

    def _protected_job_assignments(
        self, state: GameState
    ) -> dict[str, tuple[Any, str]]:
        protected: dict[str, tuple[Any, str]] = {}
        patients = (
            state.population.sick_population
            + state.population.critical_population
        )
        for building_id, building in sorted(state.buildings.items()):
            if (
                building.building_type not in _CRITICAL_BUILDING_TYPES
                or not building.is_operational
                or (
                    building.building_type
                    in {"medical_station", "hospital"}
                    and patients <= 0
                )
            ):
                continue
            preferred = (
                (
                    "assigned_medical_apprentices",
                    "assigned_engineers",
                )
                if building.building_type
                in {"medical_station", "hospital"}
                else ("assigned_workers", "assigned_engineers")
            )
            attribute = next(
                (
                    name
                    for name in preferred
                    if getattr(building, name) > 0
                ),
                None,
            )
            if attribute is not None:
                protected[f"building:{building_id}"] = (
                    building,
                    attribute,
                )
        for resource_id, point in sorted(
            state.surface_resource_points.items()
        ):
            if (
                point.resource_type != "coal"
                or point.is_depleted
                or point.assigned_workers + point.assigned_engineers <= 0
            ):
                continue
            attribute = (
                "assigned_workers"
                if point.assigned_workers > 0
                else "assigned_engineers"
            )
            protected[f"resource:{resource_id}"] = (point, attribute)
        return protected

    def _departure_assignments(
        self, state: GameState
    ) -> list[tuple[int, str, Any, str]]:
        assignments: list[tuple[int, str, Any, str]] = []
        facilities = (
            ("facility:oath_hall", state.oath_order.oath_hall),
            ("facility:patrol_office", state.oath_order.patrol_office),
        )
        for target_id, facility in facilities:
            for attribute in ("assigned_workers", "assigned_engineers"):
                assignments.append((0, target_id, facility, attribute))
        for building_id, building in state.buildings.items():
            if building.building_type in _NON_SURVIVAL_BUILDING_TYPES:
                tier = 0
            elif building.building_type in _SECONDARY_BUILDING_TYPES:
                tier = 1
            elif building.building_type in _CRITICAL_BUILDING_TYPES:
                tier = 3
            else:
                tier = 2
            target_id = f"building:{building_id}"
            for attribute in _ASSIGNMENT_ATTRIBUTES:
                assignments.append((tier, target_id, building, attribute))
        for resource_id, point in state.surface_resource_points.items():
            tier = 3 if point.resource_type == "coal" else 1
            target_id = f"resource:{resource_id}"
            for attribute in ("assigned_workers", "assigned_engineers"):
                assignments.append((tier, target_id, point, attribute))
        attribute_order = {
            name: index for index, name in enumerate(_ASSIGNMENT_ATTRIBUTES)
        }
        return sorted(
            assignments,
            key=lambda item: (
                item[0],
                item[1],
                attribute_order[item[3]],
            ),
        )

    @staticmethod
    def _assignment_totals(state: GameState) -> dict[str, int]:
        totals = {name: 0 for name in _ASSIGNMENT_ATTRIBUTES}
        for item in state.buildings.values():
            for attribute in _ASSIGNMENT_ATTRIBUTES:
                totals[attribute] += getattr(item, attribute)
        for item in state.surface_resource_points.values():
            totals["assigned_workers"] += item.assigned_workers
            totals["assigned_engineers"] += item.assigned_engineers
        for facility in (
            state.oath_order.oath_hall,
            state.oath_order.patrol_office,
        ):
            totals["assigned_workers"] += facility.assigned_workers
            totals["assigned_engineers"] += facility.assigned_engineers
        return totals

    def _refresh_unlock(self, state: GameState) -> None:
        if self._is_page_available(state):
            state.oath_order.page_unlocked = True

    def _is_page_available(self, state: GameState) -> bool:
        return (
            state.oath_order.page_unlocked
            or state.calendar.current_day >= self.rules.unlock.guaranteed_day
            or (
                state.calendar.current_day >= self.rules.unlock.ordinary_day
                and len(state.laws.signed_law_ids)
                >= self.rules.unlock.ordinary_social_laws
            )
        )

    @staticmethod
    def _facility(state: GameState, route: str) -> RouteFacilityState:
        return (
            state.oath_order.oath_hall
            if route == "oath"
            else state.oath_order.patrol_office
        )

    @staticmethod
    def _facility_by_id(state: GameState, facility_id: str) -> RouteFacilityState:
        return (
            state.oath_order.oath_hall
            if facility_id == "oath_hall"
            else state.oath_order.patrol_office
        )

    @staticmethod
    def _facility_view(facility: RouteFacilityState) -> dict[str, Any]:
        return {
            "enabled": facility.enabled,
            "visible": facility.visible,
            "slot_cost": 0,
            "minimum_total_staff": 1,
            "staff_assignment_mode": "absolute_target_count",
            "assigned_workers": facility.assigned_workers,
            "assigned_engineers": facility.assigned_engineers,
            "is_running": facility.is_running,
            "uses_heat": False,
            "temperature_shutdown": False,
        }

    @staticmethod
    def _assigned_adults(
        state: GameState, *, exclude: RouteFacilityState | None = None
    ) -> tuple[int, int]:
        workers = engineers = 0
        for item in list(state.buildings.values()) + list(
            state.surface_resource_points.values()
        ):
            workers += item.assigned_workers
            engineers += item.assigned_engineers
        for facility in (state.oath_order.oath_hall, state.oath_order.patrol_office):
            if facility is exclude:
                continue
            workers += facility.assigned_workers
            engineers += facility.assigned_engineers
        return workers, engineers

    @staticmethod
    def _shared_meal_cost(state: GameState) -> int:
        return min(80, max(30, ceil(state.population.population_alive * 0.5)))

    @staticmethod
    def _change_emotion(
        state: GameState, *, trust: int = 0, panic: int = 0
    ) -> None:
        if state.trust_panic.trust is not None:
            state.trust_panic.trust = min(
                max(state.trust_panic.trust + trust, 0), 100
            )
        if state.trust_panic.panic is not None:
            state.trust_panic.panic = min(
                max(state.trust_panic.panic + panic, 0), 100
            )

    @staticmethod
    def _add_ending_tag(state: GameState, tag: str) -> None:
        if tag not in state.oath_order.ending_tag_candidates:
            state.oath_order.ending_tag_candidates.append(tag)

    @staticmethod
    def _illegal(reason: str, **details: Any) -> CommandValidation:
        return CommandValidation(
            False, ErrorCode.ILLEGAL_COMMAND, {"reason": reason, **details}
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
