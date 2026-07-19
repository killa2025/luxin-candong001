from __future__ import annotations

import unittest
from pathlib import Path

from furnace_winter.config import load_building_rules, load_survival_rules
from furnace_winter.gameplay import (
    ASSIGN_COMMAND,
    BUILD_COMMAND,
    END_DAY_COMMAND,
    HEAT_COMMAND,
    UNASSIGN_COMMAND,
    UPGRADE_COMMAND,
    WOODFUEL_COMMAND,
    BuildingSystem,
    EndDayEngine,
    SurvivalSystem,
    create_initial_survival_state,
)
from furnace_winter.interface import CommandRequest, ErrorCode
from furnace_winter.models import decode_game_state, encode_game_state


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class BuildingPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.survival_rules = load_survival_rules(REPOSITORY_ROOT / "data" / "survival.json")
        cls.building_rules = load_building_rules(REPOSITORY_ROOT / "data" / "buildings.json")

    def make_state(self):
        return create_initial_survival_state(self.survival_rules, random_seed=4004)

    def make_system(self) -> BuildingSystem:
        return BuildingSystem(self.building_rules, self.survival_rules)

    def make_engine(self) -> EndDayEngine:
        engine = EndDayEngine()
        SurvivalSystem(self.survival_rules, self.building_rules).install(engine)
        self.make_system().install(engine)
        return engine

    def execute(self, state, name: str, arguments: dict, command_id: str = "command"):
        return self.make_system().execute(
            state,
            CommandRequest(
                command_id,
                name,
                arguments,
                expected_state_sequence=state.command_sequence,
            ),
        )

    def test_four_prebuilt_residences_are_independent_and_use_inner_slots(self) -> None:
        state = self.make_state()

        self.assertEqual(
            sorted(state.buildings),
            [f"residence-start-{index:03d}" for index in range(1, 5)],
        )
        self.assertTrue(all(item.zone == "inner_ring" for item in state.buildings.values()))
        self.assertTrue(all(item.slot_size == 1 for item in state.buildings.values()))
        self.assertEqual(state.building_management.zone_slots_used["inner_ring"], 4)
        self.assertEqual(state.building_management.zone_slot_capacity["inner_ring"], 18)

    def test_manual_build_deducts_cost_uses_slots_and_unlocks_second_hunting_area(self) -> None:
        state = self.make_state()

        first = self.execute(
            state,
            BUILD_COMMAND,
            {"building_type": "hunting_lodge", "zone": "outer_ring"},
            "build-1",
        )
        second = self.execute(
            state,
            BUILD_COMMAND,
            {"building_type": "hunting_lodge", "zone": "outer_ring"},
            "build-2",
        )
        third = self.execute(
            state,
            BUILD_COMMAND,
            {"building_type": "hunting_lodge", "zone": "outer_ring"},
            "build-3",
        )

        self.assertTrue(first.accepted)
        self.assertTrue(first.data["second_hunting_area_unlocked"])
        self.assertEqual(state.building_management.available_hunting_areas, 2)
        self.assertTrue(second.accepted)
        self.assertEqual(state.building_management.zone_slots_used["outer_ring"], 4)
        self.assertEqual((state.resources.wood, state.resources.steel), (50, 25))
        self.assertEqual(third.code, ErrorCode.ILLEGAL_COMMAND)
        self.assertEqual(third.data["reason"], "building_limit_reached")

    def test_manual_build_excludes_auto_enabled_law_structures(self) -> None:
        state = self.make_state()
        build_spec = next(
            item for item in self.make_system().command_specs() if item.name == BUILD_COMMAND
        )
        advertised_types = build_spec.argument_options["building_type"]

        for building_type in ("guardian_hall", "patrol_office", "firepit_gathering"):
            with self.subTest(building_type=building_type):
                self.assertNotIn(building_type, advertised_types)
                result = self.execute(
                    state,
                    BUILD_COMMAND,
                    {"building_type": building_type, "zone": "inner_ring"},
                )
                self.assertEqual(result.code, ErrorCode.INVALID_ARGUMENTS)
                self.assertEqual(result.data["reason"], "unknown_building_type")

    def test_law_and_tech_prerequisites_are_checked_without_auto_building(self) -> None:
        state = self.make_state()
        blocked = self.execute(
            state,
            BUILD_COMMAND,
            {"building_type": "medical_station", "zone": "inner_ring"},
        )
        state.laws.signed_law_ids.append("basic_medical_law")
        built = self.execute(
            state,
            BUILD_COMMAND,
            {"building_type": "medical_station", "zone": "inner_ring"},
        )

        self.assertEqual(blocked.data["reason"], "prerequisite_missing")
        self.assertTrue(built.accepted)
        self.assertEqual(sum(item.building_type == "medical_station" for item in state.buildings.values()), 1)

    def test_binding_is_required_and_unique_for_resource_anchor_buildings(self) -> None:
        state = self.make_state()
        state.technologies.researched_tech_ids.append("tech_wood_processing_1")

        missing = self.execute(
            state,
            BUILD_COMMAND,
            {"building_type": "logging_camp", "zone": "outer_ring"},
        )
        first = self.execute(
            state,
            BUILD_COMMAND,
            {
                "building_type": "logging_camp",
                "zone": "outer_ring",
                "binding_id": "forest-zone-1",
            },
        )
        duplicate = self.execute(
            state,
            BUILD_COMMAND,
            {
                "building_type": "logging_camp",
                "zone": "outer_ring",
                "binding_id": "forest-zone-1",
            },
        )

        self.assertEqual(missing.data["reason"], "invalid_resource_binding")
        self.assertTrue(first.accepted)
        self.assertEqual(duplicate.data["reason"], "resource_anchor_already_bound")

    def test_assignment_sets_target_count_and_enforces_role_capacity(self) -> None:
        state = self.make_state()
        built = self.execute(
            state,
            BUILD_COMMAND,
            {"building_type": "canteen", "zone": "inner_ring"},
        )
        building_id = built.data["building_id"]
        assigned = self.execute(
            state,
            ASSIGN_COMMAND,
            {"building_id": building_id, "population_type": "workers", "count": 5},
        )
        reset = self.execute(
            state,
            ASSIGN_COMMAND,
            {"building_id": building_id, "population_type": "workers", "count": 2},
        )
        partially_unassigned = self.execute(
            state,
            UNASSIGN_COMMAND,
            {"building_id": building_id, "population_type": "workers", "count": 1},
        )
        invalid = self.execute(
            state,
            ASSIGN_COMMAND,
            {"building_id": building_id, "population_type": "engineers", "count": 1},
        )

        self.assertTrue(assigned.accepted)
        self.assertTrue(reset.accepted)
        self.assertTrue(partially_unassigned.accepted)
        self.assertEqual(state.buildings[building_id].assigned_workers, 1)
        self.assertEqual(invalid.data["reason"], "population_type_not_allowed")

    def test_upgrade_is_immediate_and_applies_to_one_prebuilt_residence(self) -> None:
        state = self.make_state()
        state.technologies.researched_tech_ids.append("tech_improved_housing_standard")

        result = self.execute(
            state,
            UPGRADE_COMMAND,
            {
                "building_id": "residence-start-001",
                "upgrade_id": "basic_to_improved_residence",
            },
        )

        self.assertTrue(result.accepted)
        self.assertTrue(result.data["instant"])
        self.assertEqual(state.buildings["residence-start-001"].building_type, "improved_residence")
        self.assertEqual(state.housing.capacity, 45)
        self.assertEqual(state.housing.basic_residences, 3)
        self.assertEqual(state.building_management.zone_slots_used["inner_ring"], 4)
        self.assertEqual((state.resources.wood, state.resources.steel), (85, 30))

    def test_heat_costs_coal_once_and_is_closed_after_end_day(self) -> None:
        state = self.make_state()
        built = self.execute(
            state,
            BUILD_COMMAND,
            {"building_type": "canteen", "zone": "inner_ring"},
        )
        building_id = built.data["building_id"]
        heated = self.execute(state, HEAT_COMMAND, {"building_id": building_id})
        repeated = self.execute(state, HEAT_COMMAND, {"building_id": building_id})

        self.assertTrue(heated.accepted)
        self.assertEqual(state.resources.coal, 50)
        self.assertEqual(repeated.data["reason"], "building_already_heated_today")

        execution = self.make_engine().execute(state, CommandRequest("end", END_DAY_COMMAND))
        self.assertTrue(execution.result.accepted)
        self.assertEqual(state.buildings[building_id].effective_temperature, 29)
        self.assertFalse(state.buildings[building_id].heated_today)

    def test_same_day_hunting_and_canteen_production_precedes_food_consumption(self) -> None:
        state = self.make_state()
        lodge = self.execute(
            state,
            BUILD_COMMAND,
            {"building_type": "hunting_lodge", "zone": "outer_ring"},
        )
        canteen = self.execute(
            state,
            BUILD_COMMAND,
            {"building_type": "canteen", "zone": "inner_ring"},
        )
        self.execute(
            state,
            ASSIGN_COMMAND,
            {"building_id": lodge.data["building_id"], "population_type": "workers", "count": 15},
        )
        self.execute(
            state,
            ASSIGN_COMMAND,
            {"building_id": canteen.data["building_id"], "population_type": "workers", "count": 5},
        )

        execution = self.make_engine().execute(state, CommandRequest("end", END_DAY_COMMAND))

        self.assertTrue(execution.result.accepted)
        self.assertEqual(state.resources.raw_food, 20)
        self.assertEqual(state.resources.cooked_food, 200)
        self.assertLess(
            [item.code for item in execution.logs].index("buildings.production.settled"),
            [item.code for item in execution.logs].index("survival.food.settled"),
        )

    def test_woodfuel_is_manual_day_only_and_only_fills_base_heating_gap(self) -> None:
        state = self.make_state()
        state.furnace.mode_id = "level_2"
        state.furnace.is_active = True
        confirmed = self.execute(state, WOODFUEL_COMMAND, {"confirm": True})

        execution = self.make_engine().execute(state, CommandRequest("end", END_DAY_COMMAND))

        self.assertTrue(confirmed.accepted)
        self.assertTrue(execution.result.accepted)
        self.assertEqual(state.daily_survival.effective_furnace_level, 2)
        self.assertEqual(state.daily_survival.coal_paid, 70)
        self.assertEqual(state.daily_survival.woodfuel_contribution, 15)
        self.assertEqual(state.daily_survival.woodfuel_wood_burned, 60)
        self.assertEqual((state.resources.coal, state.resources.wood), (0, 40))
        self.assertFalse(state.building_management.woodfuel_confirmed_today)

    def test_v2_save_migration_adds_patch_004_fields(self) -> None:
        state = self.make_state()
        legacy = encode_game_state(state)
        legacy["save_data_version"] = 2
        del legacy["building_management"]
        del legacy["daily_survival"]["woodfuel_wood_burned"]
        del legacy["daily_survival"]["woodfuel_contribution"]
        for building in legacy["buildings"].values():
            del building["bound_resource_id"]

        migrated = decode_game_state(legacy)

        self.assertEqual(migrated.save_data_version, 3)
        self.assertEqual(migrated.building_management.zone_slots_used["inner_ring"], 4)
        self.assertEqual(len(migrated.buildings), 4)


if __name__ == "__main__":
    unittest.main()
