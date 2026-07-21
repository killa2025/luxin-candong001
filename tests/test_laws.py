from __future__ import annotations

import unittest
from copy import deepcopy
from pathlib import Path

from furnace_winter.config import load_building_rules, load_law_rules, load_survival_rules
from furnace_winter.gameplay import (
    ASSIGN_COMMAND,
    BUILD_COMMAND,
    CONFIRM_END_DAY_COMMAND,
    END_DAY_COMMAND,
    MEDICAL_RATION_COMMAND,
    OVERTIME_COMMAND,
    SET_RATION_COMMAND,
    SET_WORKTIME_COMMAND,
    SIGN_LAW_COMMAND,
    TRIAGE_COMMAND,
    BuildingSystem,
    EndDayEngine,
    LawSystem,
    SurvivalSystem,
    create_initial_survival_state,
)
from furnace_winter.interface import CommandRequest, ErrorCode
from furnace_winter.models import CURRENT_SAVE_DATA_VERSION, decode_game_state, encode_game_state


ROOT = Path(__file__).resolve().parents[1]


class LawPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.survival_rules = load_survival_rules(ROOT / "data" / "survival.json")
        cls.building_rules = load_building_rules(ROOT / "data" / "buildings.json")
        cls.law_rules = load_law_rules(ROOT / "data" / "laws.json")

    def make_state(self):
        return create_initial_survival_state(self.survival_rules, self.building_rules, random_seed=5005)

    def law_system(self) -> LawSystem:
        return LawSystem(self.law_rules, self.building_rules, self.survival_rules)

    def building_system(self) -> BuildingSystem:
        return BuildingSystem(self.building_rules, self.survival_rules)

    def execute_law(self, state, name: str, arguments: dict | None = None, command_id: str = "law"):
        return self.law_system().execute(
            state,
            CommandRequest(
                command_id,
                name,
                arguments or {},
                expected_state_sequence=state.command_sequence,
            ),
        )

    def execute_building(self, state, name: str, arguments: dict, command_id: str = "building"):
        return self.building_system().execute(
            state,
            CommandRequest(
                command_id,
                name,
                arguments,
                expected_state_sequence=state.command_sequence,
            ),
        )

    def engine(self) -> EndDayEngine:
        engine = EndDayEngine()
        SurvivalSystem(self.survival_rules, self.building_rules).install(engine)
        self.building_system().install(engine)
        self.law_system().install(engine)
        return engine

    @staticmethod
    def settle(engine: EndDayEngine, state):
        execution = engine.execute(
            state,
            CommandRequest("end", END_DAY_COMMAND, expected_state_sequence=state.command_sequence),
        )
        if execution.result.code is ErrorCode.END_DAY_CONFIRMATION_REQUIRED:
            execution = engine.execute(
                state,
                CommandRequest(
                    "confirm",
                    CONFIRM_END_DAY_COMMAND,
                    execution.result.data["confirmation"],
                    expected_state_sequence=state.command_sequence,
                ),
            )
        return execution

    def sign(self, state, law_id: str, *, confirm: bool = False):
        arguments = {"law_id": law_id}
        if confirm:
            arguments["confirm"] = True
        return self.execute_law(state, SIGN_LAW_COMMAND, arguments, f"sign-{law_id}")

    def advance_to_law_day(self, state) -> None:
        state.calendar.current_day = state.laws.cooldowns.get("ordinary_law", state.calendar.current_day)

    def test_signing_uses_three_day_cooldown_and_unlocks_without_auto_building(self) -> None:
        state = self.make_state()
        signed = self.sign(state, "basic_medical_law")
        self.assertTrue(signed.accepted)
        self.assertEqual(signed.data["next_ordinary_law_day"], 4)
        self.assertEqual(signed.data["unlocked_building_ids"], ["medical_station"])
        self.assertFalse(any(item.building_type == "medical_station" for item in state.buildings.values()))

        before = deepcopy(state)
        blocked = self.sign(state, "firepit_law")
        self.assertEqual(blocked.code, ErrorCode.ILLEGAL_COMMAND)
        self.assertEqual(blocked.data["reason"], "law_cooldown_active")
        self.assertEqual(state, before)

    def test_route_prerequisites_and_mutual_exclusion_are_strict(self) -> None:
        state = self.make_state()
        self.assertTrue(self.sign(state, "coarse_soup_law").accepted)
        self.advance_to_law_day(state)
        before = deepcopy(state)
        conflict = self.sign(state, "rice_porridge_law")
        self.assertEqual(conflict.data["reason"], "law_route_locked")
        self.assertEqual(state, before)
        self.assertEqual(state.social_policy.current_ration_mode, "normal")

    def test_firepit_is_auto_enabled_without_build_or_slots(self) -> None:
        state = self.make_state()
        slots = deepcopy(state.building_management.zone_slots_used)
        panic = state.trust_panic.panic
        result = self.sign(state, "firepit_law")
        self.assertTrue(result.accepted)
        self.assertTrue(state.social_policy.firepit_enabled)
        self.assertEqual(state.building_management.zone_slots_used, slots)
        self.assertNotIn("firepit", (item.building_type for item in state.buildings.values()))
        self.assertEqual(state.trust_panic.panic, panic - 1)

    def test_emergency_ration_is_confirmed_day_only_and_restores_previous_mode(self) -> None:
        state = self.make_state()
        canteen = self.execute_building(state, BUILD_COMMAND, {"building_type": "canteen", "zone": "inner_ring"})
        self.execute_building(state, ASSIGN_COMMAND, {"building_id": canteen.data["building_id"], "population_type": "workers", "count": 5})
        self.assertTrue(self.sign(state, "coarse_soup_law").accepted)
        self.assertTrue(self.execute_law(state, SET_RATION_COMMAND, {"mode": "coarse_soup"}).accepted)
        state.social_policy.consecutive_ration_days = 6
        self.advance_to_law_day(state)
        self.assertTrue(self.sign(state, "emergency_ration_law").accepted)
        state.resources.raw_food = 0
        before = deepcopy(state)
        rejected = self.execute_law(state, SET_RATION_COMMAND, {"mode": "emergency", "confirm": False})
        self.assertEqual(rejected.data["reason"], "confirmation_required")
        self.assertEqual(state, before)
        self.assertTrue(self.execute_law(state, SET_RATION_COMMAND, {"mode": "emergency", "confirm": True}).accepted)
        cooked_before = state.resources.cooked_food
        settled = self.settle(self.engine(), state)
        self.assertTrue(settled.result.accepted)
        self.assertEqual(cooked_before - state.resources.cooked_food, 40)
        self.assertEqual(state.social_policy.current_ration_mode, "coarse_soup")
        self.assertIsNone(state.social_policy.previous_ration_mode)
        self.assertEqual(state.social_policy.consecutive_ration_days, 6)

    def test_overtime_doubles_target_production_and_resets_after_day(self) -> None:
        state = self.make_state()
        canteen = self.execute_building(state, BUILD_COMMAND, {"building_type": "canteen", "zone": "inner_ring"})
        self.execute_building(state, ASSIGN_COMMAND, {"building_id": canteen.data["building_id"], "population_type": "workers", "count": 5})
        self.assertTrue(self.sign(state, "overtime_law").accepted)
        rejected = self.execute_law(state, OVERTIME_COMMAND, {"building_id": canteen.data["building_id"], "confirm": False})
        self.assertEqual(rejected.data["reason"], "confirmation_required")
        self.assertTrue(self.execute_law(state, OVERTIME_COMMAND, {"building_id": canteen.data["building_id"], "confirm": True}).accepted)
        state.resources.raw_food = 200
        self.assertTrue(self.settle(self.engine(), state).result.accepted)
        self.assertEqual(state.resources.raw_food, 80)
        self.assertEqual(state.population.sick_population, 0)
        self.assertIsNone(state.social_policy.overtime_building_id)

    def test_long_shift_persists_and_applies_integer_output_multiplier(self) -> None:
        state = self.make_state()
        lodge = self.execute_building(state, BUILD_COMMAND, {"building_type": "hunting_lodge", "zone": "outer_ring"})
        self.execute_building(state, ASSIGN_COMMAND, {"building_id": lodge.data["building_id"], "population_type": "workers", "count": 15})
        self.assertTrue(self.sign(state, "overtime_law").accepted)
        self.advance_to_law_day(state)
        self.assertTrue(self.sign(state, "long_shift_law").accepted)
        self.assertTrue(self.execute_law(state, SET_WORKTIME_COMMAND, {"mode": "long_shift"}).accepted)
        raw_before = state.resources.raw_food
        self.assertTrue(self.settle(self.engine(), state).result.accepted)
        self.assertEqual(state.resources.raw_food - raw_before, 50)
        self.assertEqual(state.population.sick_population, 0)
        self.assertEqual(state.social_policy.current_worktime_mode, "long_shift")
        self.assertEqual(state.social_policy.consecutive_long_shift_days, 1)

    def test_long_shift_fraction_is_saved_as_an_exact_remainder(self) -> None:
        state = self.make_state()
        state.furnace.mode_id = "off"
        state.furnace.is_active = False
        state.technologies.researched_tech_ids.append("tech_wood_processing_1")
        camp = self.execute_building(
            state,
            BUILD_COMMAND,
            {
                "building_type": "logging_camp",
                "zone": "outer_ring",
                "binding_id": "forest-zone-1",
            },
        )
        self.execute_building(
            state,
            ASSIGN_COMMAND,
            {
                "building_id": camp.data["building_id"],
                "population_type": "workers",
                "count": 1,
            },
        )
        self.assertTrue(self.sign(state, "overtime_law").accepted)
        self.advance_to_law_day(state)
        self.assertTrue(self.sign(state, "long_shift_law").accepted)
        self.assertTrue(
            self.execute_law(state, SET_WORKTIME_COMMAND, {"mode": "long_shift"}).accepted
        )

        outputs = []
        previous_wood = state.resources.wood
        engine = self.engine()
        for _day in range(3):
            self.assertTrue(self.settle(engine, state).result.accepted)
            outputs.append(state.resources.wood - previous_wood)
            previous_wood = state.resources.wood

        building = state.buildings[camp.data["building_id"]]
        self.assertEqual(outputs, [3, 5, 5])
        self.assertEqual(building.production_multiplier_remainder_numerator, 3)
        self.assertEqual(building.production_multiplier_remainder_denominator, 4)
        restored = decode_game_state(encode_game_state(state))
        self.assertEqual(restored, state)

    def test_medical_ration_uses_actual_patients_and_only_cooked_food(self) -> None:
        state = self.make_state()
        self.assertTrue(self.sign(state, "basic_medical_law").accepted)
        station = self.execute_building(state, BUILD_COMMAND, {"building_type": "medical_station", "zone": "inner_ring"})
        self.execute_building(state, ASSIGN_COMMAND, {"building_id": station.data["building_id"], "population_type": "engineers", "count": 5})
        self.advance_to_law_day(state)
        self.assertTrue(self.sign(state, "medical_ration_law").accepted)
        state.population.healthy_population = 60
        state.population.sick_population = 15
        state.population.critical_population = 5
        state.medical.medical_pressure = 15
        cooked_before = state.resources.cooked_food
        result = self.execute_law(state, MEDICAL_RATION_COMMAND, {"confirm": True})
        self.assertTrue(result.accepted)
        self.assertEqual(result.data["affected_patients"], 20)
        self.assertEqual(result.data["cooked_food_paid"], 60)
        self.assertEqual(state.resources.cooked_food, cooked_before - 60)
        self.assertEqual(state.population.sick_population, 0)
        self.assertEqual(state.population.critical_population, 5)
        self.assertEqual(state.medical.critical_treatment_progress, 5)
        self.assertEqual(result.data["balance_status"], "TEST_NUMERIC")

    def test_triage_interface_rejects_unsealed_balance_without_mutation(self) -> None:
        state = self.make_state()
        self.assertTrue(self.sign(state, "basic_medical_law").accepted)
        station = self.execute_building(
            state,
            BUILD_COMMAND,
            {"building_type": "medical_station", "zone": "inner_ring"},
        )
        self.execute_building(
            state,
            ASSIGN_COMMAND,
            {
                "building_id": station.data["building_id"],
                "population_type": "engineers",
                "count": 5,
            },
        )
        self.advance_to_law_day(state)
        self.assertTrue(self.sign(state, "expanded_admission_law").accepted)
        self.advance_to_law_day(state)
        self.assertTrue(self.sign(state, "medical_ration_law").accepted)
        self.advance_to_law_day(state)
        self.assertTrue(self.sign(state, "triage_law", confirm=True).accepted)
        state.population.healthy_population = 69
        state.population.sick_population = 11
        state.medical.medical_pressure = 6
        before = deepcopy(state)
        invalid = self.execute_law(
            state,
            TRIAGE_COMMAND,
            {"building_id": "missing", "confirm": True},
        )
        self.assertEqual(invalid.data["reason"], "unknown_building")
        self.assertEqual(state, before)
        result = self.execute_law(
            state,
            TRIAGE_COMMAND,
            {"building_id": station.data["building_id"], "confirm": True},
        )
        self.assertEqual(result.data["reason"], "triage_balance_not_sealed")
        self.assertEqual(state, before)

    def test_cemetery_processes_bodies_without_canceling_deaths(self) -> None:
        state = self.make_state()
        self.assertTrue(self.sign(state, "cemetery_law").accepted)
        built = self.execute_building(state, BUILD_COMMAND, {"building_type": "cemetery", "zone": "outer_ring"})
        self.assertTrue(built.accepted)
        state.population.population_alive = 77
        state.population.population_dead = 3
        state.population.workers = 47
        state.population.healthy_population = 77
        state.population.housed_population = 40
        state.population.homeless_population = 37
        self.assertTrue(self.settle(self.engine(), state).result.accepted)
        self.assertEqual(state.population.population_dead, 3)
        self.assertEqual(state.social_policy.unhandled_bodies, 0)
        self.assertEqual(state.social_policy.buried_bodies, 3)

    def test_law_state_round_trip_and_v4_migration(self) -> None:
        state = self.make_state()
        self.assertTrue(self.sign(state, "firepit_law").accepted)
        restored = decode_game_state(encode_game_state(state))
        self.assertEqual(restored, state)
        legacy = encode_game_state(self.make_state())
        legacy["save_data_version"] = 4
        del legacy["social_policy"]
        del legacy["medical"]
        migrated = decode_game_state(legacy)
        self.assertEqual(migrated.save_data_version, CURRENT_SAVE_DATA_VERSION)
        self.assertEqual(migrated.social_policy.current_ration_mode, "normal")
        self.assertEqual(migrated.medical.effective_capacity, 5)

    def test_observation_reports_available_locked_and_unlocked_items(self) -> None:
        state = self.make_state()
        self.assertTrue(self.sign(state, "basic_medical_law").accepted)
        observation = self.law_system().observe(state)
        self.assertIn("medical_station", observation["unlocked_building_ids"])
        self.assertIn("stable_therapy_law", observation["available_law_ids"])
        self.assertIn("child_school_law", observation["locked_laws"])

    def test_law_hooks_complete_all_55_days_deterministically(self) -> None:
        def run():
            state = self.make_state()
            engine = self.engine()
            for _day in range(1, 56):
                execution = self.settle(engine, state)
                self.assertTrue(execution.result.accepted)
            return state

        first = run()
        second = run()
        self.assertEqual(first, second)
        self.assertEqual(first.calendar.current_day, 55)
        self.assertTrue(first.calendar.is_day_locked)
        self.assertEqual(first.daily_survival.settled_day, 55)
