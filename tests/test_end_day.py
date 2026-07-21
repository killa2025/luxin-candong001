from __future__ import annotations

import unittest
from copy import deepcopy

from furnace_winter.gameplay import (
    AUTOSAVE_END_DAY_SLOT,
    CONFIRM_END_DAY_COMMAND,
    END_DAY_COMMAND,
    EndDayContext,
    EndDayEngine,
    EndDayExecution,
    EndDayStage,
    RiskWarning,
    RiskWarningLevel,
)
from furnace_winter.interface import (
    CommandRequest,
    ErrorCode,
    ReplayEntry,
    ReplayLog,
)
from furnace_winter.models import GameState, HardFailType, encode_game_state


def request(name: str, command_id: str = "command-1") -> CommandRequest:
    return CommandRequest(command_id, name)


def confirmation_request(
    preview: EndDayExecution,
    command_id: str = "confirm",
) -> CommandRequest:
    confirmation = preview.result.data["confirmation"]
    return CommandRequest(
        command_id,
        CONFIRM_END_DAY_COMMAND,
        arguments=confirmation,
        expected_state_sequence=confirmation["state_sequence"],
    )


def fabricated_confirmation(command_id: str = "confirm") -> CommandRequest:
    return CommandRequest(
        command_id,
        CONFIRM_END_DAY_COMMAND,
        arguments={
            "confirmation_token": "not-issued",
            "state_sequence": 0,
            "warning_signature": "not-issued",
        },
    )


class EndDayWarningTests(unittest.TestCase):
    def test_malformed_request_returns_stable_error(self) -> None:
        state = GameState.initial()

        execution = EndDayEngine().execute(state, object())  # type: ignore[arg-type]

        self.assertEqual(execution.result.code, ErrorCode.INVALID_COMMAND_FORMAT)
        self.assertEqual(execution.result.command_id, "")
        self.assertEqual(state.command_sequence, 0)

    def test_strong_warning_requires_explicit_confirmation(self) -> None:
        state = GameState.initial(random_seed=7)
        before = encode_game_state(state)
        engine = EndDayEngine()
        engine.register_risk_evaluator(
            lambda _state: (
                RiskWarning("risk.fuel", RiskWarningLevel.B_STRONG, {"shortfall": 5}),
            )
        )

        preview = engine.execute(state, request(END_DAY_COMMAND, "preview"))

        self.assertEqual(preview.result.code, ErrorCode.END_DAY_CONFIRMATION_REQUIRED)
        self.assertFalse(preview.result.state_changed)
        self.assertEqual(encode_game_state(state), before)
        self.assertIsNone(engine.last_autosave())

        confirmed = engine.execute(
            state,
            confirmation_request(preview),
        )

        self.assertEqual(confirmed.result.code, ErrorCode.OK)
        self.assertEqual(state.calendar.current_day, 2)

    def test_hard_block_rejects_preview_and_confirmation(self) -> None:
        state = GameState.initial()
        engine = EndDayEngine()
        engine.register_risk_evaluator(
            lambda _state: (
                RiskWarning("event.major_pending", RiskWarningLevel.C_HARD_BLOCK),
            )
        )

        preview = engine.execute(state, request(END_DAY_COMMAND, "command-0"))
        confirmed = engine.execute(state, fabricated_confirmation("command-1"))

        for result in (preview, confirmed):
            self.assertEqual(result.result.code, ErrorCode.END_DAY_BLOCKED)
            self.assertFalse(result.result.state_changed)

        self.assertEqual(state.calendar.current_day, 1)
        self.assertEqual(state.command_sequence, 0)
        self.assertIsNone(engine.last_autosave())

    def test_confirmation_without_preview_is_rejected(self) -> None:
        state = GameState.initial()
        engine = EndDayEngine()
        engine.register_risk_evaluator(
            lambda _state: (RiskWarning("risk.fuel", RiskWarningLevel.B_STRONG),)
        )

        execution = engine.execute(state, fabricated_confirmation())

        self.assertEqual(execution.result.code, ErrorCode.ILLEGAL_COMMAND)
        self.assertEqual(execution.result.data["reason"], "end_day_preview_required")
        self.assertEqual(state.calendar.current_day, 1)

    def test_confirmation_is_invalid_after_state_sequence_changes(self) -> None:
        state = GameState.initial()
        engine = EndDayEngine()
        engine.register_risk_evaluator(
            lambda _state: (RiskWarning("risk.fuel", RiskWarningLevel.B_STRONG),)
        )
        preview = engine.execute(state, request(END_DAY_COMMAND, "preview"))
        state.command_sequence += 1

        execution = engine.execute(state, confirmation_request(preview))

        self.assertEqual(execution.result.code, ErrorCode.STALE_STATE)
        self.assertEqual(state.calendar.current_day, 1)

    def test_confirmation_is_invalid_after_unsequenced_state_changes(self) -> None:
        state = GameState.initial()
        engine = EndDayEngine()
        engine.register_risk_evaluator(
            lambda _state: (RiskWarning("risk.fuel", RiskWarningLevel.B_STRONG),)
        )
        preview = engine.execute(state, request(END_DAY_COMMAND, "preview"))
        state.resources.coal = 1

        execution = engine.execute(state, confirmation_request(preview))

        self.assertEqual(execution.result.code, ErrorCode.STALE_STATE)
        self.assertEqual(state.calendar.current_day, 1)

    def test_confirmation_is_invalid_after_warning_changes(self) -> None:
        for changed_warning in (
            RiskWarning("risk.food", RiskWarningLevel.B_STRONG),
            RiskWarning("risk.fuel", RiskWarningLevel.A_INFO),
        ):
            with self.subTest(changed_warning=changed_warning):
                state = GameState.initial()
                current = [RiskWarning("risk.fuel", RiskWarningLevel.B_STRONG)]
                engine = EndDayEngine()
                engine.register_risk_evaluator(lambda _state: tuple(current))
                preview = engine.execute(state, request(END_DAY_COMMAND, "preview"))
                current[:] = [changed_warning]

                execution = engine.execute(state, confirmation_request(preview))

                self.assertEqual(execution.result.code, ErrorCode.STALE_STATE)
                self.assertEqual(state.calendar.current_day, 1)

    def test_confirmation_rejects_altered_token(self) -> None:
        state = GameState.initial()
        engine = EndDayEngine()
        engine.register_risk_evaluator(
            lambda _state: (RiskWarning("risk.fuel", RiskWarningLevel.B_STRONG),)
        )
        preview = engine.execute(state, request(END_DAY_COMMAND, "preview"))
        arguments = dict(preview.result.data["confirmation"])
        arguments["confirmation_token"] = "altered"

        execution = engine.execute(
            state,
            CommandRequest(
                "confirm",
                CONFIRM_END_DAY_COMMAND,
                arguments=arguments,
            ),
        )

        self.assertEqual(execution.result.code, ErrorCode.STALE_STATE)
        self.assertEqual(state.calendar.current_day, 1)

    def test_locked_recheck_hard_block_rolls_back(self) -> None:
        state = GameState.initial(random_seed=19)
        before = encode_game_state(state)
        calls = 0
        engine = EndDayEngine()

        def evaluator(_state: GameState) -> tuple[RiskWarning, ...]:
            nonlocal calls
            calls += 1
            if calls >= 3:
                return (
                    RiskWarning("event.major_pending", RiskWarningLevel.C_HARD_BLOCK),
                )
            return (RiskWarning("risk.fuel", RiskWarningLevel.B_STRONG),)

        engine.register_risk_evaluator(evaluator)
        preview = engine.execute(state, request(END_DAY_COMMAND, "preview"))

        execution = engine.execute(state, confirmation_request(preview))

        self.assertEqual(execution.result.code, ErrorCode.END_DAY_BLOCKED)
        self.assertEqual(
            execution.result.data["failed_stage"],
            EndDayStage.VALIDATE_HARD_BLOCKS.value,
        )
        self.assertEqual(encode_game_state(state), before)
        self.assertIsNone(engine.last_autosave())

    def test_information_warning_does_not_require_confirmation(self) -> None:
        state = GameState.initial()
        engine = EndDayEngine()
        engine.register_risk_evaluator(
            lambda _state: (
                RiskWarning("risk.unassigned_workers", RiskWarningLevel.A_INFO),
            )
        )

        execution = engine.execute(state, request(END_DAY_COMMAND))

        self.assertEqual(execution.result.code, ErrorCode.OK)
        self.assertEqual(state.calendar.current_day, 2)

    def test_warning_evaluator_cannot_mutate_live_state(self) -> None:
        state = GameState.initial()
        engine = EndDayEngine()

        def evaluator(snapshot: GameState) -> tuple[RiskWarning, ...]:
            snapshot.resources.coal = 999
            return (RiskWarning("risk.info", RiskWarningLevel.A_INFO),)

        engine.register_risk_evaluator(evaluator)
        engine.execute(state, request(END_DAY_COMMAND))

        self.assertEqual(state.resources.coal, 0)


class EndDaySettlementTests(unittest.TestCase):
    def test_invalid_handler_state_rolls_back_before_autosave_sink(self) -> None:
        mutators = (
            lambda state: setattr(state.resources, "coal", -7),
            lambda state: setattr(state.trust_panic, "trust", 101),
            lambda state: setattr(state, "command_sequence", -1),
            lambda state: setattr(state, "save_data_version", 999),
            lambda state: setattr(state.resources, "coal", "bad"),
            lambda state: setattr(state.laws, "signed_law_ids", ("law.example",)),
            lambda state: setattr(state.calendar, "current_day", 3),
            lambda state: setattr(state.calendar, "max_day", 56),
            lambda state: setattr(state.final_result, "hard_fail_type", "trust_fail"),
        )
        for mutator in mutators:
            with self.subTest(mutator=mutator):
                sink_records: list[object] = []
                state = GameState.initial(random_seed=31)
                engine = EndDayEngine(autosave_sink=sink_records.append)
                first = engine.execute(state, request(END_DAY_COMMAND, "day-1"))
                self.assertEqual(first.result.code, ErrorCode.OK)
                before = deepcopy(state)
                previous_autosave = engine.last_autosave()
                engine.register_stage_handler(
                    EndDayStage.RESOLVE_COLLECTION_AND_PRODUCTION,
                    lambda context, mutator=mutator: mutator(context.state),
                )

                execution = engine.execute(state, request(END_DAY_COMMAND, "day-2"))

                self.assertEqual(execution.result.code, ErrorCode.INTERNAL_ERROR)
                self.assertEqual(state, before)
                self.assertEqual(execution.random_before, execution.random_after)
                self.assertEqual(engine.last_autosave(), previous_autosave)
                self.assertEqual(len(sink_records), 1)

    def test_invalid_input_state_is_rejected_before_settlement(self) -> None:
        state = GameState.initial(random_seed=8)
        state.resources.coal = -1
        before = deepcopy(state)
        sink_records: list[object] = []
        engine = EndDayEngine(autosave_sink=sink_records.append)

        execution = engine.execute(state, request(END_DAY_COMMAND))

        self.assertEqual(execution.result.code, ErrorCode.INTERNAL_ERROR)
        self.assertEqual(execution.result.data["failed_stage"], "input_state_validation")
        self.assertEqual(state, before)
        self.assertEqual(execution.random_before, execution.random_after)
        self.assertEqual(sink_records, [])

    def test_stages_run_in_fixed_order_and_advance_exactly_one_day(self) -> None:
        state = GameState.initial()
        engine = EndDayEngine()
        visited: list[EndDayStage] = []
        configurable_stages = (
            stage
            for stage in EndDayStage
            if stage
            not in {
                EndDayStage.LOCK_INPUT,
                EndDayStage.VALIDATE_HARD_BLOCKS,
                EndDayStage.WRITE_AUTOSAVE,
                EndDayStage.ADVANCE_DAY,
            }
        )
        for stage in configurable_stages:
            engine.register_stage_handler(
                stage,
                lambda context, stage=stage: visited.append(stage),
            )

        execution = engine.execute(state, request(END_DAY_COMMAND))

        self.assertEqual(
            visited,
            [
                stage
                for stage in EndDayStage
                if stage
                not in {
                    EndDayStage.LOCK_INPUT,
                    EndDayStage.VALIDATE_HARD_BLOCKS,
                    EndDayStage.WRITE_AUTOSAVE,
                    EndDayStage.ADVANCE_DAY,
                }
            ],
        )
        self.assertEqual(
            [entry.code for entry in execution.logs if ".stage." in entry.code],
            [f"end_day.stage.{stage.value}" for stage in EndDayStage],
        )
        self.assertEqual(state.calendar.current_day, 2)
        self.assertFalse(state.calendar.is_day_locked)
        self.assertFalse(state.calendar.is_end_day_confirmed)
        self.assertEqual(state.command_sequence, 1)

    def test_autosave_is_after_cleanup_and_before_day_advance(self) -> None:
        state = GameState.initial()
        engine = EndDayEngine()

        def cleanup(context: EndDayContext) -> None:
            context.state.buildings.clear()
            context.state.resources.wood = 12

        engine.register_stage_handler(EndDayStage.CLOSE_DAILY_EFFECTS, cleanup)

        execution = engine.execute(state, request(END_DAY_COMMAND))

        self.assertIsNotNone(execution.autosave)
        assert execution.autosave is not None
        self.assertEqual(execution.autosave.slot, AUTOSAVE_END_DAY_SLOT)
        self.assertEqual(execution.autosave.settled_day, 1)
        self.assertEqual(execution.autosave.state["calendar"]["current_day"], 1)
        self.assertTrue(execution.autosave.state["calendar"]["is_day_locked"])
        self.assertEqual(execution.autosave.state["resources"]["wood"], 12)
        self.assertEqual(execution.autosave.state["command_sequence"], 1)
        self.assertEqual(execution.autosave.resume_stage, EndDayStage.ADVANCE_DAY.value)
        self.assertEqual(state.calendar.current_day, 2)

    def test_handler_abort_rolls_back_state_random_and_autosave(self) -> None:
        state = GameState.initial(random_seed=123)
        before = encode_game_state(state)
        engine = EndDayEngine()

        def abort(context: EndDayContext) -> None:
            context.state.resources.coal = 50
            context.random.next_u64()
            context.abort(details={"reason": "test"})

        engine.register_stage_handler(EndDayStage.RESOLVE_FOOD_CHAIN, abort)

        execution = engine.execute(state, request(END_DAY_COMMAND))

        self.assertEqual(execution.result.code, ErrorCode.END_DAY_BLOCKED)
        self.assertEqual(encode_game_state(state), before)
        self.assertEqual(execution.random_before, execution.random_after)
        self.assertIsNone(engine.last_autosave())

    def test_sink_failure_rolls_back_entire_settlement(self) -> None:
        def failing_sink(_record: object) -> None:
            raise OSError("test sink failure")

        state = GameState.initial(random_seed=9)
        before = encode_game_state(state)
        engine = EndDayEngine(autosave_sink=failing_sink)
        engine.register_stage_handler(
            EndDayStage.RESOLVE_COLLECTION_AND_PRODUCTION,
            lambda context: setattr(context.state.resources, "coal", 10),
        )

        execution = engine.execute(state, request(END_DAY_COMMAND))

        self.assertEqual(execution.result.code, ErrorCode.INTERNAL_ERROR)
        self.assertEqual(execution.result.data["failed_stage"], "write_autosave")
        self.assertEqual(encode_game_state(state), before)
        self.assertIsNone(engine.last_autosave())

    def test_final_state_validator_runs_before_autosave_sink(self) -> None:
        state = GameState.initial(random_seed=10)
        before = encode_game_state(state)
        autosaves: list[object] = []
        validated_days: list[int] = []
        engine = EndDayEngine(autosave_sink=autosaves.append)

        def reject_advanced_day(candidate: GameState) -> None:
            validated_days.append(candidate.calendar.current_day)
            if candidate.calendar.current_day == 2:
                raise ValueError("final state rejected")

        engine.register_state_validator(reject_advanced_day)
        execution = engine.execute(state, request(END_DAY_COMMAND))

        self.assertEqual(execution.result.code, ErrorCode.INTERNAL_ERROR)
        self.assertEqual(
            execution.result.data["failed_stage"], "commit_state_validation"
        )
        self.assertEqual(validated_days, [1, 1, 2])
        self.assertEqual(autosaves, [])
        self.assertEqual(encode_game_state(state), before)
        self.assertIsNone(engine.last_autosave())

    def test_same_seed_state_and_handlers_are_reproducible(self) -> None:
        def make_engine() -> EndDayEngine:
            engine = EndDayEngine()

            def draw(context: EndDayContext) -> None:
                value = context.random.randint(1, 100)
                context.state.resources.coal = value
                context.emit("end_day.test.random", {"value": value})

            engine.register_stage_handler(EndDayStage.RESOLVE_COLLECTION_AND_PRODUCTION, draw)
            return engine

        first_state = GameState.initial(random_seed=2025)
        second_state = deepcopy(first_state)

        first = make_engine().execute(first_state, request(END_DAY_COMMAND))
        second = make_engine().execute(second_state, request(END_DAY_COMMAND))

        self.assertEqual(encode_game_state(first_state), encode_game_state(second_state))
        self.assertEqual(first.logs, second.logs)
        self.assertEqual(first.random_after, second.random_after)

    def test_day_55_stops_at_final_settlement_boundary(self) -> None:
        state = GameState.initial()
        state.calendar.current_day = state.calendar.max_day

        execution = EndDayEngine().execute(state, request(END_DAY_COMMAND))

        self.assertEqual(execution.result.data["transition"], "final_settlement")
        self.assertEqual(state.calendar.current_day, 55)
        self.assertTrue(state.calendar.is_day_locked)
        self.assertTrue(state.calendar.is_end_day_confirmed)
        self.assertFalse(state.final_result.is_finalized)
        assert execution.autosave is not None
        self.assertEqual(execution.autosave.resume_stage, "final_settlement")

    def test_exactly_55_days_settle_and_day_56_is_rejected(self) -> None:
        state = GameState.initial(random_seed=55)
        sink_records: list[object] = []
        engine = EndDayEngine(autosave_sink=sink_records.append)

        for settled_day in range(1, 56):
            execution = engine.execute(
                state,
                request(END_DAY_COMMAND, f"day-{settled_day}"),
            )
            self.assertEqual(execution.result.code, ErrorCode.OK)
            self.assertEqual(execution.result.data["settled_day"], settled_day)

        self.assertEqual(state.calendar.current_day, 55)
        self.assertTrue(state.calendar.is_day_locked)
        self.assertEqual(len(sink_records), 55)
        previous_autosave = engine.last_autosave()

        rejected = engine.execute(state, request(END_DAY_COMMAND, "day-56"))

        self.assertEqual(rejected.result.code, ErrorCode.ILLEGAL_COMMAND)
        self.assertFalse(rejected.result.state_changed)
        self.assertEqual(len(sink_records), 55)
        self.assertEqual(engine.last_autosave(), previous_autosave)

    def test_two_full_55_day_runs_are_deterministic(self) -> None:
        def run() -> tuple[dict[str, object], list[object]]:
            state = GameState.initial(random_seed=2025)
            engine = EndDayEngine()
            boundaries: list[object] = []
            for settled_day in range(1, 56):
                execution = engine.execute(
                    state,
                    request(END_DAY_COMMAND, f"day-{settled_day}"),
                )
                boundaries.append(
                    (
                        execution.random_before,
                        execution.random_after,
                        execution.logs,
                    )
                )
            return encode_game_state(state), boundaries

        first_state, first_boundaries = run()
        second_state, second_boundaries = run()

        self.assertEqual(first_state, second_state)
        self.assertEqual(first_boundaries, second_boundaries)

    def test_all_official_hard_fail_types_can_cross_commit_boundary(self) -> None:
        for hard_fail_type in HardFailType:
            with self.subTest(hard_fail_type=hard_fail_type):
                state = GameState.initial()
                engine = EndDayEngine()
                engine.register_stage_handler(
                    EndDayStage.CHECK_HARD_FAILS,
                    lambda context, hard_fail_type=hard_fail_type: setattr(
                        context.state.final_result,
                        "hard_fail_type",
                        hard_fail_type,
                    ),
                )

                execution = engine.execute(state, request(END_DAY_COMMAND))

                self.assertEqual(execution.result.code, ErrorCode.OK)
                self.assertIs(state.final_result.hard_fail_type, hard_fail_type)

    def test_hard_fail_is_saved_and_does_not_advance(self) -> None:
        state = GameState.initial()
        engine = EndDayEngine()
        engine.register_stage_handler(
            EndDayStage.CHECK_HARD_FAILS,
            lambda context: setattr(
                context.state.final_result,
                "hard_fail_type",
                HardFailType.POPULATION_ZERO,
            ),
        )

        execution = engine.execute(state, request(END_DAY_COMMAND))

        self.assertEqual(execution.result.code, ErrorCode.OK)
        self.assertEqual(execution.result.data["transition"], "hard_fail")
        self.assertEqual(state.calendar.current_day, 1)
        self.assertTrue(state.calendar.is_day_locked)
        assert execution.autosave is not None
        self.assertEqual(execution.autosave.resume_stage, "terminal_state")
        self.assertEqual(
            execution.autosave.state["final_result"]["hard_fail_type"],
            "population_zero",
        )

    def test_execution_can_be_recorded_by_patch_001_replay(self) -> None:
        state = GameState.initial(random_seed=11)
        initial = deepcopy(state)
        command = request(END_DAY_COMMAND)
        execution = EndDayEngine().execute(state, command)
        replay = ReplayLog(initial)

        replay.append(
            ReplayEntry(
                sequence=1,
                request=command,
                result=execution.result,
                random_before=execution.random_before,
                random_after=execution.random_after,
                logs=execution.logs,
            )
        )

        stored = replay.entries()[0]
        self.assertEqual(stored.result.code, ErrorCode.OK)
        self.assertEqual(stored.random_after, state.random)
        self.assertEqual(len(stored.logs), len(tuple(EndDayStage)))


if __name__ == "__main__":
    unittest.main()
