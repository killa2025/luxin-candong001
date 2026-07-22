from __future__ import annotations

import unittest
from copy import deepcopy
from pathlib import Path

from furnace_winter.config import load_survival_rules
from furnace_winter.gameplay import (
    CONFIRM_END_DAY_COMMAND,
    END_DAY_COMMAND,
    EndDayEngine,
    EndDayStage,
    SurvivalSystem,
    create_initial_survival_state,
    is_over_capacity,
    storage_used,
)
from furnace_winter.interface import CommandRequest, ErrorCode
from furnace_winter.models import (
    CURRENT_SAVE_DATA_VERSION,
    GameState,
    HardFailType,
    SaveDataError,
    decode_game_state,
    encode_game_state,
    validate_game_state,
)
from tests import downgrade_to_pre_patch006_schema


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class SurvivalPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rules = load_survival_rules(REPOSITORY_ROOT / "data" / "survival.json")

    def make_state(self, seed: int = 2025) -> GameState:
        return create_initial_survival_state(self.rules, random_seed=seed)

    def make_engine(self) -> EndDayEngine:
        engine = EndDayEngine()
        SurvivalSystem(self.rules).install(engine)
        return engine

    @staticmethod
    def confirm(
        engine: EndDayEngine,
        state: GameState,
        preview: object,
        *,
        command_id: str = "confirm-1",
    ):
        result = preview.result  # type: ignore[attr-defined]
        confirmation = result.data["confirmation"]
        return engine.execute(
            state,
            CommandRequest(
                command_id,
                CONFIRM_END_DAY_COMMAND,
                confirmation,
                expected_state_sequence=state.command_sequence,
            ),
        )

    def test_sealed_starting_state_and_shared_storage(self) -> None:
        state = self.make_state()

        self.assertEqual(state.population.population_total, 80)
        self.assertEqual(state.population.population_alive, 80)
        self.assertEqual(
            (state.population.workers, state.population.engineers, state.population.children),
            (50, 15, 15),
        )
        self.assertEqual(state.population.healthy_population, 80)
        self.assertEqual(state.population.housed_population, 40)
        self.assertEqual(state.population.homeless_population, 40)
        self.assertEqual(state.housing.basic_residences, 4)
        self.assertEqual(state.housing.capacity, 40)
        self.assertEqual(
            (
                state.resources.coal,
                state.resources.wood,
                state.resources.steel,
                state.resources.raw_food,
                state.resources.cooked_food,
                state.resources.storage_capacity,
            ),
            (70, 100, 35, 40, 160, 800),
        )
        self.assertEqual(storage_used(state.resources), 405)
        self.assertFalse(is_over_capacity(state.resources))
        self.assertEqual(state.furnace.mode_id, "level_1")
        self.assertEqual((state.trust_panic.trust, state.trust_panic.panic), (70, 20))

    def test_fixed_weather_uses_all_55_real_integer_temperatures(self) -> None:
        expected = (
            -12, -15, -18, -14, -20, -16, -22,
            -24, -28, -32, -35, -26, -30, -34, -28, -36,
            -38, -32, -40, -42, -35, -44, -46, -38, -45, -48, -40,
            -50, -46, -52, -55, -48, -52, -56, -50, -58, -54, -60,
            -58, -62, -60, -64, -61, -42, -38, -58, -62, -65,
            -66, -68, -70, -66, -72, -74, -76,
        )
        self.assertEqual(self.rules.weather_temperatures, expected)
        self.assertEqual(self.rules.weather_for_day(1), -12)
        self.assertEqual(self.rules.weather_for_day(44), -42)
        self.assertEqual(self.rules.weather_for_day(49), -66)
        self.assertEqual(self.rules.weather_for_day(55), -76)
        self.assertTrue(all(isinstance(value, int) for value in self.rules.weather_temperatures))

    def test_furnace_command_is_structured_sequence_checked_and_lock_safe(self) -> None:
        state = self.make_state()
        system = SurvivalSystem(self.rules)
        accepted = system.execute(
            state,
            CommandRequest(
                "furnace-1",
                "game.set_furnace",
                {"level": 2},
                expected_state_sequence=0,
            ),
        )
        stale = system.execute(
            state,
            CommandRequest(
                "furnace-2",
                "game.set_furnace",
                {"level": 3},
                expected_state_sequence=0,
            ),
        )
        state.calendar.is_day_locked = True
        locked = system.execute(
            state,
            CommandRequest("furnace-3", "game.set_furnace", {"level": 1}),
        )

        self.assertTrue(accepted.accepted)
        self.assertEqual(state.furnace.mode_id, "level_2")
        self.assertEqual(state.command_sequence, 1)
        self.assertEqual(stale.code, ErrorCode.STALE_STATE)
        self.assertEqual(locked.code, ErrorCode.ILLEGAL_COMMAND)

    def test_furnace_command_rejects_invalid_input_state_without_mutation(self) -> None:
        state = self.make_state()
        state.population.population_alive = 79
        before = deepcopy(state)

        result = SurvivalSystem(self.rules).execute(
            state,
            CommandRequest("furnace-invalid", "game.set_furnace", {"level": 2}),
        )

        self.assertFalse(result.accepted)
        self.assertEqual(result.code, ErrorCode.INTERNAL_ERROR)
        self.assertEqual(result.data["failed_stage"], "input_state_validation")
        self.assertEqual(state, before)

    def test_furnace_command_failures_keep_state_and_machine_identity_safe(self) -> None:
        state = self.make_state()
        before = deepcopy(state)

        malformed = SurvivalSystem(self.rules).execute(
            state,
            CommandRequest(None, "game.set_furnace", {"level": 2}),  # type: ignore[arg-type]
        )
        self.assertEqual(malformed.command_id, "")
        self.assertEqual(state, before)

        state.final_result.hard_fail_type = HardFailType.POPULATION_ZERO
        failed_before = deepcopy(state)
        failed = SurvivalSystem(self.rules).execute(
            state,
            CommandRequest("furnace-failed", "game.set_furnace", {"level": 2}),
        )
        self.assertEqual(failed.code, ErrorCode.ILLEGAL_COMMAND)
        self.assertEqual(failed.data["reason"], "game_already_failed")
        self.assertEqual(state, failed_before)

    def test_day_one_heating_food_housing_and_zone_temperatures(self) -> None:
        state = self.make_state()
        execution = self.make_engine().execute(
            state,
            CommandRequest("end-1", END_DAY_COMMAND),
        )

        self.assertTrue(execution.result.accepted)
        self.assertEqual(state.resources.coal, 25)
        self.assertEqual(state.resources.cooked_food, 80)
        self.assertEqual(state.resources.raw_food, 40)
        self.assertEqual(state.calendar.current_day, 2)
        self.assertEqual(state.daily_survival.settled_day, 1)
        self.assertEqual(state.daily_survival.base_temperature, -12)
        self.assertEqual(state.daily_survival.target_furnace_level, 1)
        self.assertEqual(state.daily_survival.effective_furnace_level, 1)
        self.assertEqual(state.daily_survival.coal_paid, 45)
        self.assertFalse(state.daily_survival.heating_shortfall)
        self.assertEqual(
            state.daily_survival.zone_temperatures,
            {"inner_ring": 11, "middle_ring": 6, "outer_ring": 0},
        )
        self.assertEqual(state.daily_survival.cooked_food_eaten, 80)
        self.assertEqual(state.population.homeless_population, 40)
        self.assertEqual(execution.random_before, execution.random_after)

    def test_fuel_shortfall_requires_preview_and_uses_highest_full_level(self) -> None:
        state = self.make_state()
        state.furnace.mode_id = "level_2"
        state.furnace.is_active = True
        engine = self.make_engine()
        preview = engine.execute(
            state,
            CommandRequest("end-preview", END_DAY_COMMAND),
        )

        self.assertEqual(preview.result.code, ErrorCode.END_DAY_CONFIRMATION_REQUIRED)
        self.assertEqual(state.resources.coal, 70)
        warning = next(
            item for item in preview.warnings if item.warning_id == "survival.heating_fuel_shortfall"
        )
        self.assertEqual(warning.details["affordable_level"], 1)

        execution = self.confirm(engine, state, preview)

        self.assertTrue(execution.result.accepted)
        self.assertEqual(state.resources.coal, 25)
        self.assertEqual(state.daily_survival.target_furnace_level, 2)
        self.assertEqual(state.daily_survival.effective_furnace_level, 1)
        self.assertTrue(state.daily_survival.heating_shortfall)
        self.assertEqual(state.furnace.mode_id, "level_1")
        self.assertTrue(state.furnace.is_active)
        log_codes = [item.code for item in execution.logs]
        self.assertLess(
            log_codes.index("survival.heating.actual_level_resolved"),
            log_codes.index("survival.temperature.calculated"),
        )

    def test_today_production_cannot_pay_today_heating_shortfall(self) -> None:
        state = self.make_state()
        state.resources.coal = 25
        engine = self.make_engine()

        def produce_coal(context) -> None:
            context.state.resources.coal += 100

        engine.register_stage_handler(
            EndDayStage.RESOLVE_COLLECTION_AND_PRODUCTION,
            produce_coal,
        )
        preview = engine.execute(state, CommandRequest("preview", END_DAY_COMMAND))
        execution = self.confirm(engine, state, preview)

        self.assertTrue(execution.result.accepted)
        self.assertEqual(state.daily_survival.effective_furnace_level, 0)
        self.assertEqual(state.daily_survival.coal_paid, 0)
        self.assertEqual(state.resources.coal, 125)

    def test_food_consumes_cooked_then_raw_and_reports_unfed_without_guessing_progression(self) -> None:
        state = self.make_state()
        state.population.population_total = 3
        state.population.population_alive = 3
        state.population.workers = 3
        state.population.engineers = 0
        state.population.children = 0
        state.population.healthy_population = 3
        state.population.housed_population = 3
        state.population.homeless_population = 0
        state.resources.cooked_food = 1
        state.resources.raw_food = 1
        state.housing.capacity = 40
        engine = self.make_engine()
        preview = engine.execute(state, CommandRequest("preview", END_DAY_COMMAND))
        execution = self.confirm(engine, state, preview)

        self.assertTrue(execution.result.accepted)
        self.assertEqual(state.resources.cooked_food, 0)
        self.assertEqual(state.resources.raw_food, 0)
        self.assertEqual(state.daily_survival.cooked_food_eaten, 1)
        self.assertEqual(state.daily_survival.raw_food_eaten, 1)
        self.assertEqual(state.daily_survival.unfed_population, 1)
        self.assertEqual(state.hunger.mild_population, 0)
        self.assertEqual(state.hunger.severe_population, 0)
        self.assertEqual(state.hunger.starving_population, 0)

    def test_same_state_seed_and_actions_are_reproducible(self) -> None:
        first = self.make_state(seed=77)
        second = deepcopy(first)
        first_execution = self.make_engine().execute(
            first,
            CommandRequest("end", END_DAY_COMMAND),
        )
        second_execution = self.make_engine().execute(
            second,
            CommandRequest("end", END_DAY_COMMAND),
        )

        self.assertEqual(first, second)
        self.assertEqual(first_execution.logs, second_execution.logs)
        self.assertEqual(first_execution.random_after, second_execution.random_after)

    def test_survival_foundation_completes_all_55_days_deterministically(self) -> None:
        def run(seed: int) -> GameState:
            state = self.make_state(seed=seed)
            engine = self.make_engine()
            for day in range(1, 56):
                execution = engine.execute(
                    state,
                    CommandRequest(
                        f"end-{day}",
                        END_DAY_COMMAND,
                        expected_state_sequence=state.command_sequence,
                    ),
                )
                if execution.result.code is ErrorCode.END_DAY_CONFIRMATION_REQUIRED:
                    execution = self.confirm(
                        engine,
                        state,
                        execution,
                        command_id=f"confirm-{day}",
                    )
                self.assertTrue(execution.result.accepted)
            return state

        first = run(91)
        second = run(91)

        self.assertEqual(first, second)
        self.assertEqual(first.calendar.current_day, 55)
        self.assertTrue(first.calendar.is_day_locked)
        self.assertFalse(first.final_result.is_finalized)
        self.assertEqual(first.daily_survival.settled_day, 55)

    def test_save_v4_round_trip_and_v1_migration(self) -> None:
        state = self.make_state()
        restored = decode_game_state(encode_game_state(state))
        self.assertEqual(restored, state)

        legacy = encode_game_state(state)
        downgrade_to_pre_patch006_schema(legacy)
        legacy["save_data_version"] = 1
        del legacy["building_management"]
        del legacy["surface_resource_points"]
        del legacy["housing"]
        del legacy["hunger"]
        del legacy["daily_survival"]
        for building in legacy["buildings"].values():
            del building["bound_resource_id"]
            del building["production_remainder_numerator"]
            del building["production_multiplier_remainder_numerator"]
            del building["production_multiplier_remainder_denominator"]
        legacy["furnace"]["mode_id"] = None
        migrated = decode_game_state(legacy)

        self.assertEqual(migrated.save_data_version, CURRENT_SAVE_DATA_VERSION)
        self.assertEqual(migrated.housing.capacity, 40)
        self.assertEqual(migrated.furnace.mode_id, "level_1")

        for corrupt in (
            {**legacy, "housing": {"basic_residences": 4, "capacity": 40}},
            {**legacy, "furnace": {"is_active": "yes", "mode_id": None, "pressure": 0}},
        ):
            with self.subTest(corrupt=corrupt), self.assertRaises(SaveDataError):
                decode_game_state(corrupt)

    def test_invalid_population_housing_hunger_and_furnace_invariants_are_rejected(self) -> None:
        invalid_states = []
        for mutate in (
            lambda state: setattr(state.population, "population_alive", 79),
            lambda state: setattr(state.population, "homeless_population", 39),
            lambda state: setattr(state.hunger, "mild_population", 81),
            lambda state: setattr(state.furnace, "mode_id", "level_4"),
        ):
            state = self.make_state()
            mutate(state)
            invalid_states.append(state)

        for state in invalid_states:
            with self.subTest(state=state), self.assertRaises(SaveDataError):
                validate_game_state(state)

    def test_dead_population_cannot_remain_in_living_occupation_pools(self) -> None:
        state = self.make_state()
        state.population.population_alive = 79
        state.population.population_dead = 1
        state.population.healthy_population = 79
        state.population.homeless_population = 39

        with self.assertRaises(SaveDataError):
            validate_game_state(state)

    def test_loaded_rule_mappings_cannot_be_mutated_at_runtime(self) -> None:
        with self.assertRaises(TypeError):
            self.rules.furnace_levels[1] = self.rules.furnace_levels[0]  # type: ignore[index]
        with self.assertRaises(TypeError):
            self.rules.zone_modifiers["inner_ring"] = 99  # type: ignore[index]


if __name__ == "__main__":
    unittest.main()
