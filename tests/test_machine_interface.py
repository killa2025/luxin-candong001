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
    FeedbackItem,
    FeedbackLevel,
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

    def test_command_schema_rejects_values_outside_declared_options(self) -> None:
        catalog = CommandCatalog()
        catalog.register(
            CommandSpec(
                name="test.mode",
                required_arguments={"mode": ArgumentKind.STRING},
                argument_options={"mode": ("normal", "emergency")},
            )
        )

        result = CommandValidator(catalog).validate(
            CommandRequest(
                "command-options",
                "test.mode",
                {"mode": "emergency_ration"},
            )
        )

        self.assertEqual(result.code, ErrorCode.INVALID_ARGUMENTS)
        self.assertEqual(result.details["invalid_options"], ["mode"])
        self.assertEqual(
            result.details["allowed_options"],
            {"mode": ["normal", "emergency"]},
        )

    def test_command_schema_exposes_and_validates_argument_semantics(self) -> None:
        catalog = CommandCatalog()
        catalog.register(
            CommandSpec(
                name="test.assign",
                required_arguments={"count": ArgumentKind.INTEGER},
                argument_semantics={"count": "absolute_target_count"},
            )
        )

        self.assertEqual(
            catalog.get("test.assign").argument_semantics,
            {"count": "absolute_target_count"},
        )
        with self.assertRaises(ValueError):
            catalog.register(
                CommandSpec(
                    name="test.unknown-semantic",
                    argument_semantics={"count": "absolute_target_count"},
                )
            )

        confirm_catalog = CommandCatalog()
        confirm_catalog.register(
            CommandSpec(
                name="test.confirmed",
                required_arguments={"confirm": ArgumentKind.BOOLEAN},
            )
        )
        self.assertEqual(
            confirm_catalog.get("test.confirmed").argument_semantics[
                "confirm"
            ],
            "explicit_true_only_never_preview",
        )
        false_confirmation = CommandValidator(confirm_catalog).validate(
            CommandRequest(
                "command-confirm-false",
                "test.confirmed",
                {"confirm": False},
            )
        )
        self.assertEqual(false_confirmation.code, ErrorCode.ILLEGAL_COMMAND)
        self.assertEqual(
            false_confirmation.details["reason"],
            "confirm_false_is_not_preview",
        )
        self.assertFalse(false_confirmation.details["state_will_change"])
        with self.assertRaises(ValueError):
            catalog.register(
                CommandSpec(
                    name="test.bad-semantic",
                    required_arguments={"count": ArgumentKind.INTEGER},
                    argument_semantics={"count": "Not normalized"},
                )
            )

    def test_confirm_false_precedes_missing_fields_only_for_confirm_specs(self) -> None:
        confirm_catalog = CommandCatalog()
        confirm_catalog.register(
            CommandSpec(
                name="test.confirmed",
                required_arguments={
                    "target": ArgumentKind.STRING,
                    "confirm": ArgumentKind.BOOLEAN,
                },
            )
        )
        confirm_result = CommandValidator(confirm_catalog).validate(
            CommandRequest(
                "command-confirm-false-missing-target",
                "test.confirmed",
                {"confirm": False},
            )
        )

        plain_catalog = CommandCatalog()
        plain_catalog.register(
            CommandSpec(
                name="test.plain",
                required_arguments={"target": ArgumentKind.STRING},
            )
        )
        plain_result = CommandValidator(plain_catalog).validate(
            CommandRequest(
                "command-plain-false",
                "test.plain",
                {"confirm": False},
            )
        )

        self.assertEqual(confirm_result.code, ErrorCode.ILLEGAL_COMMAND)
        self.assertEqual(
            confirm_result.details["reason"],
            "confirm_false_is_not_preview",
        )
        self.assertEqual(plain_result.code, ErrorCode.INVALID_ARGUMENTS)
        self.assertEqual(plain_result.details["missing"], ["target"])
        self.assertEqual(plain_result.details["unexpected"], ["confirm"])

    def test_unknown_commands_are_rejected(self) -> None:
        result = self.validator.validate(CommandRequest("command-1", "game.unknown"))

        self.assertEqual(result.code, ErrorCode.COMMAND_NOT_REGISTERED)

    def test_malformed_command_identity_returns_stable_error(self) -> None:
        requests = (
            CommandRequest(None, "test.action"),  # type: ignore[arg-type]
            CommandRequest(1, "test.action"),  # type: ignore[arg-type]
            CommandRequest("command-1", None),  # type: ignore[arg-type]
            CommandRequest("command-1", 1),  # type: ignore[arg-type]
            CommandRequest(" ", "test.action"),
            CommandRequest(" command-1 ", "test.action"),
        )
        for request in requests:
            with self.subTest(request=request):
                result = self.validator.validate(request)

                self.assertEqual(result.code, ErrorCode.INVALID_COMMAND_FORMAT)

    def test_malformed_arguments_return_stable_error(self) -> None:
        wrong_shape = self.validator.validate(
            CommandRequest("command-1", "test.action", [])  # type: ignore[arg-type]
        )
        self.assertEqual(wrong_shape.code, ErrorCode.INVALID_COMMAND_FORMAT)
        self.assertEqual(
            wrong_shape.details["field_errors"]["arguments"],
            {"required_kind": "OBJECT", "actual_kind": "ARRAY"},
        )

        requests = (
            CommandRequest("command-2", "test.action", {"amount": {1}}),
            CommandRequest("command-3", "test.action", {"amount": float("nan")}),
        )
        for request in requests:
            with self.subTest(request=request):
                result = self.validator.validate(request)

                self.assertEqual(result.code, ErrorCode.INVALID_ARGUMENTS)
                self.assertEqual(
                    result.details["reason"],
                    "arguments_contains_non_json_value",
                )

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
        self.assertEqual(stale.details["current_state_sequence"], 3)
        self.assertTrue(stale.details["requires_fresh_observation"])
        self.assertEqual(stale.details["retry_expected_state_sequence"], 3)
        self.assertEqual(illegal.code, ErrorCode.ILLEGAL_COMMAND)


class ReplayInterfaceTests(unittest.TestCase):
    def test_event_log_is_append_only_and_ordered(self) -> None:
        log = EventLog()
        log.append(LogEntry(1, LogCategory.SYSTEM, "START"))

        with self.assertRaises(ValueError):
            log.append(LogEntry(1, LogCategory.SYSTEM, "DUPLICATE"))

        self.assertEqual(log.entries()[0].code, "START")

    def test_event_log_snapshots_payload_on_write_and_read(self) -> None:
        payload = {"nested": {"value": 1}}
        log = EventLog()
        log.append(LogEntry(1, LogCategory.SYSTEM, "SNAPSHOT", payload))

        payload["nested"]["value"] = 2
        returned = log.entries()
        returned[0].payload["nested"]["value"] = 3

        self.assertEqual(log.entries()[0].payload["nested"]["value"], 1)

    def test_event_log_rejects_non_json_payload(self) -> None:
        log = EventLog()

        with self.assertRaises(TypeError):
            log.append(
                LogEntry(1, LogCategory.SYSTEM, "INVALID", {"bad": {1, 2}})
            )

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

    def test_replay_snapshots_request_result_feedback_and_logs(self) -> None:
        arguments = {"amount": 1}
        result_data = {"nested": {"value": 2}}
        feedback_data = {"detail": {"value": 3}}
        log_payload = {"event": {"value": 4}}
        request = CommandRequest("command-1", "test.action", arguments)
        result = CommandResult(
            "command-1",
            True,
            ErrorCode.OK,
            feedback=(
                FeedbackItem(FeedbackLevel.INFO, data=feedback_data),
            ),
            data=result_data,
        )
        random = DeterministicRandom(5).snapshot()
        replay = ReplayLog(GameState.initial(random_seed=5))
        replay.append(
            ReplayEntry(
                1,
                request,
                result,
                random,
                random,
                logs=(LogEntry(1, LogCategory.RESULT, "OK", log_payload),),
            )
        )

        arguments["amount"] = 9
        result_data["nested"]["value"] = 9
        feedback_data["detail"]["value"] = 9
        log_payload["event"]["value"] = 9
        returned = replay.entries()
        returned[0].request.arguments["amount"] = 8
        returned[0].result.data["nested"]["value"] = 8
        returned[0].result.feedback[0].data["detail"]["value"] = 8
        returned[0].logs[0].payload["event"]["value"] = 8

        stored = replay.entries()[0]
        self.assertEqual(stored.request.arguments["amount"], 1)
        self.assertEqual(stored.result.data["nested"]["value"], 2)
        self.assertEqual(stored.result.feedback[0].data["detail"]["value"], 3)
        self.assertEqual(stored.logs[0].payload["event"]["value"], 4)


class MachineStartupTests(unittest.TestCase):
    def test_state_command_outputs_json_with_requested_seed(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            exit_code = main(["state", "--seed", "31415"])

        document = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(document["protocol_version"], 1)
        self.assertEqual(document["state"]["random"]["seed"], 31415)
        self.assertEqual(
            document["state"]["trust_panic"], {"panic": 20, "trust": 70}
        )
        self.assertEqual(document["state"]["population"]["population_alive"], 80)
        self.assertEqual(document["state"]["resources"]["coal"], 70)
        self.assertEqual(
            [item["name"] for item in document["available_commands"]],
            [
                "game.confirm_end_day",
                "game.end_day",
                "game.set_furnace",
                "game.assign",
                "game.assign_resource",
                "game.build",
                "game.heat",
                "game.unassign",
                "game.unassign_resource",
                "game.upgrade",
                "game.woodfuel",
                "game.medical_ration",
                "game.memorial",
                "game.overtime",
                "game.set_ration",
                "game.set_worktime",
                "game.sign_law",
                "game.triage",
                "game.cancel_research",
                "game.research",
                "game.set_overload",
                "game.resolve_event",
                "game.resolve_old_city_event",
                "game.sign_oath_order_law",
                "game.staff_oath_order_facility",
                "game.use_oath_order_action",
                "game.end_run",
            ],
        )
        self.assertEqual(document["state"]["events"]["generated_for_day"], 1)
        self.assertIsInstance(document["event_views"], list)
        self.assertEqual(document["promise_views"], [])
        self.assertFalse(document["old_city_view"]["is_unlocked"])
        self.assertFalse(document["oath_order_view"]["page_unlocked"])
        self.assertFalse(document["ending_report_view"]["available"])
        self.assertEqual(len(document["state"]["surface_resource_points"]), 12)


if __name__ == "__main__":
    unittest.main()
