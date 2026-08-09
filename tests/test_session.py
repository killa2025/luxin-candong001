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
from furnace_winter.interface import ErrorCode
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
        self.assertEqual(malformed.result.code, ErrorCode.INVALID_ARGUMENTS)
        self.assertIsNone(malformed.replay_sequence)
        self.assertEqual(
            malformed_identity.result.code,
            ErrorCode.INVALID_COMMAND_FORMAT,
        )
        self.assertIsNone(malformed_identity.replay_sequence)
        self.assertEqual(stale.result.code, ErrorCode.STALE_STATE)

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


if __name__ == "__main__":
    unittest.main()
