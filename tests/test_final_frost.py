from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from furnace_winter.config import (
    FinalFrostConfigError,
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
    RESOLVE_EVENT_COMMAND,
    RESOLVE_OLD_CITY_COMMAND,
    SurvivalSystem,
    TechnologySystem,
    create_initial_survival_state,
)
from furnace_winter.gameplay.end_day import EndDayContext
from furnace_winter.gameplay.survival import (
    is_building_expected_operational,
)
from furnace_winter.models import (
    BuildingState,
    DeterministicRandom,
    EventResolutionRecord,
    FrostDayRecord,
    PromiseSettlementRecord,
    SaveDataError,
    decode_game_state,
    encode_game_state,
    validate_game_state,
)
from furnace_winter.interface import CommandRequest, ErrorCode


ROOT = Path(__file__).resolve().parents[1]


class FinalFrostPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.survival = load_survival_rules(ROOT / "data" / "survival.json")
        cls.buildings = load_building_rules(ROOT / "data" / "buildings.json")
        cls.technology = load_technology_rules(
            ROOT / "data" / "technologies.json"
        )
        cls.laws = load_law_rules(ROOT / "data" / "laws.json")
        cls.events = load_event_rules(ROOT / "data" / "events.json")
        cls.oath_order = load_oath_order_rules(
            ROOT / "data" / "oath_order.json"
        )
        cls.rules = load_final_frost_rules(
            ROOT / "data" / "final_frost.json"
        )

    def make_state(self, day: int = 49):
        state = create_initial_survival_state(
            self.survival, self.buildings, random_seed=9009
        )
        state.calendar.current_day = day
        state.resources.coal = 2000
        state.resources.cooked_food = 1000
        state.resources.raw_food = 0
        for event_id, trigger_day in (
            ("arrival_day6", 6),
            ("arrival_day19", 19),
            ("arrival_day37", 37),
        ):
            if day <= trigger_day:
                continue
            state.events.fixed_arrival_choices[event_id] = "reject"
            state.events.resolved_event_ids.append(event_id)
            state.events.occurrence_counts[event_id] = 1
            state.events.resolution_history.append(
                EventResolutionRecord(
                    event_id=event_id,
                    option_id="reject",
                    event_type="major",
                    resolved_day=trigger_day,
                    instance_id=f"{event_id}#0001",
                    occurrence_index=1,
                    resource_changes={
                        "coal": 0,
                        "wood": 0,
                        "steel": 0,
                        "raw_food": 0,
                        "cooked_food": 0,
                    },
                )
            )
        return state

    def system(self) -> FinalFrostSystem:
        return FinalFrostSystem(
            self.rules,
            self.buildings,
            self.survival,
            self.technology,
        )

    def test_observation_discloses_surface_collection_shutdown(self) -> None:
        state = self.make_state(day=49)
        system = self.system()
        system.prepare_new_day(state)
        view = system.observe(state)["forced_shutdown"]

        self.assertTrue(view["surface_resource_collection_shutdown"])
        self.assertIn(
            "surface-steel-1",
            view["affected_surface_resource_point_ids"],
        )

    def test_daily_service_history_records_actual_operations(self) -> None:
        state = self.make_state(day=49)
        state.daily_survival.settled_day = 49
        state.daily_survival.base_temperature = -66
        state.daily_survival.zone_temperatures = {
            "inner_ring": -30,
            "middle_ring": -30,
            "outer_ring": -30,
        }
        state.final_frost.entered = True
        state.final_frost.baseline_day = 49
        state.final_frost.baseline_alive_population = (
            state.population.population_alive
        )
        state.final_frost.baseline_healthy_population = (
            state.population.healthy_population
        )
        state.final_frost.baseline_sick_population = (
            state.population.sick_population
        )
        state.final_frost.baseline_critical_population = (
            state.population.critical_population
        )
        state.final_frost.baseline_disabled_population = (
            state.population.disabled_population
        )
        state.final_frost.baseline_workable_population = (
            state.population.workers + state.population.engineers
        )
        state.final_frost.wood_supply_check_day = 49
        state.final_frost.wood_supply_logging_cost = 35
        state.buildings["canteen-history"] = BuildingState(
            building_id="canteen-history",
            building_type="canteen",
            zone="inner_ring",
            slot_size=2,
            is_built=True,
            is_operational=True,
            assigned_workers=5,
        )
        state.buildings["medical-history"] = BuildingState(
            building_id="medical-history",
            building_type="medical_station",
            zone="inner_ring",
            slot_size=1,
            is_built=True,
            is_operational=True,
            assigned_engineers=5,
        )
        state.building_management.zone_slots_used["inner_ring"] += 3
        state.medical.building_capacity = 10
        state.medical.effective_capacity = (
            state.medical.temporary_capacity + 10
        )
        state.medical.medical_pressure = max(
            state.population.sick_population
            + state.population.critical_population
            - state.medical.effective_capacity,
            0,
        )
        system = self.system()

        system.capture_daily_record(
            self.context(state, 49, EndDayStage.CAPTURE_DAILY_RECORDS)
        )

        record = state.final_frost.daily_records["49"]
        base_cap = min(
            22,
            12 + max(0, record.population_start - 80) // 35,
        )
        record.base_natural_death_cap = base_cap
        record.applied_natural_death_cap = base_cap
        state.final_frost.frost_population_person_days = (
            record.population_start
        )
        self.assertTrue(record.service_history_known)
        self.assertTrue(record.canteen_operational)
        self.assertEqual(record.medical_operational_building_count, 1)
        self.assertEqual(record.medical_building_capacity, 10)
        del state.buildings["canteen-history"]
        del state.buildings["medical-history"]
        state.building_management.zone_slots_used["inner_ring"] -= 3
        state.medical.building_capacity = 0
        state.medical.effective_capacity = state.medical.temporary_capacity
        state.medical.medical_pressure = max(
            state.population.sick_population
            + state.population.critical_population
            - state.medical.effective_capacity,
            0,
        )
        view = system.observe(state)["daily_service_history"]["49"]
        self.assertEqual(
            view,
            {
                "known": True,
                "canteen_operational": True,
                "medical_operational_building_count": 1,
                "medical_building_capacity": 10,
            },
        )

        state.calendar.current_day = 50
        state.daily_survival.settled_day = 50
        state.daily_survival.base_temperature = -68
        system.capture_daily_record(
            self.context(state, 50, EndDayStage.CAPTURE_DAILY_RECORDS)
        )
        record = state.final_frost.daily_records["50"]
        record.base_natural_death_cap = base_cap
        record.applied_natural_death_cap = base_cap
        state.final_frost.frost_population_person_days += (
            record.population_start
        )
        self.assertTrue(record.service_history_known)
        self.assertFalse(record.canteen_operational)
        self.assertEqual(record.medical_operational_building_count, 0)
        self.assertEqual(record.medical_building_capacity, 0)

    def full_engine(
        self,
        *,
        autosave_sink=None,
    ) -> tuple[EndDayEngine, EventSystem, OathOrderSystem]:
        engine = EndDayEngine(autosave_sink=autosave_sink)
        SurvivalSystem(
            self.survival,
            self.buildings,
            self.technology,
        ).install(engine)
        BuildingSystem(
            self.buildings,
            self.survival,
            self.technology,
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
        events = EventSystem(
            self.events,
            self.buildings,
            self.survival,
            self.technology,
        )
        events.install(engine)
        oath_order = OathOrderSystem(
            self.oath_order,
            self.buildings,
            self.survival,
            self.technology,
        )
        oath_order.install(engine)
        self.system().install(engine)
        return engine, events, oath_order

    def settle(self, engine: EndDayEngine, state, command_id: str):
        execution = engine.execute(
            state,
            CommandRequest(
                command_id,
                END_DAY_COMMAND,
                {},
                state.command_sequence,
            ),
        )
        if execution.result.code is ErrorCode.END_DAY_CONFIRMATION_REQUIRED:
            execution = engine.execute(
                state,
                CommandRequest(
                    f"confirm-{command_id}",
                    CONFIRM_END_DAY_COMMAND,
                    execution.result.data["confirmation"],
                    state.command_sequence,
                ),
            )
        return execution

    @staticmethod
    def resolve_active_events(events: EventSystem, state) -> None:
        for event_id, event in list(state.events.active_events.items()):
            for option_id in event.option_ids:
                result = events.execute(
                    state,
                    CommandRequest(
                        f"resolve-{state.command_sequence + 1}",
                        RESOLVE_EVENT_COMMAND,
                        {
                            "event_id": event_id,
                            "option_id": option_id,
                        },
                        state.command_sequence,
                    ),
                )
                if result.code is ErrorCode.OK:
                    break
            else:
                raise AssertionError(f"no legal option for {event_id}")

    @staticmethod
    def resolve_pending_old_city(
        oath_order: OathOrderSystem,
        state,
    ) -> None:
        options = {
            "southern_letter": "publish",
            "rumors": "public_explain",
            "public_gathering": "public_explain",
            "countdown": "do_not_stop",
        }
        while state.old_city.pending_event_id is not None:
            event_id = state.old_city.pending_event_id
            result = oath_order.execute(
                state,
                CommandRequest(
                    f"old-city-{state.command_sequence + 1}",
                    RESOLVE_OLD_CITY_COMMAND,
                    {
                        "event_id": event_id,
                        "option_id": options[event_id],
                    },
                    state.command_sequence,
                ),
            )
            if result.code is not ErrorCode.OK:
                raise AssertionError((event_id, result.code, result.data))

    @staticmethod
    def v10_document(state) -> dict:
        document = encode_game_state(state)
        document["save_data_version"] = 10
        del document["final_frost"]
        del document["medical"]["sick_treatment_progress"]
        document["events"].pop("fixed_arrival_pressure_days")
        document["events"].pop("natural_death_overflow_candidates")
        for field in (
            "system_scores",
            "total_score",
            "major_tags",
            "defining_tags",
        ):
            del document["final_result"][field]
        return document

    @staticmethod
    def set_population(
        state,
        *,
        healthy: int,
        sick: int = 0,
        critical: int = 0,
        disabled: int = 0,
        housed: int | None = None,
    ) -> None:
        alive = healthy + sick + critical + disabled
        population = state.population
        population.population_total = alive
        population.population_total_ever = alive
        population.population_alive = alive
        population.population_dead = 0
        population.workers = alive
        population.engineers = 0
        population.children = 0
        population.healthy_population = healthy
        population.sick_population = sick
        population.critical_population = critical
        population.disabled_population = disabled
        population.housed_population = min(
            state.housing.capacity if housed is None else housed,
            alive,
        )
        population.homeless_population = (
            alive - population.housed_population
        )
        state.hunger.none_population = alive
        state.hunger.light_population = 0
        state.hunger.severe_population = 0
        state.hunger.starving_population = 0

    def frost_record(
        self,
        day: int,
        *,
        population_start: int = 80,
        population_end: int | None = None,
        **changes,
    ) -> FrostDayRecord:
        if population_end is None:
            population_end = population_start
        base_cap = min(
            22, 12 + max(0, population_start - 80) // 35
        )
        conditions = changes.get("extreme_crisis_conditions", [])
        applied_cap = (
            (base_cap * 3 + 1) // 2
            if len(conditions) >= 2
            else base_cap
        )
        defaults = {
            "day": day,
            "real_temperature": self.rules.temperatures[day].real,
            "display_label": self.rules.temperatures[day].display_label,
            "population_start": population_start,
            "population_end": population_end,
            "base_natural_death_cap": base_cap,
            "applied_natural_death_cap": applied_cap,
        }
        defaults.update(changes)
        return FrostDayRecord(**defaults)

    @staticmethod
    def context(state, day: int, stage: EndDayStage) -> EndDayContext:
        return EndDayContext(
            state=state,
            random=DeterministicRandom.from_state(state.random),
            settled_day=day,
            stage=stage,
            _emit=lambda _code, _payload: None,
        )

    def test_config_seals_calendar_shutdowns_and_status(self) -> None:
        self.assertEqual((self.rules.start_day, self.rules.end_day), (49, 55))
        self.assertEqual(
            [self.rules.temperatures[day].real for day in range(49, 56)],
            [-66, -68, -70, -66, -72, -74, -76],
        )
        self.assertEqual(
            self.rules.shutdown_building_types,
            {
                "hunting_lodge",
                "logging_camp",
                "small_coal_miner",
                "small_steel_miner",
            },
        )
        source = json.loads(
            (ROOT / "data" / "final_frost.json").read_text(encoding="utf-8")
        )
        source["calendar"]["start_day"] = 48
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "final_frost.json"
            path.write_text(
                json.dumps(source, ensure_ascii=False), encoding="utf-8"
            )
            with self.assertRaises(FinalFrostConfigError):
                load_final_frost_rules(path)

    def test_config_rejects_every_reviewed_contract_mutation(self) -> None:
        source = json.loads(
            (ROOT / "data" / "final_frost.json").read_text(encoding="utf-8")
        )
        mutations = {
            "surface collection": lambda item: item["restrictions"].update(
                {"shutdown_surface_collection": False}
            ),
            "display label": lambda item: item["calendar"]["temperatures"][
                "49"
            ].update({"display_label": "not-canonical"}),
            "key technology": lambda item: item["preparation"][
                "key_technology_ids"
            ].append("tech_missing"),
            "tag severity": lambda item: item["tag_severity"].pop(
                "grave_city"
            ),
            "grave threshold": lambda item: item["scoring"].update(
                {"grave_city_death_ratio_percent": 25}
            ),
            "Patch 022 preparation threshold": lambda item: item[
                "preparation"
            ].update({"prepared_required_items": 5}),
            "Patch 022 result band": lambda item: item["scoring"][
                "result_score_minimums"
            ].update({"high_victory": 20}),
            "Patch 022 high-victory death threshold": lambda item: item[
                "scoring"
            ].update({"high_victory_death_ratio_percent": 20}),
            "natural death cap": lambda item: item["damage"].update(
                {"natural_death_cap_base": 11}
            ),
            "Patch 013 hunger divisor": lambda item: item["hunger"].update(
                {"death_divisor": 7}
            ),
            "Patch 013 food score ratio": lambda item: item["hunger"].update(
                {"score_peak_two_percent": 24}
            ),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                document = deepcopy(source)
                mutate(document)
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / "final_frost.json"
                    path.write_text(
                        json.dumps(document, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    with self.assertRaises(FinalFrostConfigError):
                        load_final_frost_rules(path)

    def test_nested_scoring_configuration_is_immutable(self) -> None:
        minimums = self.rules.scoring["result_score_minimums"]
        with self.assertRaises(TypeError):
            minimums["high_victory"] = 0
        self.assertEqual(minimums["high_victory"], 22)

    def test_day_49_baseline_and_preparation_are_stable(self) -> None:
        state = self.make_state()
        self.system().prepare_new_day(state)
        baseline = deepcopy(state.final_frost)
        self.system().prepare_new_day(state)
        self.assertEqual(state.final_frost, baseline)
        self.assertEqual(state.final_frost.baseline_day, 49)
        self.assertEqual(state.final_frost.baseline_alive_population, 80)
        self.assertEqual(state.final_frost.prepared_item_count, 6)
        self.assertEqual(
            state.final_frost.preparation_tags, ["prepared_for_frost"]
        )

    def test_patch022_preparation_is_stricter_but_legacy_runs_keep_old_band(
        self,
    ) -> None:
        current = self.make_state()
        current.trust_panic.trust = 50
        current.trust_panic.panic = 50
        self.system().prepare_new_day(current)
        self.assertEqual(current.final_frost.prepared_item_count, 4)
        self.assertEqual(current.final_frost.preparation_tags, [])

        legacy = self.make_state()
        legacy.final_frost.balance_profile_id = "legacy_patch021"
        legacy.trust_panic.trust = 50
        legacy.trust_panic.panic = 50
        self.system().prepare_new_day(legacy)
        self.assertEqual(legacy.final_frost.prepared_item_count, 6)
        self.assertEqual(
            legacy.final_frost.preparation_tags,
            ["prepared_for_frost"],
        )

    def test_patch022_result_bands_are_harder_without_removing_high_victory(
        self,
    ) -> None:
        system = self.system()
        current = self.make_state()
        self.assertEqual(current.final_frost.balance_profile_id, "patch022")
        expectations = {
            24: "high_victory",
            22: "high_victory",
            21: "standard_victory",
            18: "standard_victory",
            17: "bitter_victory",
            12: "bitter_victory",
            11: "collapse_survival",
            7: "collapse_survival",
            6: "ember_survival",
        }
        for total, expected in expectations.items():
            with self.subTest(total=total):
                self.assertEqual(
                    system._result_for_total(current, total), expected
                )

        viable_high_scores = dict(
            zip(
                (
                    "coal_and_core",
                    "food",
                    "housing_and_temperature",
                    "medical_and_disease",
                    "trust_and_panic",
                    "population_and_death",
                ),
                (4, 4, 4, 4, 3, 3),
                strict=True,
            )
        )
        self.assertEqual(sum(viable_high_scores.values()), 22)
        self.assertEqual(
            system._apply_result_caps(
                current, viable_high_scores, "high_victory"
            ),
            "high_victory",
        )

        weak_system_scores = dict(viable_high_scores)
        weak_system_scores["trust_and_panic"] = 2
        weak_system_scores["coal_and_core"] = 4
        self.assertEqual(
            system._apply_result_caps(
                current, weak_system_scores, "high_victory"
            ),
            "standard_victory",
        )
        current.population.population_total_ever = 100
        current.population.population_dead = 5
        self.assertEqual(
            system._apply_result_caps(
                current, viable_high_scores, "high_victory"
            ),
            "high_victory",
        )
        current.population.population_dead = 6
        self.assertEqual(
            system._apply_result_caps(
                current, viable_high_scores, "high_victory"
            ),
            "standard_victory",
        )

    def test_v16_migration_preserves_legacy_balance_and_rejects_forgery(
        self,
    ) -> None:
        source = encode_game_state(self.make_state(day=12))
        source["save_data_version"] = 16
        del source["final_frost"]["balance_profile_id"]

        restored = decode_game_state(source)

        self.assertEqual(restored.save_data_version, 17)
        self.assertEqual(
            restored.final_frost.balance_profile_id,
            "legacy_patch021",
        )
        self.assertEqual(
            self.system().observe(restored)["balance_profile_id"],
            "legacy_patch021",
        )
        self.assertEqual(
            self.system()._result_for_total(restored, 15),
            "standard_victory",
        )

        forged = encode_game_state(self.make_state(day=12))
        forged["save_data_version"] = 16
        with self.assertRaisesRegex(
            SaveDataError,
            "pre-v17 save cannot contain a balance profile",
        ):
            decode_game_state(forged)

        invalid = encode_game_state(self.make_state(day=12))
        invalid["final_frost"]["balance_profile_id"] = "unknown"
        with self.assertRaisesRegex(
            SaveDataError, "unsupported final-frost balance profile"
        ):
            decode_game_state(invalid)

    def test_v16_completed_result_keeps_legacy_ending_and_report(self) -> None:
        state = self.make_state()
        state.final_frost.balance_profile_id = "legacy_patch021"
        system = self.system()
        system.prepare_new_day(state)
        for day in range(49, 56):
            state.final_frost.daily_records[str(day)] = self.frost_record(day)
        state.final_frost.frost_population_person_days = 80 * 7
        state.calendar.current_day = 55
        state.daily_survival.settled_day = 55
        state.daily_survival.base_temperature = -76
        state.daily_survival.zone_temperatures = {
            "inner_ring": -40,
            "middle_ring": -42,
            "outer_ring": -44,
        }
        system.finalize_day_55(
            self.context(
                state, 55, EndDayStage.RECORD_DAILY_LOG_AND_ENDING_TAGS
            )
        )
        expected_result = deepcopy(state.final_result)
        legacy = encode_game_state(state)
        legacy["save_data_version"] = 16
        del legacy["final_frost"]["balance_profile_id"]

        restored = decode_game_state(legacy)

        self.assertEqual(restored.final_result, expected_result)
        self.assertEqual(
            restored.final_frost.balance_profile_id,
            "legacy_patch021",
        )
        system.validate_state(restored)

    def test_day_49_food_preparation_only_converts_raw_food_for_running_canteen(
        self,
    ) -> None:
        def prepared_state(
            *,
            operational: bool,
            temperature: int,
            furnace_mode: str = "level_3",
            workers: int = 5,
            children: int = 0,
        ):
            state = self.make_state()
            state.furnace.mode_id = furnace_mode
            state.resources.cooked_food = 0
            state.resources.raw_food = 200
            state.trust_panic.trust = 49
            canteen_rule = self.buildings.buildings["canteen"]
            state.buildings["canteen-test"] = BuildingState(
                building_id="canteen-test",
                building_type="canteen",
                zone="inner_ring",
                slot_size=canteen_rule.slot_size,
                is_built=True,
                is_operational=operational,
                assigned_workers=workers,
                assigned_children=children,
                can_heat=True,
                effective_temperature=temperature,
                is_shutdown_by_temperature=(
                    canteen_rule.min_operating_temperature is not None
                    and temperature < canteen_rule.min_operating_temperature
                ),
            )
            state.building_management.zone_slots_used["inner_ring"] += (
                canteen_rule.slot_size
            )
            return state

        running = prepared_state(operational=False, temperature=-60)
        before_resources = deepcopy(running.resources)
        self.system().prepare_new_day(running)
        self.assertEqual(running.final_frost.prepared_item_count, 4)
        self.assertEqual(
            running.final_frost.preparation_tags,
            [],
        )
        self.assertEqual(running.resources, before_resources)

        for name, state in (
            (
                "D49 furnace off",
                prepared_state(
                    operational=True,
                    temperature=-35,
                    furnace_mode="off",
                ),
            ),
            (
                "illegal staffing",
                prepared_state(
                    operational=True,
                    temperature=-35,
                    workers=0,
                    children=5,
                ),
            ),
        ):
            with self.subTest(name=name):
                self.system().prepare_new_day(state)
                self.assertEqual(state.final_frost.prepared_item_count, 4)
                self.assertEqual(state.final_frost.preparation_tags, [])

    def test_day_48_running_canteen_uses_day_49_projection_for_preparation(
        self,
    ) -> None:
        state = self.make_state(day=48)
        state.furnace.mode_id = "level_3"
        state.technologies.researched_tech_ids = [
            "tech_drawing_board",
            "tech_drafting_instrument",
            "tech_furnace_coal_saving_1",
            "tech_furnace_coal_saving_2",
        ]
        state.resources.coal = 120
        state.resources.cooked_food = 0
        state.resources.raw_food = 200
        state.trust_panic.trust = 49
        canteen_rule = self.buildings.buildings["canteen"]
        canteen = BuildingState(
            building_id="canteen-boundary",
            building_type="canteen",
            zone="inner_ring",
            slot_size=canteen_rule.slot_size,
            is_built=True,
            assigned_workers=5,
            can_heat=True,
        )
        state.buildings[canteen.building_id] = canteen
        state.building_management.zone_slots_used["inner_ring"] += (
            canteen_rule.slot_size
        )
        self.system().validate_state(state)

        engine = EndDayEngine()
        SurvivalSystem(
            self.survival,
            self.buildings,
            self.technology,
        ).install(engine)
        BuildingSystem(
            self.buildings,
            self.survival,
            self.technology,
        ).install(engine)
        self.system().install(engine)

        settled = self.settle(engine, state, "d48-canteen-boundary")

        self.assertEqual(
            settled.result.code,
            ErrorCode.OK,
            settled.result.data,
        )
        self.assertEqual(state.calendar.current_day, 49)
        canteen = state.buildings[canteen.building_id]
        self.assertTrue(canteen.is_operational)
        self.assertGreaterEqual(
            canteen.effective_temperature,
            canteen_rule.min_operating_temperature,
        )
        self.assertFalse(
            is_building_expected_operational(
                state,
                canteen,
                self.buildings,
                self.survival,
                self.technology,
            )
        )
        self.assertEqual(state.resources.coal, 0)
        self.assertEqual(state.resources.cooked_food, 40)
        self.assertEqual(state.resources.raw_food, 140)
        self.assertEqual(state.final_frost.prepared_item_count, 4)
        self.assertEqual(
            state.final_frost.preparation_tags,
            ["unprepared_frost"],
        )

    def test_unprepared_preparation_tag_overrides_prepared_tag(self) -> None:
        state = self.make_state()
        state.resources.coal = 0
        state.resources.cooked_food = 0
        state.resources.raw_food = 0
        state.population.housed_population = state.population.population_alive
        state.population.homeless_population = 0
        state.furnace.pressure = 80
        state.technologies.researched_tech_ids = [
            "tech_final_furnace_stability"
        ]

        self.system().prepare_new_day(state)

        self.assertGreaterEqual(state.final_frost.prepared_item_count, 5)
        self.assertGreaterEqual(state.final_frost.unprepared_item_count, 3)
        self.assertEqual(
            state.final_frost.preparation_tags,
            ["unprepared_frost"],
        )

    def test_surface_collection_is_frozen_without_consuming_reserve(self) -> None:
        state = self.make_state()
        point = next(iter(state.surface_resource_points.values()))
        point.assigned_workers = 5
        before = deepcopy(point)
        BuildingSystem(
            self.buildings, self.survival, self.technology
        ).resolve_production(
            self.context(
                state,
                49,
                EndDayStage.RESOLVE_COLLECTION_AND_PRODUCTION,
            )
        )
        self.assertEqual(point.remaining_amount, before.remaining_amount)
        self.assertEqual(point.production_remainder_numerator, 0)

    def test_frost_health_updates_structured_metrics_and_round_trips(self) -> None:
        state = self.make_state()
        system = self.system()
        system.prepare_new_day(state)
        for building in state.buildings.values():
            building.effective_temperature = -60
        system.resolve_frost_health(
            self.context(
                state, 49, EndDayStage.RESOLVE_HOUSING_COLD_AND_HUNGER
            )
        )
        state.daily_survival.settled_day = 49
        state.daily_survival.base_temperature = -66
        state.daily_survival.zone_temperatures = {
            "inner_ring": -40,
            "middle_ring": -42,
            "outer_ring": -44,
        }
        system.capture_daily_record(
            self.context(state, 49, EndDayStage.CAPTURE_DAILY_RECORDS)
        )
        record = state.final_frost.daily_records["49"]
        self.assertGreater(record.new_sick, 0)
        self.assertGreater(
            record.homeless_new_sick
            + record.homeless_new_disabled
            + record.homeless_cold_deaths,
            0,
        )
        self.assertEqual(record.real_temperature, -66)
        restored = decode_game_state(encode_game_state(state))
        self.assertEqual(restored, state)

    def test_critical_treatment_recovers_to_sick_and_clears_empty_progress(self) -> None:
        state = self.make_state()
        self.set_population(state, healthy=36, critical=4, housed=40)
        state.medical.effective_capacity = 4
        system = self.system()
        system.prepare_new_day(state)
        with patch.object(
            FinalFrostSystem,
            "_exposure",
            return_value=[(0, 40, False)],
        ):
            system.resolve_frost_health(
                self.context(
                    state,
                    49,
                    EndDayStage.RESOLVE_HOUSING_COLD_AND_HUNGER,
                )
            )
        self.assertEqual(
            (
                state.population.healthy_population,
                state.population.sick_population,
                state.population.critical_population,
            ),
            (36, 1, 3),
        )

        empty = self.make_state()
        self.set_population(empty, healthy=40, housed=40)
        empty.medical.sick_treatment_progress = 2
        empty.medical.critical_treatment_progress = 3
        with patch.object(
            FinalFrostSystem,
            "_exposure",
            return_value=[(0, 40, False)],
        ):
            system.resolve_frost_health(
                self.context(
                    empty,
                    49,
                    EndDayStage.RESOLVE_HOUSING_COLD_AND_HUNGER,
                )
            )
        self.assertEqual(empty.medical.sick_treatment_progress, 0)
        self.assertEqual(empty.medical.critical_treatment_progress, 0)

    def test_untreated_sick_progression_uses_exact_exposure_divisors(self) -> None:
        expected_new_critical = {0: 4, 1: 4, 2: 4, 3: 5, 4: 6}
        for exposure_level, expected in expected_new_critical.items():
            with self.subTest(exposure_level=exposure_level):
                state = self.make_state()
                self.set_population(
                    state,
                    healthy=0,
                    sick=12,
                    disabled=28,
                    housed=40,
                )
                state.medical.effective_capacity = 0
                with patch.object(
                    FinalFrostSystem,
                    "_exposure",
                    return_value=[(exposure_level, 40, False)],
                ):
                    self.system().resolve_frost_health(
                        self.context(
                            state,
                            49,
                            EndDayStage.RESOLVE_HOUSING_COLD_AND_HUNGER,
                        )
                    )
                self.assertEqual(
                    state.events.metrics["patch009_new_critical"],
                    expected,
                )

    def test_zero_capacity_high_exposure_forces_one_critical_death(self) -> None:
        state = self.make_state()
        self.set_population(
            state,
            healthy=0,
            critical=1,
            disabled=39,
            housed=40,
        )
        state.medical.effective_capacity = 0
        with patch.object(
            FinalFrostSystem,
            "_exposure",
            return_value=[(3, 40, False)],
        ):
            self.system().resolve_frost_health(
                self.context(
                    state,
                    49,
                    EndDayStage.RESOLVE_HOUSING_COLD_AND_HUNGER,
                )
            )
        self.assertEqual(
            state.events.metrics["patch009_raw_disease_deaths"],
            1,
        )
        self.assertEqual(state.population.population_dead, 1)

    def test_natural_death_cap_scales_and_only_two_crises_break_it(self) -> None:
        cases = (
            (80, False, 12, 12),
            (80, True, 12, 18),
            (115, False, 13, 13),
            (1000, False, 22, 22),
        )
        for alive, heating_shortfall, expected_base, expected_applied in cases:
            with self.subTest(
                alive=alive,
                heating_shortfall=heating_shortfall,
            ):
                state = self.make_state()
                self.set_population(
                    state,
                    healthy=alive,
                    housed=min(alive, 40),
                )
                state.daily_survival.heating_shortfall = heating_shortfall
                with patch.object(
                    FinalFrostSystem,
                    "_exposure",
                    return_value=[(0, alive, False)],
                ):
                    self.system().resolve_frost_health(
                        self.context(
                            state,
                            49,
                            EndDayStage.RESOLVE_HOUSING_COLD_AND_HUNGER,
                        )
                    )
                self.assertEqual(
                    state.events.metrics[
                        "patch009_base_natural_death_cap"
                    ],
                    expected_base,
                )
                self.assertEqual(
                    state.events.metrics[
                        "patch009_applied_natural_death_cap"
                    ],
                    expected_applied,
                )

    def test_disease_uses_cap_before_cold_and_overflow_is_persisted_once(self) -> None:
        state = self.make_state()
        self.set_population(
            state,
            healthy=400,
            critical=100,
            housed=0,
        )
        state.medical.temporary_capacity = 0
        state.medical.building_capacity = 0
        state.medical.effective_capacity = 0
        system = self.system()
        system.prepare_new_day(state)
        with patch.object(
            FinalFrostSystem,
            "_exposure",
            return_value=[(4, 500, True)],
        ):
            system.resolve_frost_health(
                self.context(
                    state,
                    49,
                    EndDayStage.RESOLVE_HOUSING_COLD_AND_HUNGER,
                )
            )
        metrics = state.events.metrics
        self.assertEqual(
            (
                metrics["patch009_raw_disease_deaths"],
                metrics["patch009_disease_deaths"],
                metrics["patch009_disease_death_overflow"],
                metrics["patch009_raw_cold_deaths"],
                metrics["patch009_cold_deaths"],
                metrics["patch009_cold_death_overflow"],
            ),
            (49, 33, 16, 22, 0, 22),
        )
        self.assertEqual(state.population.population_dead, 33)
        self.assertEqual(state.population.population_alive, 467)
        self.assertEqual(
            (
                state.population.healthy_population,
                state.population.sick_population,
                state.population.critical_population,
                state.population.disabled_population,
            ),
            (280, 51, 96, 40),
        )
        self.assertEqual(
            state.events.natural_death_overflow_candidates,
            {"49": 38},
        )

        state.daily_survival.settled_day = 49
        state.daily_survival.base_temperature = -66
        state.daily_survival.zone_temperatures = {
            "inner_ring": -66,
            "middle_ring": -66,
            "outer_ring": -66,
        }
        system.capture_daily_record(
            self.context(state, 49, EndDayStage.CAPTURE_DAILY_RECORDS)
        )
        record = state.final_frost.daily_records["49"]
        self.assertEqual(record.natural_death_overflow_pressure, 38)
        self.assertEqual(record.extreme_crisis_conditions, sorted(
            record.extreme_crisis_conditions
        ))
        self.assertEqual(
            state.final_frost.pending_extreme_crisis_conditions,
            [],
        )
        state.population.housed_population = 40
        state.population.homeless_population = 427
        restored = decode_game_state(encode_game_state(state))
        self.assertEqual(
            restored.events.natural_death_overflow_candidates,
            {"49": 38},
        )

    def test_day_55_scores_six_systems_and_applies_quality_cap(self) -> None:
        state = self.make_state()
        system = self.system()
        system.prepare_new_day(state)
        for day in range(49, 56):
            state.final_frost.daily_records[str(day)] = self.frost_record(day)
        state.final_frost.frost_population_person_days = 80 * 7
        state.calendar.current_day = 55
        state.daily_survival.settled_day = 55
        state.daily_survival.base_temperature = -76
        state.daily_survival.zone_temperatures = {
            "inner_ring": -40,
            "middle_ring": -42,
            "outer_ring": -44,
        }
        system.finalize_day_55(
            self.context(
                state, 55, EndDayStage.RECORD_DAILY_LOG_AND_ENDING_TAGS
            )
        )
        self.assertTrue(state.final_result.is_finalized)
        self.assertTrue(state.final_result.report.is_generated)
        self.assertEqual(state.final_result.report.generated_day, 55)
        self.assertEqual(state.calendar.current_day, 55)
        self.assertNotIn("56", state.final_frost.daily_records)
        self.assertEqual(len(state.final_result.system_scores), 6)
        self.assertEqual(
            state.final_result.total_score,
            sum(state.final_result.system_scores.values()),
        )
        self.assertIn(state.final_result.ending_id, {
            "high_victory",
            "standard_victory",
            "bitter_victory",
            "collapse_survival",
            "ember_survival",
        })
        validate_game_state(
            state, self.buildings, self.survival, self.technology
        )
        state.final_result.system_scores["food"] = max(
            state.final_result.system_scores["food"] - 1,
            0,
        )
        state.final_result.total_score = sum(
            state.final_result.system_scores.values()
        )
        with self.assertRaisesRegex(
            ValueError,
            "canonical frost history",
        ):
            system.validate_state(state)

    def test_explicit_system_collapse_conditions_override_higher_scores(
        self,
    ) -> None:
        state = self.make_state()
        state.final_frost.daily_records = {
            str(day): self.frost_record(day) for day in range(49, 56)
        }
        for day in (49, 50, 51):
            state.final_frost.daily_records[str(day)].overload_redline = True
        for day in (49, 50, 51, 52):
            state.final_frost.daily_records[
                str(day)
            ].critical_building_frozen = True
            state.final_frost.daily_records[str(day)].medical_collapse = True
        state.medical.effective_capacity = 100

        scores = self.system()._score(state)

        self.assertEqual(scores["coal_and_core"], 0)
        self.assertEqual(scores["housing_and_temperature"], 0)
        self.assertEqual(scores["medical_and_disease"], 0)

    def test_v10_migration_is_safe_before_frost_and_rejects_frost_history_gap(self) -> None:
        state = self.make_state(day=48)
        document = self.v10_document(state)
        restored = decode_game_state(document)
        self.assertEqual(restored.calendar.current_day, 48)
        self.assertFalse(restored.final_frost.entered)

        document["calendar"]["current_day"] = 49
        with self.assertRaisesRegex(SaveDataError, "cannot reconstruct"):
            decode_game_state(document)

    def test_v10_migration_rejects_accepted_arrival_after_pressure_window_starts(
        self,
    ) -> None:
        def arrival_document(
            *,
            current_day: int,
            settled_day: int | None,
            option_id: str,
        ) -> dict:
            state = self.make_state(day=max(current_day, 7))
            history = next(
                item
                for item in state.events.resolution_history
                if item.event_id == "arrival_day6"
            )
            state.events.fixed_arrival_choices["arrival_day6"] = option_id
            history.option_id = option_id
            state.calendar.current_day = current_day
            state.daily_survival.settled_day = settled_day
            if settled_day is not None:
                temperature = self.survival.weather_for_day(settled_day)
                state.daily_survival.base_temperature = temperature
                state.daily_survival.zone_temperatures = {
                    "inner_ring": temperature,
                    "middle_ring": temperature,
                    "outer_ring": temperature,
                }
                state.daily_survival.storage_used = sum(
                    getattr(state.resources, name)
                    for name in (
                        "coal",
                        "wood",
                        "steel",
                        "raw_food",
                        "cooked_food",
                    )
                )
            return self.v10_document(state)

        safe_acceptance = arrival_document(
            current_day=6,
            settled_day=5,
            option_id="accept_all",
        )
        self.assertEqual(
            decode_game_state(safe_acceptance).calendar.current_day,
            6,
        )

        for current_day, settled_day in (
            (6, 6),
            (7, 6),
            (10, 10),
            (11, 10),
        ):
            with self.subTest(
                current_day=current_day,
                settled_day=settled_day,
            ):
                accepted = arrival_document(
                    current_day=current_day,
                    settled_day=settled_day,
                    option_id="accept_partial",
                )
                with self.assertRaisesRegex(
                    SaveDataError,
                    "pressure history cannot be reconstructed",
                ):
                    decode_game_state(accepted)

        rejected = arrival_document(
            current_day=11,
            settled_day=10,
            option_id="reject",
        )
        self.assertEqual(
            decode_game_state(rejected).events.fixed_arrival_choices[
                "arrival_day6"
            ],
            "reject",
        )

    def test_v11_rejects_deleted_future_and_wrong_baseline_records(self) -> None:
        state = self.make_state()
        self.system().prepare_new_day(state)
        state.calendar.current_day = 50
        state.daily_survival.settled_day = 49
        state.daily_survival.base_temperature = -66
        state.daily_survival.zone_temperatures = {
            "inner_ring": -66,
            "middle_ring": -66,
            "outer_ring": -66,
        }
        state.final_frost.daily_records["49"] = self.frost_record(49)
        state.final_frost.frost_population_person_days = 80
        document = encode_game_state(state)
        self.assertEqual(decode_game_state(document), state)

        deleted = deepcopy(document)
        del deleted["final_frost"]["daily_records"]["49"]
        with self.assertRaisesRegex(SaveDataError, "cover every settled day"):
            decode_game_state(deleted)

        future = deepcopy(document)
        future["final_frost"]["daily_records"]["50"] = encode_game_state(
            self.make_state()
        )["final_frost"]["daily_records"].get("50", {
            **future["final_frost"]["daily_records"]["49"],
            "day": 50,
        })
        with self.assertRaisesRegex(SaveDataError, "cover every settled day"):
            decode_game_state(future)

        wrong_baseline = deepcopy(document)
        wrong_baseline["final_frost"]["daily_records"]["49"][
            "population_start"
        ] = 79
        wrong_baseline["final_frost"]["daily_records"]["49"][
            "population_end"
        ] = 79
        with self.assertRaisesRegex(SaveDataError, "D49 baseline"):
            decode_game_state(wrong_baseline)

    def test_old_city_route_and_arrival_tags_use_patch_008_fact_ids(self) -> None:
        state = self.make_state()
        system = self.system()
        system.prepare_new_day(state)
        for day in range(49, 56):
            state.final_frost.daily_records[str(day)] = self.frost_record(day)
        state.old_city.result_id = "partial_exodus"
        state.oath_order.signed_law_ids = [
            "guard_oath",
            "mourning_bell",
            "shared_meal",
            "ember_roster",
            "stay_oath",
            "final_oath",
        ]
        state.oath_order.final_oath_active = True
        state.oath_order.action_last_used_day = {
            "shared_meal": 40,
            "stay_persuasion": 41,
        }
        state.events.fixed_arrival_choices = {
            "arrival_day6": "accept_all",
            "arrival_day19": "accept_all",
            "arrival_day37": "reject",
        }
        scores = system._score(state)
        tags = system._ending_tags(state, scores)
        self.assertLessEqual(scores["trust_and_panic"], 2)
        self.assertIn("old_city_departed", tags)
        self.assertIn("old_city_persuaded", tags)
        self.assertIn("final_oath", tags)
        self.assertIn("opened_gates", tags)

    def test_cold_day_thresholds_are_integer_and_scoring_reads_flags(self) -> None:
        for cold_population, mass_population, expected_cold, expected_mass in (
            (19, 31, False, False),
            (20, 32, True, True),
        ):
            with self.subTest(
                cold_population=cold_population,
                mass_population=mass_population,
            ):
                state = self.make_state()
                system = self.system()
                system.prepare_new_day(state)
                state.events.metrics.update(
                    {
                        "patch009_population_start": 80,
                        "patch009_cold_housed": cold_population,
                        "patch009_mass_exposure": mass_population,
                    }
                )
                system.capture_daily_record(
                    self.context(
                        state,
                        49,
                        EndDayStage.CAPTURE_DAILY_RECORDS,
                    )
                )
                record = state.final_frost.daily_records["49"]
                self.assertEqual(record.cold_houses_day, expected_cold)
                self.assertEqual(
                    record.mass_cold_exposure_day,
                    expected_mass,
                )

        state = self.make_state()
        state.housing.capacity = 80
        state.population.housed_population = 80
        state.population.homeless_population = 0
        state.final_frost.daily_records = {
            str(day): self.frost_record(
                day,
                cold_houses_population=1,
                cold_houses_day=False,
            )
            for day in range(49, 56)
        }
        self.assertEqual(
            self.system()._score(state)["housing_and_temperature"],
            4,
        )
        for day in range(49, 54):
            state.final_frost.daily_records[str(day)].cold_houses_day = True
        self.assertEqual(
            self.system()._score(state)["housing_and_temperature"],
            0,
        )

    def test_grave_city_uses_strict_configured_historical_ratio_only(self) -> None:
        scores = {
            "coal_and_core": 3,
            "food": 3,
            "housing_and_temperature": 3,
            "medical_and_disease": 3,
            "trust_and_panic": 3,
            "population_and_death": 3,
        }

        def tags_for(
            deaths: int,
            total_ever: int,
            *,
            departures: int = 0,
            unhandled_bodies: int = 0,
            system: FinalFrostSystem | None = None,
        ) -> list[str]:
            state = self.make_state()
            current_total = total_ever - departures
            alive = current_total - deaths
            population = state.population
            population.population_total_ever = total_ever
            population.population_total = current_total
            population.population_alive = alive
            population.population_dead = deaths
            population.workers = alive
            population.engineers = 0
            population.children = 0
            population.healthy_population = alive
            population.sick_population = 0
            population.critical_population = 0
            population.disabled_population = 0
            population.housed_population = min(alive, state.housing.capacity)
            population.homeless_population = (
                alive - population.housed_population
            )
            state.old_city.actual_departures = departures
            state.social_policy.unhandled_bodies = unhandled_bodies
            return (system or self.system())._ending_tags(state, scores)

        self.assertNotIn("grave_city", tags_for(29, 100))
        self.assertNotIn("grave_city", tags_for(30, 100))
        self.assertIn("grave_city", tags_for(31, 100))
        self.assertIn("grave_city", tags_for(15, 40))
        self.assertNotIn("grave_city", tags_for(21, 100))
        self.assertNotIn(
            "grave_city",
            tags_for(25, 100, departures=20),
        )
        self.assertNotIn(
            "grave_city",
            tags_for(0, 80, unhandled_bodies=100),
        )

        changed_scoring = dict(self.rules.scoring)
        changed_scoring["grave_city_death_ratio_percent"] = 50
        changed_rules = replace(self.rules, scoring=changed_scoring)
        configured = FinalFrostSystem(
            changed_rules,
            self.buildings,
            self.survival,
            self.technology,
        )
        self.assertNotIn(
            "grave_city",
            tags_for(40, 100, system=configured),
        )

    def test_clean_and_broken_survival_tags_follow_full_boundaries(self) -> None:
        state = self.make_state()
        state.final_frost.daily_records = {
            str(day): self.frost_record(day) for day in range(49, 56)
        }
        clean_scores = {
            "coal_and_core": 2,
            "food": 3,
            "housing_and_temperature": 3,
            "medical_and_disease": 3,
            "trust_and_panic": 3,
            "population_and_death": 3,
        }
        clean_tags = self.system()._ending_tags(state, clean_scores)
        self.assertIn("frost_survived_clean", clean_tags)

        one_zero_scores = {
            "coal_and_core": 0,
            "food": 4,
            "housing_and_temperature": 4,
            "medical_and_disease": 4,
            "trust_and_panic": 4,
            "population_and_death": 4,
        }
        broken_tags = self.system()._ending_tags(state, one_zero_scores)
        self.assertNotIn("frost_survived_broken", broken_tags)

        two_zero_scores = dict(one_zero_scores)
        two_zero_scores["food"] = 0
        self.assertIn(
            "frost_survived_broken",
            self.system()._ending_tags(state, two_zero_scores),
        )

        state.population.population_total = 20
        state.population.population_alive = 20
        state.population.healthy_population = 20
        state.population.workers = 20
        state.population.housed_population = 20
        state.population.homeless_population = 0
        overlap_scores = {
            "coal_and_core": 4,
            "food": 4,
            "housing_and_temperature": 4,
            "medical_and_disease": 4,
            "trust_and_panic": 4,
            "population_and_death": 1,
        }
        overlap_tags = self.system()._ending_tags(state, overlap_scores)
        self.assertIn("frost_survived_broken", overlap_tags)
        self.assertNotIn("frost_survived_clean", overlap_tags)

    def test_frozen_homeless_uses_only_homeless_group_harm(self) -> None:
        state = self.make_state()
        scores = {
            "coal_and_core": 4,
            "food": 4,
            "housing_and_temperature": 4,
            "medical_and_disease": 4,
            "trust_and_panic": 4,
            "population_and_death": 4,
        }
        state.final_frost.daily_records = {
            str(day): self.frost_record(day) for day in range(49, 56)
        }
        record = state.final_frost.daily_records["49"]
        record.homeless_exposure_population = 1
        record.new_sick = 5
        record.new_disabled = 2
        record.cold_deaths = 1
        record.raw_cold_deaths = 1
        record.actual_cold_deaths = 1

        self.assertNotIn(
            "frozen_homeless",
            self.system()._ending_tags(state, scores),
        )

        record.homeless_new_sick = 1
        self.assertIn(
            "frozen_homeless",
            self.system()._ending_tags(state, scores),
        )

    def test_refugee_and_promise_tags_use_windowed_settlement_facts(self) -> None:
        state = self.make_state()
        scores = {
            "coal_and_core": 4,
            "food": 4,
            "housing_and_temperature": 4,
            "medical_and_disease": 4,
            "trust_and_panic": 4,
            "population_and_death": 4,
        }
        state.events.fixed_arrival_choices["arrival_day6"] = "accept_all"
        state.events.fixed_arrival_pressure_days["arrival_day6"] = [6, 7]
        self.assertNotIn(
            "refugee_pressure",
            self.system()._ending_tags(state, scores),
        )
        state.events.fixed_arrival_pressure_days["arrival_day6"].append(8)
        self.assertIn(
            "refugee_pressure",
            self.system()._ending_tags(state, scores),
        )

        state.promises.settlement_history = [
            PromiseSettlementRecord(
                promise_id=f"promise-{index}",
                promise_type="medical",
                settled_day=10 + index,
                outcome="success",
                severity="serious",
                trust_change=1,
                panic_change=-1,
            )
            for index in range(4)
        ]
        self.assertIn(
            "promise_keeper",
            self.system()._ending_tags(state, scores),
        )
        state.promises.settlement_history = [
            PromiseSettlementRecord(
                promise_id=f"failed-{index}",
                promise_type="food",
                settled_day=20 + index,
                outcome="failure",
                severity="minor",
                trust_change=-1,
                panic_change=1,
            )
            for index in range(3)
        ]
        self.assertIn(
            "promise_breaker",
            self.system()._ending_tags(state, scores),
        )

        state.old_city.promise_outcome = "failure"
        state.old_city.promise_settled_day = 40
        self.assertNotIn(
            "old_city_promise_failed",
            self.system()._ending_tags(state, scores),
        )
        state.old_city.countdown_day = 41
        self.assertIn(
            "old_city_promise_failed",
            self.system()._ending_tags(state, scores),
        )

    def test_final_frost_history_rejects_discontinuous_population(self) -> None:
        state = self.make_state()
        system = self.system()
        system.prepare_new_day(state)
        state.calendar.current_day = 51
        state.daily_survival.settled_day = 50
        state.daily_survival.base_temperature = self.rules.temperatures[50].real
        state.daily_survival.zone_temperatures = {
            "inner_ring": self.rules.temperatures[50].real,
            "middle_ring": self.rules.temperatures[50].real,
            "outer_ring": self.rules.temperatures[50].real,
        }
        for day, start in ((49, 80), (50, 79)):
            state.final_frost.daily_records[str(day)] = self.frost_record(
                day,
                population_start=start,
                population_end=80,
            )
        with self.assertRaisesRegex(SaveDataError, "discontinuous"):
            decode_game_state(encode_game_state(state))

    def test_d48_old_city_panic_below_new_floor_is_not_erased_by_firepit(
        self,
    ) -> None:
        state = self.make_state(day=48)
        self.set_population(state, healthy=20, housed=20)
        state.resources.coal = 2000
        state.resources.cooked_food = 1000
        state.resources.raw_food = 0
        state.furnace.is_active = True
        state.furnace.mode_id = "level_3"
        state.laws.signed_law_ids = ["firepit_law"]
        state.laws.active_law_ids = ["firepit_law"]
        state.social_policy.firepit_enabled = True
        state.trust_panic.panic = 9

        old = state.old_city
        old.is_unlocked = True
        old.reference_population = 20
        old.low_threshold = 10
        old.middle_threshold = 18
        old.high_threshold = 28
        old.member_count = 20
        old.active_stage_id = "public_gathering"
        old.stage_events_seen = [
            "southern_letter",
            "rumors",
            "public_gathering",
        ]

        engine, _events, _oath_order = self.full_engine()
        execution = self.settle(engine, state, "d48-old-city-firepit")

        self.assertEqual(execution.result.code, ErrorCode.OK)
        self.assertEqual(state.old_city.result_id, "partial_exodus")
        self.assertEqual(state.trust_panic.panic, 14)
        codes = [item.code for item in execution.logs]
        self.assertLess(
            codes.index("old_city.daily.updated"),
            codes.index("laws.firepit_daily_relief.resolved"),
        )
        self.assertLess(
            codes.index("laws.firepit_daily_relief.resolved"),
            codes.index("end_day.stage.check_hard_fails"),
        )

    def test_d49_firepit_updates_panic_before_frost_daily_record(
        self,
    ) -> None:
        state = self.make_state(day=49)
        self.set_population(state, healthy=20, housed=20)
        state.resources.coal = 2000
        state.resources.cooked_food = 1000
        state.resources.raw_food = 0
        state.furnace.is_active = True
        state.furnace.mode_id = "level_3"
        state.laws.signed_law_ids = ["firepit_law"]
        state.laws.active_law_ids = ["firepit_law"]
        state.social_policy.firepit_enabled = True
        state.trust_panic.panic = 80
        self.system().prepare_new_day(state)

        engine, _events, _oath_order = self.full_engine()
        execution = self.settle(engine, state, "d49-firepit-record")

        self.assertEqual(execution.result.code, ErrorCode.OK)
        self.assertEqual(state.trust_panic.panic, 79)
        self.assertFalse(state.final_frost.daily_records["49"].panic_crisis)
        codes = [item.code for item in execution.logs]
        self.assertLess(
            codes.index("end_day.stage.update_promise_targets"),
            codes.index("laws.firepit_daily_relief.resolved"),
        )
        self.assertLess(
            codes.index("laws.firepit_daily_relief.resolved"),
            codes.index("final_frost.day.recorded"),
        )
        self.assertLess(
            codes.index("final_frost.day.recorded"),
            codes.index("end_day.stage.check_hard_fails"),
        )

    def test_full_d48_to_d55_pipeline_uses_every_real_system_and_rolls_back(
        self,
    ) -> None:
        state = self.make_state(day=48)
        self.set_population(state, healthy=20, housed=20)
        state.resources.coal = 1400
        state.resources.cooked_food = 200
        state.resources.raw_food = 0
        state.furnace.is_active = True
        state.furnace.mode_id = "level_3"
        state.old_city.is_unlocked = True
        state.old_city.reference_population = 20
        state.old_city.low_threshold = 10
        state.old_city.middle_threshold = 18
        state.old_city.high_threshold = 28
        state.old_city.stage_events_seen = [
            "southern_letter",
            "rumors",
            "public_gathering",
            "countdown",
        ]
        state.old_city.countdown_day = 48
        state.old_city.resolved = True
        state.old_city.result_id = "scattered"
        state.old_city.settlement_day = 48
        state.old_city.settlement_member_count = 8
        state.old_city.settlement_resource_losses = {
            "cooked_food": 0,
            "coal": 0,
            "wood": 0,
            "steel": 0,
        }
        autosaves = []
        engine, events, oath_order = self.full_engine(
            autosave_sink=autosaves.append
        )
        events.initialize_day(state)
        pre_day_55 = None

        for day in range(48, 56):
            self.assertEqual(state.calendar.current_day, day)
            self.resolve_active_events(events, state)
            self.resolve_pending_old_city(oath_order, state)
            if day == 55:
                pre_day_55 = deepcopy(state)
            execution = self.settle(engine, state, f"full-end-{day}")
            self.assertEqual(
                execution.result.code,
                ErrorCode.OK,
                (
                    day,
                    execution.result.data,
                    [
                        (item.code, dict(item.payload))
                        for item in execution.logs[-5:]
                    ],
                ),
            )
            self.assertEqual(
                decode_game_state(encode_game_state(state)),
                state,
            )

        self.assertEqual(
            sorted(int(day) for day in state.final_frost.daily_records),
            list(range(49, 56)),
        )
        self.assertEqual(len(autosaves), 8)
        self.assertTrue(state.final_result.is_finalized)
        self.assertTrue(state.final_result.report.is_generated)
        self.assertEqual(state.final_result.report.generated_day, 55)
        self.assertEqual(state.calendar.current_day, 55)
        self.assertNotIn("56", state.final_frost.daily_records)
        self.assertEqual(
            state.final_result.total_score,
            sum(state.final_result.system_scores.values()),
        )
        all_tags = set(state.final_result.ending_tags)
        self.assertFalse(
            {"prepared_for_frost", "unprepared_frost"}.issubset(all_tags)
        )
        self.assertFalse(
            {"frost_survived_clean", "frost_survived_broken"}.issubset(
                all_tags
            )
        )

        assert pre_day_55 is not None
        failed = deepcopy(pre_day_55)
        failed_before = deepcopy(failed)
        failed_autosaves = []
        failed_engine, _failed_events, _failed_oath_order = self.full_engine(
            autosave_sink=failed_autosaves.append
        )

        def corrupt_final_result(context: EndDayContext) -> None:
            context.state.final_result.system_scores["food"] = 99

        failed_engine.register_stage_handler(
            EndDayStage.RECORD_DAILY_LOG_AND_ENDING_TAGS,
            corrupt_final_result,
        )
        rejected = self.settle(failed_engine, failed, "corrupt-end-55")
        self.assertEqual(rejected.result.code, ErrorCode.INTERNAL_ERROR)
        self.assertEqual(failed, failed_before)
        self.assertEqual(failed_autosaves, [])
        self.assertIsNone(failed_engine.last_autosave())

    def test_day_48_boundary_and_day_49_settlement_are_transactional(self) -> None:
        state = self.make_state(day=48)
        building_system = BuildingSystem(
            self.buildings, self.survival, self.technology
        )
        built = building_system.execute(
            state,
            CommandRequest(
                "build-hunting-boundary",
                "game.build",
                {"building_type": "hunting_lodge", "zone": "outer_ring"},
                state.command_sequence,
            ),
        )
        self.assertEqual(built.code, ErrorCode.OK)
        hunting_lodge_id = built.data["building_id"]
        state.buildings[hunting_lodge_id].assigned_workers = 5
        state.buildings[hunting_lodge_id].is_operational = True
        engine = EndDayEngine()
        SurvivalSystem(
            self.survival, self.buildings, self.technology
        ).install(engine)
        BuildingSystem(
            self.buildings, self.survival, self.technology
        ).install(engine)
        self.system().install(engine)

        def settle(command_id: str):
            execution = engine.execute(
                state,
                CommandRequest(
                    command_id,
                    END_DAY_COMMAND,
                    {},
                    state.command_sequence,
                ),
            )
            if (
                execution.result.code
                is ErrorCode.END_DAY_CONFIRMATION_REQUIRED
            ):
                execution = engine.execute(
                    state,
                    CommandRequest(
                        f"confirm-{command_id}",
                        CONFIRM_END_DAY_COMMAND,
                        execution.result.data["confirmation"],
                        state.command_sequence,
                    ),
                )
            self.assertEqual(execution.result.code, ErrorCode.OK)
            return execution

        settle("end-48")
        self.assertEqual(state.calendar.current_day, 49)
        self.assertEqual(state.final_frost.baseline_day, 49)
        self.assertFalse(state.buildings[hunting_lodge_id].is_operational)
        before = deepcopy(state)
        settled = settle("end-49")
        self.assertIn("49", state.final_frost.daily_records)
        self.assertIsNotNone(settled.autosave)
        self.assertNotEqual(state, before)
