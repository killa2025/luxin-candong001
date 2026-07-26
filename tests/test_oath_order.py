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
from furnace_winter.interface import CommandRequest, ErrorCode
from furnace_winter.models import (
    CURRENT_SAVE_DATA_VERSION,
    DeterministicRandom,
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

    def test_old_city_day24_activation_and_blocking_event(self) -> None:
        system = self.system()
        state = self.make_state(day=24)
        system.prepare_new_day(state)
        self.assertTrue(state.old_city.is_unlocked)
        self.assertEqual(state.old_city.pending_event_id, "southern_letter")
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
        system.prepare_new_day(state)
        self.execute(
            system,
            state,
            RESOLVE_OLD_CITY_COMMAND,
            event_id="southern_letter",
            option_id="publish",
        )
        state.old_city.active_stage_id = "countdown"
        state.old_city.member_count = state.old_city.high_threshold
        state.old_city.countdown_day = 45
        state.old_city.pending_event_id = "countdown"
        state.old_city.stage_events_seen = [
            "southern_letter", "rumors", "public_gathering", "countdown"
        ]
        result = self.execute(
            system,
            state,
            RESOLVE_OLD_CITY_COMMAND,
            event_id="countdown",
            option_id="promise_reduce_old_city",
        )
        self.assertEqual(result.code, ErrorCode.OK)
        assert state.old_city.promise_target_count is not None
        state.old_city.member_count = state.old_city.promise_target_count
        system.update_old_city(self.context(state))
        self.assertTrue(state.old_city.promise_settled)
        self.assertEqual(state.old_city.promise_outcome, "success")

    def test_final_settlement_removes_people_without_deaths_or_negative_resources(self) -> None:
        system = self.system()
        state = self.make_state(day=44)
        state.resources.cooked_food = 1
        state.resources.coal = 1
        state.resources.wood = 1
        state.resources.steel = 1
        system.prepare_new_day(state)
        self.execute(
            system,
            state,
            RESOLVE_OLD_CITY_COMMAND,
            event_id="southern_letter",
            option_id="publish",
        )
        state.old_city.active_stage_id = "countdown"
        state.old_city.member_count = state.old_city.high_threshold
        state.old_city.countdown_day = 48
        state.old_city.pending_event_id = "countdown"
        state.old_city.stage_events_seen = [
            "southern_letter", "rumors", "public_gathering", "countdown"
        ]
        dead_before = state.population.population_dead
        alive_before = state.population.population_alive
        result = self.execute(
            system,
            state,
            RESOLVE_OLD_CITY_COMMAND,
            event_id="countdown",
            option_id="do_not_stop",
        )
        self.assertEqual(result.code, ErrorCode.OK)
        self.assertTrue(state.old_city.resolved)
        self.assertLess(state.population.population_alive, alive_before)
        self.assertEqual(state.population.population_dead, dead_before)
        self.assertGreaterEqual(state.population.engineers, 2)
        self.assertTrue(
            all(
                value >= 0
                for value in (
                    state.resources.cooked_food,
                    state.resources.coal,
                    state.resources.wood,
                    state.resources.steel,
                )
            )
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

        for document in mutations:
            with self.subTest(document=document), self.assertRaises(SaveDataError):
                decode_game_state(document)


if __name__ == "__main__":
    unittest.main()
