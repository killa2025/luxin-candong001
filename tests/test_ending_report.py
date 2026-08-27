from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
from pathlib import Path

from furnace_winter.cli import main
from furnace_winter.config import (
    load_building_rules,
    load_final_frost_rules,
    load_survival_rules,
    load_technology_rules,
)
from furnace_winter.gameplay import (
    END_RUN_COMMAND,
    EndingReportSystem,
    FinalFrostSystem,
    create_initial_survival_state,
)
from furnace_winter.gameplay.end_day import EndDayContext, EndDayStage
from furnace_winter.interface import CommandRequest, ErrorCode
from furnace_winter.models import (
    CURRENT_SAVE_DATA_VERSION,
    CURRENT_ENDING_REPORT_FORMAT_VERSION,
    LEGACY_ENDING_REPORT_FORMAT_VERSION,
    PATCH_020_ENDING_REPORT_FORMAT_VERSION,
    PATCH_027_ENDING_REPORT_FORMAT_VERSION,
    PATCH_029_ENDING_REPORT_FORMAT_VERSION,
    BuildingState,
    DeterministicRandom,
    EndingReportState,
    EventResolutionRecord,
    FrostDayRecord,
    HardFailType,
    RunState,
    SaveDataError,
    decode_game_state,
    encode_game_state,
    validate_game_state,
)
from furnace_winter.models.ending_selection import (
    canonical_report_body_text_ids,
    canonical_report_pending_text_ids,
    legacy_report_pending_text_ids,
    patch020_report_body_text_ids,
    patch020_report_pending_text_ids,
    patch027_report_body_text_ids,
    patch027_report_pending_text_ids,
    patch029_report_body_text_ids,
    patch029_report_pending_text_ids,
    report_template_values,
)
from furnace_winter.text import (
    build_ending_pending_registry,
    build_ending_text_registry,
)


ROOT = Path(__file__).resolve().parents[1]


class EndingReportPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.survival = load_survival_rules(ROOT / "data" / "survival.json")
        cls.buildings = load_building_rules(ROOT / "data" / "buildings.json")
        cls.technology = load_technology_rules(
            ROOT / "data" / "technologies.json"
        )
        cls.frost = load_final_frost_rules(
            ROOT / "data" / "final_frost.json"
        )

    def frost_system(self) -> FinalFrostSystem:
        return FinalFrostSystem(
            self.frost,
            self.buildings,
            self.survival,
            self.technology,
        )

    def state_before_finalization(self):
        state = create_initial_survival_state(
            self.survival, self.buildings, random_seed=1010
        )
        state.calendar.current_day = 55
        state.daily_survival.settled_day = 55
        state.daily_survival.base_temperature = (
            self.frost.temperatures[55].real
        )
        state.daily_survival.zone_temperatures = {
            "inner_ring": self.frost.temperatures[55].real,
            "middle_ring": self.frost.temperatures[55].real,
            "outer_ring": self.frost.temperatures[55].real,
        }
        for event_id, trigger_day in (
            ("arrival_day6", 6),
            ("arrival_day19", 19),
            ("arrival_day37", 37),
        ):
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
        population = state.population.population_alive
        state.final_frost.entered = True
        state.final_frost.baseline_day = 49
        state.final_frost.baseline_alive_population = population
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
        state.final_frost.prepared_item_count = 0
        state.final_frost.unprepared_item_count = 6
        state.final_frost.preparation_tags = ["unprepared_frost"]
        base_cap = min(22, 12 + max(0, population - 80) // 35)
        state.final_frost.daily_records = {
            str(day): FrostDayRecord(
                day=day,
                real_temperature=self.frost.temperatures[day].real,
                display_label=self.frost.temperatures[day].display_label,
                population_start=population,
                population_end=population,
                base_natural_death_cap=base_cap,
                applied_natural_death_cap=base_cap,
            )
            for day in range(49, 56)
        }
        state.final_frost.frost_population_person_days = population * 7
        return state

    def completed_state(self, seed: int = 1010):
        state = self.state_before_finalization()
        state.random = DeterministicRandom(seed).snapshot()
        system = self.frost_system()
        context = EndDayContext(
            state=state,
            random=DeterministicRandom.from_state(state.random),
            settled_day=55,
            stage=EndDayStage.RECORD_DAILY_LOG_AND_ENDING_TAGS,
            _emit=lambda _code, _payload: None,
        )
        system.finalize_day_55(context)
        state.calendar.is_day_locked = True
        state.calendar.is_end_day_confirmed = True
        restored = decode_game_state(encode_game_state(state))
        self.assertEqual(restored, state)
        return state

    def configure_resolved_partial_old_city(
        self,
        state,
        *,
        actual_departures: int,
        resource_losses: dict[str, int],
    ) -> None:
        old = state.old_city
        old.is_unlocked = True
        old.reference_population = state.population.population_alive
        old.low_threshold = 5
        old.middle_threshold = 10
        old.high_threshold = 30
        old.stage_events_seen = [
            "southern_letter",
            "rumors",
            "public_gathering",
            "countdown",
        ]
        old.countdown_day = 48
        old.resolved = True
        old.result_id = "partial_exodus"
        old.settlement_day = 48
        old.settlement_member_count = 20
        old.theoretical_departures = 8
        old.actual_departures = actual_departures
        state.population.population_total_ever = (
            state.population.population_total + actual_departures
        )
        old.reduction_reason = (
            "population_protection" if actual_departures < 8 else None
        )
        old.settlement_resource_losses = resource_losses
        state.final_result.report = EndingReportState()
        EndingReportSystem().generate(state)

    @staticmethod
    def execute(
        system: EndingReportSystem,
        state,
        command_id: str,
        arguments: dict,
    ):
        return system.execute(
            state,
            CommandRequest(
                command_id,
                END_RUN_COMMAND,
                arguments,
                state.command_sequence,
            ),
        )

    def test_end_run_rejects_d54_incomplete_confirmation_and_hard_fail(self) -> None:
        system = EndingReportSystem()
        d54 = self.state_before_finalization()
        d54.calendar.current_day = 54
        d54.daily_survival.settled_day = 53
        d54.daily_survival.base_temperature = (
            self.frost.temperatures[53].real
        )
        d54.daily_survival.zone_temperatures = {
            "inner_ring": self.frost.temperatures[53].real,
            "middle_ring": self.frost.temperatures[53].real,
            "outer_ring": self.frost.temperatures[53].real,
        }
        del d54.final_frost.daily_records["54"]
        del d54.final_frost.daily_records["55"]
        d54.final_frost.frost_population_person_days = (
            d54.population.population_alive * 5
        )
        before = deepcopy(d54)
        rejected = self.execute(system, d54, "d54-end", {"confirm": True})
        self.assertEqual(rejected.code, ErrorCode.ILLEGAL_COMMAND)
        self.assertEqual(rejected.data["reason"], "d55_not_reached")
        self.assertEqual(d54, before)

        incomplete = self.state_before_finalization()
        rejected = self.execute(
            system, incomplete, "incomplete-end", {"confirm": True}
        )
        self.assertEqual(rejected.code, ErrorCode.ILLEGAL_COMMAND)
        self.assertEqual(
            rejected.data["reason"], "d55_final_settlement_incomplete"
        )

        completed = self.completed_state()
        missing = self.execute(system, completed, "missing-confirm", {})
        self.assertEqual(missing.code, ErrorCode.INVALID_ARGUMENTS)
        false_confirm = self.execute(
            system, completed, "false-confirm", {"confirm": False}
        )
        self.assertEqual(false_confirm.code, ErrorCode.ILLEGAL_COMMAND)
        self.assertEqual(
            false_confirm.data["reason"],
            "confirm_false_is_not_preview",
        )

        hard_fail = self.completed_state()
        final = hard_fail.final_result
        final.hard_fail_type = HardFailType.POPULATION_ZERO
        final.ending_id = "hard_fail"
        final.ending_tags = ["hard_fail", "population_zero"]
        final.system_scores = {}
        final.total_score = None
        final.major_tags = []
        final.defining_tags = []
        final.report = EndingReportState()
        EndingReportSystem().generate(hard_fail)
        hard_fail_view = system.observe(hard_fail)
        self.assertEqual(
            hard_fail_view["title"]["text_id"],
            "ending.hard_fail.population_zero.title",
        )
        self.assertIn(
            "ending.report.death_record.none",
            [item["text_id"] for item in hard_fail_view["body"]],
        )
        self.assertEqual(hard_fail_view["pending_text_ids"], [])
        rejected = self.execute(
            system, hard_fail, "hard-fail-end", {"confirm": True}
        )
        self.assertEqual(rejected.code, ErrorCode.ILLEGAL_COMMAND)
        self.assertEqual(
            rejected.data["reason"], "hard_fail_cannot_be_overwritten"
        )

    def test_success_preserves_result_is_idempotent_and_never_creates_d56(
        self,
    ) -> None:
        state = self.completed_state()
        system = EndingReportSystem()
        original = deepcopy(state.final_result)
        original_population = deepcopy(state.population)
        original_resources = deepcopy(state.resources)
        original_trust_panic = deepcopy(state.trust_panic)
        original_random = deepcopy(state.random)
        original_frost = deepcopy(state.final_frost)
        original_calendar = deepcopy(state.calendar)

        result = self.execute(system, state, "end-run", {"confirm": True})

        self.assertEqual(result.code, ErrorCode.OK)
        self.assertIs(state.final_result.run_state, RunState.ENDED)
        self.assertEqual(
            state.final_result.termination_reason.value, "player_ended"
        )
        self.assertEqual(state.final_result.ending_id, original.ending_id)
        self.assertEqual(
            state.final_result.system_scores, original.system_scores
        )
        self.assertEqual(
            state.final_result.ending_tags, original.ending_tags
        )
        self.assertEqual(state.population, original_population)
        self.assertEqual(state.resources, original_resources)
        self.assertEqual(state.trust_panic, original_trust_panic)
        self.assertEqual(state.random, original_random)
        self.assertEqual(state.final_frost, original_frost)
        self.assertEqual(state.calendar, original_calendar)
        self.assertEqual(state.calendar.current_day, 55)
        self.assertNotIn("56", state.final_frost.daily_records)
        first_state = deepcopy(state)
        first_report = deepcopy(result.data)

        repeated = self.execute(
            system, state, "end-run-again", {"confirm": True}
        )
        self.assertEqual(repeated.code, ErrorCode.ILLEGAL_COMMAND)
        self.assertEqual(repeated.data["reason"], "already_ended")
        self.assertEqual(state, first_state)
        self.assertEqual(system.observe(state), first_report)

    def test_report_uses_seeded_persisted_selection_and_omits_placeholders(
        self,
    ) -> None:
        first = self.completed_state()
        same = self.completed_state()
        second = self.completed_state(seed=999999)
        first_view = EndingReportSystem().observe(first)
        same_view = EndingReportSystem().observe(same)
        second_view = EndingReportSystem().observe(second)

        self.assertEqual(first_view, same_view)
        self.assertEqual(
            first.final_result.report.format_version,
            CURRENT_ENDING_REPORT_FORMAT_VERSION,
        )
        self.assertNotEqual(first_view["body"], second_view["body"])
        self.assertTrue(first_view["body"])
        self.assertEqual(first_view["pending_text_ids"], [])
        self.assertEqual(
            first_view["pending_text_ids"],
            sorted(set(first_view["pending_text_ids"])),
        )
        rendered_ids = {
            first_view["title"]["text_id"],
            *(item["text_id"] for item in first_view["body"]),
        }
        self.assertEqual(
            first_view["body"][0]["text_id"],
            "ending.standard_victory.body.03",
        )
        self.assertIn(
            "ending.report.death_record.none", rendered_ids
        )
        self.assertNotIn("ending.report.frostfall_deaths", rendered_ids)
        self.assertFalse(
            any(
                text_id.startswith("ending.report.illness.")
                for text_id in rendered_ids
            )
        )
        self.assertFalse(any(text_id.endswith(".pool") for text_id in rendered_ids))
        self.assertNotIn("TODO_TEXT", json.dumps(first_view, ensure_ascii=False))
        self.assertNotIn("PENDING", json.dumps(first_view, ensure_ascii=False))
        self.assertIn(
            "没有任何人被霜落吞噬，你做得很好，执政官。",
            [item["text"] for item in first_view["body"]],
        )

    def test_additional_death_and_medical_text_require_exact_facts(
        self,
    ) -> None:
        death_state = self.completed_state()
        death_state.population.population_dead = 5
        death_state.final_result.defining_tags = ["mass_death"]
        death_state.final_result.major_tags = []
        death_state.final_frost.frost_deaths = 0
        for seed in range(32):
            death_state.random = DeterministicRandom(seed).snapshot()
            selected = canonical_report_body_text_ids(death_state)
            self.assertNotIn("ending.additional.death.03", selected)

        medical_state = self.completed_state()
        medical_state.population.population_dead = 0
        medical_state.final_result.defining_tags = ["medical_collapse"]
        medical_state.final_result.major_tags = []
        medical_state.buildings["medical-station-test"] = BuildingState(
            building_id="medical-station-test",
            building_type="medical_station",
            zone="inner_ring",
            slot_size=1,
            is_built=True,
            is_operational=True,
        )
        for record in medical_state.final_frost.daily_records.values():
            record.actual_disease_deaths = 0
            record.medical_overflow = True
        for seed in range(32):
            medical_state.random = DeterministicRandom(seed).snapshot()
            selected = canonical_report_body_text_ids(medical_state)
            self.assertFalse(
                any(
                    text_id.startswith("ending.additional.medical.")
                    for text_id in selected
                )
            )

        station = medical_state.buildings["medical-station-test"]
        station.assigned_medical_apprentices = 1
        selected = canonical_report_body_text_ids(medical_state)
        self.assertNotIn("ending.additional.medical.03", selected)

        medical_state.buildings["hospital-doctor-test"] = BuildingState(
            building_id="hospital-doctor-test",
            building_type="hospital",
            zone="inner_ring",
            slot_size=1,
            is_built=True,
            is_operational=True,
            assigned_engineers=1,
        )
        selected = canonical_report_body_text_ids(medical_state)
        self.assertNotIn("ending.additional.medical.03", selected)

        station.assigned_engineers = 1
        selected = canonical_report_body_text_ids(medical_state)
        self.assertIn("ending.additional.medical.03", selected)

    def test_primary_illness_sentence_matches_d55_service_fact(self) -> None:
        state = self.completed_state()
        state.population.sick_population = 6
        state.final_result.system_scores["medical_and_disease"] = 1
        state.buildings["medical-station-test"] = BuildingState(
            building_id="medical-station-test",
            building_type="medical_station",
            zone="inner_ring",
            slot_size=1,
            is_built=True,
            is_operational=True,
        )
        record = state.final_frost.daily_records["55"]
        record.service_history_known = True
        record.medical_operational_building_count = 0
        record.medical_building_capacity = 0

        selected = canonical_report_body_text_ids(state)
        self.assertNotIn("ending.report.illness.04", selected)
        self.assertIn(
            "ending.report.illness.no_service",
            selected,
        )
        self.assertNotIn(
            "ending.report.illness.no_operational_service",
            canonical_report_pending_text_ids(state),
        )

        state.resources.coal = 0
        state.resources.raw_food = 1
        state.resources.cooked_food = 0
        selected = canonical_report_body_text_ids(state)
        self.assertIn("ending.report.illness.no_service", selected)
        self.assertIn("ending.report.coal_food.coal_empty", selected)
        self.assertEqual(
            sum(
                text_id
                in {
                    "ending.report.coal_food.coal_empty",
                    "ending.report.coal_food.food_empty",
                    "ending.report.coal_food.both_empty",
                }
                for text_id in selected
            ),
            1,
        )

        record.service_history_known = False
        self.assertNotIn(
            "ending.report.illness.no_service",
            canonical_report_body_text_ids(state),
        )
        self.assertIn(
            "ending.report.illness.no_operational_service",
            canonical_report_pending_text_ids(state),
        )
        self.assertIn(
            "ending.report.illness.04",
            patch020_report_body_text_ids(state),
        )
        self.assertNotIn(
            "ending.report.illness.no_service",
            patch027_report_body_text_ids(state),
        )
        self.assertIn(
            "ending.report.illness.no_operational_service",
            patch027_report_pending_text_ids(state),
        )

        record.service_history_known = True
        record.medical_operational_building_count = 1
        record.medical_building_capacity = 10
        self.assertIn(
            "ending.report.illness.04",
            canonical_report_body_text_ids(state),
        )
        self.assertNotIn(
            "ending.report.illness.no_operational_service",
            canonical_report_pending_text_ids(state),
        )

    def test_primary_coal_food_sentence_matches_each_zero_stock_fact(self) -> None:
        state = self.completed_state()
        state.resources.coal = 7
        state.resources.raw_food = 0
        state.resources.cooked_food = 0
        state.final_result.system_scores["coal_and_core"] = 2
        state.final_result.system_scores["food"] = 0

        selected = canonical_report_body_text_ids(state)
        self.assertIn(
            "ending.report.coal_food.food_empty",
            selected,
        )
        self.assertNotIn(
            "ending.report.coal_food.zero_stock",
            canonical_report_pending_text_ids(state),
        )
        self.assertIn(
            "ending.report.coal_food.01",
            patch020_report_body_text_ids(state),
        )
        self.assertNotIn(
            "ending.report.coal_food.food_empty",
            patch027_report_body_text_ids(state),
        )
        self.assertIn(
            "ending.report.coal_food.zero_stock",
            patch027_report_pending_text_ids(state),
        )

        state.resources.cooked_food = 1
        self.assertIn(
            "ending.report.coal_food.01",
            canonical_report_body_text_ids(state),
        )
        self.assertNotIn(
            "ending.report.coal_food.zero_stock",
            canonical_report_pending_text_ids(state),
        )

        state.resources.coal = 0
        self.assertIn(
            "ending.report.coal_food.coal_empty",
            canonical_report_body_text_ids(state),
        )

        state.resources.cooked_food = 0
        self.assertIn(
            "ending.report.coal_food.both_empty",
            canonical_report_body_text_ids(state),
        )

    def test_patch029_user_confirmed_report_text_is_exact(self) -> None:
        registry = build_ending_text_registry()
        expected = {
            "ending.report.illness.no_service": (
                "终局封存时，城里仍有病患，却已经没有一处医疗设施能够"
                "继续接诊。\n\n人们只能自己决定，把仅剩的照料先留给"
                "谁——以及让谁在无人回应的黑暗里继续等下去。"
            ),
            "ending.report.coal_food.coal_empty": (
                "食物还留在仓里，煤仓却已经空了。\n\n人们守着最后的"
                "口粮争论：是把它分给今天仍活着的人，还是留给一个可能"
                "永远不会到来的明天。"
            ),
            "ending.report.coal_food.food_empty": (
                "煤仓里还留着黑色的余量，食物却一份也没有剩下。\n\n"
                "人们这才明白，炉火可以让身体保持温暖，却不能阻止饥饿"
                "把尊严一点点剥走。"
            ),
            "ending.report.coal_food.both_empty": (
                "煤仓与食物仓一起见了底。\n\n人们围在炉城最后的余温"
                "旁，不再问明天吃什么、烧什么，只开始沉默地看着彼此"
                "——仿佛最后的答案，迟早要从某个人身上取走。"
            ),
        }
        for text_id, text in expected.items():
            with self.subTest(text_id=text_id):
                entry = registry.require(text_id)
                self.assertEqual(entry.text, text)
                self.assertEqual(entry.status.value, "USER_OVERRIDE")

    def test_patch030_user_confirmed_long_text_is_runtime_safe(self) -> None:
        registry = build_ending_text_registry()
        text_ids = {
            "ending.route.oath.full_text",
            "ending.route.final_oath.full_text",
            "ending.route.iron.full_text",
            "ending.route.final_decree.full_text",
            "ending.old_city.scattered.full_text",
            "ending.old_city.partial_exodus.full_text",
            "ending.old_city.large_exodus.full_text",
            "ending.old_city.unresolved.full_text",
            "ending.old_city.promise.success",
            "ending.old_city.promise.failure",
            "ending.children.labor_low_risk.full_text",
            "ending.children.labor_all_jobs.full_text",
            "ending.children.protection.no_shelter.full_text",
            "ending.children.protection.shelter_only.full_text",
            "ending.children.protection.school.full_text",
            "ending.children.protection.medical_track.full_text",
            "ending.children.protection.engineering_track.full_text",
            "ending.entertainment.no_operational_facility.full_text",
            "ending.entertainment.tavern.full_text",
            "ending.entertainment.casino.full_text",
        }
        for text_id in sorted(text_ids):
            with self.subTest(text_id=text_id):
                entry = registry.require(text_id)
                self.assertEqual(entry.status.value, "USER_OVERRIDE")
                self.assertNotIn("TODO_TEXT", entry.text)
                self.assertNotIn("PENDING", entry.text)
        self.assertIsNone(
            registry.get("ending.entertainment.sedation_city.full_text")
        )
        pending = {
            entry.entry_id: entry
            for entry in build_ending_pending_registry().entries()
        }
        self.assertEqual(
            pending[
                "ending.entertainment.sedation_city.full_text"
            ].status.value,
            "PENDING",
        )

    def test_format_three_report_remains_strictly_loadable(self) -> None:
        state = self.completed_state()
        state.resources.coal = 0
        state.resources.raw_food = 0
        state.resources.cooked_food = 0
        state.final_result.report.format_version = (
            PATCH_027_ENDING_REPORT_FORMAT_VERSION
        )
        state.final_result.report.body_text_ids = patch027_report_body_text_ids(
            state
        )
        state.final_result.report.pending_text_ids = (
            patch027_report_pending_text_ids(state)
        )

        restored = decode_game_state(encode_game_state(state))

        self.assertEqual(
            restored.final_result.report.format_version,
            PATCH_027_ENDING_REPORT_FORMAT_VERSION,
        )
        self.assertEqual(
            restored.final_result.report.body_text_ids,
            state.final_result.report.body_text_ids,
        )
        self.assertEqual(
            restored.final_result.report.pending_text_ids,
            state.final_result.report.pending_text_ids,
        )

        disguised_as_current = encode_game_state(state)
        disguised_as_current["final_result"]["report"][
            "format_version"
        ] = CURRENT_ENDING_REPORT_FORMAT_VERSION
        with self.assertRaisesRegex(
            SaveDataError, "text selection is not canonical"
        ):
            decode_game_state(disguised_as_current)

    def test_format_four_report_remains_strictly_loadable(self) -> None:
        state = self.completed_state()
        state.oath_order.page_unlocked = True
        state.oath_order.selected_route = "oath"
        state.oath_order.signed_law_ids = ["guard_oath"]
        state.oath_order.law_signed_days = {"guard_oath": 35}
        state.oath_order.next_law_day = 37
        state.oath_order.oath_hall.enabled = True
        state.oath_order.oath_hall.visible = True
        state.final_result.report.format_version = (
            PATCH_029_ENDING_REPORT_FORMAT_VERSION
        )
        state.final_result.report.body_text_ids = patch029_report_body_text_ids(
            state
        )
        state.final_result.report.pending_text_ids = (
            patch029_report_pending_text_ids(state)
        )

        restored = decode_game_state(encode_game_state(state))

        self.assertEqual(
            restored.final_result.report.format_version,
            PATCH_029_ENDING_REPORT_FORMAT_VERSION,
        )
        self.assertEqual(
            restored.final_result.report.body_text_ids,
            state.final_result.report.body_text_ids,
        )
        self.assertIn(
            "ending.route.oath.full_text",
            restored.final_result.report.pending_text_ids,
        )
        self.assertNotIn(
            "ending.route.oath.full_text",
            restored.final_result.report.body_text_ids,
        )

        disguised_as_current = encode_game_state(state)
        disguised_as_current["final_result"]["report"][
            "format_version"
        ] = CURRENT_ENDING_REPORT_FORMAT_VERSION
        with self.assertRaisesRegex(
            SaveDataError, "text selection is not canonical"
        ):
            decode_game_state(disguised_as_current)

    def test_format_two_report_remains_strictly_loadable(self) -> None:
        state = self.completed_state()
        state.final_result.report.format_version = (
            PATCH_020_ENDING_REPORT_FORMAT_VERSION
        )
        state.final_result.report.body_text_ids = patch020_report_body_text_ids(
            state
        )
        state.final_result.report.pending_text_ids = (
            patch020_report_pending_text_ids(state)
        )

        restored = decode_game_state(encode_game_state(state))
        self.assertEqual(
            restored.final_result.report.format_version,
            PATCH_020_ENDING_REPORT_FORMAT_VERSION,
        )
        self.assertEqual(
            restored.final_result.report.body_text_ids,
            state.final_result.report.body_text_ids,
        )

    def test_unprovable_medical_history_text_is_pending(self) -> None:
        state = self.completed_state()
        state.population.population_dead = 5
        state.final_result.defining_tags = ["medical_collapse"]
        state.final_result.major_tags = []
        state.buildings["late-medical-station"] = BuildingState(
            building_id="late-medical-station",
            building_type="medical_station",
            zone="inner_ring",
            slot_size=1,
            is_built=True,
            is_operational=True,
        )
        death_day = next(iter(state.final_frost.daily_records.values()))
        death_day.actual_disease_deaths = 1
        death_day.medical_collapse = False
        death_day.hospital_shutdown = False
        death_day.medical_overflow = True

        pending_ids = {
            "ending.additional.medical.01",
            "ending.additional.medical.02",
        }
        for seed in range(64):
            state.random = DeterministicRandom(seed).snapshot()
            selected = canonical_report_body_text_ids(state)
            self.assertTrue(pending_ids.isdisjoint(selected))

        registry = build_ending_text_registry()
        pending_entries = {
            entry.entry_id: entry
            for entry in build_ending_pending_registry().entries()
        }
        for text_id in pending_ids:
            self.assertIsNotNone(registry.get(text_id))
            self.assertEqual(pending_entries[text_id].status.value, "PENDING")
            self.assertIn(text_id, canonical_report_pending_text_ids(state))

    def test_known_daily_medical_history_enables_only_proven_text(self) -> None:
        state = self.completed_state()
        state.final_result.defining_tags = ["medical_collapse"]
        state.final_result.major_tags = []
        for record in state.final_frost.daily_records.values():
            record.service_history_known = True
        record = state.final_frost.daily_records["51"]
        record.medical_operational_building_count = 1
        record.medical_building_capacity = 10
        record.actual_disease_deaths = 1
        record.medical_collapse = False
        record.medical_overflow = True

        selected_across_seeds: set[str] = set()
        for seed in range(64):
            state.random = DeterministicRandom(seed).snapshot()
            selected_across_seeds.update(canonical_report_body_text_ids(state))
        self.assertIn("ending.additional.medical.01", selected_across_seeds)
        self.assertIn("ending.additional.medical.02", selected_across_seeds)
        self.assertNotIn(
            "ending.additional.medical.01",
            canonical_report_pending_text_ids(state),
        )
        self.assertNotIn(
            "ending.additional.medical.02",
            canonical_report_pending_text_ids(state),
        )

        record.actual_disease_deaths = 0
        state.final_frost.daily_records["52"].actual_disease_deaths = 1
        state.final_frost.daily_records["52"].medical_overflow = True
        for seed in range(64):
            state.random = DeterministicRandom(seed).snapshot()
            selected = canonical_report_body_text_ids(state)
            self.assertNotIn("ending.additional.medical.01", selected)
            self.assertNotIn("ending.additional.medical.02", selected)

    def test_food_additional_does_not_invent_a_canteen_history(self) -> None:
        state = self.completed_state()
        state.final_result.defining_tags = ["famine_city"]
        state.final_result.major_tags = []
        self.assertFalse(
            any(
                building.building_type == "canteen"
                for building in state.buildings.values()
            )
        )
        for seed in range(64):
            state.random = DeterministicRandom(seed).snapshot()
            selected = canonical_report_body_text_ids(state)
            self.assertNotIn("ending.additional.food.01", selected)
            self.assertIn("ending.additional.food.02", selected)
        self.assertIn(
            "ending.additional.food.01",
            canonical_report_pending_text_ids(state),
        )

        for record in state.final_frost.daily_records.values():
            record.service_history_known = True
        self.assertNotIn(
            "ending.additional.food.01",
            canonical_report_pending_text_ids(state),
        )
        state.final_frost.daily_records["53"].canteen_operational = True
        selected_across_seeds: set[str] = set()
        for seed in range(64):
            state.random = DeterministicRandom(seed).snapshot()
            selected_across_seeds.update(canonical_report_body_text_ids(state))
        self.assertIn("ending.additional.food.01", selected_across_seeds)

    def test_children_full_text_replaces_pending_protection_trace(
        self,
    ) -> None:
        registry = build_ending_text_registry()
        pending_registry = build_ending_pending_registry()
        self.assertIsNone(registry.get("ending.trace.children_protected"))
        pending_entries = {
            entry.entry_id: entry for entry in pending_registry.entries()
        }
        self.assertNotIn("ending.trace.children_protected", pending_entries)

        state = self.completed_state()
        state.laws.signed_law_ids = [
            "child_protection_law",
            "child_school_law",
        ]
        for building_type in ("child_shelter", "school"):
            building_id = f"{building_type}-test"
            state.buildings[building_id] = BuildingState(
                building_id=building_id,
                building_type=building_type,
                zone="inner_ring",
                slot_size=1,
                is_built=True,
                is_operational=True,
            )
        self.assertNotIn(
            "ending.trace.children_protected",
            canonical_report_body_text_ids(state),
        )
        self.assertIn(
            "ending.children.protection.school.full_text",
            canonical_report_body_text_ids(state),
        )
        self.assertNotIn(
            "ending.trace.children_protected",
            canonical_report_pending_text_ids(state),
        )

    def test_patch030_terminal_route_text_replaces_general_route_trace(
        self,
    ) -> None:
        state = self.completed_state()
        state.oath_order.selected_route = "oath"
        selected = canonical_report_body_text_ids(state)
        self.assertIn("ending.route.oath.full_text", selected)
        self.assertNotIn("ending.trace.oath_route", selected)

        state.oath_order.signed_law_ids = ["final_oath"]
        state.oath_order.final_oath_active = True
        selected = canonical_report_body_text_ids(state)
        self.assertIn("ending.route.final_oath.full_text", selected)
        self.assertNotIn("ending.route.oath.full_text", selected)

        state.oath_order.selected_route = "iron"
        state.oath_order.signed_law_ids = ["highest_order"]
        state.oath_order.final_oath_active = False
        state.oath_order.highest_order_active = True
        selected = canonical_report_body_text_ids(state)
        self.assertIn("ending.route.final_decree.full_text", selected)
        self.assertNotIn("ending.route.iron.full_text", selected)
        self.assertNotIn("ending.trace.iron_route", selected)

    def test_patch030_old_city_text_uses_result_and_one_promise_appendix(
        self,
    ) -> None:
        state = self.completed_state()
        state.old_city.is_unlocked = True
        cases = {
            "scattered": "ending.old_city.scattered.full_text",
            "partial_exodus": "ending.old_city.partial_exodus.full_text",
            "large_exodus": "ending.old_city.large_exodus.full_text",
            None: "ending.old_city.unresolved.full_text",
        }
        for result_id, expected in cases.items():
            with self.subTest(result_id=result_id):
                state.old_city.result_id = result_id
                state.old_city.actual_departures = (
                    7 if result_id in {"partial_exodus", "large_exodus"} else 0
                )
                state.old_city.settlement_resource_losses = (
                    {"coal": 1}
                    if result_id in {"partial_exodus", "large_exodus"}
                    else {}
                )
                selected = canonical_report_body_text_ids(state)
                self.assertIn(expected, selected)
                self.assertNotIn("ending.trace.old_city", selected)

        state.old_city.result_id = "partial_exodus"
        state.old_city.actual_departures = 7
        state.old_city.settlement_resource_losses = {"coal": 1}
        state.old_city.promise_settled = True
        state.old_city.promise_outcome = "success"
        selected = canonical_report_body_text_ids(state)
        self.assertIn("ending.old_city.promise.success", selected)
        self.assertNotIn("ending.old_city.promise.failure", selected)
        rendered = build_ending_text_registry().require(
            "ending.old_city.partial_exodus.full_text"
        ).text.format_map(report_template_values(state))
        self.assertIn("7 个人", rendered)

        state.old_city.promise_outcome = "failure"
        selected = canonical_report_body_text_ids(state)
        self.assertIn("ending.old_city.promise.failure", selected)
        self.assertNotIn("ending.old_city.promise.success", selected)

    def test_patch030_old_city_omits_unproven_departure_claims(self) -> None:
        zero_losses = {
            "cooked_food": 0,
            "coal": 0,
            "wood": 0,
            "steel": 0,
        }
        for actual_departures in (0, 7):
            with self.subTest(actual_departures=actual_departures):
                state = self.completed_state()
                self.configure_resolved_partial_old_city(
                    state,
                    actual_departures=actual_departures,
                    resource_losses=zero_losses,
                )
                selected = canonical_report_body_text_ids(state)
                self.assertNotIn(
                    "ending.old_city.partial_exodus.full_text",
                    selected,
                )
                self.assertIn(
                    "ending.old_city.full_text",
                    canonical_report_pending_text_ids(state),
                )
                restored = decode_game_state(encode_game_state(state))
                validate_game_state(
                    restored,
                    self.buildings,
                    self.survival,
                    self.technology,
                )

        applicable = self.completed_state()
        self.configure_resolved_partial_old_city(
            applicable,
            actual_departures=7,
            resource_losses={
                "cooked_food": 0,
                "coal": 1,
                "wood": 0,
                "steel": 0,
            },
        )
        self.assertIn(
            "ending.old_city.partial_exodus.full_text",
            canonical_report_body_text_ids(applicable),
        )
        self.assertNotIn(
            "ending.old_city.full_text",
            canonical_report_pending_text_ids(applicable),
        )

    def test_patch030_children_text_uses_only_proven_law_and_building_facts(
        self,
    ) -> None:
        state = self.completed_state()
        cases = (
            (["child_labor_low_risk_law"], "ending.children.labor_low_risk.full_text"),
            (
                ["child_labor_low_risk_law", "child_labor_all_jobs_law"],
                "ending.children.labor_all_jobs.full_text",
            ),
            (
                ["child_protection_law"],
                "ending.children.protection.no_shelter.full_text",
            ),
        )
        for laws, expected in cases:
            with self.subTest(expected=expected):
                state.laws.signed_law_ids = laws
                self.assertIn(expected, canonical_report_body_text_ids(state))

        state.laws.signed_law_ids = ["child_protection_law"]
        state.buildings["child-shelter-test"] = BuildingState(
            building_id="child-shelter-test",
            building_type="child_shelter",
            zone="inner_ring",
            slot_size=1,
            is_built=True,
        )
        self.assertIn(
            "ending.children.protection.shelter_only.full_text",
            canonical_report_body_text_ids(state),
        )
        state.buildings["school-test"] = BuildingState(
            building_id="school-test",
            building_type="school",
            zone="inner_ring",
            slot_size=1,
            is_built=True,
        )
        state.laws.signed_law_ids.append("child_school_law")
        self.assertIn(
            "ending.children.protection.school.full_text",
            canonical_report_body_text_ids(state),
        )
        state.laws.signed_law_ids.append("medical_apprentices_law")
        self.assertIn(
            "ending.children.protection.medical_track.full_text",
            canonical_report_body_text_ids(state),
        )
        state.laws.signed_law_ids[-1] = "engineering_apprentices_law"
        self.assertIn(
            "ending.children.protection.engineering_track.full_text",
            canonical_report_body_text_ids(state),
        )
        self.assertNotIn(
            "ending.trace.children_protected",
            canonical_report_pending_text_ids(state),
        )

    def test_patch030_entertainment_text_uses_current_operational_fact(
        self,
    ) -> None:
        state = self.completed_state()
        state.laws.signed_law_ids = ["tavern_law"]
        selected = canonical_report_body_text_ids(state)
        self.assertIn(
            "ending.entertainment.no_operational_facility.full_text",
            selected,
        )
        self.assertNotIn("ending.trace.entertainment", selected)

        state.buildings["tavern-test"] = BuildingState(
            building_id="tavern-test",
            building_type="small_tavern",
            zone="inner_ring",
            slot_size=1,
            is_built=True,
            is_operational=True,
        )
        self.assertIn(
            "ending.entertainment.tavern.full_text",
            canonical_report_body_text_ids(state),
        )
        state.laws.signed_law_ids.append("casino_law")
        state.buildings["casino-test"] = BuildingState(
            building_id="casino-test",
            building_type="grand_casino",
            zone="middle_ring",
            slot_size=1,
            is_built=True,
            is_operational=True,
        )
        self.assertIn(
            "ending.entertainment.casino.full_text",
            canonical_report_body_text_ids(state),
        )
        state.final_result.ending_tags.append("sedation_city")
        self.assertNotIn(
            "ending.entertainment.sedation_city.full_text",
            canonical_report_body_text_ids(state),
        )
        self.assertIn(
            "ending.entertainment.sedation_city.full_text",
            canonical_report_pending_text_ids(state),
        )

    def test_patch030_rejects_forged_sedation_narrative(self) -> None:
        state = self.completed_state()
        forged = encode_game_state(state)
        forged["final_result"]["report"]["body_text_ids"].insert(
            -1,
            "ending.entertainment.sedation_city.full_text",
        )

        with self.assertRaisesRegex(
            SaveDataError,
            "text selection is not canonical",
        ):
            decode_game_state(forged)

    def test_report_save_is_strict_and_v11_migrates_without_terminal_state(
        self,
    ) -> None:
        state = self.completed_state()
        document = encode_game_state(state)
        tampered = deepcopy(document)
        tampered["final_result"]["report"]["pending_text_ids"].append(
            "ending.report.fake"
        )
        tampered["final_result"]["report"]["pending_text_ids"].sort()
        with self.assertRaisesRegex(
            SaveDataError, "text selection is not canonical"
        ):
            decode_game_state(tampered)

        wrong_body = deepcopy(document)
        wrong_body["final_result"]["report"]["body_text_ids"][0] = (
            "ending.ember_survival.body.01"
        )
        with self.assertRaisesRegex(
            SaveDataError, "text selection is not canonical"
        ):
            decode_game_state(wrong_body)

        disguised_as_legacy = deepcopy(document)
        disguised_as_legacy["final_result"]["report"]["body_text_ids"] = []
        disguised_as_legacy["final_result"]["report"][
            "pending_text_ids"
        ] = legacy_report_pending_text_ids(state)
        with self.assertRaisesRegex(
            SaveDataError, "text selection is not canonical"
        ):
            decode_game_state(disguised_as_legacy)

        deleted_report = deepcopy(document)
        deleted_report["final_result"]["report"] = {
            "format_version": CURRENT_ENDING_REPORT_FORMAT_VERSION,
            "is_generated": False,
            "generated_day": None,
            "ending_state": None,
            "display_result_id": None,
            "title_text_id": None,
            "body_text_ids": [],
            "pending_text_ids": [],
            "hidden_achievement_ids": [],
            "limiting_factor_ids": [],
        }
        with self.assertRaisesRegex(
            SaveDataError,
            "completed result must retain its generated ending report",
        ):
            decode_game_state(deleted_report)

        ended = self.completed_state()
        result = self.execute(
            EndingReportSystem(), ended, "strict-sequence", {"confirm": True}
        )
        self.assertEqual(result.code, ErrorCode.OK)
        wrong_sequence = encode_game_state(ended)
        wrong_sequence["command_sequence"] += 1
        with self.assertRaisesRegex(
            SaveDataError, "termination history is inconsistent"
        ):
            decode_game_state(wrong_sequence)

        legacy = encode_game_state(
            create_initial_survival_state(
                self.survival, self.buildings, random_seed=11
            )
        )
        legacy["save_data_version"] = 11
        del legacy["final_frost"]["balance_profile_id"]
        for field in (
            "run_state",
            "termination_reason",
            "termination_day",
            "termination_command_sequence",
            "report",
        ):
            del legacy["final_result"][field]
        migrated = decode_game_state(legacy)
        self.assertEqual(
            migrated.save_data_version, CURRENT_SAVE_DATA_VERSION
        )
        self.assertIs(migrated.final_result.run_state, RunState.ACTIVE)
        self.assertFalse(migrated.final_result.report.is_generated)
        self.assertEqual(
            migrated.final_result.report.format_version,
            CURRENT_ENDING_REPORT_FORMAT_VERSION,
        )

        terminal_legacy = encode_game_state(self.completed_state())
        terminal_legacy["save_data_version"] = 11
        del terminal_legacy["final_frost"]["balance_profile_id"]
        terminal_legacy["hunger"] = {
            "mild_population": 0,
            "severe_population": 0,
            "starving_population": 0,
        }
        del terminal_legacy["cold_exposure"]
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
            del terminal_legacy["final_frost"][field]
        for record in terminal_legacy["final_frost"]["daily_records"].values():
            del record["unfed_population"]
            del record["raw_hunger_deaths"]
            del record["hunger_death_overflow"]
        for field in (
            "run_state",
            "termination_reason",
            "termination_day",
            "termination_command_sequence",
            "report",
        ):
            del terminal_legacy["final_result"][field]
        terminal_migrated = decode_game_state(terminal_legacy)
        self.assertTrue(terminal_migrated.final_result.report.is_generated)
        self.assertEqual(
            terminal_migrated.final_result.report.ending_state,
            terminal_migrated.final_result.ending_id,
        )

    def test_legacy_patch010_report_remains_readable_without_reselection(
        self,
    ) -> None:
        state = self.completed_state()
        legacy_document = encode_game_state(state)
        legacy_report = legacy_document["final_result"]["report"]
        legacy_report["body_text_ids"] = []
        legacy_report["pending_text_ids"] = legacy_report_pending_text_ids(
            state
        )
        del legacy_report["format_version"]
        legacy_document["save_data_version"] = 14
        del legacy_document["final_frost"]["balance_profile_id"]

        restored = decode_game_state(legacy_document)
        view = EndingReportSystem().observe(restored)

        self.assertEqual(
            restored.save_data_version, CURRENT_SAVE_DATA_VERSION
        )
        self.assertEqual(
            restored.final_result.report.format_version,
            LEGACY_ENDING_REPORT_FORMAT_VERSION,
        )
        self.assertEqual(restored.final_result.report.body_text_ids, [])
        self.assertEqual(
            view["pending_text_ids"], legacy_report["pending_text_ids"]
        )
        self.assertEqual(view["content_status"], "partial_pending_text")

    def test_old_v17_ungenerated_report_loads_and_generates_current_format(
        self,
    ) -> None:
        legacy = self.state_before_finalization()
        document = encode_game_state(legacy)
        document["final_result"]["report"]["format_version"] = (
            PATCH_020_ENDING_REPORT_FORMAT_VERSION
        )
        tampered = deepcopy(document)
        tampered["final_result"]["report"]["pending_text_ids"] = [
            "ending.report.fake"
        ]
        with self.assertRaisesRegex(
            SaveDataError,
            "ungenerated ending report cannot retain report fields",
        ):
            decode_game_state(tampered)

        patch027_document = deepcopy(document)
        patch027_document["final_result"]["report"]["format_version"] = (
            PATCH_027_ENDING_REPORT_FORMAT_VERSION
        )
        patch027_restored = decode_game_state(patch027_document)
        self.assertFalse(patch027_restored.final_result.report.is_generated)
        self.assertEqual(
            patch027_restored.final_result.report.format_version,
            PATCH_027_ENDING_REPORT_FORMAT_VERSION,
        )

        restored = decode_game_state(document)

        self.assertFalse(restored.final_result.report.is_generated)
        self.assertEqual(
            restored.final_result.report.format_version,
            PATCH_020_ENDING_REPORT_FORMAT_VERSION,
        )
        context = EndDayContext(
            state=restored,
            random=DeterministicRandom.from_state(restored.random),
            settled_day=55,
            stage=EndDayStage.RECORD_DAILY_LOG_AND_ENDING_TAGS,
            _emit=lambda _code, _payload: None,
        )
        self.frost_system().finalize_day_55(context)
        self.assertTrue(restored.final_result.report.is_generated)
        self.assertEqual(
            restored.final_result.report.format_version,
            CURRENT_ENDING_REPORT_FORMAT_VERSION,
        )
        self.assertEqual(
            decode_game_state(encode_game_state(restored)), restored
        )

    def test_v15_format2_migration_marks_service_history_unknown(self) -> None:
        state = self.completed_state()
        state.final_result.defining_tags = ["famine_city"]
        state.final_result.major_tags = []
        state.final_result.ending_tags = [
            state.final_result.ending_id,
            "famine_city",
        ]
        report = state.final_result.report
        report.format_version = PATCH_020_ENDING_REPORT_FORMAT_VERSION
        report.body_text_ids = patch020_report_body_text_ids(state)
        report.pending_text_ids = [
            text_id
            for text_id in patch020_report_pending_text_ids(state)
            if text_id != "ending.additional.food.01"
        ]
        document = encode_game_state(state)
        document["save_data_version"] = 15
        del document["final_frost"]["balance_profile_id"]
        for record in document["final_frost"]["daily_records"].values():
            for field in (
                "service_history_known",
                "canteen_operational",
                "medical_operational_building_count",
                "medical_building_capacity",
            ):
                del record[field]

        restored = decode_game_state(document)

        self.assertEqual(
            restored.save_data_version, CURRENT_SAVE_DATA_VERSION
        )
        self.assertEqual(
            restored.final_result.report.format_version,
            PATCH_020_ENDING_REPORT_FORMAT_VERSION,
        )
        self.assertIn(
            "ending.additional.food.01",
            restored.final_result.report.pending_text_ids,
        )
        self.assertTrue(
            all(
                not record.service_history_known
                and not record.canteen_operational
                and record.medical_operational_building_count == 0
                and record.medical_building_capacity == 0
                for record in restored.final_frost.daily_records.values()
            )
        )

    def test_v15_format2_migration_clears_unprovable_pending_without_records(
        self,
    ) -> None:
        state = create_initial_survival_state(
            self.survival, self.buildings, random_seed=15
        )
        final = state.final_result
        final.is_finalized = True
        final.hard_fail_type = HardFailType.TRUST_EXILE
        final.ending_id = "hard_fail"
        final.ending_tags = ["hard_fail", "trust_exile"]
        EndingReportSystem().generate(state)
        final.report.format_version = PATCH_020_ENDING_REPORT_FORMAT_VERSION
        final.report.body_text_ids = patch020_report_body_text_ids(state)
        final.report.pending_text_ids = sorted(
            {
                *patch020_report_pending_text_ids(state),
                "ending.additional.food.01",
                "ending.additional.medical.01",
                "ending.additional.medical.02",
            }
        )
        document = encode_game_state(state)
        document["save_data_version"] = 15
        del document["final_frost"]["balance_profile_id"]

        restored = decode_game_state(document)

        self.assertEqual(restored.final_frost.daily_records, {})
        self.assertEqual(
            restored.final_result.report.format_version,
            PATCH_020_ENDING_REPORT_FORMAT_VERSION,
        )
        for text_id in (
            "ending.additional.food.01",
            "ending.additional.medical.01",
            "ending.additional.medical.02",
        ):
            self.assertNotIn(
                text_id, restored.final_result.report.pending_text_ids
            )

    def test_service_history_strictly_rejects_forged_or_reversed_facts(
        self,
    ) -> None:
        state = self.completed_state()
        forged = encode_game_state(state)
        forged_record = forged["final_frost"]["daily_records"]["49"]
        forged_record["canteen_operational"] = True
        with self.assertRaisesRegex(
            SaveDataError,
            "unknown final frost service history",
        ):
            decode_game_state(forged)

        reversed_history = encode_game_state(state)
        reversed_history["final_frost"]["daily_records"]["49"][
            "service_history_known"
        ] = True
        with self.assertRaisesRegex(
            SaveDataError,
            "empty prefix",
        ):
            decode_game_state(reversed_history)

        pre_v16 = encode_game_state(state)
        pre_v16["save_data_version"] = 15
        del pre_v16["final_frost"]["balance_profile_id"]
        pre_v16["final_frost"]["daily_records"]["49"][
            "service_history_known"
        ] = True
        with self.assertRaisesRegex(
            SaveDataError,
            "pre-v16 save cannot contain Patch 021",
        ):
            decode_game_state(pre_v16)

    def test_user_confirmed_death_lines_are_selected_and_rendered_verbatim(
        self,
    ) -> None:
        registry = build_ending_text_registry()
        templates = {
            "ending.report.death_record.none": (
                "没有任何人被霜落吞噬，你做得很好，执政官。"
            ),
            "ending.report.death_record.cemetery": (
                "5 人没能走到最后。你为他们留下了墓园，那些名字化成了"
                "一个个墓碑被纪念。"
            ),
            "ending.report.death_record.cold_pit": (
                "5 人没能走到最后。他们被安置在冷藏坑的冰冷秩序里，"
                "等待炉城决定他们还有什么价值。"
            ),
            "ending.report.death_record.unhandled": (
                "5 人没能走到最后。档案封存时，3 具遗体掩埋进风雪里。"
            ),
            "ending.report.death_record.ember_roster": (
                "5 人没能走到最后。余烬名册记下了他们的名字，让死者没有"
                "只成为冰冷的数字。"
            ),
        }
        values = {"total_deaths": 5, "unhandled_bodies": 3}
        for text_id, expected in templates.items():
            rendered = registry.require(text_id).text.format_map(values)
            self.assertEqual(rendered, expected)
            self.assertNotIn("本局共有", rendered)

        state = self.completed_state()
        self.assertIn(
            "ending.report.death_record.none",
            canonical_report_body_text_ids(state),
        )
        state.population.population_dead = 5
        state.social_policy.death_path = "cemetery"
        state.social_policy.unhandled_bodies = 3
        self.assertIn(
            "ending.report.death_record.unhandled",
            canonical_report_body_text_ids(state),
        )
        state.social_policy.unhandled_bodies = 0
        self.assertIn(
            "ending.report.death_record.cemetery",
            canonical_report_body_text_ids(state),
        )
        state.social_policy.death_path = "cold_pit"
        self.assertIn(
            "ending.report.death_record.cold_pit",
            canonical_report_body_text_ids(state),
        )
        state.social_policy.death_path = "none"
        state.oath_order.signed_law_ids = ["ember_roster"]
        self.assertIn(
            "ending.report.death_record.ember_roster",
            canonical_report_body_text_ids(state),
        )

    def test_patch030_resolves_long_form_and_death_handling_pending(self) -> None:
        state = self.completed_state()
        self.assertEqual(canonical_report_pending_text_ids(state), [])

        state.oath_order.selected_route = "oath"
        state.oath_order.signed_law_ids = ["final_oath"]
        state.oath_order.final_oath_active = True
        state.old_city.is_unlocked = True
        state.population.population_dead = 1
        selected = canonical_report_body_text_ids(state)
        pending = canonical_report_pending_text_ids(state)

        self.assertEqual(pending, [])
        self.assertIn("ending.route.final_oath.full_text", selected)
        self.assertNotIn("ending.route.oath.full_text", selected)
        self.assertIn("ending.old_city.unresolved.full_text", selected)
        self.assertFalse(
            any("death_handling.full_text" in text_id for text_id in selected)
        )
        self.assertFalse(any(text_id.endswith(".pool") for text_id in selected))

    def test_report_template_values_recover_the_original_start_population(
        self,
    ) -> None:
        state = self.completed_state()
        state.population.population_total_ever += 12
        state.events.resolution_history[0].population_added = 12
        values = report_template_values(state)
        self.assertEqual(values["start_population"], 80)

    def test_cli_reads_the_persisted_machine_report(self) -> None:
        state = self.completed_state()
        with tempfile.TemporaryDirectory() as directory:
            save_path = Path(directory) / "ending.json"
            save_path.write_text(
                json.dumps(encode_game_state(state), ensure_ascii=False),
                encoding="utf-8",
            )
            output = StringIO()
            with redirect_stdout(output):
                exit_code = main(["report", str(save_path)])
        report = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(report["available"])
        self.assertEqual(report["content_status"], "complete")
        self.assertTrue(report["body_complete"])
        self.assertEqual(
            report["pending_text_count"], len(report["pending_text_ids"])
        )
        self.assertEqual(
            report["ending_state"], state.final_result.ending_id
        )
        self.assertEqual(report["run_state"], "active")


if __name__ == "__main__":
    unittest.main()
