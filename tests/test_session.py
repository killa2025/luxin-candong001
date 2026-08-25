from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from furnace_winter import GameSession
from furnace_winter.cli import main
from furnace_winter.interface import (
    AutosaveSnapshotPathError,
    AutosaveSnapshotValidationError,
    ErrorCode,
)
from furnace_winter.models import dumps, encode_game_state


ROOT = Path(__file__).resolve().parents[1]


class GameSessionTests(unittest.TestCase):
    def new_session(self, **kwargs):
        return GameSession.new(config_dir=ROOT / "data", **kwargs)

    def test_session_exposes_all_systems_and_validated_numeric_views(self) -> None:
        session = self.new_session(seed=1101)

        status = session.status()
        self.assertEqual(status["day"], 1)
        self.assertEqual(status["population"]["alive"], 80)
        self.assertEqual(status["ration"]["selected_mode"], "normal")
        self.assertEqual(status["ration"]["effective_mode"], "normal")
        self.assertEqual(
            {spec.name for spec in session.command_specs()},
            {
                "game.assign",
                "game.assign_resource",
                "game.build",
                "game.cancel_research",
                "game.confirm_end_day",
                "game.end_day",
                "game.end_run",
                "game.heat",
                "game.medical_ration",
                "game.memorial",
                "game.overtime",
                "game.research",
                "game.resolve_event",
                "game.resolve_old_city_event",
                "game.set_furnace",
                "game.set_overload",
                "game.set_ration",
                "game.set_worktime",
                "game.sign_law",
                "game.sign_oath_order_law",
                "game.staff_oath_order_facility",
                "game.triage",
                "game.unassign",
                "game.unassign_resource",
                "game.upgrade",
                "game.use_oath_order_action",
                "game.woodfuel",
            },
        )

        survival = session.rules_view("survival")
        buildings = session.rules_view("buildings")
        technologies = session.rules_view("technologies")
        self.assertEqual(survival["config_status"], "FINAL")
        self.assertEqual(buildings["config_status"], "TEST_NUMERIC")
        self.assertEqual(technologies["config_status"], "TEST_NUMERIC")
        self.assertEqual(
            survival["document"]["furnace_levels"]["2"]["coal_cost"],
            85,
        )
        self.assertEqual(
            buildings["document"]["buildings"]["canteen"]["wood_cost"],
            20,
        )
        self.assertEqual(
            technologies["document"]["technologies"]["tech_drawing_board"][
                "research_days"
            ],
            1,
        )

        observation = session.observe()
        self.assertFalse(status["persistence"]["autosave_end_day_present"])
        self.assertEqual(
            status["persistence"]["autosave_end_day_view_request"],
            {"type": "autosave"},
        )
        self.assertEqual(
            observation.available_rule_sections,
            (
                "buildings",
                "events",
                "final_frost",
                "laws",
                "maps",
                "oath_order",
                "survival",
                "technologies",
            ),
        )
        self.assertEqual(
            observation.protocol_contract["rules_query"]["request_shape"],
            {"type": "rules", "section": "RULE_SECTION_STRING"},
        )
        self.assertEqual(
            observation.protocol_contract["end_day_confirmation"][
                "token_scope"
            ],
            "current_game_session",
        )
        self.assertEqual(
            observation.protocol_contract["sequence_semantics"],
            {
                "replay_sequence": {
                    "scope": "current_game_session",
                    "persistence": "not_saved",
                    "assigned_to": "recorded_command_attempts",
                    "includes_rejected_commands": True,
                    "may_be_null_when_attempt_is_not_recorded": True,
                    "resets_when_session_opens": True,
                    "use_for_optimistic_concurrency": False,
                },
                "state_sequence": {
                    "scope": "persistent_game_state",
                    "persistence": "saved_in_game_state",
                    "increments_on": "committed_state_changes_only",
                    "includes_rejected_commands": False,
                    "resets_when_session_opens": False,
                    "request_field": "expected_state_sequence",
                    "use_for_optimistic_concurrency": True,
                },
            },
        )
        persistence = observation.protocol_contract["persistence_files"]
        self.assertEqual(
            persistence["primary_save"]["accepted_by"],
            ["play", "report"],
        )
        self.assertFalse(
            persistence["autosave_end_day"]["accepted_as_primary_save"]
        )
        self.assertEqual(
            persistence["autosave_end_day"]["view_request_shape"],
            {"type": "autosave"},
        )
        self.assertIsNotNone(observation.law_view)
        self.assertEqual(len(observation.technology_view), 37)
        self.assertIn("law_rules", observation.oath_order_view)
        assign_resource = next(
            spec
            for spec in session.command_specs()
            if spec.name == "game.assign_resource"
        )
        self.assertEqual(
            assign_resource.argument_semantics["count"],
            "absolute_target_count",
        )
        set_ration = next(
            spec
            for spec in session.command_specs()
            if spec.name == "game.set_ration"
        )
        self.assertEqual(
            set_ration.argument_semantics["confirm"],
            "explicit_true_only_never_preview",
        )
        build = next(
            spec
            for spec in session.command_specs()
            if spec.name == "game.build"
        )
        self.assertEqual(build.related_rule_sections, ("buildings",))
        research = next(
            spec
            for spec in session.command_specs()
            if spec.name == "game.research"
        )
        self.assertEqual(research.related_rule_sections, ("technologies",))
        sign_law = next(
            spec
            for spec in session.command_specs()
            if spec.name == "game.sign_law"
        )
        self.assertEqual(sign_law.related_rule_sections, ("laws",))
        confirm_end_day = next(
            spec
            for spec in session.command_specs()
            if spec.name == "game.confirm_end_day"
        )
        self.assertEqual(
            confirm_end_day.argument_semantics["confirmation_token"],
            "same_session_preview_token",
        )
        self.assertEqual(
            confirm_end_day.related_protocol_contracts,
            ("end_day_confirmation",),
        )
        contracts = observation.final_frost_view["final_result"][
            "tag_contracts"
        ]
        self.assertEqual(
            contracts["frost_survived_clean"]["meaning_id"],
            "stable_system_survival_not_zero_deaths",
        )
        self.assertFalse(
            contracts["frost_survived_clean"]["zero_deaths_required"]
        )
        self.assertFalse(
            contracts["frost_survived_clean"][
                "city_continuity_broken_allowed"
            ]
        )
        self.assertEqual(
            contracts["frost_survived_clean"]["blocked_by_tag"],
            "frost_survived_broken",
        )
        self.assertEqual(
            contracts["frost_survived_clean"]["city_continuity"][
                "minimum_alive_population"
            ],
            40,
        )
        self.assertEqual(
            contracts["frost_survived_broken"]["takes_precedence_over"],
            ["frost_survived_clean"],
        )
        self.assertEqual(
            contracts["frost_survived_broken"]["applies_when_any"][0],
            {"condition_id": "zero_score_systems", "minimum": 2},
        )

    def test_mutating_command_is_saved_and_loadable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir) / "game.json"
            session = self.new_session(
                seed=1102,
                save_path=save_path,
            )

            execution = session.command("game.set_furnace", {"level": 2})
            restored = GameSession.load(
                save_path,
                config_dir=ROOT / "data",
            )

        self.assertEqual(execution.result.code, ErrorCode.OK)
        self.assertTrue(execution.save_written)
        self.assertEqual(restored.status()["state_sequence"], 1)
        self.assertEqual(restored.status()["furnace"]["mode_id"], "level_2")

    def test_rejected_command_does_not_change_state_or_save(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir) / "game.json"
            session = self.new_session(seed=1103, save_path=save_path)
            before_state = encode_game_state(session.state)
            before_save = save_path.read_bytes()

            execution = session.command("game.not_registered")

            self.assertEqual(
                execution.result.code,
                ErrorCode.COMMAND_NOT_REGISTERED,
            )
            self.assertEqual(encode_game_state(session.state), before_state)
            self.assertEqual(save_path.read_bytes(), before_save)

    def test_sequence_contract_distinguishes_session_attempts_from_saved_state(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir) / "sequences.json"
            session = self.new_session(seed=1126, save_path=save_path)

            rejected = session.command("game.not_registered")
            committed = session.command("game.set_furnace", {"level": 2})
            reopened = GameSession.load(save_path, config_dir=ROOT / "data")
            reopened_rejected = reopened.command("game.not_registered")
            contract = reopened.observe().protocol_contract["sequence_semantics"]

        self.assertEqual(rejected.replay_sequence, 1)
        self.assertEqual(rejected.result.state_sequence, 0)
        self.assertEqual(committed.replay_sequence, 2)
        self.assertEqual(committed.result.state_sequence, 1)
        self.assertEqual(reopened_rejected.replay_sequence, 1)
        self.assertEqual(reopened_rejected.result.state_sequence, 1)
        self.assertTrue(
            contract["replay_sequence"]["includes_rejected_commands"]
        )
        self.assertTrue(
            contract["replay_sequence"]["resets_when_session_opens"]
        )
        self.assertEqual(
            contract["state_sequence"]["request_field"],
            "expected_state_sequence",
        )
        self.assertFalse(
            contract["state_sequence"]["includes_rejected_commands"]
        )

    def test_depletion_result_is_returned_and_recorded_in_same_end_day(self) -> None:
        session = self.new_session(seed=1127)
        point_id = "surface-steel-1"
        session._state.surface_resource_points[point_id].remaining_amount = 1
        assigned = session.command(
            "game.assign_resource",
            {
                "resource_point_id": point_id,
                "population_type": "engineers",
                "count": 1,
            },
        )

        settled = session.command("game.end_day")
        if settled.result.code is ErrorCode.END_DAY_CONFIRMATION_REQUIRED:
            settled = session.command(
                "game.confirm_end_day",
                settled.result.data["confirmation"],
            )
        warning = next(
            item
            for item in settled.result.data["warnings"]
            if item["warning_id"] == "buildings.resource_points_depleted"
        )
        replay_warning = next(
            item
            for item in session.replay_document().entries[-1].result.data["warnings"]
            if item["warning_id"] == "buildings.resource_points_depleted"
        )
        replay_log = next(
            item
            for item in session.replay_document().entries[-1].logs
            if item.code == "buildings.resource_points.depleted"
        )

        self.assertEqual(assigned.result.code, ErrorCode.OK)
        self.assertEqual(settled.result.code, ErrorCode.OK)
        self.assertEqual(warning["assessment_stage"], "settlement_result")
        self.assertEqual(warning["details"]["resource_point_ids"], [point_id])
        self.assertEqual(warning["details"]["released_engineers_total"], 1)
        self.assertTrue(
            warning["details"]["assignments_released_automatically"]
        )
        self.assertEqual(replay_warning, warning)
        self.assertEqual(replay_log.payload, warning["details"])

    def test_depletion_fact_is_absent_from_replay_when_autosave_sink_fails(
        self,
    ) -> None:
        session = self.new_session(seed=1128)
        point_id = "surface-steel-1"
        session._state.surface_resource_points[point_id].remaining_amount = 1
        assigned = session.command(
            "game.assign_resource",
            {
                "resource_point_id": point_id,
                "population_type": "engineers",
                "count": 1,
            },
        )
        before = encode_game_state(session.state)

        def fail_autosave_sink(_record) -> None:
            raise OSError("test-only autosave receiver failure")

        session.end_day._autosave_sink = fail_autosave_sink
        failed = session.command("game.end_day")
        if failed.result.code is ErrorCode.END_DAY_CONFIRMATION_REQUIRED:
            failed = session.command(
                "game.confirm_end_day",
                failed.result.data["confirmation"],
            )
        replay_entry = session.replay_document().entries[-1]

        self.assertEqual(assigned.result.code, ErrorCode.OK)
        self.assertEqual(failed.result.code, ErrorCode.INTERNAL_ERROR)
        self.assertEqual(failed.result.data["failed_stage"], "write_autosave")
        self.assertEqual(encode_game_state(session.state), before)
        self.assertNotIn(
            "buildings.resource_points_depleted",
            {
                item["warning_id"]
                for item in failed.result.data["warnings"]
            },
        )
        self.assertNotIn(
            "buildings.resource_points.depleted",
            {item.code for item in replay_entry.logs},
        )
        self.assertEqual(
            session.state.surface_resource_points[point_id].remaining_amount,
            1,
        )
        self.assertEqual(
            session.state.surface_resource_points[point_id].assigned_engineers,
            1,
        )

    def test_rules_query_command_guess_returns_the_official_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir) / "game.json"
            session = self.new_session(seed=1125, save_path=save_path)
            before_state = encode_game_state(session.state)
            before_save = save_path.read_bytes()

            execution = session.command(
                "rules.query",
                {"section": "buildings"},
            )

            self.assertEqual(
                execution.result.code,
                ErrorCode.COMMAND_NOT_REGISTERED,
            )
            self.assertEqual(
                execution.result.data["reason"],
                "command_name_not_registered",
            )
            self.assertFalse(
                execution.result.data["rules_query_is_game_command"]
            )
            contract = execution.result.data["rules_query_contract"]
            self.assertEqual(
                contract["request_shape"],
                {"type": "rules", "section": "RULE_SECTION_STRING"},
            )
            self.assertIn("buildings", contract["available_sections"])
            self.assertEqual(encode_game_state(session.state), before_state)
            self.assertEqual(save_path.read_bytes(), before_save)
            self.assertFalse(execution.result.state_changed)
            self.assertFalse(execution.save_written)

    def test_invalid_ration_option_returns_structured_rejection(self) -> None:
        session = self.new_session(seed=1112)
        before = encode_game_state(session.state)

        execution = session.command(
            "game.set_ration",
            {"mode": "emergency_ration"},
        )

        self.assertEqual(execution.result.code, ErrorCode.INVALID_ARGUMENTS)
        self.assertEqual(
            execution.result.data,
            {
                "invalid_options": ["mode"],
                "allowed_options": {
                    "mode": [
                        "coarse_soup",
                        "emergency",
                        "normal",
                        "rice_porridge",
                    ]
                },
            },
        )
        self.assertEqual(encode_game_state(session.state), before)

    def test_save_failure_rolls_back_command_transaction(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir) / "game.json"
            session = self.new_session(seed=1104, save_path=save_path)
            before = encode_game_state(session.state)

            def fail_save() -> None:
                raise OSError("test-only")

            session.save = fail_save  # type: ignore[method-assign]
            execution = session.command("game.set_furnace", {"level": 2})

        self.assertEqual(execution.result.code, ErrorCode.INTERNAL_ERROR)
        self.assertFalse(execution.result.state_changed)
        self.assertEqual(execution.result.data["failed_stage"], "session_save")
        self.assertEqual(encode_game_state(session.state), before)

    def test_end_day_confirmation_remains_in_one_session(self) -> None:
        session = self.new_session(seed=1105)
        self.assertEqual(
            session.command("game.set_furnace", {"level": 0}).result.code,
            ErrorCode.OK,
        )

        preview = session.command("game.end_day")
        self.assertEqual(
            preview.result.code,
            ErrorCode.END_DAY_CONFIRMATION_REQUIRED,
        )
        confirmation = preview.result.data["confirmation"]
        settled = session.command("game.confirm_end_day", confirmation)

        self.assertEqual(settled.result.code, ErrorCode.OK)
        self.assertEqual(settled.status["day"], 2)
        self.assertEqual(settled.result.data["settled_day"], 1)

    def test_end_day_confirmation_explains_cross_session_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir) / "game.json"
            first = self.new_session(seed=1124, save_path=save_path)
            self.assertEqual(
                first.command("game.set_furnace", {"level": 0}).result.code,
                ErrorCode.OK,
            )
            preview = first.command("game.end_day")
            confirmation = preview.result.data["confirmation"]
            lifecycle = preview.result.data["confirmation_lifecycle"]

            reopened = GameSession.load(save_path, config_dir=ROOT / "data")
            rejected = reopened.command("game.confirm_end_day", confirmation)

        self.assertEqual(
            preview.result.code,
            ErrorCode.END_DAY_CONFIRMATION_REQUIRED,
        )
        self.assertEqual(lifecycle["token_scope"], "current_game_session")
        self.assertTrue(lifecycle["requires_preview_in_same_session"])
        self.assertEqual(rejected.result.code, ErrorCode.ILLEGAL_COMMAND)
        self.assertEqual(rejected.result.data["reason"], "end_day_preview_required")
        self.assertFalse(
            rejected.result.data["active_preview_in_current_session"]
        )
        self.assertTrue(
            rejected.result.data[
                "tokens_from_closed_or_other_sessions_are_invalid"
            ]
        )
        self.assertEqual(
            rejected.result.data["required_preview_command"],
            "game.end_day",
        )
        self.assertEqual(
            rejected.result.data["confirmation_lifecycle"],
            lifecycle,
        )
        self.assertFalse(rejected.result.state_changed)
        self.assertFalse(rejected.save_written)

    def test_firepit_floor_does_not_mask_moderate_same_day_hunger_panic(self) -> None:
        session = self.new_session(seed=1118)
        self.assertEqual(
            session.command(
                "game.sign_law",
                {"law_id": "firepit_law"},
            ).result.code,
            ErrorCode.OK,
        )
        session._state.trust_panic.panic = 9
        session._state.resources.raw_food = 0
        session._state.resources.cooked_food = 0

        execution = session.command("game.end_day")
        if execution.result.code is ErrorCode.END_DAY_CONFIRMATION_REQUIRED:
            execution = session.command(
                "game.confirm_end_day",
                execution.result.data["confirmation"],
            )

        self.assertEqual(execution.result.code, ErrorCode.OK)
        self.assertEqual(
            session.state.events.metrics["patch013_hunger_panic_gain"],
            5,
        )
        self.assertEqual(session.state.trust_panic.panic, 14)

    def test_end_day_save_failure_restores_confirmation_and_autosaves(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir) / "game.json"
            session = self.new_session(seed=1110, save_path=save_path)
            first_day = session.command("game.end_day")
            self.assertEqual(first_day.result.code, ErrorCode.OK)
            old_engine_autosave = session.end_day.last_autosave()
            old_session_autosave = session._last_end_day_autosave
            autosave_path = session.autosave_path
            assert autosave_path is not None
            old_disk_autosave = autosave_path.read_bytes()

            self.assertEqual(
                session.command(
                    "game.set_furnace",
                    {"level": 0},
                ).result.code,
                ErrorCode.OK,
            )
            preview = session.command("game.end_day")
            self.assertEqual(
                preview.result.code,
                ErrorCode.END_DAY_CONFIRMATION_REQUIRED,
            )
            confirmation = preview.result.data["confirmation"]
            before_state = encode_game_state(session.state)
            before_save = save_path.read_bytes()

            original_save = session.save

            def fail_save() -> None:
                save_path.write_bytes(b"partially-replaced")
                raise OSError("test-only")

            session.save = fail_save  # type: ignore[method-assign]
            failed = session.command("game.confirm_end_day", confirmation)
            session.save = original_save  # type: ignore[method-assign]

            self.assertEqual(failed.result.code, ErrorCode.INTERNAL_ERROR)
            self.assertEqual(encode_game_state(session.state), before_state)
            self.assertEqual(save_path.read_bytes(), before_save)
            self.assertEqual(autosave_path.read_bytes(), old_disk_autosave)
            self.assertEqual(
                session.end_day.last_autosave(),
                old_engine_autosave,
            )
            self.assertEqual(
                session._last_end_day_autosave,
                old_session_autosave,
            )

            retried = session.command(
                "game.confirm_end_day",
                confirmation,
            )

            self.assertEqual(retried.result.code, ErrorCode.OK)
            self.assertEqual(retried.status["day"], 3)
            self.assertEqual(
                session.end_day.last_autosave().settled_day,  # type: ignore[union-attr]
                2,
            )

    def test_end_day_autosave_persists_pre_advance_boundary_separately(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir) / "game.json"
            session = self.new_session(seed=1111, save_path=save_path)

            execution = session.command("game.end_day")
            autosave_path = session.autosave_path
            assert autosave_path is not None
            autosave = json.loads(autosave_path.read_text(encoding="utf-8"))
            main_save = json.loads(save_path.read_text(encoding="utf-8"))

            self.assertEqual(execution.result.code, ErrorCode.OK)
            self.assertNotEqual(autosave_path, save_path)
            self.assertEqual(autosave["slot"], "autosave_end_day")
            self.assertEqual(autosave["settled_day"], 1)
            self.assertEqual(autosave["resume_stage"], "advance_day")
            self.assertEqual(autosave["state"]["calendar"]["current_day"], 1)
            self.assertTrue(
                autosave["state"]["calendar"]["is_day_locked"]
            )
            self.assertTrue(
                autosave["state"]["calendar"]["is_end_day_confirmed"]
            )
            self.assertEqual(main_save["calendar"]["current_day"], 2)
            self.assertFalse(main_save["calendar"]["is_day_locked"])
            self.assertNotIn("resume_stage", main_save)
            restored = GameSession.load(
                save_path,
                config_dir=ROOT / "data",
            )
            self.assertEqual(restored.status()["day"], 2)
            view = restored.autosave_view()

            self.assertTrue(view["available"])
            self.assertEqual(view["document_type"], "end_day_autosave_snapshot")
            self.assertEqual(view["source"], "disk")
            self.assertEqual(view["settled_day"], 1)
            self.assertEqual(view["resume_stage"], "advance_day")
            self.assertEqual(view["state"]["calendar"]["current_day"], 1)
            self.assertTrue(view["state"]["calendar"]["is_day_locked"])
            self.assertFalse(view["contract"]["accepted_as_primary_save"])
            self.assertTrue(
                restored.status()["persistence"]["autosave_end_day_present"]
            )

            autosave_bytes = autosave_path.read_bytes()
            with self.assertRaisesRegex(
                ValueError,
                "end_day_autosave_snapshot_is_not_primary_save",
            ):
                self.new_session(
                    seed=9999,
                    save_path=autosave_path,
                    overwrite=True,
                )
            self.assertEqual(autosave_path.read_bytes(), autosave_bytes)

    def test_autosave_view_is_unavailable_before_first_end_day(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            session = self.new_session(
                seed=1129,
                save_path=Path(temp_dir) / "game.json",
            )

            view = session.autosave_view()

        self.assertFalse(view["available"])
        self.assertEqual(view["source"], "none")
        self.assertEqual(view["slot"], "autosave_end_day")
        self.assertFalse(view["contract"]["accepted_as_primary_save"])

    def test_malformed_autosave_does_not_block_primary_save_loading(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir) / "game.json"
            session = self.new_session(seed=1130, save_path=save_path)
            self.assertEqual(
                session.command("game.end_day").result.code,
                ErrorCode.OK,
            )
            autosave_path = session.autosave_path
            assert autosave_path is not None
            document = json.loads(autosave_path.read_text(encoding="utf-8"))
            document["unexpected"] = True
            autosave_path.write_text(
                json.dumps(document, ensure_ascii=False),
                encoding="utf-8",
            )

            restored = GameSession.load(save_path, config_dir=ROOT / "data")

            self.assertEqual(restored.status()["day"], 2)
            with self.assertRaises(AutosaveSnapshotValidationError) as caught:
                restored.autosave_view()
            self.assertEqual(caught.exception.code, "AUTOSAVE_SNAPSHOT_INVALID")
            self.assertEqual(
                caught.exception.details["reason"],
                "top_level_fields_invalid",
            )
            self.assertEqual(caught.exception.details["field"], "$")

    def test_autosave_view_rejects_inconsistent_day_and_resume_stage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir) / "game.json"
            session = self.new_session(seed=1132, save_path=save_path)
            self.assertEqual(
                session.command("game.end_day").result.code,
                ErrorCode.OK,
            )
            autosave_path = session.autosave_path
            assert autosave_path is not None
            original = json.loads(autosave_path.read_text(encoding="utf-8"))
            restored = GameSession.load(save_path, config_dir=ROOT / "data")

            cases = (
                ("settled_day", 999, "settled_day_state_mismatch"),
                ("resume_stage", "invented_stage", "resume_stage_unknown"),
                (
                    "resume_stage",
                    "terminal_state",
                    "resume_stage_state_mismatch",
                ),
            )
            for field, value, message in cases:
                with self.subTest(field=field, value=value):
                    document = deepcopy(original)
                    document[field] = value
                    autosave_path.write_text(
                        json.dumps(document, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    with self.assertRaisesRegex(
                        AutosaveSnapshotValidationError,
                        message,
                    ):
                        restored.autosave_view()

    def test_autosave_view_rejects_duplicate_and_descending_log_sequences(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir) / "game.json"
            session = self.new_session(seed=1133, save_path=save_path)
            self.assertEqual(
                session.command("game.end_day").result.code,
                ErrorCode.OK,
            )
            autosave_path = session.autosave_path
            assert autosave_path is not None
            original = json.loads(autosave_path.read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(original["logs"]), 3)
            restored = GameSession.load(save_path, config_dir=ROOT / "data")

            for first, second in ((1, 1), (2, 1)):
                with self.subTest(sequences=(first, second)):
                    document = deepcopy(original)
                    document["logs"][0]["sequence"] = first
                    document["logs"][1]["sequence"] = second
                    autosave_path.write_text(
                        json.dumps(document, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    with self.assertRaises(
                        AutosaveSnapshotValidationError
                    ) as caught:
                        restored.autosave_view()
                    self.assertEqual(
                        caught.exception.details["reason"],
                        "log_sequence_not_strictly_increasing",
                    )
                    self.assertEqual(
                        caught.exception.details["field"],
                        "logs[1].sequence",
                    )

    def test_overwrite_new_session_clears_previous_autosave(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir) / "game.json"
            previous = self.new_session(seed=100, save_path=save_path)
            self.assertEqual(
                previous.command("game.end_day").result.code,
                ErrorCode.OK,
            )
            autosave_path = previous.autosave_path
            assert autosave_path is not None
            previous_autosave = json.loads(
                autosave_path.read_text(encoding="utf-8")
            )
            self.assertEqual(
                previous_autosave["state"]["random"]["seed"],
                100,
            )

            replacement = self.new_session(
                seed=200,
                save_path=save_path,
                overwrite=True,
            )
            replacement_save = json.loads(
                save_path.read_text(encoding="utf-8")
            )

            self.assertEqual(replacement.status()["day"], 1)
            self.assertEqual(replacement_save["random"]["seed"], 200)
            self.assertEqual(
                replacement_save["calendar"]["current_day"],
                1,
            )
            self.assertFalse(autosave_path.exists())

    def test_residual_autosave_blocks_new_session_without_overwrite(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir) / "game.json"
            previous = self.new_session(seed=100, save_path=save_path)
            self.assertEqual(
                previous.command("game.end_day").result.code,
                ErrorCode.OK,
            )
            autosave_path = previous.autosave_path
            assert autosave_path is not None
            autosave_bytes = autosave_path.read_bytes()
            save_path.unlink()

            with self.assertRaises(FileExistsError):
                self.new_session(seed=200, save_path=save_path)

            self.assertFalse(save_path.exists())
            self.assertEqual(autosave_path.read_bytes(), autosave_bytes)

            replacement = self.new_session(
                seed=200,
                save_path=save_path,
                overwrite=True,
            )
            self.assertEqual(replacement.status()["day"], 1)
            self.assertTrue(save_path.exists())
            self.assertFalse(autosave_path.exists())

    def test_new_session_autosave_cleanup_failure_restores_both_files(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir) / "game.json"
            previous = self.new_session(seed=100, save_path=save_path)
            self.assertEqual(
                previous.command("game.end_day").result.code,
                ErrorCode.OK,
            )
            autosave_path = previous.autosave_path
            assert autosave_path is not None
            save_bytes = save_path.read_bytes()
            autosave_bytes = autosave_path.read_bytes()

            def remove_then_fail(session: GameSession) -> None:
                target = session.autosave_path
                assert target is not None
                target.unlink()
                raise OSError("test-only cleanup failure")

            with patch.object(
                GameSession,
                "_remove_end_day_autosave",
                remove_then_fail,
            ):
                with self.assertRaises(OSError):
                    self.new_session(
                        seed=200,
                        save_path=save_path,
                        overwrite=True,
                    )

            self.assertEqual(save_path.read_bytes(), save_bytes)
            self.assertEqual(autosave_path.read_bytes(), autosave_bytes)
            restored = GameSession.load(
                save_path,
                config_dir=ROOT / "data",
            )
            self.assertEqual(restored.status()["day"], 2)
            restored_autosave = json.loads(
                autosave_path.read_text(encoding="utf-8")
            )
            self.assertEqual(
                restored_autosave["state"]["random"]["seed"],
                100,
            )

    def test_same_seed_and_commands_produce_same_state_and_replay(self) -> None:
        first = self.new_session(seed=1106)
        second = self.new_session(seed=1106)
        commands = (
            (
                "game.assign_resource",
                {
                    "resource_point_id": "surface-coal-1",
                    "population_type": "workers",
                    "count": 10,
                },
            ),
            ("game.set_furnace", {"level": 2}),
            ("game.end_day", {}),
        )
        for name, arguments in commands:
            self.assertEqual(
                first.command(name, arguments).result.code,
                second.command(name, arguments).result.code,
            )

        self.assertEqual(
            encode_game_state(first.state),
            encode_game_state(second.state),
        )
        self.assertEqual(
            dumps(first.replay_document()),
            dumps(second.replay_document()),
        )

    def test_observation_is_a_snapshot_and_payload_errors_are_stable(self) -> None:
        session = self.new_session(seed=1107)
        observation = session.observe()
        observation.state.resources.coal = 0

        malformed = session.execute_payload(  # type: ignore[arg-type]
            {"name": "game.set_furnace", "arguments": []}
        )
        malformed_identity = session.execute_payload(
            {
                "command_id": 7,
                "name": "game.set_furnace",
                "arguments": {"level": 2},
            }
        )
        stale = session.execute_payload(
            {
                "name": "game.set_furnace",
                "arguments": {"level": 2},
                "expected_state_sequence": 99,
            }
        )

        self.assertEqual(session.status()["resources"]["coal"], 70)
        self.assertEqual(
            malformed.result.code,
            ErrorCode.INVALID_COMMAND_FORMAT,
        )
        self.assertEqual(
            malformed.result.data["field_errors"]["arguments"],
            {"required_kind": "OBJECT", "actual_kind": "ARRAY"},
        )
        self.assertEqual(
            malformed.result.data["request_shape"]["arguments"],
            "OBJECT",
        )
        self.assertIsNone(malformed.replay_sequence)
        self.assertEqual(
            malformed_identity.result.code,
            ErrorCode.INVALID_COMMAND_FORMAT,
        )
        self.assertEqual(
            malformed_identity.result.data["reason"],
            "invalid_command_format",
        )
        self.assertEqual(
            malformed_identity.result.data["unsupported_field_aliases"],
            {"command": "name"},
        )
        self.assertEqual(
            malformed_identity.result.data["accepted_envelope_shapes"][0][
                "type"
            ],
            "command",
        )
        self.assertEqual(
            malformed_identity.result.data["request_fields"]["required"],
            ["name"],
        )
        self.assertNotIn(
            "json_lines_envelope_example",
            malformed_identity.result.data,
        )
        format_details = json.dumps(
            malformed_identity.result.data,
            ensure_ascii=False,
            sort_keys=True,
        )
        self.assertNotIn("game.", format_details)
        self.assertNotIn("furnace", format_details)
        self.assertNotIn("level", format_details)
        self.assertIsNone(malformed_identity.replay_sequence)
        self.assertEqual(stale.result.code, ErrorCode.STALE_STATE)
        self.assertEqual(stale.result.data["current_state_sequence"], 0)
        self.assertTrue(stale.result.data["requires_fresh_observation"])
        self.assertEqual(stale.result.data["retry_expected_state_sequence"], 0)

    def test_confirm_false_precedes_missing_fields_without_state_pollution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir) / "confirm-false.json"
            session = self.new_session(seed=1120, save_path=save_path)
            before_state = encode_game_state(session.state)
            before_save = save_path.read_bytes()
            before_replay_count = len(session.replay_document().entries)

            rejected = session.command(
                "game.overtime",
                {"confirm": False},
            )

            self.assertEqual(rejected.result.code, ErrorCode.ILLEGAL_COMMAND)
            self.assertEqual(
                rejected.result.data["reason"],
                "confirm_false_is_not_preview",
            )
            self.assertFalse(rejected.result.data["state_will_change"])
            self.assertFalse(rejected.save_written)
            self.assertEqual(encode_game_state(session.state), before_state)
            self.assertEqual(save_path.read_bytes(), before_save)
            self.assertEqual(rejected.result.state_sequence, 0)
            replay = session.replay_document()
            self.assertEqual(len(replay.entries), before_replay_count + 1)
            self.assertFalse(replay.entries[-1].result.accepted)
            self.assertFalse(replay.entries[-1].result.state_changed)
            self.assertEqual(replay.entries[-1].result.state_sequence, 0)

    def test_replay_can_be_exported_as_canonical_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            session = self.new_session(seed=1108)
            session.command("game.set_furnace", {"level": 2})
            path = Path(temp_dir) / "replay.json"

            session.write_replay(path)
            document = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(document["format_version"], 1)
        self.assertEqual(document["entries"][0]["request"]["name"], "game.set_furnace")
        self.assertEqual(document["entries"][0]["result"]["code"], "OK")

    def test_replay_cannot_overwrite_save_or_autosave(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir) / "game.json"
            session = self.new_session(seed=1112, save_path=save_path)
            self.assertEqual(
                session.command("game.end_day").result.code,
                ErrorCode.OK,
            )
            autosave_path = session.autosave_path
            assert autosave_path is not None
            save_bytes = save_path.read_bytes()
            autosave_bytes = autosave_path.read_bytes()

            with self.assertRaises(ValueError):
                session.write_replay(save_path, overwrite=True)
            with self.assertRaises(ValueError):
                session.write_replay(autosave_path, overwrite=True)

            self.assertEqual(save_path.read_bytes(), save_bytes)
            self.assertEqual(autosave_path.read_bytes(), autosave_bytes)
            restored = GameSession.load(
                save_path,
                config_dir=ROOT / "data",
            )
            self.assertEqual(restored.status()["day"], 2)

    def test_save_and_replay_cannot_target_runtime_config_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_dir = root / "data"
            shutil.copytree(ROOT / "data", config_dir)
            config_paths = sorted(config_dir.glob("*.json"))
            config_bytes = {
                config_path: config_path.read_bytes()
                for config_path in config_paths
            }

            for config_path in config_paths:
                with self.subTest(save_path=config_path):
                    with self.assertRaises(ValueError):
                        GameSession.new(
                            config_dir=config_dir,
                            save_path=config_path,
                            seed=1113,
                            overwrite=True,
                        )
                    self.assertEqual(
                        config_path.read_bytes(),
                        config_bytes[config_path],
                    )

            save_path = root / "game.json"
            session = GameSession.new(
                config_dir=config_dir,
                save_path=save_path,
                seed=1113,
            )
            for config_path in config_paths:
                with self.subTest(replay_path=config_path):
                    with self.assertRaises(ValueError):
                        session.write_replay(
                            config_path,
                            overwrite=True,
                        )
                    self.assertEqual(
                        config_path.read_bytes(),
                        config_bytes[config_path],
                    )
            restored = GameSession.load(
                save_path,
                config_dir=config_dir,
            )
            self.assertEqual(restored.status()["day"], 1)

    def test_existing_replay_requires_explicit_safe_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            session = self.new_session(seed=1114)
            path = Path(temp_dir) / "replay.json"
            session.write_replay(path)
            original_bytes = path.read_bytes()
            session.command("game.set_furnace", {"level": 2})

            with self.assertRaises(FileExistsError):
                session.write_replay(path)
            self.assertEqual(path.read_bytes(), original_bytes)

            session.write_replay(path, overwrite=True)
            document = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(len(document["entries"]), 1)

            ordinary_path = Path(temp_dir) / "notes.json"
            ordinary_path.write_bytes(b'{"not":"a replay"}')
            ordinary_bytes = ordinary_path.read_bytes()
            with self.assertRaises(ValueError):
                session.write_replay(ordinary_path, overwrite=True)
            self.assertEqual(ordinary_path.read_bytes(), ordinary_bytes)

    def test_replay_overwrite_rejects_every_malformed_entry_shape(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            session = self.new_session(seed=1115)
            session.command("game.set_furnace", {"level": 2})
            session.command("game.set_furnace", {"level": 1})
            path = Path(temp_dir) / "replay.json"
            session.write_replay(path)
            valid_document = json.loads(path.read_text(encoding="utf-8"))

            malformed_entry = deepcopy(valid_document)
            malformed_entry["entries"][0] = 123

            missing_field = deepcopy(valid_document)
            del missing_field["entries"][0]["result"]

            invalid_random = deepcopy(valid_document)
            invalid_random["entries"][0]["random_after"][
                "internal_state"
            ] = -1

            invalid_sequence = deepcopy(valid_document)
            invalid_sequence["entries"][1]["sequence"] = (
                invalid_sequence["entries"][0]["sequence"]
            )

            mismatched_command = deepcopy(valid_document)
            mismatched_command["entries"][0]["result"]["command_id"] = (
                "different-command"
            )

            invalid_log = deepcopy(valid_document)
            invalid_log["entries"][0]["logs"][0]["category"] = "UNKNOWN"

            cases = {
                "malformed_entry": malformed_entry,
                "missing_field": missing_field,
                "invalid_random": invalid_random,
                "invalid_sequence": invalid_sequence,
                "mismatched_command": mismatched_command,
                "invalid_log": invalid_log,
            }
            for name, document in cases.items():
                with self.subTest(name=name):
                    path.write_text(
                        json.dumps(document, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    malformed_bytes = path.read_bytes()

                    with self.assertRaises(ValueError):
                        session.write_replay(path, overwrite=True)

                    self.assertEqual(path.read_bytes(), malformed_bytes)


class PlayCliTests(unittest.TestCase):
    def test_json_lines_exposes_status_specs_and_supported_envelopes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir) / "cli-queries.json"
            requests = (
                {"type": "status"},
                {"type": "command_specs"},
                {"type": "unsupported"},
                {"type": "quit"},
            )
            input_stream = StringIO(
                "".join(json.dumps(item) + "\n" for item in requests)
            )
            output_stream = StringIO()
            with patch("sys.stdin", input_stream), redirect_stdout(output_stream):
                exit_code = main(
                    [
                        "play",
                        str(save_path),
                        "--data-dir",
                        str(ROOT / "data"),
                        "--new",
                    ]
                )
            lines = [
                json.loads(line)
                for line in output_stream.getvalue().splitlines()
            ]

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            [item["type"] for item in lines],
            ["observation", "status", "command_specs", "error", "closed"],
        )
        self.assertEqual(lines[1]["status"]["day"], 1)
        self.assertTrue(
            any(
                spec["name"] == "game.end_day"
                for spec in lines[2]["command_specs"]
            )
        )
        self.assertEqual(lines[3]["code"], "UNKNOWN_ENVELOPE_TYPE")
        self.assertEqual(
            lines[3]["supported_envelope_types"],
            [
                "autosave",
                "command",
                "command_specs",
                "observe",
                "quit",
                "replay",
                "rules",
                "status",
            ],
        )
        self.assertEqual(lines[1]["status"]["state_sequence"], 0)
        self.assertEqual(lines[4]["status"]["state_sequence"], 0)

    def test_json_lines_autosave_view_and_direct_path_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir) / "cli-autosave.json"
            session = GameSession.new(
                config_dir=ROOT / "data",
                save_path=save_path,
                seed=1131,
            )
            self.assertEqual(
                session.command("game.end_day").result.code,
                ErrorCode.OK,
            )
            autosave_path = session.autosave_path
            assert autosave_path is not None

            input_stream = StringIO(
                json.dumps({"type": "autosave"})
                + "\n"
                + json.dumps({"type": "quit"})
                + "\n"
            )
            play_output = StringIO()
            with patch("sys.stdin", input_stream), redirect_stdout(play_output):
                play_exit = main(
                    [
                        "play",
                        str(save_path),
                        "--data-dir",
                        str(ROOT / "data"),
                    ]
                )
            play_lines = [
                json.loads(line)
                for line in play_output.getvalue().splitlines()
            ]

            direct_play_output = StringIO()
            with patch("sys.stdin", StringIO()), redirect_stdout(
                direct_play_output
            ):
                direct_play_exit = main(
                    [
                        "play",
                        str(autosave_path),
                        "--data-dir",
                        str(ROOT / "data"),
                    ]
                )
            direct_play_error = json.loads(direct_play_output.getvalue())

            report_output = StringIO()
            with redirect_stdout(report_output):
                report_exit = main(["report", str(autosave_path)])
            report_error = json.loads(report_output.getvalue())

        self.assertEqual(play_exit, 0)
        self.assertEqual(
            [item["type"] for item in play_lines],
            ["observation", "autosave", "closed"],
        )
        autosave = play_lines[1]["autosave"]
        self.assertTrue(autosave["available"])
        self.assertEqual(autosave["settled_day"], 1)
        self.assertEqual(autosave["state"]["calendar"]["current_day"], 1)
        self.assertEqual(direct_play_exit, 1)
        self.assertEqual(report_exit, 1)
        for error in (direct_play_error, report_error):
            self.assertEqual(
                error["code"],
                "AUTOSAVE_SNAPSHOT_NOT_PRIMARY_SAVE",
            )
            self.assertFalse(error["accepted_as_primary_save"])
            self.assertEqual(
                error["inspect_request_after_opening_primary_save"],
                {"type": "autosave"},
            )
            self.assertEqual(
                Path(error["recovery"]["open_primary_save_path"]),
                save_path,
            )
            self.assertTrue(error["recovery"]["do_not_extract_nested_state"])

    def test_autosave_path_error_resolves_extensionless_primary_save(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir) / "game"
            session = GameSession.new(
                config_dir=ROOT / "data",
                seed=1134,
                save_path=save_path,
            )
            self.assertEqual(
                session.command("game.end_day").result.code,
                ErrorCode.OK,
            )
            autosave_path = session.autosave_path
            assert autosave_path is not None

            with self.assertRaises(AutosaveSnapshotPathError) as caught:
                GameSession.load(autosave_path, config_dir=ROOT / "data")

            details = caught.exception.details
            recovery = details["recovery"]
            self.assertEqual(
                Path(recovery["open_primary_save_path"]),
                save_path,
            )
            self.assertEqual(recovery["primary_save_path_resolution"], "resolved")
            self.assertFalse(recovery["primary_save_path_ambiguous"])
            self.assertEqual(
                [Path(path) for path in recovery["recognized_primary_save_paths"]],
                [save_path],
            )

    def test_autosave_path_error_reports_ambiguous_primary_save_candidates(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            extensionless_path = Path(temp_dir) / "game"
            session = GameSession.new(
                config_dir=ROOT / "data",
                seed=1135,
                save_path=extensionless_path,
            )
            self.assertEqual(
                session.command("game.end_day").result.code,
                ErrorCode.OK,
            )
            json_path = Path(temp_dir) / "game.json"
            json_path.write_bytes(extensionless_path.read_bytes())
            autosave_path = session.autosave_path
            assert autosave_path is not None

            with self.assertRaises(AutosaveSnapshotPathError) as caught:
                GameSession.load(autosave_path, config_dir=ROOT / "data")

            recovery = caught.exception.details["recovery"]
            self.assertIsNone(recovery["open_primary_save_path"])
            self.assertEqual(
                recovery["primary_save_path_resolution"],
                "ambiguous",
            )
            self.assertTrue(recovery["primary_save_path_ambiguous"])
            self.assertEqual(
                {Path(path) for path in recovery["recognized_primary_save_paths"]},
                {extensionless_path, json_path},
            )

    def test_json_lines_diagnoses_each_damaged_autosave_constraint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir) / "diagnostic.json"
            session = GameSession.new(
                config_dir=ROOT / "data",
                seed=1136,
                save_path=save_path,
            )
            self.assertEqual(
                session.command("game.end_day").result.code,
                ErrorCode.OK,
            )
            autosave_path = session.autosave_path
            assert autosave_path is not None
            original = json.loads(autosave_path.read_text(encoding="utf-8"))
            original_primary_bytes = save_path.read_bytes()

            cases = (
                (
                    "settled_day_mismatch",
                    lambda document: document.__setitem__("settled_day", 2),
                    "settled_day",
                    "settled_day_state_mismatch",
                ),
                (
                    "unknown_resume_stage",
                    lambda document: document.__setitem__(
                        "resume_stage", "hard_fail"
                    ),
                    "resume_stage",
                    "resume_stage_unknown",
                ),
                (
                    "mismatched_resume_stage",
                    lambda document: document.__setitem__(
                        "resume_stage", "terminal_state"
                    ),
                    "resume_stage",
                    "resume_stage_state_mismatch",
                ),
                (
                    "duplicate_log_sequence",
                    lambda document: document["logs"][1].__setitem__(
                        "sequence", 1
                    ),
                    "logs[1].sequence",
                    "log_sequence_not_strictly_increasing",
                ),
                (
                    "descending_log_sequence",
                    lambda document: document["logs"][1].__setitem__(
                        "sequence", 0
                    ),
                    "logs[1].sequence",
                    "log_sequence_not_strictly_increasing",
                ),
            )
            for case_id, mutate, field, reason in cases:
                with self.subTest(case_id=case_id):
                    document = deepcopy(original)
                    mutate(document)
                    autosave_path.write_text(
                        json.dumps(document, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    damaged_bytes = autosave_path.read_bytes()
                    output = StringIO()
                    with patch(
                        "sys.stdin",
                        StringIO(
                            json.dumps({"type": "autosave"})
                            + "\n"
                            + json.dumps({"type": "quit"})
                            + "\n"
                        ),
                    ), redirect_stdout(output):
                        exit_code = main(
                            [
                                "play",
                                str(save_path),
                                "--data-dir",
                                str(ROOT / "data"),
                            ]
                        )
                    lines = [
                        json.loads(line)
                        for line in output.getvalue().splitlines()
                    ]
                    error = lines[1]

                    self.assertEqual(exit_code, 0)
                    self.assertEqual(error["type"], "error")
                    self.assertEqual(error["code"], "AUTOSAVE_SNAPSHOT_INVALID")
                    self.assertEqual(error["field"], field)
                    self.assertEqual(error["reason"], reason)
                    self.assertTrue(error["constraint"])
                    self.assertEqual(error["path"], str(autosave_path))
                    self.assertEqual(
                        error["allowed_values"],
                        ["advance_day", "terminal_state", "final_settlement"]
                        if field == "resume_stage"
                        else [],
                    )
                    self.assertEqual(lines[2]["type"], "closed")
                    self.assertEqual(save_path.read_bytes(), original_primary_bytes)
                    self.assertEqual(autosave_path.read_bytes(), damaged_bytes)

    def test_json_lines_session_creates_save_and_returns_compact_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir) / "cli-save.json"
            input_stream = StringIO(
                json.dumps(
                    {
                        "name": "game.set_furnace",
                        "arguments": {"level": 2},
                    }
                )
                + "\n"
                + json.dumps({"type": "quit"})
                + "\n"
            )
            output_stream = StringIO()
            with patch("sys.stdin", input_stream), redirect_stdout(output_stream):
                exit_code = main(
                    [
                        "play",
                        str(save_path),
                        "--data-dir",
                        str(ROOT / "data"),
                        "--new",
                    ]
                )
            lines = [
                json.loads(line)
                for line in output_stream.getvalue().splitlines()
            ]

        self.assertEqual(exit_code, 0)
        self.assertEqual([item["type"] for item in lines], [
            "observation",
            "execution",
            "closed",
        ])
        self.assertEqual(lines[1]["execution"]["result"]["code"], "OK")
        self.assertEqual(
            lines[1]["execution"]["status"]["furnace"]["mode_id"],
            "level_2",
        )

    def test_json_lines_wrong_command_alias_returns_protocol_only_shapes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir) / "cli-format.json"
            input_stream = StringIO(
                json.dumps(
                    {
                        "command": "UNUSED_COMMAND_NAME",
                        "arguments": {},
                    }
                )
                + "\n"
                + json.dumps({"type": "quit"})
                + "\n"
            )
            output_stream = StringIO()
            with patch("sys.stdin", input_stream), redirect_stdout(output_stream):
                exit_code = main(
                    [
                        "play",
                        str(save_path),
                        "--data-dir",
                        str(ROOT / "data"),
                        "--new",
                    ]
                )
            lines = [
                json.loads(line)
                for line in output_stream.getvalue().splitlines()
            ]

        self.assertEqual(exit_code, 0)
        result = lines[1]["execution"]["result"]
        self.assertEqual(result["code"], "INVALID_COMMAND_FORMAT")
        self.assertEqual(
            result["data"]["unsupported_field_aliases"],
            {"command": "name"},
        )
        self.assertEqual(
            result["data"]["request_fields"]["required"], ["name"]
        )
        serialized = json.dumps(result["data"], ensure_ascii=False)
        self.assertNotIn("game.", serialized)


if __name__ == "__main__":
    unittest.main()
