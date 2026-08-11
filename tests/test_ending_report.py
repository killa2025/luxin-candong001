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
    CURRENT_ENDING_REPORT_FORMAT_VERSION,
    LEGACY_ENDING_REPORT_FORMAT_VERSION,
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
)
from furnace_winter.models.ending_selection import (
    canonical_report_body_text_ids,
    canonical_report_pending_text_ids,
    legacy_report_pending_text_ids,
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
            false_confirm.data["reason"], "confirmation_required"
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
            "ending.high_victory.body.02",
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
        self.assertIn("ending.additional.medical.03", selected)

        station.assigned_medical_apprentices = 0
        medical_state.population.population_dead = 5
        first_record = next(
            iter(medical_state.final_frost.daily_records.values())
        )
        first_record.actual_disease_deaths = 1
        medical_state.final_frost.frost_deaths = 1
        for seed in range(32):
            medical_state.random = DeterministicRandom(seed).snapshot()
            selected = canonical_report_body_text_ids(medical_state)
            medical_ids = {
                text_id
                for text_id in selected
                if text_id.startswith("ending.additional.medical.")
            }
            self.assertTrue(
                medical_ids
                <= {
                    "ending.additional.medical.01",
                    "ending.additional.medical.02",
                }
            )
            self.assertTrue(medical_ids)

    def test_children_protected_trace_is_pending_and_not_runtime_text(
        self,
    ) -> None:
        registry = build_ending_text_registry()
        pending_registry = build_ending_pending_registry()
        self.assertIsNone(registry.get("ending.trace.children_protected"))
        pending_entries = {
            entry.entry_id: entry for entry in pending_registry.entries()
        }
        self.assertIn("ending.trace.children_protected", pending_entries)
        self.assertEqual(
            pending_entries["ending.trace.children_protected"].status.value,
            "PENDING",
        )

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
            "ending.trace.children_protected",
            canonical_report_pending_text_ids(state),
        )

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
        for field in (
            "run_state",
            "termination_reason",
            "termination_day",
            "termination_command_sequence",
            "report",
        ):
            del legacy["final_result"][field]
        migrated = decode_game_state(legacy)
        self.assertEqual(migrated.save_data_version, 15)
        self.assertIs(migrated.final_result.run_state, RunState.ACTIVE)
        self.assertFalse(migrated.final_result.report.is_generated)
        self.assertEqual(
            migrated.final_result.report.format_version,
            CURRENT_ENDING_REPORT_FORMAT_VERSION,
        )

        terminal_legacy = encode_game_state(self.completed_state())
        terminal_legacy["save_data_version"] = 11
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

        restored = decode_game_state(legacy_document)
        view = EndingReportSystem().observe(restored)

        self.assertEqual(restored.save_data_version, 15)
        self.assertEqual(
            restored.final_result.report.format_version,
            LEGACY_ENDING_REPORT_FORMAT_VERSION,
        )
        self.assertEqual(restored.final_result.report.body_text_ids, [])
        self.assertEqual(
            view["pending_text_ids"], legacy_report["pending_text_ids"]
        )
        self.assertEqual(view["content_status"], "partial_pending_text")

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

    def test_pending_ids_only_describe_unsealed_long_form_text(self) -> None:
        state = self.completed_state()
        self.assertEqual(canonical_report_pending_text_ids(state), [])

        state.oath_order.selected_route = "oath"
        state.oath_order.signed_law_ids = ["final_oath"]
        state.oath_order.final_oath_active = True
        state.old_city.is_unlocked = True
        state.population.population_dead = 1
        pending = canonical_report_pending_text_ids(state)

        self.assertEqual(pending, sorted(set(pending)))
        self.assertIn("ending.route.oath.full_text", pending)
        self.assertIn("ending.route.final_oath.full_text", pending)
        self.assertIn("ending.old_city.full_text", pending)
        self.assertIn("ending.death_handling.full_text", pending)
        self.assertFalse(any(text_id.endswith(".pool") for text_id in pending))

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
