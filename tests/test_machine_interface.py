from __future__ import annotations

import json
import unittest
from contextlib import redirect_stdout
from io import StringIO

from furnace_winter.cli import main
from furnace_winter.interface import (
    ArgumentKind,
    CommandCatalog,
    CommandRequest,
    CommandResult,
    CommandSpec,
    CommandValidation,
    CommandValidator,
    ErrorCode,
    EventLog,
    LogCategory,
    LogEntry,
    ReplayEntry,
    ReplayLog,
)
from furnace_winter.models import DeterministicRandom, GameState


class CommandInterfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = CommandCatalog()
        self.catalog.register(
            CommandSpec(
                name="test.action",
                required_arguments={"amount": ArgumentKind.INTEGER},
            )
        )
        self.validator = CommandValidator(self.catalog)

    def test_command_schema_validation(self) -> None:
        valid = self.validator.validate(
            CommandRequest("command-1", "test.action", {"amount": 2})
        )
        invalid = self.validator.validate(
            CommandRequest("command-2", "test.action", {"amount": "2"})
        )

        self.assertEqual(valid.code, ErrorCode.OK)
        self.assertEqual(invalid.code, ErrorCode.INVALID_ARGUMENTS)

    def test_unknown_commands_are_rejected(self) -> None:
        result = self.validator.validate(CommandRequest("command-1", "game.unknown"))

        self.assertEqual(result.code, ErrorCode.COMMAND_NOT_REGISTERED)

    def test_stale_state_and_legality_hooks_are_separate(self) -> None:
        state = GameState.initial()
        state.command_sequence = 3
        stale = self.validator.validate(
            CommandRequest(
                "command-1",
                "test.action",
                {"amount": 1},
                expected_state_sequence=2,
            ),
            state,
        )
        illegal = self.validator.validate(
            CommandRequest("command-2", "test.action", {"amount": 1}),
            state,
            lambda _state, _request: CommandValidation(
                False, ErrorCode.ILLEGAL_COMMAND, {"reason": "test-only"}
            ),
        )

        self.assertEqual(stale.code, ErrorCode.STALE_STATE)
        self.assertEqual(illegal.code, ErrorCode.ILLEGAL_COMMAND)


class ReplayInterfaceTests(unittest.TestCase):
    def test_event_log_is_append_only_and_ordered(self) -> None:
        log = EventLog()
        log.append(LogEntry(1, LogCategory.SYSTEM, "START"))

        with self.assertRaises(ValueError):
            log.append(LogEntry(1, LogCategory.SYSTEM, "DUPLICATE"))

        self.assertEqual(log.entries()[0].code, "START")

    def test_replay_log_records_command_result_and_random_boundaries(self) -> None:
        random = DeterministicRandom(11)
        before = random.snapshot()
        random.next_u64()
        after = random.snapshot()
        request = CommandRequest("command-1", "test.action", {"amount": 1})
        result = CommandResult("command-1", True, ErrorCode.OK, state_sequence=1)
        initial_state = GameState.initial(random_seed=11)
        log = ReplayLog(initial_state)

        log.append(ReplayEntry(1, request, result, before, after))

        self.assertEqual(log.entries()[0].random_before, before)
        self.assertEqual(log.entries()[0].random_after, after)
        self.assertEqual(log.document().initial_state["random"]["seed"], 11)


class MachineStartupTests(unittest.TestCase):
    def test_state_command_outputs_json_with_requested_seed(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            exit_code = main(["state", "--seed", "31415"])

        document = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(document["protocol_version"], 1)
        self.assertEqual(document["state"]["random"]["seed"], 31415)
        self.assertEqual(document["available_commands"], [])


if __name__ == "__main__":
    unittest.main()
