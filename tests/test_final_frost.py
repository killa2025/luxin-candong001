from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from furnace_winter.config import (
    FinalFrostConfigError,
    load_building_rules,
    load_final_frost_rules,
    load_survival_rules,
    load_technology_rules,
)
from furnace_winter.gameplay import (
    BuildingSystem,
    CONFIRM_END_DAY_COMMAND,
    END_DAY_COMMAND,
    EndDayEngine,
    EndDayStage,
    FinalFrostSystem,
    SurvivalSystem,
    create_initial_survival_state,
)
from furnace_winter.gameplay.end_day import EndDayContext
from furnace_winter.models import (
    DeterministicRandom,
    EventResolutionRecord,
    FrostDayRecord,
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

    def test_day_49_baseline_and_preparation_are_stable(self) -> None:
        state = self.make_state()
        self.system().prepare_new_day(state)
        baseline = deepcopy(state.final_frost)
        self.system().prepare_new_day(state)
        self.assertEqual(state.final_frost, baseline)
        self.assertEqual(state.final_frost.baseline_day, 49)
        self.assertEqual(state.final_frost.baseline_alive_population, 80)
        self.assertEqual(state.final_frost.prepared_item_count, 4)
        self.assertEqual(state.final_frost.preparation_tags, [])

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
            self.context(state, 49, EndDayStage.UPDATE_PROMISE_TARGETS)
        )
        record = state.final_frost.daily_records["49"]
        self.assertGreater(record.new_sick, 0)
        self.assertEqual(record.real_temperature, -66)
        restored = decode_game_state(encode_game_state(state))
        self.assertEqual(restored, state)

    def test_day_55_scores_six_systems_and_applies_quality_cap(self) -> None:
        state = self.make_state()
        system = self.system()
        system.prepare_new_day(state)
        for day in range(49, 56):
            rule = self.rules.temperatures[day]
            state.final_frost.daily_records[str(day)] = FrostDayRecord(
                day=day,
                real_temperature=rule.real,
                display_label=rule.display_label,
                population_start=80,
                population_end=80,
            )
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

    def test_v10_migration_is_safe_before_frost_and_rejects_frost_history_gap(self) -> None:
        state = self.make_state(day=48)
        document = encode_game_state(state)
        document["save_data_version"] = 10
        del document["final_frost"]
        del document["medical"]["sick_treatment_progress"]
        for field in (
            "system_scores",
            "total_score",
            "major_tags",
            "defining_tags",
        ):
            del document["final_result"][field]
        restored = decode_game_state(document)
        self.assertEqual(restored.calendar.current_day, 48)
        self.assertFalse(restored.final_frost.entered)

        document["calendar"]["current_day"] = 49
        with self.assertRaisesRegex(SaveDataError, "cannot reconstruct"):
            decode_game_state(document)

    def test_old_city_route_and_arrival_tags_use_patch_008_fact_ids(self) -> None:
        state = self.make_state()
        system = self.system()
        system.prepare_new_day(state)
        for day in range(49, 56):
            rule = self.rules.temperatures[day]
            state.final_frost.daily_records[str(day)] = FrostDayRecord(
                day=day,
                real_temperature=rule.real,
                display_label=rule.display_label,
                population_start=80,
                population_end=80,
            )
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

    def test_final_frost_history_rejects_discontinuous_population(self) -> None:
        state = self.make_state()
        system = self.system()
        system.prepare_new_day(state)
        for day, start in ((49, 80), (50, 79)):
            rule = self.rules.temperatures[day]
            state.final_frost.daily_records[str(day)] = FrostDayRecord(
                day=day,
                real_temperature=rule.real,
                display_label=rule.display_label,
                population_start=start,
                population_end=80,
            )
        with self.assertRaisesRegex(SaveDataError, "discontinuous"):
            decode_game_state(encode_game_state(state))

    def test_day_48_boundary_and_day_49_settlement_are_transactional(self) -> None:
        state = self.make_state(day=48)
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
        before = deepcopy(state)
        settled = settle("end-49")
        self.assertIn("49", state.final_frost.daily_records)
        self.assertIsNotNone(settled.autosave)
        self.assertNotEqual(state, before)
