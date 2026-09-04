from __future__ import annotations

import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from furnace_winter.config import (
    load_building_rules,
    load_event_rules,
    load_final_frost_rules,
    load_law_rules,
    load_oath_order_rules,
    load_survival_rules,
    load_technology_rules,
)
from furnace_winter.gameplay import (
    BuildingSystem,
    CONFIRM_END_DAY_COMMAND,
    END_DAY_COMMAND,
    EndDayEngine,
    EndDayStage,
    EventSystem,
    FinalFrostSystem,
    LawSystem,
    OathOrderSystem,
    SurvivalSystem,
    TechnologySystem,
)
from furnace_winter.gameplay.end_day import EndDayContext
from furnace_winter.gameplay.hunger import (
    remove_non_hunger_deaths_or_departures,
    remove_starvation_deaths,
)
from furnace_winter.models import (
    CURRENT_SAVE_DATA_VERSION,
    LEGACY_ENDING_REPORT_FORMAT_VERSION,
    BuildingState,
    DeterministicRandom,
    EventResolutionRecord,
    FrostDayRecord,
    SaveDataError,
    decode_game_state,
    encode_game_state,
)
from furnace_winter.models.ending_selection import (
    legacy_report_pending_text_ids,
)
from furnace_winter.interface import (
    CommandRequest,
    ErrorCode,
    ReplayEntry,
    ReplayLog,
    decode_replay_document,
)
from furnace_winter.models import to_primitive
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
        cls.events = load_event_rules(ROOT / "data" / "events.json")
        cls.laws = load_law_rules(ROOT / "data" / "laws.json")
        cls.oath_order = load_oath_order_rules(
            ROOT / "data" / "oath_order.json"
        )

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

    def event_system(self) -> EventSystem:
        return EventSystem(
            self.events,
            self.buildings,
            self.survival,
            self.technology,
        )

    def full_engine(self) -> EndDayEngine:
        engine = EndDayEngine()
        SurvivalSystem(
            self.survival, self.buildings, self.technology
        ).install(engine)
        BuildingSystem(
            self.buildings, self.survival, self.technology
        ).install(engine)
        LawSystem(
            self.laws,
            self.buildings,
            self.survival,
            self.technology,
        ).install(engine)
        TechnologySystem(
            self.technology,
            self.buildings,
            self.survival,
            self.laws,
        ).install(engine)
        self.event_system().install(engine)
        OathOrderSystem(
            self.oath_order,
            self.buildings,
            self.survival,
            self.technology,
        ).install(engine)
        self.system().install(engine)
        return engine

    @staticmethod
    def context(state, day: int, stage: EndDayStage) -> EndDayContext:
        return EndDayContext(
            state=state,
            random=DeterministicRandom.from_state(state.random),
            settled_day=day,
            stage=stage,
            _emit=lambda _code, _payload: None,
        )

    def settle_full_day_with_replay(self, state, command_id: str):
        self.seed_fixed_arrival_rejections(
            state, through_day=state.calendar.current_day
        )
        initial = deepcopy(state)
        engine = self.full_engine()
        preview_request = CommandRequest(
            f"preview-{command_id}",
            END_DAY_COMMAND,
            {},
            state.command_sequence,
        )
        preview = engine.execute(state, preview_request)
        self.assertEqual(
            preview.result.code,
            ErrorCode.END_DAY_CONFIRMATION_REQUIRED,
            preview.result.data,
        )
        confirm_request = CommandRequest(
            f"confirm-{command_id}",
            CONFIRM_END_DAY_COMMAND,
            preview.result.data["confirmation"],
            state.command_sequence,
        )
        execution = engine.execute(state, confirm_request)
        replay = ReplayLog(initial)
        for sequence, request, item in (
            (1, preview_request, preview),
            (2, confirm_request, execution),
        ):
            replay.append(
                ReplayEntry(
                    sequence=sequence,
                    request=request,
                    result=item.result,
                    random_before=item.random_before,
                    random_after=item.random_after,
                    logs=item.logs,
                )
            )
        document = replay.document()
        self.assertEqual(
            decode_replay_document(to_primitive(document)), document
        )
        self.assertEqual(document.entries[0].result, preview.result)
        self.assertEqual(document.entries[1].logs, execution.logs)
        return preview, execution, document

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

    @staticmethod
    def downgrade_v14_to_v13(document: dict) -> dict:
        document["save_data_version"] = 13
        document.get("technologies", {}).pop("research_profile_id", None)
        document.get("technologies", {}).pop("research_remainder_tenths", None)
        del document["final_frost"]["balance_profile_id"]
        del document["final_result"]["report"]["format_version"]
        del document["cold_exposure"]
        document["hunger"] = {
            "mild_population": document["hunger"]["light_population"],
            "severe_population": document["hunger"]["severe_population"],
            "starving_population": document["hunger"]["starving_population"],
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
            "legacy_hunger_history_unknown",
            "legacy_hunger_record_days",
            "frost_hunger_days",
            "frost_unfed_person_days",
            "frost_population_person_days",
            "frost_peak_unfed_count",
            "frost_peak_population_start",
            "frost_hunger_deaths",
        ):
            del document["final_frost"][field]
        for record in document["final_frost"]["daily_records"].values():
            for field in (
                "unfed_population",
                "raw_hunger_deaths",
                "hunger_death_overflow",
            ):
                del record[field]
        del document["final_result"]["report"]["limiting_factor_ids"]
        return document

    def seed_fixed_arrival_rejections(
        self, state, *, through_day: int | None = None
    ) -> None:
        for event_id, rule in self.events.fixed_arrivals.items():
            if through_day is not None and rule.day > through_day:
                continue
            effect = rule.options["reject"]
            state.events.fixed_arrival_choices[event_id] = "reject"
            state.events.resolved_event_ids.append(event_id)
            state.events.occurrence_counts[event_id] = 1
            state.events.resolution_history.append(
                EventResolutionRecord(
                    event_id=event_id,
                    option_id="reject",
                    event_type="major",
                    resolved_day=rule.day,
                    instance_id=f"{event_id}#0001",
                    occurrence_index=1,
                    trust_change=effect.trust,
                    panic_change=effect.panic,
                    resource_changes={
                        "coal": 0,
                        "wood": 0,
                        "steel": 0,
                        "raw_food": 0,
                        "cooked_food": 0,
                    },
                )
            )

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

    def test_effective_furnace_off_guarantees_a_cold_death_each_ordinary_day(self) -> None:
        state = self.state(day=14)
        self.set_alive(state, 80, housed=80)
        state.furnace.mode_id = "off"
        state.furnace.is_active = False
        system = self.system()

        for day in (14, 15):
            state.calendar.current_day = day
            state.daily_survival.settled_day = day
            state.daily_survival.base_temperature = (
                self.survival.weather_for_day(day)
            )
            state.daily_survival.zone_temperatures = {
                "inner_ring": state.daily_survival.base_temperature,
                "middle_ring": state.daily_survival.base_temperature,
                "outer_ring": state.daily_survival.base_temperature,
            }
            state.daily_survival.effective_furnace_level = 0
            state.daily_survival.heating_shortfall = False
            deaths_before = state.population.population_dead
            system.resolve_frost_health(
                self.context(
                    state,
                    day,
                    EndDayStage.RESOLVE_HOUSING_COLD_AND_HUNGER,
                )
            )

            self.assertEqual(state.population.population_dead, deaths_before + 1)
            self.assertEqual(
                state.events.deaths_today_by_cause.get("cold_exposure", 0),
                day - 13,
            )
            self.assertEqual(
                state.events.metrics[
                    "patch009_furnace_off_minimum_death_applied"
                ],
                1,
            )

    def test_furnace_off_and_zero_affordable_heat_warn_conditional_minimum_death(self) -> None:
        state = self.state(day=14)
        system = SurvivalSystem(
            self.survival,
            self.buildings,
            self.technology,
        )

        state.furnace.mode_id = "off"
        state.furnace.is_active = False
        off = {
            warning.warning_id: warning
            for warning in system.evaluate_risks(state)
        }["survival.furnace_off"]
        self.assertEqual(off.details["minimum_natural_deaths_if_settled"], 1)
        self.assertEqual(
            off.details[
                "minimum_cold_exposure_deaths_if_no_disease_or_hunger_deaths"
            ],
            1,
        )
        self.assertEqual(
            off.details["conditional_death_cause"], "cold_exposure"
        )
        self.assertTrue(off.details["minimum_death_rule_applies"])
        self.assertEqual(
            off.details["minimum_death_rule_scope"],
            "effective_furnace_level_zero_only",
        )
        self.assertFalse(
            off.details["minimum_death_values_are_total_death_prediction"]
        )
        self.assertFalse(
            off.details["nonzero_effective_level_guarantees_safety"]
        )
        self.assertNotIn("death_cause", off.details)

        state.furnace.mode_id = "level_1"
        state.furnace.is_active = True
        state.resources.coal = 0
        shortfall = {
            warning.warning_id: warning
            for warning in system.evaluate_risks(state)
        }["survival.heating_fuel_shortfall"]
        self.assertEqual(shortfall.details["affordable_level"], 0)
        self.assertEqual(
            shortfall.details[
                "minimum_natural_deaths_if_effective_level_zero"
            ],
            1,
        )
        self.assertEqual(
            shortfall.details[
                "minimum_cold_exposure_deaths_if_effective_level_zero_and_no_disease_or_hunger_deaths"
            ],
            1,
        )
        self.assertEqual(
            shortfall.details[
                "conditional_death_cause_if_effective_level_zero"
            ],
            "cold_exposure",
        )
        self.assertNotIn(
            "death_cause_if_effective_level_zero", shortfall.details
        )

        state.furnace.mode_id = "level_3"
        state.resources.coal = 50
        partial = {
            warning.warning_id: warning
            for warning in system.evaluate_risks(state)
        }["survival.heating_fuel_shortfall"]
        self.assertEqual(partial.details["projected_effective_level"], 1)
        self.assertFalse(partial.details["minimum_death_rule_applies"])
        self.assertEqual(
            partial.details["minimum_death_rule_scope"],
            "effective_furnace_level_zero_only",
        )
        self.assertFalse(
            partial.details["minimum_death_values_are_total_death_prediction"]
        )
        self.assertFalse(
            partial.details["nonzero_effective_level_guarantees_safety"]
        )

    def test_formal_furnace_off_disease_death_does_not_claim_or_add_cold_death(self) -> None:
        state = self.state(day=14)
        self.set_alive(state, 40, housed=40)
        state.population.healthy_population = 20
        state.population.critical_population = 20
        state.medical.temporary_capacity = 0
        state.medical.effective_capacity = 0
        state.medical.medical_pressure = 20
        state.furnace.mode_id = "off"
        state.furnace.is_active = False
        state.resources.cooked_food = 1000
        state.resources.raw_food = 0

        preview, execution, replay = self.settle_full_day_with_replay(
            state, "off-disease"
        )

        self.assertTrue(execution.result.accepted)
        warning = {
            item.warning_id: item for item in preview.warnings
        }["survival.furnace_off"]
        self.assertNotIn("death_cause", warning.details)
        self.assertEqual(
            warning.details["minimum_natural_deaths_if_settled"], 1
        )
        health_log = next(
            item
            for item in execution.logs
            if item.code == "final_frost.health.resolved"
        )
        self.assertGreater(health_log.payload["disease_deaths"], 0)
        self.assertEqual(health_log.payload["cold_deaths"], 0)
        self.assertFalse(
            health_log.payload["furnace_off_minimum_death_applied"]
        )
        result_warning = {
            item.warning_id: item for item in execution.warnings
        }["survival.deaths_occurred"]
        self.assertEqual(result_warning.assessment_stage.value, "settlement_result")
        self.assertEqual(
            result_warning.details["total_deaths"],
            health_log.payload["disease_deaths"],
        )
        self.assertEqual(
            result_warning.details["disease_deaths"],
            health_log.payload["disease_deaths"],
        )
        self.assertEqual(result_warning.details["hunger_deaths"], 0)
        self.assertEqual(result_warning.details["cold_exposure_deaths"], 0)
        self.assertTrue(result_warning.details["cause_breakdown_matches_total"])
        self.assertIn(
            "laws.unhandled_bodies_after_settlement",
            {item.warning_id for item in execution.warnings},
        )
        self.assertIn(
            "survival.deaths_occurred",
            {
                item["warning_id"]
                for item in replay.entries[-1].result.data["warnings"]
            },
        )
        self.assertEqual(len(replay.entries), 2)

    def test_formal_zero_affordable_heat_hunger_death_does_not_add_cold_death(self) -> None:
        state = self.state(day=14)
        self.set_alive(state, 40, housed=40)
        state.hunger.none_population = 32
        state.hunger.starving_population = 8
        state.furnace.mode_id = "level_1"
        state.furnace.is_active = True
        state.resources.coal = 0
        state.resources.cooked_food = 0
        state.resources.raw_food = 0

        preview, execution, replay = self.settle_full_day_with_replay(
            state, "shortfall-hunger"
        )

        self.assertTrue(execution.result.accepted)
        warning = {
            item.warning_id: item for item in preview.warnings
        }["survival.heating_fuel_shortfall"]
        self.assertNotIn(
            "death_cause_if_effective_level_zero", warning.details
        )
        self.assertEqual(
            warning.details[
                "minimum_natural_deaths_if_effective_level_zero"
            ],
            1,
        )
        health_log = next(
            item
            for item in execution.logs
            if item.code == "final_frost.health.resolved"
        )
        self.assertGreater(health_log.payload["hunger_deaths"], 0)
        self.assertEqual(health_log.payload["cold_deaths"], 0)
        self.assertFalse(
            health_log.payload["furnace_off_minimum_death_applied"]
        )
        result_warning = {
            item.warning_id: item for item in execution.warnings
        }["survival.deaths_occurred"]
        self.assertEqual(
            result_warning.details["hunger_deaths"],
            health_log.payload["hunger_deaths"],
        )
        self.assertEqual(result_warning.details["cold_exposure_deaths"], 0)
        self.assertTrue(result_warning.details["cause_breakdown_matches_total"])
        self.assertEqual(len(replay.entries), 2)

    def test_formal_furnace_off_without_other_deaths_adds_logged_cold_death(self) -> None:
        state = self.state(day=14)
        self.set_alive(state, 40, housed=40)
        state.furnace.mode_id = "off"
        state.furnace.is_active = False
        state.resources.cooked_food = 1000
        state.resources.raw_food = 0

        _preview, execution, replay = self.settle_full_day_with_replay(
            state, "off-cold"
        )

        self.assertTrue(execution.result.accepted)
        health_log = next(
            item
            for item in execution.logs
            if item.code == "final_frost.health.resolved"
        )
        self.assertGreaterEqual(health_log.payload["cold_deaths"], 1)
        self.assertTrue(
            health_log.payload["furnace_off_minimum_death_applied"]
        )
        result_warning = {
            item.warning_id: item for item in execution.warnings
        }["survival.deaths_occurred"]
        self.assertEqual(result_warning.details["disease_deaths"], 0)
        self.assertEqual(result_warning.details["hunger_deaths"], 0)
        self.assertEqual(
            result_warning.details["cold_exposure_deaths"],
            health_log.payload["cold_deaths"],
        )
        self.assertTrue(result_warning.details["cause_breakdown_matches_total"])
        self.assertEqual(len(replay.entries), 2)

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

    def test_level_two_cold_disability_remainder_accumulates_before_frost(self) -> None:
        state = self.state(day=2)
        self.set_alive(state, 8)
        state.medical.effective_capacity = 100
        system = self.system()
        with (
            patch.object(
                FinalFrostSystem,
                "_exposure",
                return_value=[(2, 8, True)],
            ),
            patch.object(
                FinalFrostSystem,
                "_homeless_exposure_level",
                return_value=2,
            ),
        ):
            for day in range(2, 10):
                system.resolve_frost_health(
                    self.context(
                        state,
                        day,
                        EndDayStage.RESOLVE_HOUSING_COLD_AND_HUNGER,
                    )
                )

        self.assertEqual(
            state.cold_exposure.homeless_disability_remainders["2"],
            4,
        )

    def test_cold_snapshot_resets_and_excludes_housed_exposure(self) -> None:
        state = self.state(day=4)
        self.set_alive(state, 40, housed=40)
        state.events.metrics["cold_exposure_level"] = 5
        system = self.system()
        system._write_cold_exposure_snapshot(
            state, settled_day=3, is_frost_day=False
        )
        self.assertEqual(
            {
                name: state.events.metrics[name]
                for name in (
                    "cold_exposure_snapshot_day",
                    "homeless_population",
                    "cold_exposure_level",
                )
            },
            {
                "cold_exposure_snapshot_day": 3,
                "homeless_population": 0,
                "cold_exposure_level": 0,
            },
        )

        self.set_alive(state, 60, housed=40)
        for building in state.buildings.values():
            if building.building_type == "residence":
                building.effective_temperature = -99
        with patch.object(
            FinalFrostSystem,
            "_homeless_exposure_level",
            return_value=2,
        ):
            system._write_cold_exposure_snapshot(
                state, settled_day=3, is_frost_day=False
            )
        state.events.metrics["cold_exposure_warning_streak"] = 1
        self.assertNotIn(
            "cold_house_night",
            {
                event_id
                for event_id, _event_type in self.event_system()._condition_candidates(
                    state
                )
            },
        )

        system._write_cold_exposure_snapshot(
            state,
            settled_day=3,
            is_frost_day=False,
            exposure=[(2, 8, True), (4, 12, True), (5, 40, False)],
        )
        self.assertEqual(state.events.metrics["cold_exposure_level"], 4)

    def test_cold_house_uses_one_previous_day_snapshot_for_both_thresholds(self) -> None:
        system = self.system()
        events = self.event_system()

        qualifying = self.state(day=4)
        self.set_alive(qualifying, 60, housed=40)
        with patch.object(
            FinalFrostSystem,
            "_homeless_exposure_level",
            return_value=3,
        ):
            system._write_cold_exposure_snapshot(
                qualifying, settled_day=3, is_frost_day=False
            )
        qualifying.events.metrics["cold_exposure_warning_streak"] = 1
        self.assertIn(
            "cold_house_night",
            {event_id for event_id, _kind in events._condition_candidates(qualifying)},
        )
        activated = deepcopy(qualifying)
        events.initialize_day(activated)
        self.assertIn("cold_house_night", activated.events.active_events)
        snapshot = next(
            view["status_summary"]
            for view in events.active_event_views(activated)
            if view["event_id"] == "cold_house_night"
        )
        self.assertEqual(snapshot["cold_exposure_snapshot_day"], 3)
        self.assertEqual(snapshot["cold_exposure_homeless_population"], 20)
        self.assertEqual(snapshot["cold_exposure_level"], 3)

        too_few = self.state(day=4)
        self.set_alive(too_few, 50, housed=40)
        with patch.object(
            FinalFrostSystem,
            "_homeless_exposure_level",
            return_value=4,
        ):
            system._write_cold_exposure_snapshot(
                too_few, settled_day=3, is_frost_day=False
            )
        too_few.events.metrics["cold_exposure_warning_streak"] = 1
        self.assertNotIn(
            "cold_house_night",
            {event_id for event_id, _kind in events._condition_candidates(too_few)},
        )

        # Current-day housing changes cannot be mixed with yesterday's level.
        self.set_alive(qualifying, 40, housed=40)
        self.assertIn(
            "cold_house_night",
            {event_id for event_id, _kind in events._condition_candidates(qualifying)},
        )
        qualifying.events.metrics["cold_exposure_snapshot_day"] = 2
        self.assertNotIn(
            "cold_house_night",
            {event_id for event_id, _kind in events._condition_candidates(qualifying)},
        )

    def test_cold_snapshot_save_and_replay_preserve_event_result(self) -> None:
        state = self.state(day=4)
        self.set_alive(state, 60, housed=40)
        with patch.object(
            FinalFrostSystem,
            "_homeless_exposure_level",
            return_value=3,
        ):
            self.system()._write_cold_exposure_snapshot(
                state, settled_day=3, is_frost_day=False
            )
        state.events.metrics["cold_exposure_warning_streak"] = 1
        expected = self.event_system()._condition_candidates(state)

        restored = decode_game_state(encode_game_state(state))
        replay_state = decode_game_state(ReplayLog(state).document().initial_state)

        for candidate in (restored, replay_state):
            event_system = self.event_system()
            self.assertEqual(event_system._condition_candidates(candidate), expected)
            event_system.initialize_day(candidate)
            self.assertIn("cold_house_night", candidate.events.active_events)

    def test_cold_snapshot_strict_save_validation_rejects_mixed_facts(self) -> None:
        state = self.state(day=4)
        self.set_alive(state, 60, housed=40)
        with patch.object(
            FinalFrostSystem,
            "_homeless_exposure_level",
            return_value=3,
        ):
            self.system()._write_cold_exposure_snapshot(
                state, settled_day=3, is_frost_day=False
            )
        document = encode_game_state(state)

        missing_population = deepcopy(document)
        del missing_population["events"]["metrics"]["homeless_population"]
        with self.assertRaisesRegex(SaveDataError, "must retain"):
            decode_game_state(missing_population)

        wrong_day = deepcopy(document)
        wrong_day["events"]["metrics"]["cold_exposure_snapshot_day"] = 2
        with self.assertRaisesRegex(SaveDataError, "latest settled day"):
            decode_game_state(wrong_day)

        stale_level = deepcopy(document)
        stale_level["events"]["metrics"]["homeless_population"] = 0
        with self.assertRaisesRegex(SaveDataError, "must match"):
            decode_game_state(stale_level)

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

    def test_mixed_legacy_frost_uses_v13_food_score_for_entire_period(self) -> None:
        state = self.state(day=55)
        state.final_frost.daily_records = {
            str(day): FrostDayRecord(
                day=day,
                real_temperature=self.rules.temperatures[day].real,
                display_label=self.rules.temperatures[day].display_label,
                population_start=80,
                population_end=80,
                food_shortage=day == 55,
                starvation=day == 55,
                unfed_population=1 if day == 55 else 0,
            )
            for day in range(49, 56)
        }
        state.final_frost.frost_hunger_days = 1
        state.final_frost.frost_unfed_person_days = 1
        state.final_frost.frost_population_person_days = 560
        state.final_frost.frost_peak_unfed_count = 1
        state.final_frost.frost_peak_population_start = 80

        self.assertEqual(self.system()._score(state)["food"], 3)

        state.final_frost.legacy_hunger_history_unknown = True
        state.final_frost.legacy_hunger_record_days = list(range(49, 55))
        self.assertEqual(self.system()._score(state)["food"], 2)

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
        document = self.downgrade_v14_to_v13(encode_game_state(state))

        migrated = decode_game_state(document)
        self.assertEqual(
            migrated.save_data_version, CURRENT_SAVE_DATA_VERSION
        )
        self.assertEqual(migrated.hunger.none_population, 80)

        invalid = encode_game_state(migrated)
        invalid["hunger"]["none_population"] = 79
        invalid["hunger"]["light_population"] = 1
        invalid["hunger"]["illness_remainder"] = 5
        with self.assertRaisesRegex(SaveDataError, "integer range"):
            decode_game_state(invalid)

    def test_v13_completed_starvation_history_keeps_legacy_score(self) -> None:
        state = self.state(day=49)
        state.final_frost.balance_profile_id = "legacy_patch021"
        system = self.system()
        system.prepare_new_day(state)
        state.final_frost.wood_supply_legacy_exempt = True
        state.final_frost.legacy_hunger_history_unknown = True
        population = state.population.population_alive
        base_cap = min(22, 12 + max(0, population - 80) // 35)
        state.final_frost.daily_records = {
            str(day): FrostDayRecord(
                day=day,
                real_temperature=self.rules.temperatures[day].real,
                display_label=self.rules.temperatures[day].display_label,
                population_start=population,
                population_end=population,
                food_shortage=day == 50,
                starvation=day == 50,
                base_natural_death_cap=base_cap,
                applied_natural_death_cap=base_cap,
            )
            for day in range(49, 56)
        }
        state.final_frost.frost_population_person_days = population * 7
        state.final_frost.legacy_hunger_record_days = list(range(49, 56))
        state.calendar.current_day = 55
        state.daily_survival.settled_day = 55
        state.daily_survival.base_temperature = self.rules.temperatures[55].real
        state.daily_survival.zone_temperatures = {
            "inner_ring": self.rules.temperatures[55].real,
            "middle_ring": self.rules.temperatures[55].real,
            "outer_ring": self.rules.temperatures[55].real,
        }
        self.seed_fixed_arrival_rejections(state)
        system.finalize_day_55(
            self.context(
                state, 55, EndDayStage.RECORD_DAILY_LOG_AND_ENDING_TAGS
            )
        )
        self.assertEqual(state.final_result.system_scores["food"], 2)
        state.final_result.report.format_version = (
            LEGACY_ENDING_REPORT_FORMAT_VERSION
        )
        state.final_result.report.body_text_ids = []
        state.final_result.report.pending_text_ids = (
            legacy_report_pending_text_ids(state)
        )
        original_result = deepcopy(state.final_result)

        legacy = self.downgrade_v14_to_v13(encode_game_state(state))
        migrated = decode_game_state(legacy)

        self.assertTrue(migrated.final_frost.legacy_hunger_history_unknown)
        self.assertEqual(
            migrated.final_frost.daily_records["50"].unfed_population, 0
        )
        self.assertEqual(migrated.final_result, original_result)
        system.validate_state(migrated)

    def test_v13_in_progress_frost_uses_v14_allocation_on_next_day(self) -> None:
        legacy_source = self.state(day=49)
        system = self.system()
        system.prepare_new_day(legacy_source)
        legacy_source.final_frost.wood_supply_legacy_exempt = True
        legacy_source.final_frost.legacy_hunger_history_unknown = True
        legacy_source.final_frost.legacy_hunger_record_days = list(
            range(49, 55)
        )
        population = legacy_source.population.population_alive
        base_cap = min(22, 12 + max(0, population - 80) // 35)
        legacy_source.final_frost.daily_records = {
            str(day): FrostDayRecord(
                day=day,
                real_temperature=self.rules.temperatures[day].real,
                display_label=self.rules.temperatures[day].display_label,
                population_start=population,
                population_end=population,
                base_natural_death_cap=base_cap,
                applied_natural_death_cap=base_cap,
            )
            for day in range(49, 55)
        }
        legacy_source.final_frost.frost_population_person_days = population * 6
        legacy_source.calendar.current_day = 55
        legacy_source.daily_survival.settled_day = 54
        legacy_source.daily_survival.base_temperature = (
            self.rules.temperatures[54].real
        )
        legacy_source.daily_survival.zone_temperatures = {
            "inner_ring": self.rules.temperatures[54].real,
            "middle_ring": self.rules.temperatures[54].real,
            "outer_ring": self.rules.temperatures[54].real,
        }
        self.seed_fixed_arrival_rejections(legacy_source)
        legacy_source.resources.cooked_food = 0
        legacy_source.resources.raw_food = 0
        legacy_source.hunger.none_population = 0
        legacy_source.hunger.starving_population = population
        legacy_source.population.healthy_population = population - 20
        legacy_source.population.critical_population = 20
        legacy_source.medical.medical_pressure = 15
        legacy_source.furnace.mode_id = "off"
        legacy_source.furnace.is_active = False
        legacy_source.furnace.overload_level = 0

        legacy_document = self.downgrade_v14_to_v13(
            encode_game_state(legacy_source)
        )
        migrated = decode_game_state(legacy_document)
        self.assertEqual(
            migrated.final_frost.legacy_hunger_record_days,
            list(range(49, 55)),
        )

        def settle_with_replay(state, command_id: str):
            initial = deepcopy(state)
            engine = self.full_engine()
            request = CommandRequest(
                command_id,
                END_DAY_COMMAND,
                {},
                state.command_sequence,
            )
            execution = engine.execute(state, request)
            if execution.result.code is ErrorCode.END_DAY_CONFIRMATION_REQUIRED:
                request = CommandRequest(
                    f"confirm-{command_id}",
                    CONFIRM_END_DAY_COMMAND,
                    execution.result.data["confirmation"],
                    state.command_sequence,
                )
                execution = engine.execute(state, request)
            replay = ReplayLog(initial)
            replay.append(
                ReplayEntry(
                    sequence=1,
                    request=request,
                    result=execution.result,
                    random_before=execution.random_before,
                    random_after=execution.random_after,
                    logs=execution.logs,
                )
            )
            return execution, replay.document()

        first = deepcopy(migrated)
        second = deepcopy(migrated)
        first_execution, first_replay = settle_with_replay(first, "mixed-1")
        second_execution, second_replay = settle_with_replay(second, "mixed-1")

        self.assertEqual(first_execution.result.code, ErrorCode.OK)
        self.assertEqual(second_execution.result.code, ErrorCode.OK)
        self.assertEqual(encode_game_state(first), encode_game_state(second))
        self.assertEqual(to_primitive(first_replay), to_primitive(second_replay))
        self.assertEqual(
            decode_game_state(encode_game_state(first)), first
        )
        self.assertEqual(
            decode_replay_document(to_primitive(first_replay)),
            first_replay,
        )

        record = first.final_frost.daily_records["55"]
        self.assertGreater(record.raw_disease_deaths, 0)
        self.assertGreater(record.raw_hunger_deaths, 0)
        self.assertGreater(record.raw_cold_deaths, 0)
        self.assertGreater(
            record.raw_disease_deaths
            + record.raw_hunger_deaths
            + record.raw_cold_deaths,
            record.applied_natural_death_cap,
        )
        self.assertEqual(
            record.actual_disease_deaths
            + record.food_deaths
            + record.actual_cold_deaths,
            record.applied_natural_death_cap,
        )
        self.assertEqual(
            first.final_frost.legacy_hunger_record_days,
            list(range(49, 55)),
        )
        self.assertTrue(first.final_frost.legacy_hunger_history_unknown)
        self.assertEqual(
            first.final_result.system_scores["food"],
            system._score(first)["food"],
        )

    def test_v13_migration_rejects_coerced_scalar_types(self) -> None:
        base = self.downgrade_v14_to_v13(
            encode_game_state(self.state())
        )
        for path, value in (
            (("hunger", "mild_population"), True),
            (("hunger", "severe_population"), "0"),
            (("population", "population_alive"), "80"),
            (("daily_survival", "unfed_population"), True),
            (("resources", "wood"), "200"),
            (("final_frost", "entered"), 0),
        ):
            with self.subTest(path=path, value=value):
                invalid = deepcopy(base)
                invalid[path[0]][path[1]] = value
                with self.assertRaises(SaveDataError):
                    decode_game_state(invalid)

    def test_v13_migration_rejects_coerced_frost_record_types(self) -> None:
        state = self.state(day=49)
        system = self.system()
        system.prepare_new_day(state)
        population = state.population.population_alive
        base_cap = min(22, 12 + max(0, population - 80) // 35)
        state.final_frost.daily_records["49"] = FrostDayRecord(
            day=49,
            real_temperature=self.rules.temperatures[49].real,
            display_label=self.rules.temperatures[49].display_label,
            population_start=population,
            population_end=population,
            base_natural_death_cap=base_cap,
            applied_natural_death_cap=base_cap,
        )
        state.final_frost.frost_population_person_days = population
        state.daily_survival.settled_day = 49
        state.daily_survival.base_temperature = self.rules.temperatures[49].real
        state.daily_survival.zone_temperatures = {
            "inner_ring": self.rules.temperatures[49].real,
            "middle_ring": self.rules.temperatures[49].real,
            "outer_ring": self.rules.temperatures[49].real,
        }
        base = self.downgrade_v14_to_v13(encode_game_state(state))
        for field, value in (
            ("day", "49"),
            ("population_start", True),
            ("food_deaths", "0"),
            ("starvation", 0),
        ):
            with self.subTest(field=field, value=value):
                invalid = deepcopy(base)
                invalid["final_frost"]["daily_records"]["49"][field] = value
                with self.assertRaises(SaveDataError):
                    decode_game_state(invalid)


if __name__ == "__main__":
    unittest.main()
