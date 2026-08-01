from __future__ import annotations

import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from furnace_winter.config import (
    load_building_rules,
    load_final_frost_rules,
    load_survival_rules,
    load_technology_rules,
)
from furnace_winter.gameplay import EndDayStage, FinalFrostSystem
from furnace_winter.gameplay.end_day import EndDayContext
from furnace_winter.gameplay.hunger import (
    remove_non_hunger_deaths_or_departures,
    remove_starvation_deaths,
)
from furnace_winter.models import (
    BuildingState,
    DeterministicRandom,
    FrostDayRecord,
    SaveDataError,
    decode_game_state,
    encode_game_state,
)
from furnace_winter.gameplay.survival import create_initial_survival_state


ROOT = Path(__file__).resolve().parents[1]


class Patch013BalanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.survival = load_survival_rules(ROOT / "data" / "survival.json")
        cls.buildings = load_building_rules(ROOT / "data" / "buildings.json")
        cls.technology = load_technology_rules(
            ROOT / "data" / "technologies.json"
        )
        cls.rules = load_final_frost_rules(ROOT / "data" / "final_frost.json")

    def system(self) -> FinalFrostSystem:
        return FinalFrostSystem(
            self.rules,
            self.buildings,
            self.survival,
            self.technology,
        )

    def state(self, *, day: int = 1):
        state = create_initial_survival_state(
            self.survival, self.buildings, random_seed=13013
        )
        state.calendar.current_day = day
        return state

    @staticmethod
    def context(state, day: int, stage: EndDayStage) -> EndDayContext:
        return EndDayContext(
            state=state,
            random=DeterministicRandom.from_state(state.random),
            settled_day=day,
            stage=stage,
            _emit=lambda _code, _payload: None,
        )

    @staticmethod
    def set_alive(state, alive: int, *, housed: int = 0) -> None:
        population = state.population
        population.population_total = alive
        population.population_total_ever = alive
        population.population_alive = alive
        population.population_dead = 0
        population.workers = alive
        population.engineers = 0
        population.children = 0
        population.healthy_population = alive
        population.sick_population = 0
        population.critical_population = 0
        population.disabled_population = 0
        population.housed_population = housed
        population.homeless_population = alive - housed
        state.hunger.none_population = alive
        state.hunger.light_population = 0
        state.hunger.severe_population = 0
        state.hunger.starving_population = 0

    def test_hunger_feeds_deepest_pool_and_moves_all_pools_once(self) -> None:
        state = self.state()
        self.set_alive(state, 20, housed=20)
        state.hunger.none_population = 5
        state.hunger.light_population = 5
        state.hunger.severe_population = 5
        state.hunger.starving_population = 5
        state.daily_survival.unfed_population = 8

        self.system()._settle_hunger_pools(state, population_start=20)

        self.assertEqual(
            (
                state.hunger.none_population,
                state.hunger.light_population,
                state.hunger.severe_population,
                state.hunger.starving_population,
            ),
            (2, 10, 8, 0),
        )

    def test_three_unfed_days_reach_starving_and_recovery_is_one_layer(self) -> None:
        state = self.state()
        self.set_alive(state, 24, housed=24)
        system = self.system()
        raw_deaths = []
        for _day in range(3):
            state.daily_survival.unfed_population = 24
            effects = system._settle_hunger_pools(
                state, population_start=24
            )
            raw_deaths.append(effects["raw_deaths"])

        self.assertEqual(raw_deaths, [0, 0, 3])
        self.assertEqual(state.hunger.starving_population, 24)
        self.assertEqual(state.hunger.total_hunger_days, 3)
        self.assertEqual(state.hunger.total_unfed_person_days, 72)

        for expected in ((0, 0, 24, 0), (0, 24, 0, 0), (24, 0, 0, 0)):
            state.daily_survival.unfed_population = 0
            system._settle_hunger_pools(state, population_start=24)
            self.assertEqual(
                (
                    state.hunger.none_population,
                    state.hunger.light_population,
                    state.hunger.severe_population,
                    state.hunger.starving_population,
                ),
                expected,
            )
        self.assertEqual(
            (
                state.hunger.illness_remainder,
                state.hunger.severe_remainder,
                state.hunger.death_remainder,
                state.hunger.trust_remainder,
                state.hunger.panic_remainder,
            ),
            (0, 0, 0, 0, 0),
        )

    def test_hunger_social_pressure_is_capped_and_applied_once(self) -> None:
        state = self.state()
        state.hunger.none_population = 0
        state.hunger.starving_population = 80
        state.daily_survival.unfed_population = 80
        system = self.system()
        effects = system._settle_hunger_pools(state, population_start=80)
        self.assertEqual((effects["trust_loss"], effects["panic_gain"]), (6, 8))

        system.apply_hunger_social_pressure(
            self.context(state, 1, EndDayStage.RESOLVE_TRUST_AND_PANIC)
        )
        self.assertEqual((state.trust_panic.trust, state.trust_panic.panic), (64, 28))

    def test_non_hunger_losses_use_confirmed_order_and_are_batch_stable(self) -> None:
        original = self.state()
        self.set_alive(original, 20, housed=20)
        original.hunger.none_population = 4
        original.hunger.light_population = 5
        original.hunger.severe_population = 6
        original.hunger.starving_population = 5

        batch = deepcopy(original)
        remove_non_hunger_deaths_or_departures(batch, 11)
        batch.population.population_alive -= 11
        batch.population.population_dead += 11
        batch.population.workers -= 11
        batch.population.healthy_population -= 11
        batch.population.housed_population -= 11

        sequential = deepcopy(original)
        for _ in range(11):
            remove_non_hunger_deaths_or_departures(sequential, 1)
            sequential.population.population_alive -= 1
            sequential.population.population_dead += 1
            sequential.population.workers -= 1
            sequential.population.healthy_population -= 1
            sequential.population.housed_population -= 1

        expected = (0, 0, 4, 5)
        self.assertEqual(
            (
                batch.hunger.none_population,
                batch.hunger.light_population,
                batch.hunger.severe_population,
                batch.hunger.starving_population,
            ),
            expected,
        )
        self.assertEqual(batch.hunger, sequential.hunger)
        self.assertEqual(
            sum(expected), batch.population.population_alive
        )
        self.assertEqual(
            decode_game_state(encode_game_state(batch)).hunger,
            batch.hunger,
        )

    def test_starvation_losses_only_remove_starving_and_clear_remainder(self) -> None:
        state = self.state()
        self.set_alive(state, 12, housed=12)
        state.hunger.none_population = 2
        state.hunger.light_population = 3
        state.hunger.severe_population = 4
        state.hunger.starving_population = 3
        state.hunger.death_remainder = 7

        remove_starvation_deaths(state, 3)
        state.population.population_alive -= 3
        state.population.population_dead += 3
        state.population.workers -= 3
        state.population.healthy_population -= 3
        state.population.housed_population -= 3

        self.assertEqual(
            (
                state.hunger.none_population,
                state.hunger.light_population,
                state.hunger.severe_population,
                state.hunger.starving_population,
            ),
            (2, 3, 4, 0),
        )
        self.assertEqual(state.hunger.death_remainder, 0)
        with self.assertRaisesRegex(
            ValueError, "starvation deaths must come from hunger_starving"
        ):
            remove_starvation_deaths(state, 1)

    def test_d1_normal_homelessness_has_no_death_and_furnace_off_is_capped(self) -> None:
        normal = self.state(day=1)
        normal.daily_survival.settled_day = 1
        normal.daily_survival.base_temperature = self.survival.weather_for_day(1)
        normal.daily_survival.effective_furnace_level = 1
        self.system().resolve_frost_health(
            self.context(
                normal, 1, EndDayStage.RESOLVE_HOUSING_COLD_AND_HUNGER
            )
        )
        self.assertEqual(
            normal.events.deaths_today_by_cause.get("cold_exposure", 0), 0
        )

        off = self.state(day=1)
        off.daily_survival.settled_day = 1
        off.daily_survival.base_temperature = self.survival.weather_for_day(1)
        off.daily_survival.effective_furnace_level = 0
        off.furnace.is_active = False
        off.furnace.mode_id = "off"
        self.system().resolve_frost_health(
            self.context(off, 1, EndDayStage.RESOLVE_HOUSING_COLD_AND_HUNGER)
        )
        self.assertEqual(
            off.events.deaths_today_by_cause.get("cold_exposure", 0), 1
        )

    def test_small_cold_group_accumulates_exact_saved_remainders(self) -> None:
        state = self.state(day=2)
        self.set_alive(state, 8)
        state.medical.effective_capacity = 100
        system = self.system()
        with patch.object(
            FinalFrostSystem, "_exposure", return_value=[(4, 8, True)]
        ):
            for day in range(2, 6):
                system.resolve_frost_health(
                    self.context(
                        state,
                        day,
                        EndDayStage.RESOLVE_HOUSING_COLD_AND_HUNGER,
                    )
                )
                self.assertEqual(
                    state.events.deaths_today_by_cause.get(
                        "cold_exposure", 0
                    ),
                    0,
                )
            system.resolve_frost_health(
                self.context(
                    state, 6, EndDayStage.RESOLVE_HOUSING_COLD_AND_HUNGER
                )
            )
        self.assertEqual(
            state.events.deaths_today_by_cause.get("cold_exposure", 0), 1
        )
        self.assertEqual(
            state.cold_exposure.homeless_death_remainders["level_4_base"],
            0,
        )

    def test_cold_remainder_does_not_grow_outside_its_exposure_level(self) -> None:
        state = self.state(day=2)
        self.set_alive(state, 8)
        state.medical.effective_capacity = 100
        system = self.system()
        with patch.object(
            FinalFrostSystem, "_exposure", return_value=[(4, 8, True)]
        ):
            system.resolve_frost_health(
                self.context(
                    state, 2, EndDayStage.RESOLVE_HOUSING_COLD_AND_HUNGER
                )
            )
        before = state.cold_exposure.homeless_death_remainders[
            "level_4_base"
        ]
        with patch.object(
            FinalFrostSystem, "_exposure", return_value=[(0, 8, True)]
        ):
            system.resolve_frost_health(
                self.context(
                    state, 3, EndDayStage.RESOLVE_HOUSING_COLD_AND_HUNGER
                )
            )
        self.assertEqual(
            state.cold_exposure.homeless_death_remainders[
                "level_4_base"
            ],
            before,
        )

    def test_food_score_uses_exact_ratio_boundaries(self) -> None:
        state = self.state(day=55)
        state.final_frost.daily_records = {
            str(day): FrostDayRecord(
                day=day,
                real_temperature=self.rules.temperatures[day].real,
                display_label=self.rules.temperatures[day].display_label,
                population_start=100,
                population_end=100,
            )
            for day in range(49, 56)
        }
        state.final_frost.frost_hunger_days = 1
        state.final_frost.frost_peak_unfed_count = 10
        state.final_frost.frost_peak_population_start = 100
        state.final_frost.frost_unfed_person_days = 35
        state.final_frost.frost_population_person_days = 700
        self.assertEqual(self.system()._score(state)["food"], 2)

        state.final_frost.frost_peak_unfed_count = 9
        state.final_frost.frost_unfed_person_days = 34
        self.assertEqual(self.system()._score(state)["food"], 3)

        state.final_frost.frost_peak_unfed_count = 50
        self.assertEqual(self.system()._score(state)["food"], 0)

    def test_d49_wood_supply_lock_is_machine_readable_and_caps_result(self) -> None:
        state = self.state(day=49)
        for point in state.surface_resource_points.values():
            if point.resource_type == "wood":
                point.remaining_amount = 0
        state.resources.wood = 34
        system = self.system()
        system.prepare_new_day(state)
        self.assertTrue(state.final_frost.wood_supply_locked)
        scores = {name: 4 for name in (
            "coal_and_core",
            "food",
            "housing_and_temperature",
            "medical_and_disease",
            "trust_and_panic",
            "population_and_death",
        )}
        self.assertEqual(
            system._apply_result_caps(
                state,
                scores,
                "high_victory",
            ),
            "collapse_survival",
        )
        self.assertIn(
            "wood_supply_locked", system._ending_tags(state, scores)
        )

        staffed = self.state(day=49)
        for point in staffed.surface_resource_points.values():
            if point.resource_type == "wood":
                point.remaining_amount = 0
        staffed.resources.wood = 0
        staffed.buildings["logging-test"] = BuildingState(
            building_id="logging-test",
            building_type="logging_camp",
            zone="outer_ring",
            slot_size=2,
            is_built=True,
            is_operational=True,
            bound_resource_id="forest-zone-1",
            assigned_workers=1,
        )
        self.system().prepare_new_day(staffed)
        self.assertFalse(staffed.final_frost.wood_supply_locked)

    def test_v13_migration_builds_four_pools_and_strict_remainder_ranges(self) -> None:
        state = self.state()
        document = encode_game_state(state)
        document["save_data_version"] = 13
        del document["cold_exposure"]
        document["hunger"] = {
            "mild_population": 0,
            "severe_population": 0,
            "starving_population": 0,
        }
        for field in (
            "wood_supply_check_day",
            "wood_supply_surface_exhausted",
            "wood_supply_logging_camp_available",
            "wood_supply_wood_stock",
            "wood_supply_logging_cost",
            "wood_supply_alternative_available",
            "wood_supply_legacy_exempt",
            "wood_supply_locked",
            "frost_hunger_days",
            "frost_unfed_person_days",
            "frost_population_person_days",
            "frost_peak_unfed_count",
            "frost_peak_population_start",
            "frost_hunger_deaths",
        ):
            del document["final_frost"][field]
        del document["final_result"]["report"]["limiting_factor_ids"]

        migrated = decode_game_state(document)
        self.assertEqual(migrated.save_data_version, 14)
        self.assertEqual(migrated.hunger.none_population, 80)

        invalid = encode_game_state(migrated)
        invalid["hunger"]["none_population"] = 79
        invalid["hunger"]["light_population"] = 1
        invalid["hunger"]["illness_remainder"] = 5
        with self.assertRaisesRegex(SaveDataError, "integer range"):
            decode_game_state(invalid)


if __name__ == "__main__":
    unittest.main()
