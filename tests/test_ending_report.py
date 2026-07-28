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
        return state

    def completed_state(self):
        state = self.state_before_finalization()
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
        self.assertIn(
            "ending.report.death_record_sentence",
            hard_fail_view["pending_text_ids"],
        )
        self.assertIn(
            "ending.report.frostfall_deaths.zero_sentence",
            hard_fail_view["pending_text_ids"],
        )
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

    def test_report_omits_unsealed_text_and_is_seed_independent(self) -> None:
        first = self.completed_state()
        second = deepcopy(first)
        second.random = DeterministicRandom(999999).snapshot()
        first_view = EndingReportSystem().observe(first)
        second_view = EndingReportSystem().observe(second)

        self.assertEqual(
            first_view["pending_text_ids"],
            second_view["pending_text_ids"],
        )
        self.assertEqual(first_view["body"], [])
        self.assertIn(
            "ending.report.death_record_sentence",
            first_view["pending_text_ids"],
        )
        self.assertIn(
            "ending.report.frostfall_deaths.zero_sentence",
            first_view["pending_text_ids"],
        )
        self.assertEqual(
            first_view["pending_text_ids"],
            sorted(set(first_view["pending_text_ids"])),
        )
        rendered_ids = {
            first_view["title"]["text_id"],
            *(item["text_id"] for item in first_view["body"]),
        }
        self.assertNotIn(
            "ending.report.death_record_sentence", rendered_ids
        )
        self.assertFalse(any(text_id.endswith(".pool") for text_id in rendered_ids))
        self.assertNotIn("TODO_TEXT", json.dumps(first_view, ensure_ascii=False))

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
            SaveDataError, "pending text ids are not canonical"
        ):
            decode_game_state(tampered)

        deleted_report = deepcopy(document)
        deleted_report["final_result"]["report"] = {
            "is_generated": False,
            "generated_day": None,
            "ending_state": None,
            "display_result_id": None,
            "title_text_id": None,
            "body_text_ids": [],
            "pending_text_ids": [],
            "hidden_achievement_ids": [],
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
        self.assertEqual(migrated.save_data_version, 12)
        self.assertIs(migrated.final_result.run_state, RunState.ACTIVE)
        self.assertFalse(migrated.final_result.report.is_generated)

        terminal_legacy = encode_game_state(self.completed_state())
        terminal_legacy["save_data_version"] = 11
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
        self.assertEqual(
            report["ending_state"], state.final_result.ending_id
        )
        self.assertEqual(report["run_state"], "active")


if __name__ == "__main__":
    unittest.main()
