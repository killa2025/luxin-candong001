from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from furnace_winter.config import (
    OathOrderConfigError,
    load_building_rules,
    load_oath_order_rules,
    load_survival_rules,
    load_technology_rules,
)
from furnace_winter.gameplay import (
    ASSIGN_RESOURCE_COMMAND,
    END_DAY_COMMAND,
    RESOLVE_OLD_CITY_COMMAND,
    SIGN_OATH_ORDER_LAW_COMMAND,
    STAFF_OATH_ORDER_FACILITY_COMMAND,
    USE_OATH_ORDER_ACTION_COMMAND,
    OathOrderSystem,
    BuildingSystem,
    EndDayEngine,
    create_initial_survival_state,
)
from furnace_winter.gameplay.end_day import (
    EndDayContext,
    EndDayStage,
    RiskWarningLevel,
)
from furnace_winter.interface import CommandRequest, ErrorCode, GameSession
from furnace_winter.models import (
    BuildingState,
    CURRENT_SAVE_DATA_VERSION,
    DeterministicRandom,
    EventResolutionRecord,
    HardFailType,
    SaveDataError,
    decode_game_state,
    encode_game_state,
)


ROOT = Path(__file__).resolve().parents[1]


class OathOrderPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.survival_rules = load_survival_rules(ROOT / "data" / "survival.json")
        cls.building_rules = load_building_rules(ROOT / "data" / "buildings.json")
        cls.technology_rules = load_technology_rules(
            ROOT / "data" / "technologies.json"
        )
        cls.rules = load_oath_order_rules(ROOT / "data" / "oath_order.json")

    def make_state(self, *, day: int = 1):
        state = create_initial_survival_state(
            self.survival_rules, self.building_rules, random_seed=8008
        )
        state.calendar.current_day = day
        state.trust_panic.trust = 50
        state.trust_panic.panic = 30
        return state

    def system(self) -> OathOrderSystem:
        return OathOrderSystem(
            self.rules,
            self.building_rules,
            self.survival_rules,
            self.technology_rules,
        )

    def execute(self, system, state, name, **arguments):
        return system.execute(
            state,
            CommandRequest(
                command_id=f"cmd-{state.command_sequence + 1}",
                name=name,
                arguments=arguments,
                expected_state_sequence=state.command_sequence,
            ),
        )

    def context(self, state, stage=EndDayStage.UPDATE_PROMISE_TARGETS):
        return EndDayContext(
            state=state,
            random=DeterministicRandom.from_state(state.random),
            settled_day=state.calendar.current_day,
            stage=stage,
            _emit=lambda _code, _payload: None,
        )

    def enter_oath_route(self, system, state) -> None:
        result = self.execute(
            system,
            state,
            SIGN_OATH_ORDER_LAW_COMMAND,
            law_id="guard_oath",
            confirm=True,
        )
        self.assertEqual(result.code, ErrorCode.OK)

    def prepare_countdown(
        self,
        system: OathOrderSystem,
        state,
        *,
        deadline_day: int,
        option_id: str | None = None,
    ) -> None:
        system.prepare_new_day(state)
        self.assertEqual(
            self.execute(
                system,
                state,
                RESOLVE_OLD_CITY_COMMAND,
                event_id="southern_letter",
                option_id="publish",
            ).code,
            ErrorCode.OK,
        )
        old = state.old_city
        old.active_stage_id = "countdown"
        old.member_count = old.high_threshold
        old.countdown_day = deadline_day
        old.pending_event_id = "countdown" if option_id is not None else None
        old.stage_events_seen = [
            "southern_letter",
            "rumors",
            "public_gathering",
            "countdown",
        ]
        if option_id is not None:
            self.assertEqual(
                self.execute(
                    system,
                    state,
                    RESOLVE_OLD_CITY_COMMAND,
                    event_id="countdown",
                    option_id=option_id,
                ).code,
                ErrorCode.OK,
            )

    def end_day(self, system: OathOrderSystem, state):
        engine = EndDayEngine()
        system.install(engine)
        return engine.execute(
            state,
            CommandRequest(
                f"end-{state.command_sequence + 1}",
                END_DAY_COMMAND,
                {},
                state.command_sequence,
            ),
        )

    @staticmethod
    def add_rejected_arrival_history(state, *, through_day: int) -> None:
        for event_id, day in (
            ("arrival_day6", 6),
            ("arrival_day19", 19),
            ("arrival_day37", 37),
        ):
            if day >= through_day:
                continue
            state.events.fixed_arrival_choices[event_id] = "reject"
            state.events.resolved_event_ids.append(event_id)
            state.events.occurrence_counts[event_id] = 1
            state.events.resolution_history.append(
                EventResolutionRecord(
                    event_id=event_id,
                    option_id="reject",
                    event_type="major",
                    resolved_day=day,
                    instance_id=f"{event_id}#0001",
                    occurrence_index=1,
                    trust_change=0,
                    panic_change=0,
                    resource_changes={
                        "coal": 0,
                        "wood": 0,
                        "steel": 0,
                        "raw_food": 0,
                        "cooked_food": 0,
                    },
                )
            )

    def sign_full_oath_route(self, system, state) -> None:
        self.enter_oath_route(system, state)
        staffed = self.execute(
            system,
            state,
            STAFF_OATH_ORDER_FACILITY_COMMAND,
            facility_id="oath_hall",
            workers=1,
            engineers=0,
        )
        self.assertEqual(staffed.code, ErrorCode.OK)
        for law_id in (
            "mourning_bell",
            "shared_meal",
            "ember_roster",
            "stay_oath",
            "final_oath",
        ):
            state.calendar.current_day = state.oath_order.next_law_day
            result = self.execute(
                system,
                state,
                SIGN_OATH_ORDER_LAW_COMMAND,
                law_id=law_id,
            )
            self.assertEqual(result.code, ErrorCode.OK)

    def sign_full_iron_route(self, system, state) -> None:
        result = self.execute(
            system,
            state,
            SIGN_OATH_ORDER_LAW_COMMAND,
            law_id="city_patrol_order",
            confirm=True,
        )
        self.assertEqual(result.code, ErrorCode.OK)
        staffed = self.execute(
            system,
            state,
            STAFF_OATH_ORDER_FACILITY_COMMAND,
            facility_id="patrol_office",
            workers=1,
            engineers=0,
        )
        self.assertEqual(staffed.code, ErrorCode.OK)
        for law_id in (
            "morning_roll_call",
            "unified_announcement",
            "temporary_detain",
            "household_registry_check",
            "highest_order",
        ):
            state.calendar.current_day = state.oath_order.next_law_day
            result = self.execute(
                system,
                state,
                SIGN_OATH_ORDER_LAW_COMMAND,
                law_id=law_id,
            )
            self.assertEqual(result.code, ErrorCode.OK)

    def test_config_is_strict_and_machine_readable(self) -> None:
        self.assertEqual(self.rules.unlock.guaranteed_day, 35)
        self.assertEqual(len(self.rules.laws), 12)
        document = json.loads(
            (ROOT / "data" / "oath_order.json").read_text(encoding="utf-8")
        )
        document["unlock"]["guaranteed_day"] = 34
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "oath_order.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(OathOrderConfigError):
                load_oath_order_rules(path)

    def test_page_unlock_and_route_entry_confirmation(self) -> None:
        system = self.system()
        state = self.make_state(day=34)
        blocked = self.execute(
            system,
            state,
            SIGN_OATH_ORDER_LAW_COMMAND,
            law_id="guard_oath",
            confirm=True,
        )
        self.assertEqual(blocked.code, ErrorCode.ILLEGAL_COMMAND)
        state.calendar.current_day = 35
        missing_confirmation = self.execute(
            system,
            state,
            SIGN_OATH_ORDER_LAW_COMMAND,
            law_id="guard_oath",
        )
        self.assertEqual(missing_confirmation.data["reason"], "confirmation_required")
        self.enter_oath_route(system, state)
        self.assertEqual(state.oath_order.selected_route, "oath")

    def test_social_law_unlock_and_independent_cooldown(self) -> None:
        system = self.system()
        state = self.make_state(day=30)
        state.laws.signed_law_ids = [f"social-{index}" for index in range(8)]
        state.laws.active_law_ids = list(state.laws.signed_law_ids)
        self.enter_oath_route(system, state)
        self.assertEqual(state.oath_order.next_law_day, 32)
        self.assertNotIn("ordinary_law", state.laws.cooldowns)

    def test_route_facility_is_automatic_slotless_and_temperature_independent(self) -> None:
        system = self.system()
        state = self.make_state(day=35)
        slots_before = deepcopy(state.building_management.zone_slots_used)
        buildings_before = deepcopy(state.buildings)
        self.enter_oath_route(system, state)
        view = system.route_view(state)["facilities"]["oath_hall"]
        self.assertTrue(view["enabled"])
        self.assertEqual(view["slot_cost"], 0)
        self.assertEqual(view["minimum_total_staff"], 1)
        self.assertEqual(view["staff_assignment_mode"], "absolute_target_count")
        self.assertFalse(view["uses_heat"])
        self.assertEqual(state.buildings, buildings_before)
        self.assertEqual(state.building_management.zone_slots_used, slots_before)
        staffed = self.execute(
            system,
            state,
            STAFF_OATH_ORDER_FACILITY_COMMAND,
            facility_id="oath_hall",
            workers=1,
            engineers=0,
        )
        self.assertEqual(staffed.code, ErrorCode.OK)
        self.assertTrue(state.oath_order.oath_hall.is_running)
        state.furnace.is_active = False
        self.assertTrue(state.oath_order.oath_hall.is_running)

    def test_route_view_discloses_law_order_costs_and_action_contracts(self) -> None:
        system = self.system()
        state = self.make_state(day=35)

        view = system.route_view(state)
        self.assertEqual(view["balance_status"], "TEST_NUMERIC")
        laws = {item["law_id"]: item for item in view["law_rules"]}
        actions = {item["action_id"]: item for item in view["action_rules"]}

        self.assertEqual(view["entry_law_ids"], {
            "oath": "guard_oath",
            "iron": "city_patrol_order",
        })
        self.assertTrue(laws["city_patrol_order"]["confirmation_required"])
        self.assertEqual(
            laws["morning_roll_call"]["required_law_ids"],
            ["city_patrol_order"],
        )
        self.assertEqual(laws["highest_order"]["trust_change"], -8)
        self.assertTrue(laws["highest_order"]["facility_required"])
        self.assertEqual(actions["patrol"]["required_law_id"], "city_patrol_order")
        self.assertEqual(actions["patrol"]["cooldown_days"], 3)
        self.assertEqual(
            actions["patrol"]["required_facility_id"], "patrol_office"
        )
        self.assertTrue(actions["patrol"]["facility_required"])

        self.assertEqual(
            {
                law_id: (laws[law_id]["trust_change"], laws[law_id]["panic_change"])
                for law_id in (
                    "guard_oath",
                    "mourning_bell",
                    "shared_meal",
                    "ember_roster",
                    "stay_oath",
                    "final_oath",
                )
            },
            {
                "guard_oath": (1, -1),
                "mourning_bell": (0, -1),
                "shared_meal": (0, 0),
                "ember_roster": (0, 0),
                "stay_oath": (0, 0),
                "final_oath": (0, 8),
            },
        )
        self.assertEqual(
            (
                actions["guard_oath"]["cooldown_days"],
                actions["guard_oath"]["trust_change"],
                actions["guard_oath"]["panic_change"],
            ),
            (5, 1, 0),
        )
        self.assertEqual(
            (
                actions["mourning_bell"]["cooldown_days"],
                actions["mourning_bell"]["panic_change"],
            ),
            (6, -2),
        )
        self.assertEqual(
            (
                actions["shared_meal"]["cooldown_days"],
                actions["shared_meal"]["trust_change"],
                actions["shared_meal"]["panic_change"],
            ),
            (5, 1, -2),
        )
        self.assertEqual(
            (
                actions["stay_persuasion"]["cooldown_days"],
                actions["stay_persuasion"]["trust_change"],
                actions["stay_persuasion"]["current_cooked_food_cost"],
                actions["stay_persuasion"]["old_city_change"],
            ),
            (5, 0, 40, -6),
        )

    def test_patch019_guard_oath_action_applies_provisional_values(self) -> None:
        system = self.system()
        state = self.make_state(day=35)
        self.enter_oath_route(system, state)
        self.assertEqual((state.trust_panic.trust, state.trust_panic.panic), (51, 29))
        self.assertEqual(
            self.execute(
                system,
                state,
                STAFF_OATH_ORDER_FACILITY_COMMAND,
                facility_id="oath_hall",
                workers=1,
                engineers=0,
            ).code,
            ErrorCode.OK,
        )

        result = self.execute(
            system,
            state,
            USE_OATH_ORDER_ACTION_COMMAND,
            action_id="guard_oath",
        )

        self.assertEqual(result.code, ErrorCode.OK)
        self.assertEqual(result.data["trust_change"], 1)
        self.assertEqual(result.data["panic_change"], 0)
        self.assertEqual(result.data["next_available_day"], 40)
        self.assertEqual((state.trust_panic.trust, state.trust_panic.panic), (52, 29))

        spec = next(
            item
            for item in system.command_specs()
            if item.name == STAFF_OATH_ORDER_FACILITY_COMMAND
        )
        self.assertEqual(
            spec.argument_semantics,
            {
                "workers": "absolute_target_count",
                "engineers": "absolute_target_count",
            },
        )

    def test_legacy_oath_action_cooldowns_load_in_game_session(
        self,
    ) -> None:
        cases = (
            ("guard_oath", 35, (3, 4), 5),
            ("mourning_bell", 37, (4,), 6),
            ("shared_meal", 37, (4,), 5),
            ("stay_persuasion", 39, (3,), 5),
        )
        for action_id, used_day, old_cooldowns, new_cooldown in cases:
            for old_cooldown in old_cooldowns:
                with self.subTest(
                    action_id=action_id, old_cooldown=old_cooldown
                ), tempfile.TemporaryDirectory() as directory:
                    system = self.system()
                    state = self.make_state(day=35)
                    system.prepare_new_day(state)
                    self.enter_oath_route(system, state)
                    self.assertEqual(
                        self.execute(
                            system,
                            state,
                            STAFF_OATH_ORDER_FACILITY_COMMAND,
                            facility_id="oath_hall",
                            workers=1,
                            engineers=0,
                        ).code,
                        ErrorCode.OK,
                    )
                    prerequisite_laws = {
                        "mourning_bell": ("mourning_bell",),
                        "shared_meal": ("shared_meal",),
                        "stay_persuasion": ("shared_meal", "stay_oath"),
                    }.get(action_id, ())
                    for law_id in prerequisite_laws:
                        state.calendar.current_day = state.oath_order.next_law_day
                        self.assertEqual(
                            self.execute(
                                system,
                                state,
                                SIGN_OATH_ORDER_LAW_COMMAND,
                                law_id=law_id,
                            ).code,
                            ErrorCode.OK,
                        )
                    state.calendar.current_day = used_day
                    if action_id == "mourning_bell":
                        state.events.deaths_today_by_cause = {"cold": 1}
                    if action_id == "stay_persuasion":
                        state.resources.cooked_food = 100
                        state.old_city.member_count = 20
                    result = self.execute(
                        system,
                        state,
                        USE_OATH_ORDER_ACTION_COMMAND,
                        action_id=action_id,
                    )
                    self.assertEqual(result.code, ErrorCode.OK)
                    self.assertEqual(
                        result.data["next_available_day"], used_day + new_cooldown
                    )

                    state.oath_order.action_next_available_day[action_id] = (
                        used_day + old_cooldown
                    )
                    self.add_rejected_arrival_history(
                        state,
                        through_day=state.calendar.current_day + 1,
                    )
                    save_path = Path(directory) / f"legacy-{action_id}-v14.json"
                    save_path.write_text(
                        json.dumps(encode_game_state(state), ensure_ascii=False),
                        encoding="utf-8",
                    )

                    restored = GameSession.load(save_path, config_dir=ROOT / "data")

                    self.assertEqual(
                        restored.state.oath_order.action_next_available_day[
                            action_id
                        ],
                        used_day + old_cooldown,
                    )

    def test_regular_staffing_respects_route_facility_assignment(self) -> None:
        system = self.system()
        state = self.make_state(day=35)
        state.population.workers = 1
        self.enter_oath_route(system, state)
        self.execute(
            system,
            state,
            STAFF_OATH_ORDER_FACILITY_COMMAND,
            facility_id="oath_hall",
            workers=1,
            engineers=0,
        )
        buildings = BuildingSystem(
            self.building_rules,
            self.survival_rules,
            self.technology_rules,
        )
        result = buildings.execute(
            state,
            CommandRequest(
                "assign-1",
                ASSIGN_RESOURCE_COMMAND,
                {
                    "resource_point_id": "surface-coal-1",
                    "population_type": "workers",
                    "count": 1,
                },
                state.command_sequence,
            ),
        )
        self.assertEqual(result.code, ErrorCode.ILLEGAL_COMMAND)
        self.assertEqual(result.data["reason"], "population_not_available")

    def test_routes_are_permanently_exclusive(self) -> None:
        system = self.system()
        state = self.make_state(day=35)
        self.enter_oath_route(system, state)
        state.calendar.current_day = state.oath_order.next_law_day
        blocked = self.execute(
            system,
            state,
            SIGN_OATH_ORDER_LAW_COMMAND,
            law_id="city_patrol_order",
            confirm=True,
        )
        self.assertEqual(blocked.data["reason"], "law_route_locked")

    def test_action_cost_cooldown_and_failure_are_transactional(self) -> None:
        system = self.system()
        state = self.make_state(day=35)
        self.enter_oath_route(system, state)
        self.execute(
            system,
            state,
            STAFF_OATH_ORDER_FACILITY_COMMAND,
            facility_id="oath_hall",
            workers=1,
            engineers=0,
        )
        state.calendar.current_day = state.oath_order.next_law_day
        self.execute(
            system,
            state,
            SIGN_OATH_ORDER_LAW_COMMAND,
            law_id="shared_meal",
        )
        state.resources.cooked_food = 29
        action_view = {
            item["action_id"]: item
            for item in system.route_view(state)["action_rules"]
        }["shared_meal"]
        self.assertEqual(action_view["current_cooked_food_cost"], 40)
        self.assertEqual(
            action_view["required_facility_id"], "oath_hall"
        )
        self.assertTrue(action_view["required_facility_running"])
        before = deepcopy(state)
        failed = self.execute(
            system, state, USE_OATH_ORDER_ACTION_COMMAND, action_id="shared_meal"
        )
        self.assertEqual(failed.code, ErrorCode.ILLEGAL_COMMAND)
        self.assertEqual(state, before)
        state.resources.cooked_food = 100
        result = self.execute(
            system, state, USE_OATH_ORDER_ACTION_COMMAND, action_id="shared_meal"
        )
        self.assertEqual(result.code, ErrorCode.OK)
        self.assertEqual(result.data["cooked_food_paid"], 40)
        repeated = self.execute(
            system, state, USE_OATH_ORDER_ACTION_COMMAND, action_id="shared_meal"
        )
        self.assertEqual(repeated.data["reason"], "action_cooldown_active")

    def test_stay_persuasion_pays_fixed_food_and_reduces_old_city_by_six(
        self,
    ) -> None:
        system = self.system()
        state = self.make_state(day=35)
        system.prepare_new_day(state)
        self.enter_oath_route(system, state)
        self.assertEqual(
            self.execute(
                system,
                state,
                STAFF_OATH_ORDER_FACILITY_COMMAND,
                facility_id="oath_hall",
                workers=1,
                engineers=0,
            ).code,
            ErrorCode.OK,
        )
        for law_id in ("shared_meal", "stay_oath"):
            state.calendar.current_day = state.oath_order.next_law_day
            self.assertEqual(
                self.execute(
                    system,
                    state,
                    SIGN_OATH_ORDER_LAW_COMMAND,
                    law_id=law_id,
                ).code,
                ErrorCode.OK,
            )
        state.old_city.member_count = 20
        state.resources.cooked_food = 39
        before = deepcopy(state)

        rejected = self.execute(
            system,
            state,
            USE_OATH_ORDER_ACTION_COMMAND,
            action_id="stay_persuasion",
        )

        self.assertEqual(rejected.code, ErrorCode.ILLEGAL_COMMAND)
        self.assertEqual(rejected.data["reason"], "insufficient_cooked_food")
        self.assertEqual(rejected.data["required"], 40)
        self.assertEqual(state, before)

        state.resources.cooked_food = 100
        result = self.execute(
            system,
            state,
            USE_OATH_ORDER_ACTION_COMMAND,
            action_id="stay_persuasion",
        )

        self.assertEqual(result.code, ErrorCode.OK)
        self.assertEqual(result.data["cooked_food_paid"], 40)
        self.assertEqual(result.data["old_city_change"], -6)
        self.assertEqual(result.data["trust_change"], 0)
        self.assertEqual(result.data["next_available_day"], 44)
        self.assertEqual(state.resources.cooked_food, 60)
        self.assertEqual(state.old_city.member_count, 14)

    def test_action_view_exposes_dynamic_cost_boundaries_and_facility_block(self) -> None:
        system = self.system()

        def set_alive_population(state, alive: int) -> None:
            population = state.population
            population.population_total_ever = alive
            population.population_total = alive
            population.population_alive = alive
            population.population_dead = 0
            population.workers = alive
            population.engineers = 0
            population.children = 0
            population.medical_apprentices = 0
            population.engineering_apprentices = 0
            population.healthy_population = alive
            population.sick_population = 0
            population.critical_population = 0
            population.disabled_population = 0
            population.housed_population = min(alive, state.housing.capacity)
            population.homeless_population = (
                alive - population.housed_population
            )
            state.hunger.none_population = alive
            state.hunger.light_population = 0
            state.hunger.severe_population = 0
            state.hunger.starving_population = 0

        low_population = self.make_state(day=35)
        set_alive_population(low_population, 20)
        high_population = self.make_state(day=35)
        set_alive_population(high_population, 200)

        low_rule = {
            item["action_id"]: item
            for item in system.route_view(low_population)["action_rules"]
        }["shared_meal"]
        high_rule = {
            item["action_id"]: item
            for item in system.route_view(high_population)["action_rules"]
        }["shared_meal"]

        self.assertEqual(low_rule["current_cooked_food_cost"], 30)
        self.assertEqual(high_rule["current_cooked_food_cost"], 80)
        self.assertEqual(
            low_rule["cooked_food_cost_formula"],
            {
                "kind": "population_scaled_clamped",
                "population_field": "population_alive",
                "population_numerator": 1,
                "population_denominator": 2,
                "rounding": "ceiling",
                "minimum": 30,
                "maximum": 80,
            },
        )

        blocked = self.make_state(day=35)
        self.enter_oath_route(system, blocked)
        blocked.calendar.current_day = blocked.oath_order.next_law_day
        self.assertEqual(
            self.execute(
                system,
                blocked,
                SIGN_OATH_ORDER_LAW_COMMAND,
                law_id="shared_meal",
            ).code,
            ErrorCode.OK,
        )
        blocked_rule = {
            item["action_id"]: item
            for item in system.route_view(blocked)["action_rules"]
        }["shared_meal"]
        rejected = self.execute(
            system,
            blocked,
            USE_OATH_ORDER_ACTION_COMMAND,
            action_id="shared_meal",
        )

        self.assertTrue(blocked_rule["facility_required"])
        self.assertEqual(blocked_rule["required_facility_id"], "oath_hall")
        self.assertFalse(blocked_rule["required_facility_running"])
        self.assertEqual(rejected.data["reason"], "route_facility_not_running")

    def test_old_city_day24_activation_and_blocking_event(self) -> None:
        system = self.system()
        state = self.make_state(day=24)
        system.prepare_new_day(state)
        self.assertTrue(state.old_city.is_unlocked)
        self.assertEqual(state.old_city.pending_event_id, "southern_letter")
        view = system.old_city_view(state)
        self.assertEqual(
            view["available_option_ids"], ["publish", "suppress"]
        )
        self.assertEqual(
            [item["option_id"] for item in view["option_previews"]],
            ["publish", "suppress"],
        )
        self.assertEqual(view["unavailable_options"], [])
        warnings = system.evaluate_risks(state)
        self.assertEqual(warnings[0].level, RiskWarningLevel.C_HARD_BLOCK)
        result = self.execute(
            system,
            state,
            RESOLVE_OLD_CITY_COMMAND,
            event_id="southern_letter",
            option_id="publish",
        )
        self.assertEqual(result.code, ErrorCode.OK)
        self.assertGreater(state.old_city.member_count, 0)
        self.assertIsNone(state.old_city.pending_event_id)

    def test_old_city_rejection_and_view_expose_event_specific_options(
        self,
    ) -> None:
        system = self.system()
        state = self.make_state(day=24)
        system.prepare_new_day(state)

        rejected = self.execute(
            system,
            state,
            RESOLVE_OLD_CITY_COMMAND,
            event_id="southern_letter",
            option_id="ask_for_time",
        )

        self.assertEqual(rejected.code, ErrorCode.ILLEGAL_COMMAND)
        self.assertEqual(
            rejected.data["available_option_ids"],
            ["publish", "suppress"],
        )
        self.assertEqual(
            system.old_city_view(state)["available_option_ids"],
            ["publish", "suppress"],
        )

    def test_countdown_view_marks_conditionally_unavailable_options(
        self,
    ) -> None:
        system = self.system()
        state = self.make_state(day=40)
        self.prepare_countdown(
            system,
            state,
            deadline_day=45,
            option_id=None,
        )
        state.old_city.pending_event_id = "countdown"
        state.trust_panic.trust = 49

        view = system.old_city_view(state)

        self.assertEqual(
            view["available_option_ids"],
            ["promise_reduce_old_city", "do_not_stop"],
        )
        self.assertEqual(
            view["unavailable_options"],
            [
                {
                    "option_id": "ask_for_time",
                    "reason": "old_city_time_request_unavailable",
                }
            ],
        )

    def test_countdown_previews_expose_outcomes_without_mutating_state(
        self,
    ) -> None:
        system = self.system()
        state = self.make_state(day=40)
        self.prepare_countdown(
            system,
            state,
            deadline_day=45,
            option_id=None,
        )
        state.old_city.pending_event_id = "countdown"
        before = deepcopy(state)

        view = system.old_city_view(state)

        previews = {
            item["option_id"]: item["preview"]
            for item in view["option_previews"]
        }
        promise = previews["promise_reduce_old_city"]
        self.assertEqual(promise["countdown_day_after"], 45)
        self.assertTrue(promise["promise_active_after"])
        self.assertEqual(
            promise["promise_target_count"],
            state.old_city.middle_threshold - 1,
        )
        self.assertEqual(promise["promise_deadline_day"], 45)
        extension = previews["ask_for_time"]
        self.assertEqual(extension["countdown_day_after"], 47)
        self.assertFalse(extension["promise_active_after"])
        self.assertIsNone(extension["promise_target_count"])
        self.assertIsNone(extension["promise_deadline_day"])
        self.assertNotIn("hidden_growth_days_remaining", view)
        for preview in previews.values():
            self.assertNotIn("hidden_growth_days_remaining", preview)
        self.assertEqual(state, before)

    def test_old_city_view_exposes_active_and_settled_promise_lifecycle(
        self,
    ) -> None:
        system = self.system()
        state = self.make_state(day=40)
        self.prepare_countdown(
            system,
            state,
            deadline_day=45,
            option_id="promise_reduce_old_city",
        )

        active = system.old_city_view(state)
        self.assertTrue(active["promise_active"])
        self.assertEqual(active["promise_created_day"], 40)
        self.assertEqual(
            active["promise_target_count"],
            state.old_city.middle_threshold - 1,
        )
        self.assertEqual(active["promise_deadline_day"], 45)
        self.assertFalse(active["promise_settled"])
        self.assertIsNone(active["promise_outcome"])
        self.assertIsNone(active["promise_settled_day"])
        self.assertNotIn("hidden_growth_days_remaining", active)

        assert state.old_city.promise_target_count is not None
        state.old_city.member_count = state.old_city.promise_target_count
        state.calendar.current_day = 41
        transition = EndDayContext(
            state=state,
            random=DeterministicRandom.from_state(state.random),
            settled_day=40,
            stage=EndDayStage.ADVANCE_DAY,
            _emit=lambda _code, _payload: None,
        )
        system.resolve_old_city_deadline_transition(transition)

        settled = system.old_city_view(state)
        self.assertFalse(settled["promise_active"])
        self.assertTrue(settled["promise_settled"])
        self.assertEqual(settled["promise_outcome"], "success")
        self.assertEqual(settled["promise_settled_day"], 41)
        self.assertEqual(
            settled["promise_target_count"],
            active["promise_target_count"],
        )
        self.assertEqual(settled["promise_deadline_day"], 45)

    def test_pending_old_city_event_blocks_end_day_transactionally(self) -> None:
        system = self.system()
        state = self.make_state(day=24)
        system.prepare_new_day(state)
        engine = EndDayEngine()
        system.install(engine)
        before = deepcopy(state)
        execution = engine.execute(
            state,
            CommandRequest("end-1", END_DAY_COMMAND, {}),
        )
        self.assertEqual(execution.result.code, ErrorCode.END_DAY_BLOCKED)
        self.assertEqual(state, before)

    def test_old_city_threshold_stage_is_once_only(self) -> None:
        system = self.system()
        state = self.make_state(day=24)
        system.prepare_new_day(state)
        self.execute(
            system,
            state,
            RESOLVE_OLD_CITY_COMMAND,
            event_id="southern_letter",
            option_id="publish",
        )
        state.old_city.member_count = state.old_city.low_threshold
        system._advance_old_city_stage(state)
        self.assertEqual(state.old_city.pending_event_id, "rumors")
        self.execute(
            system,
            state,
            RESOLVE_OLD_CITY_COMMAND,
            event_id="rumors",
            option_id="public_explain",
        )
        state.old_city.member_count = state.old_city.low_threshold
        system._advance_old_city_stage(state)
        self.assertIsNone(state.old_city.pending_event_id)
        self.assertEqual(state.old_city.stage_events_seen.count("rumors"), 1)

    def test_day37_arrival_delta_is_consumed_by_old_city(self) -> None:
        system = self.system()
        state = self.make_state(day=37)
        system.prepare_new_day(state)
        self.execute(
            system,
            state,
            RESOLVE_OLD_CITY_COMMAND,
            event_id="southern_letter",
            option_id="publish",
        )
        before = state.old_city.member_count
        state.events.metrics["pending_old_city_arrival_delta"] = -5
        system.update_old_city(self.context(state))
        self.assertNotIn("pending_old_city_arrival_delta", state.events.metrics)
        self.assertLess(state.old_city.member_count, before + 1)

    def test_old_city_promise_has_success_and_failure_lifecycle(self) -> None:
        system = self.system()
        state = self.make_state(day=40)
        self.prepare_countdown(
            system,
            state,
            deadline_day=45,
            option_id="promise_reduce_old_city",
        )
        assert state.old_city.promise_target_count is not None
        state.old_city.member_count = max(
            state.old_city.promise_target_count - 10, 0
        )
        system.update_old_city(self.context(state))
        self.assertTrue(state.old_city.promise_active)
        state.calendar.current_day = 41
        transition = EndDayContext(
            state=state,
            random=DeterministicRandom.from_state(state.random),
            settled_day=40,
            stage=EndDayStage.ADVANCE_DAY,
            _emit=lambda _code, _payload: None,
        )
        system.resolve_old_city_deadline_transition(transition)
        self.assertTrue(state.old_city.promise_settled)
        self.assertEqual(state.old_city.promise_outcome, "success")

    def test_final_settlement_records_actual_low_stock_losses_and_machine_id(self) -> None:
        system = self.system()
        state = self.make_state(day=44)
        self.add_rejected_arrival_history(state, through_day=44)
        state.resources.cooked_food = 1
        state.resources.coal = 1
        state.resources.wood = 1
        state.resources.steel = 1
        dead_before = state.population.population_dead
        alive_before = state.population.population_alive
        self.prepare_countdown(
            system,
            state,
            deadline_day=48,
            option_id="do_not_stop",
        )
        self.assertTrue(state.old_city.resolved)
        self.assertLess(state.population.population_alive, alive_before)
        self.assertEqual(state.population.population_dead, dead_before)
        self.assertGreaterEqual(state.population.engineers, 2)
        self.assertEqual(state.old_city.result_id, "large_exodus")
        self.assertEqual(
            state.old_city.settlement_resource_losses,
            {"cooked_food": 1, "coal": 1, "wood": 1, "steel": 1},
        )
        self.assertEqual(
            decode_game_state(encode_game_state(state)), state
        )

    def test_countdown_deadline_resolves_before_day48_with_ordered_logs(self) -> None:
        system = self.system()
        state = self.make_state(day=40)
        self.prepare_countdown(system, state, deadline_day=40)

        execution = self.end_day(system, state)

        self.assertEqual(execution.result.code, ErrorCode.OK)
        self.assertEqual(state.calendar.current_day, 41)
        self.assertTrue(state.old_city.resolved)
        codes = [item.code for item in execution.logs]
        ordered = [
            codes.index("deadline_day_end_state"),
            codes.index("promise_resolution"),
            codes.index("old_city_final_resolution"),
        ]
        self.assertEqual(ordered, sorted(ordered))

    def test_deadline_transition_validation_failure_rolls_back_and_skips_autosave(
        self,
    ) -> None:
        system = self.system()
        state = self.make_state(day=40)
        self.prepare_countdown(system, state, deadline_day=40)
        before = deepcopy(state)
        autosaves = []
        engine = EndDayEngine(autosave_sink=autosaves.append)
        system.install(engine)

        def corrupt_after_resolution(context: EndDayContext) -> None:
            context.state.old_city.result_id = "forged_result"

        engine.register_new_day_context_handler(corrupt_after_resolution)
        execution = engine.execute(
            state,
            CommandRequest(
                "end-corrupt",
                END_DAY_COMMAND,
                {},
                state.command_sequence,
            ),
        )

        self.assertEqual(execution.result.code, ErrorCode.INTERNAL_ERROR)
        self.assertEqual(state, before)
        self.assertEqual(autosaves, [])

    def test_countdown_extension_resolves_only_after_extended_deadline(self) -> None:
        system = self.system()
        state = self.make_state(day=40)
        self.prepare_countdown(
            system,
            state,
            deadline_day=40,
            option_id="ask_for_time",
        )
        self.assertEqual(state.old_city.countdown_day, 42)

        self.assertEqual(self.end_day(system, state).result.code, ErrorCode.OK)
        self.assertFalse(state.old_city.resolved)
        self.assertEqual(self.end_day(system, state).result.code, ErrorCode.OK)
        self.assertFalse(state.old_city.resolved)
        final = self.end_day(system, state)
        self.assertEqual(final.result.code, ErrorCode.OK)
        self.assertTrue(state.old_city.resolved)
        self.assertEqual(state.old_city.settlement_day, 42)

    def test_deadline_day_is_playable_then_promise_fails_next_day(self) -> None:
        system = self.system()
        state = self.make_state(day=45)
        self.prepare_countdown(
            system,
            state,
            deadline_day=45,
            option_id="promise_reduce_old_city",
        )
        system.update_old_city(self.context(state))
        self.assertTrue(state.old_city.promise_active)
        self.assertFalse(state.old_city.promise_settled)

        execution = self.end_day(system, state)

        self.assertEqual(execution.result.code, ErrorCode.OK)
        self.assertEqual(state.calendar.current_day, 46)
        self.assertEqual(state.old_city.promise_outcome, "failure")
        self.assertEqual(state.old_city.promise_settled_day, 46)
        self.assertTrue(state.old_city.resolved)

    def test_deadline_final_state_settles_promise_before_old_city_result(self) -> None:
        system = self.system()
        state = self.make_state(day=45)
        self.prepare_countdown(
            system,
            state,
            deadline_day=45,
            option_id="promise_reduce_old_city",
        )
        assert state.old_city.promise_target_count is not None
        state.old_city.member_count = max(
            state.old_city.promise_target_count - 4, 0
        )

        execution = self.end_day(system, state)

        self.assertEqual(execution.result.code, ErrorCode.OK)
        self.assertEqual(state.old_city.promise_outcome, "success")
        self.assertEqual(state.old_city.result_id, "scattered")
        payloads = {
            item.code: item.payload
            for item in execution.logs
            if item.code
            in {
                "deadline_day_end_state",
                "promise_resolution",
                "old_city_final_resolution",
            }
        }
        self.assertEqual(payloads["promise_resolution"]["outcome"], "success")
        self.assertEqual(
            payloads["old_city_final_resolution"]["result_id"], "scattered"
        )

    def test_old_city_resource_losses_cover_zero_and_sufficient_stock(self) -> None:
        system = self.system()
        for stock in (0, 1000):
            with self.subTest(stock=stock):
                state = self.make_state(day=44)
                self.add_rejected_arrival_history(state, through_day=44)
                self.prepare_countdown(system, state, deadline_day=48)
                state.resources.cooked_food = stock
                state.resources.coal = stock
                state.resources.wood = stock
                state.resources.steel = stock

                settlement = system._settle_old_city(state)
                departed = settlement["actual_departures"]
                expected_theoretical = {
                    "cooked_food": departed * 2,
                    "coal": departed * 3,
                    "wood": departed * 2,
                    "steel": departed,
                }
                expected = {
                    key: min(stock, value)
                    for key, value in expected_theoretical.items()
                }
                self.assertEqual(settlement["resource_losses"], expected)
                self.assertEqual(
                    decode_game_state(encode_game_state(state)), state
                )

    def test_partial_and_large_exodus_ids_survive_v10_round_trip(self) -> None:
        system = self.system()
        for result_id, member_count in (
            ("partial_exodus", "middle"),
            ("large_exodus", "high"),
        ):
            with self.subTest(result_id=result_id):
                state = self.make_state(day=44)
                self.add_rejected_arrival_history(state, through_day=44)
                self.prepare_countdown(system, state, deadline_day=48)
                state.old_city.member_count = (
                    state.old_city.middle_threshold
                    if member_count == "middle"
                    else state.old_city.high_threshold
                )
                system._settle_old_city(state)
                self.assertEqual(state.old_city.result_id, result_id)
                restored = decode_game_state(encode_game_state(state))
                self.assertEqual(restored.old_city.result_id, result_id)

    def test_departure_caps_actual_count_to_protect_critical_jobs(self) -> None:
        system = self.system()
        state = self.make_state(day=44)
        population = state.population
        population.population_total = 6
        population.population_alive = 6
        population.workers = 4
        population.engineers = 2
        population.children = 0
        population.medical_apprentices = 0
        population.engineering_apprentices = 0
        population.healthy_population = 6
        population.sick_population = 0
        population.critical_population = 0
        population.disabled_population = 0
        population.housed_population = 6
        population.homeless_population = 0
        for building_id, building_type in (
            ("critical-canteen", "canteen"),
            ("critical-hunt", "hunting_lodge"),
            ("critical-greenhouse", "greenhouse"),
        ):
            state.buildings[building_id] = BuildingState(
                building_id=building_id,
                building_type=building_type,
                zone="middle_ring",
                slot_size=2,
                is_built=True,
                is_operational=True,
                assigned_workers=1,
            )
        coal = state.surface_resource_points["surface-coal-1"]
        coal.assigned_workers = 1
        old = state.old_city
        old.is_unlocked = True
        old.reference_population = 6
        old.low_threshold = 1
        old.middle_threshold = 2
        old.high_threshold = 3
        old.active_stage_id = "countdown"
        old.stage_events_seen = [
            "southern_letter",
            "rumors",
            "public_gathering",
            "countdown",
        ]
        old.countdown_day = 48
        old.member_count = 3

        settlement = system._settle_old_city(state)

        self.assertEqual(settlement["theoretical_departures"], 1)
        self.assertEqual(settlement["actual_departures"], 0)
        self.assertEqual(settlement["protected_engineers"], 2)
        self.assertEqual(
            settlement["reduction_reason"],
            "critical_jobs_and_engineer_floor",
        )
        self.assertEqual(
            set(settlement["protected_jobs"]),
            {
                "building:critical-canteen",
                "building:critical-greenhouse",
                "building:critical-hunt",
                "resource:surface-coal-1",
            },
        )
        self.assertTrue(
            all(
                state.buildings[building_id].assigned_workers == 1
                for building_id in (
                    "critical-canteen",
                    "critical-hunt",
                    "critical-greenhouse",
                )
            )
        )
        self.assertEqual(coal.assigned_workers, 1)

    def test_departure_resynchronizes_medical_capacity_after_staff_loss(
        self,
    ) -> None:
        system = self.system()
        state = self.make_state(day=44)
        state.population.population_total = 5
        state.population.population_alive = 5
        state.population.workers = 0
        state.population.engineers = 5
        state.population.children = 0
        state.population.sick_population = 3
        state.population.healthy_population = 2
        state.population.critical_population = 0
        state.population.disabled_population = 0
        state.population.housed_population = 5
        state.population.homeless_population = 0
        state.buildings["medical-1"] = BuildingState(
            building_id="medical-1",
            building_type="medical_station",
            zone="inner_ring",
            slot_size=2,
            is_built=True,
            is_operational=True,
            assigned_engineers=5,
        )
        state.medical.building_capacity = 10
        state.medical.effective_capacity = (
            state.medical.temporary_capacity + 10
        )
        state.medical.medical_pressure = 0

        departure = system._remove_population(state, requested=4)

        self.assertEqual(departure["actual_departures"], 3)
        self.assertEqual(state.population.engineers, 2)
        self.assertEqual(
            state.buildings["medical-1"].assigned_engineers, 2
        )
        self.assertEqual(state.medical.building_capacity, 4)
        self.assertEqual(
            state.medical.effective_capacity,
            state.medical.temporary_capacity + 4,
        )
        self.assertEqual(state.medical.medical_pressure, 0)

    def test_protected_job_summary_remains_historical_after_reassignment(
        self,
    ) -> None:
        system = self.system()
        state = self.make_state(day=44)
        self.add_rejected_arrival_history(state, through_day=44)
        self.prepare_countdown(system, state, deadline_day=48)
        coal = state.surface_resource_points["surface-coal-1"]
        coal.assigned_workers = 1

        system._settle_old_city(state)

        self.assertEqual(
            state.old_city.protected_jobs["resource:surface-coal-1"], 1
        )
        coal.assigned_workers = 0
        self.assertEqual(decode_game_state(encode_game_state(state)), state)

    def test_capped_resource_losses_survive_cross_day_restock(self) -> None:
        system = self.system()
        state = self.make_state(day=44)
        self.add_rejected_arrival_history(state, through_day=44)
        self.prepare_countdown(system, state, deadline_day=44)
        resources = ("cooked_food", "coal", "wood", "steel")
        for resource in resources:
            setattr(state.resources, resource, 1)

        settlement = system._settle_old_city(state)

        self.assertEqual(
            settlement["resource_losses"],
            {resource: 1 for resource in resources},
        )
        self.assertEqual(self.end_day(system, state).result.code, ErrorCode.OK)
        self.assertEqual(state.calendar.current_day, 45)
        for resource in resources:
            setattr(state.resources, resource, 7)
        self.assertEqual(decode_game_state(encode_game_state(state)), state)

    def test_new_day_settlement_rechecks_both_hard_fail_axes(self) -> None:
        cases = (
            (
                "trust_without_final_oath",
                None,
                16,
                30,
                HardFailType.TRUST_EXILE,
                None,
                0,
            ),
            (
                "trust_with_final_oath",
                "oath",
                16,
                30,
                None,
                "oath_carried_zero_trust",
                1,
            ),
            (
                "panic_without_highest_order",
                None,
                50,
                84,
                HardFailType.PANIC_EXPELLED,
                None,
                0,
            ),
            (
                "panic_with_highest_order",
                "iron",
                50,
                84,
                None,
                "decree_carried_panic",
                1,
            ),
        )
        for (
            name,
            route,
            trust,
            panic,
            expected_fail,
            expected_tag,
            expected_new_day_calls,
        ) in cases:
            with self.subTest(name=name):
                system = self.system()
                state = self.make_state(day=35 if route else 45)
                if route == "oath":
                    self.sign_full_oath_route(system, state)
                elif route == "iron":
                    self.sign_full_iron_route(system, state)
                self.prepare_countdown(
                    system,
                    state,
                    deadline_day=45,
                    option_id="promise_reduce_old_city",
                )
                state.old_city.member_count = state.old_city.high_threshold
                state.trust_panic.trust = trust
                state.trust_panic.panic = panic
                new_day_calls: list[int] = []
                engine = EndDayEngine()
                system.install(engine)
                engine.register_new_day_handler(
                    lambda current, calls=new_day_calls: calls.append(
                        current.calendar.current_day
                    )
                )

                execution = engine.execute(
                    state,
                    CommandRequest(
                        f"end-{name}",
                        END_DAY_COMMAND,
                        {},
                        state.command_sequence,
                    ),
                )

                self.assertEqual(execution.result.code, ErrorCode.OK)
                self.assertEqual(
                    state.old_city.promise_outcome, "failure"
                )
                self.assertEqual(state.old_city.result_id, "large_exodus")
                self.assertEqual(
                    state.final_result.hard_fail_type, expected_fail
                )
                self.assertEqual(
                    execution.result.data["transition"],
                    "hard_fail" if expected_fail is not None else "next_day",
                )
                self.assertEqual(len(new_day_calls), expected_new_day_calls)
                if expected_tag is not None:
                    self.assertIn(
                        expected_tag,
                        state.oath_order.ending_tag_candidates,
                    )
                recheck_logs = [
                    item
                    for item in execution.logs
                    if item.code
                    == "end_day.new_day_hard_fail_rechecked"
                ]
                self.assertEqual(len(recheck_logs), 1)
                self.assertEqual(
                    recheck_logs[0].payload[
                        "new_day_handlers_skipped"
                    ],
                    expected_fail is not None,
                )

    def test_final_oath_only_rewrites_trust_axis(self) -> None:
        system = self.system()
        state = self.make_state(day=35)
        self.sign_full_oath_route(system, state)
        state.trust_panic.trust = 0
        state.trust_panic.panic = 90
        system.check_hard_fails(
            self.context(state, EndDayStage.CHECK_HARD_FAILS)
        )
        self.assertIsNone(state.final_result.hard_fail_type)
        self.assertIn(
            "oath_carried_zero_trust", state.oath_order.ending_tag_candidates
        )
        state.trust_panic.panic = 100
        system.check_hard_fails(
            self.context(state, EndDayStage.CHECK_HARD_FAILS)
        )
        self.assertEqual(
            state.final_result.hard_fail_type, HardFailType.PANIC_EXPELLED
        )

    def test_hard_fail_is_committed_and_autosaved_at_end_day(self) -> None:
        system = self.system()
        state = self.make_state(day=1)
        state.trust_panic.trust = 0
        engine = EndDayEngine()
        system.install(engine)
        execution = engine.execute(
            state,
            CommandRequest("end-1", END_DAY_COMMAND, {}),
        )
        self.assertEqual(execution.result.code, ErrorCode.OK)
        self.assertEqual(
            state.final_result.hard_fail_type, HardFailType.TRUST_EXILE
        )
        self.assertEqual(state.calendar.current_day, 1)
        self.assertIsNotNone(execution.autosave)

    def test_highest_order_only_rewrites_panic_axis(self) -> None:
        system = self.system()
        state = self.make_state(day=35)
        self.sign_full_iron_route(system, state)
        state.trust_panic.trust = 10
        state.trust_panic.panic = 100
        system.check_hard_fails(
            self.context(state, EndDayStage.CHECK_HARD_FAILS)
        )
        self.assertIsNone(state.final_result.hard_fail_type)
        self.assertIn(
            "decree_carried_panic", state.oath_order.ending_tag_candidates
        )
        state.trust_panic.trust = 0
        system.check_hard_fails(
            self.context(state, EndDayStage.CHECK_HARD_FAILS)
        )
        self.assertEqual(
            state.final_result.hard_fail_type, HardFailType.TRUST_EXILE
        )

    def test_population_zero_is_never_immunized(self) -> None:
        system = self.system()
        state = self.make_state(day=35)
        self.sign_full_oath_route(system, state)
        state.population.population_alive = 0
        state.population.population_total = state.population.population_dead
        state.population.healthy_population = 0
        state.population.sick_population = 0
        state.population.critical_population = 0
        state.population.disabled_population = 0
        system.check_hard_fails(
            self.context(state, EndDayStage.CHECK_HARD_FAILS)
        )
        self.assertEqual(
            state.final_result.hard_fail_type, HardFailType.POPULATION_ZERO
        )

    def test_v9_migration_and_v10_round_trip(self) -> None:
        state = self.make_state()
        document = encode_game_state(state)
        document["save_data_version"] = 9
        migrated = decode_game_state(document)
        self.assertEqual(migrated.save_data_version, CURRENT_SAVE_DATA_VERSION)
        self.assertEqual(migrated.oath_order.selected_route, None)
        self.assertEqual(
            decode_game_state(encode_game_state(migrated)), migrated
        )

    def test_v9_migration_accepts_day24_boundary_and_pending_activation(self) -> None:
        for activation_pending in (False, True):
            with self.subTest(activation_pending=activation_pending):
                state = self.make_state(day=24)
                self.add_rejected_arrival_history(state, through_day=24)
                state.old_city.activation_pending = activation_pending
                document = encode_game_state(state)
                document["save_data_version"] = 9

                migrated = decode_game_state(document)

                self.assertEqual(migrated.calendar.current_day, 24)
                self.assertEqual(
                    migrated.old_city.activation_pending,
                    activation_pending,
                )

    def test_v9_migration_rejects_day25_and_day30_old_city_gaps(self) -> None:
        for day in (25, 30):
            with self.subTest(day=day):
                state = self.make_state(day=day)
                self.add_rejected_arrival_history(state, through_day=day)
                document = encode_game_state(state)
                document["save_data_version"] = 9
                with self.assertRaisesRegex(
                    SaveDataError, "after day 24"
                ):
                    decode_game_state(document)

    def test_v9_day24_migration_still_requires_fixed_arrival_history(self) -> None:
        state = self.make_state(day=24)
        document = encode_game_state(state)
        document["save_data_version"] = 9
        with self.assertRaises(SaveDataError):
            decode_game_state(document)

    def test_route_facility_tampering_is_rejected(self) -> None:
        state = self.make_state()
        document = encode_game_state(state)
        document["oath_order"]["oath_hall"]["visible"] = True
        with self.assertRaises(SaveDataError):
            decode_game_state(document)

    def test_patch_008_lifecycle_tampering_is_rejected(self) -> None:
        system = self.system()
        state = self.make_state(day=24)
        system.prepare_new_day(state)
        base = encode_game_state(state)
        mutations = []

        wrong_pending = deepcopy(base)
        wrong_pending["old_city"]["pending_event_id"] = "rumors"
        mutations.append(wrong_pending)

        skipped_stage = deepcopy(base)
        skipped_stage["old_city"]["active_stage_id"] = "countdown"
        skipped_stage["old_city"]["pending_event_id"] = "countdown"
        skipped_stage["old_city"]["stage_events_seen"] = [
            "southern_letter", "countdown"
        ]
        skipped_stage["old_city"]["countdown_day"] = 29
        mutations.append(skipped_stage)

        route = self.make_state(day=35)
        self.enter_oath_route(system, route)
        bad_cooldown = encode_game_state(route)
        bad_cooldown["oath_order"]["next_law_day"] += 1
        mutations.append(bad_cooldown)

        settled = self.make_state(day=44)
        self.add_rejected_arrival_history(settled, through_day=44)
        self.prepare_countdown(system, settled, deadline_day=48)
        system._settle_old_city(settled)
        wrong_result = encode_game_state(settled)
        wrong_result["old_city"]["result_id"] = "large_departure"
        mutations.append(wrong_result)

        impossible_loss = encode_game_state(settled)
        impossible_loss["old_city"]["settlement_resource_losses"]["coal"] += 1
        mutations.append(impossible_loss)

        for document in mutations:
            with self.subTest(document=document), self.assertRaises(SaveDataError):
                decode_game_state(document)


if __name__ == "__main__":
    unittest.main()
