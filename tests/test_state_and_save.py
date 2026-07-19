from __future__ import annotations

import unittest
from copy import deepcopy

from furnace_winter.models import (
    CURRENT_SAVE_DATA_VERSION,
    FINAL_DAY,
    BuildingState,
    DeterministicRandom,
    GameState,
    HardFailType,
    SaveDataError,
    SaveMigrationRegistry,
    TrustPanicState,
    decode_game_state,
    encode_game_state,
    validate_game_state,
)


class GameStateTests(unittest.TestCase):
    def test_all_patch_001_state_models_initialize(self) -> None:
        state = GameState.initial(random_seed=2025)

        self.assertEqual(state.save_data_version, CURRENT_SAVE_DATA_VERSION)
        self.assertEqual(state.random.seed, 2025)
        self.assertEqual(state.calendar.max_day, FINAL_DAY)
        self.assertEqual(state.population.population_total, 0)
        self.assertEqual(state.resources.coal, 0)
        self.assertIsNone(state.trust_panic.trust)
        self.assertIsNone(state.trust_panic.panic)
        self.assertFalse(state.furnace.is_active)
        self.assertEqual(state.buildings, {})
        self.assertEqual(state.laws.signed_law_ids, [])
        self.assertEqual(state.technologies.researched_tech_ids, [])
        self.assertEqual(state.events.active_event_ids, [])
        self.assertEqual(state.promises.active_promise_ids, [])
        self.assertFalse(state.old_city.is_unlocked)
        self.assertFalse(state.final_result.is_finalized)

    def test_mutable_defaults_are_not_shared(self) -> None:
        first = GameState.initial()
        second = GameState.initial()

        first.laws.signed_law_ids.append("law.example")

        self.assertEqual(second.laws.signed_law_ids, [])

    def test_save_data_round_trip(self) -> None:
        state = GameState.initial(random_seed=42)
        random = DeterministicRandom.from_state(state.random)
        random.next_u64()
        state.random = random.snapshot()
        state.trust_panic = TrustPanicState(trust=60, panic=25)
        state.buildings["building-1"] = BuildingState(
            building_id="building-1",
            building_type="example",
            zone="inner_ring",
            slot_size=1,
        )

        restored = decode_game_state(encode_game_state(state))

        self.assertEqual(restored, state)
        restored_random = DeterministicRandom.from_state(restored.random)
        self.assertEqual(random.next_u64(), restored_random.next_u64())

    def test_missing_required_state_sections_are_rejected(self) -> None:
        for section in ("calendar", "population", "resources", "trust_panic"):
            with self.subTest(section=section):
                document = encode_game_state(GameState.initial())
                del document[section]

                with self.assertRaises(SaveDataError):
                    decode_game_state(document)

    def test_missing_required_nested_field_is_rejected(self) -> None:
        document = encode_game_state(GameState.initial())
        del document["population"]["workers"]

        with self.assertRaises(SaveDataError):
            decode_game_state(document)

    def test_invalid_current_day_and_command_sequence_are_rejected(self) -> None:
        invalid_values = (
            ("current_day", "not-a-day"),
            ("command_sequence", "not-a-sequence"),
            ("command_sequence", -1),
        )
        for field_name, value in invalid_values:
            with self.subTest(field_name=field_name, value=value):
                document = encode_game_state(GameState.initial())
                if field_name == "current_day":
                    document["calendar"][field_name] = value
                else:
                    document[field_name] = value

                with self.assertRaises(SaveDataError):
                    decode_game_state(document)

    def test_max_day_is_fixed_and_cannot_be_loaded_from_save(self) -> None:
        for value in (1, 54, 56, 100):
            with self.subTest(value=value):
                document = encode_game_state(GameState.initial())
                document["calendar"]["max_day"] = value

                with self.assertRaises(SaveDataError):
                    decode_game_state(document)

    def test_only_four_official_hard_fail_types_can_be_loaded(self) -> None:
        for hard_fail_type in HardFailType:
            with self.subTest(hard_fail_type=hard_fail_type):
                state = GameState.initial()
                state.final_result.hard_fail_type = hard_fail_type

                restored = decode_game_state(encode_game_state(state))

                self.assertIs(restored.final_result.hard_fail_type, hard_fail_type)

        for invalid in (
            "trust_fail",
            "panic_fail",
            "terminal_fail",
            "collapse_survival",
            "anything_else",
        ):
            with self.subTest(invalid=invalid):
                document = encode_game_state(GameState.initial())
                document["final_result"]["hard_fail_type"] = invalid

                with self.assertRaises(SaveDataError):
                    decode_game_state(document)

    def test_runtime_validator_uses_full_save_boundary_rules(self) -> None:
        valid = GameState.initial()
        validate_game_state(valid)
        invalid_states = []
        for mutate in (
            lambda state: setattr(state.resources, "coal", -1),
            lambda state: setattr(state.trust_panic, "trust", 101),
            lambda state: setattr(state, "command_sequence", -1),
            lambda state: setattr(state, "save_data_version", 999),
            lambda state: setattr(state.resources, "coal", "bad"),
            lambda state: setattr(state.laws, "signed_law_ids", ("law.example",)),
            lambda state: setattr(state.calendar, "max_day", 56),
            lambda state: setattr(state.final_result, "hard_fail_type", "trust_fail"),
        ):
            state = deepcopy(valid)
            mutate(state)
            invalid_states.append(state)

        for state in invalid_states:
            with self.subTest(state=state), self.assertRaises(SaveDataError):
                validate_game_state(state)

    def test_unknown_random_algorithm_is_rejected(self) -> None:
        document = encode_game_state(GameState.initial())
        document["random"]["algorithm"] = "unknown-v1"

        with self.assertRaises(SaveDataError):
            decode_game_state(document)

    def test_trust_and_panic_range_is_validated(self) -> None:
        for value in (-1, 101, True, "50"):
            with self.subTest(value=value):
                with self.assertRaises((TypeError, ValueError)):
                    TrustPanicState(trust=value)  # type: ignore[arg-type]

                document = encode_game_state(GameState.initial())
                document["trust_panic"]["trust"] = value
                with self.assertRaises(SaveDataError):
                    decode_game_state(document)

    def test_future_save_version_is_rejected(self) -> None:
        document = encode_game_state(GameState.initial())
        document["save_data_version"] = CURRENT_SAVE_DATA_VERSION + 1

        with self.assertRaises(SaveDataError):
            decode_game_state(document)

    def test_migration_interface_advances_one_version(self) -> None:
        registry = SaveMigrationRegistry(current_version=1)
        registry.register(
            0,
            lambda document: {**document, "save_data_version": 1, "migrated": True},
        )

        migrated = registry.migrate({"save_data_version": 0})

        self.assertEqual(migrated, {"save_data_version": 1, "migrated": True})


class DeterministicRandomTests(unittest.TestCase):
    def test_same_seed_and_draw_sequence_reproduce(self) -> None:
        first = DeterministicRandom(9981)
        second = DeterministicRandom(9981)

        first_values = [first.randint(1, 100), first.random(), first.next_u64()]
        second_values = [second.randint(1, 100), second.random(), second.next_u64()]

        self.assertEqual(first_values, second_values)
        self.assertEqual(first.snapshot(), second.snapshot())

    def test_saved_random_state_continues_exactly(self) -> None:
        original = DeterministicRandom(7)
        original.next_u64()
        snapshot = original.snapshot()

        restored = DeterministicRandom.from_state(snapshot)

        self.assertEqual(original.next_u64(), restored.next_u64())
        self.assertEqual(original.snapshot(), restored.snapshot())

    def test_randint_rejects_invalid_bounds(self) -> None:
        random = DeterministicRandom(1)
        for start, stop in ((1.5, 2.5), (True, 2), (1, False)):
            with self.subTest(start=start, stop=stop), self.assertRaises(TypeError):
                random.randint(start, stop)  # type: ignore[arg-type]

        with self.assertRaises(ValueError):
            random.randint(2, 1)
        with self.assertRaises(ValueError):
            random.randint(0, 1 << 64)

    def test_randint_accepts_full_unsigned_64_bit_interval(self) -> None:
        random = DeterministicRandom(1)

        value = random.randint(0, (1 << 64) - 1)

        self.assertIsInstance(value, int)
        self.assertGreaterEqual(value, 0)
        self.assertLessEqual(value, (1 << 64) - 1)


if __name__ == "__main__":
    unittest.main()
