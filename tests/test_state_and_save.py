from __future__ import annotations

import unittest

from furnace_winter.models import (
    CURRENT_SAVE_DATA_VERSION,
    BuildingState,
    DeterministicRandom,
    GameState,
    SaveDataError,
    SaveMigrationRegistry,
    decode_game_state,
    encode_game_state,
)


class GameStateTests(unittest.TestCase):
    def test_all_patch_001_state_models_initialize(self) -> None:
        state = GameState.initial(random_seed=2025)

        self.assertEqual(state.save_data_version, CURRENT_SAVE_DATA_VERSION)
        self.assertEqual(state.random.seed, 2025)
        self.assertEqual(state.calendar.max_day, 55)
        self.assertEqual(state.population.population_total, 0)
        self.assertEqual(state.resources.coal, 0)
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


if __name__ == "__main__":
    unittest.main()
