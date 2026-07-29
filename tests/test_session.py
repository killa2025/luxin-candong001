from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
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

        self.assertEqual(session.status()["day"], 1)
        self.assertEqual(session.status()["population"]["alive"], 80)
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
