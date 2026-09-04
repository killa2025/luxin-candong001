from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from furnace_winter.config import (
    BuildingConfigError,
    load_building_rules,
    load_final_frost_rules,
    load_survival_rules,
    load_technology_rules,
)
from furnace_winter import GameSession
from furnace_winter.gameplay import (
    ASSIGN_COMMAND,
    ASSIGN_RESOURCE_COMMAND,
    BUILD_COMMAND,
    CONFIRM_END_DAY_COMMAND,
    END_DAY_COMMAND,
    HEAT_COMMAND,
    UNASSIGN_COMMAND,
    UNASSIGN_RESOURCE_COMMAND,
    UPGRADE_COMMAND,
    WOODFUEL_COMMAND,
    BuildingSystem,
    EndDayEngine,
    EndDayStage,
    FinalFrostSystem,
    SurvivalSystem,
    create_initial_survival_state,
    is_over_capacity,
    storage_used,
)
from furnace_winter.interface import CommandRequest, ErrorCode
from furnace_winter.models import (
    CURRENT_SAVE_DATA_VERSION,
    EventResolutionRecord,
    SaveDataError,
    decode_game_state,
    encode_game_state,
    to_primitive,
    validate_game_state,
)
from tests import (
    downgrade_to_pre_patch006_schema,
    install_final_frost_history_stub,
    seed_final_frost_history,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class BuildingPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.survival_rules = load_survival_rules(REPOSITORY_ROOT / "data" / "survival.json")
        cls.building_rules = load_building_rules(REPOSITORY_ROOT / "data" / "buildings.json")
        cls.technology_rules = load_technology_rules(
            REPOSITORY_ROOT / "data" / "technologies.json"
        )

    def make_state(self):
        return create_initial_survival_state(
            self.survival_rules, self.building_rules, random_seed=4004
        )

    def make_system(self, *, with_technology_rules: bool = False) -> BuildingSystem:
        return BuildingSystem(
            self.building_rules,
            self.survival_rules,
            self.technology_rules if with_technology_rules else None,
        )

    def make_engine(
        self, autosave_sink=None, *, with_technology_rules: bool = False
    ) -> EndDayEngine:
        engine = EndDayEngine(autosave_sink=autosave_sink)
        technology_rules = (
            self.technology_rules if with_technology_rules else None
        )
        SurvivalSystem(
            self.survival_rules,
            self.building_rules,
            technology_rules,
        ).install(engine)
        self.make_system(
            with_technology_rules=with_technology_rules
        ).install(engine)
        install_final_frost_history_stub(engine)
        return engine

    def make_final_frost_food_state(self, *, insulated: bool = True):
        state = self.make_state()
        state.resources.wood = 200
        state.resources.steel = 100
        completed = [
            "tech_drawing_board",
            "tech_drafting_instrument",
            "tech_mechanical_calculator",
            "tech_greenhouse_cultivation",
        ]
        if insulated:
            completed.extend(
                ["tech_building_insulation_1", "tech_building_insulation_2"]
            )
        state.technologies.researched_tech_ids.extend(completed)
        canteen = self.execute(
            state,
            BUILD_COMMAND,
            {"building_type": "canteen", "zone": "inner_ring"},
            "build-canteen",
        )
        greenhouses = [
            self.execute(
                state,
                BUILD_COMMAND,
                {"building_type": "greenhouse", "zone": "middle_ring"},
                f"build-greenhouse-{index}",
            )
            for index in range(1, 3)
        ]
        self.execute(
            state,
            ASSIGN_COMMAND,
            {
                "building_id": canteen.data["building_id"],
                "population_type": "workers",
                "count": 5,
            },
            "staff-canteen",
        )
        for index, greenhouse in enumerate(greenhouses, start=1):
            self.execute(
                state,
                ASSIGN_COMMAND,
                {
                    "building_id": greenhouse.data["building_id"],
                    "population_type": "workers",
                    "count": 10,
                },
                f"staff-greenhouse-{index}",
            )
        state.calendar.current_day = 50
        seed_final_frost_history(state, through_day=49)
        state.resources.coal = 100
        state.resources.raw_food = 0
        state.resources.cooked_food = 0
        state.daily_survival.storage_used = (
            state.resources.coal
            + state.resources.wood
            + state.resources.steel
        )
        state.daily_survival.is_over_capacity = False
        return state

    def execute(
        self,
        state,
        name: str,
        arguments: dict,
        command_id: str = "command",
        *,
        system: BuildingSystem | None = None,
    ):
        return (system or self.make_system()).execute(
            state,
            CommandRequest(
                command_id,
                name,
                arguments,
                expected_state_sequence=state.command_sequence,
            ),
        )

    @staticmethod
    def confirm(engine, state, preview, command_id: str = "confirm"):
        return engine.execute(
            state,
            CommandRequest(
                command_id,
                CONFIRM_END_DAY_COMMAND,
                preview.result.data["confirmation"],
                expected_state_sequence=state.command_sequence,
            ),
        )

    def settle_day(self, state, engine=None, command_id: str = "end"):
        engine = engine or self.make_engine()
        execution = engine.execute(
            state,
            CommandRequest(
                command_id,
                END_DAY_COMMAND,
                expected_state_sequence=state.command_sequence,
            ),
        )
        if execution.result.code is ErrorCode.END_DAY_CONFIRMATION_REQUIRED:
            execution = self.confirm(engine, state, execution, f"confirm-{command_id}")
        return execution

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
                self.assertEqual(
                    result.data["invalid_options"], ["building_type"]
                )
                self.assertEqual(
                    result.data["allowed_options"]["building_type"],
                    list(advertised_types),
                )

    def test_assignment_specs_disclose_absolute_and_decrement_semantics(self) -> None:
        specs = {item.name: item for item in self.make_system().command_specs()}

        self.assertEqual(
            specs[ASSIGN_COMMAND].argument_semantics["count"],
            "absolute_target_count",
        )
        self.assertEqual(
            specs[ASSIGN_RESOURCE_COMMAND].argument_semantics["count"],
            "absolute_target_count",
        )
        self.assertEqual(
            specs[UNASSIGN_COMMAND].argument_semantics["count"],
            "decrement_count_omitted_clears_all",
        )
        self.assertEqual(
            specs[UNASSIGN_RESOURCE_COMMAND].argument_semantics["count"],
            "decrement_count_omitted_clears_all",
        )

    def test_assignment_errors_separate_unknown_targets_and_population_types(self) -> None:
        state = self.make_state()
        missing_building = self.execute(
            state,
            ASSIGN_COMMAND,
            {
                "building_id": "not-built",
                "population_type": "workers",
                "count": 1,
            },
        )
        invalid_population = self.execute(
            state,
            ASSIGN_COMMAND,
            {
                "building_id": "residence-start-001",
                "population_type": "adult",
                "count": 1,
            },
        )

        self.assertEqual(missing_building.data["reason"], "unknown_building")
        self.assertEqual(
            missing_building.data["submitted_building_id"], "not-built"
        )
        self.assertIn(
            "residence-start-001",
            missing_building.data["available_building_ids"],
        )
        self.assertEqual(
            invalid_population.data["invalid_options"], ["population_type"]
        )
        self.assertEqual(
            invalid_population.data["allowed_options"]["population_type"],
            [
                "workers",
                "engineers",
                "children",
                "medical_apprentices",
                "engineering_apprentices",
            ],
        )

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
            {"building_id": building_id, "population_type": "children", "count": 1},
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

    def test_heat_reserves_furnace_coal_costs_once_and_resets_after_end_day(self) -> None:
        state = self.make_state()
        state.calendar.current_day = 55
        seed_final_frost_history(state)
        state.resources.coal = 105
        state.furnace.mode_id = "level_2"
        state.furnace.is_active = True
        built = self.execute(
            state,
            BUILD_COMMAND,
            {"building_type": "canteen", "zone": "inner_ring"},
        )
        building_id = built.data["building_id"]
        heated = self.execute(state, HEAT_COMMAND, {"building_id": building_id})
        repeated = self.execute(state, HEAT_COMMAND, {"building_id": building_id})

        self.assertTrue(heated.accepted)
        self.assertEqual(state.resources.coal, 85)
        self.assertEqual(heated.data["remaining_city_heat_uses"], 1)
        self.assertEqual(repeated.data["reason"], "building_already_heated_today")

        execution = self.settle_day(state)
        self.assertTrue(execution.result.accepted)
        self.assertEqual(state.daily_survival.effective_furnace_level, 2)
        self.assertEqual(state.buildings[building_id].effective_temperature, -23)
        self.assertFalse(state.buildings[building_id].heated_today)
        self.assertEqual(state.building_management.heat_uses_today, 0)

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

    def test_food_warning_counts_same_day_hunting_and_canteen_output(self) -> None:
        state = self.make_state()
        lodge = self.execute(
            state,
            BUILD_COMMAND,
            {"building_type": "hunting_lodge", "zone": "outer_ring"},
            "build-lodge",
        )
        canteen = self.execute(
            state,
            BUILD_COMMAND,
            {"building_type": "canteen", "zone": "inner_ring"},
            "build-canteen",
        )
        self.execute(
            state,
            ASSIGN_COMMAND,
            {
                "building_id": lodge.data["building_id"],
                "population_type": "workers",
                "count": 15,
            },
            "staff-lodge",
        )
        self.execute(
            state,
            ASSIGN_COMMAND,
            {
                "building_id": canteen.data["building_id"],
                "population_type": "workers",
                "count": 5,
            },
            "staff-canteen",
        )
        state.resources.raw_food = 0
        state.resources.cooked_food = 0
        state.daily_survival.storage_used = (
            state.resources.coal + state.resources.wood + state.resources.steel
        )
        before = deepcopy(state)

        projection = self.make_system(
            with_technology_rules=True
        ).project_food_inventory(state)
        warnings = SurvivalSystem(
            self.survival_rules,
            self.building_rules,
            self.technology_rules,
        ).evaluate_risks(state)
        self.assertEqual(state, before)
        execution = self.make_engine(with_technology_rules=True).execute(
            state, CommandRequest("end", END_DAY_COMMAND)
        )

        self.assertNotIn(
            "survival.food_shortfall",
            {warning.warning_id for warning in warnings},
        )
        self.assertEqual(projection["available_food"], 80)
        self.assertEqual(projection["raw_food_produced"], 40)
        self.assertEqual(projection["raw_food_processed"], 40)
        self.assertEqual(projection["cooked_food_produced"], 80)
        self.assertTrue(execution.result.accepted)
        self.assertEqual(state.daily_survival.food_shortfall, 0)
        self.assertEqual(state.daily_survival.unfed_population, 0)

    def test_full_or_over_capacity_blocks_all_ordinary_production(self) -> None:
        for coal in (400, 401):
            with self.subTest(storage_used=coal + 400):
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
                    {
                        "building_id": lodge.data["building_id"],
                        "population_type": "workers",
                        "count": 15,
                    },
                )
                self.execute(
                    state,
                    ASSIGN_COMMAND,
                    {
                        "building_id": canteen.data["building_id"],
                        "population_type": "workers",
                        "count": 5,
                    },
                )
                point_id = "surface-coal-2"
                self.execute(
                    state,
                    ASSIGN_RESOURCE_COMMAND,
                    {
                        "resource_point_id": point_id,
                        "population_type": "workers",
                        "count": 1,
                    },
                )
                state.furnace.mode_id = "off"
                state.furnace.is_active = False
                state.resources.coal = coal
                state.resources.wood = 200
                state.resources.steel = 100
                state.resources.raw_food = 40
                state.resources.cooked_food = 60
                state.daily_survival.storage_used = storage_used(state.resources)
                state.daily_survival.is_over_capacity = is_over_capacity(
                    state.resources
                )
                point_before = deepcopy(state.surface_resource_points[point_id])
                lodge_before = deepcopy(state.buildings[lodge.data["building_id"]])

                warnings = SurvivalSystem(
                    self.survival_rules,
                    self.building_rules,
                    self.technology_rules,
                ).evaluate_risks(state)
                execution = self.settle_day(
                    state,
                    self.make_engine(with_technology_rules=True),
                    f"blocked-{coal}",
                )
                production_log = next(
                    item
                    for item in execution.logs
                    if item.code == "buildings.production.settled"
                )

                self.assertTrue(execution.result.accepted)
                self.assertEqual(
                    {warning.warning_id for warning in warnings}
                    & {
                        "survival.storage_at_capacity",
                        "survival.storage_over_capacity",
                    },
                    {
                        "survival.storage_at_capacity"
                        if coal == 400
                        else "survival.storage_over_capacity"
                    },
                )
                self.assertTrue(
                    production_log.payload["production_blocked_by_storage"]
                )
                self.assertEqual(
                    production_log.payload["storage_used_at_stage_start"],
                    coal + 400,
                )
                self.assertEqual(
                    production_log.payload["production"],
                    {"coal": 0, "wood": 0, "steel": 0, "raw_food": 0},
                )
                self.assertEqual(production_log.payload["raw_food_processed"], 0)
                self.assertEqual(production_log.payload["cooked_food_produced"], 0)
                self.assertEqual(
                    state.surface_resource_points[point_id], point_before
                )
                self.assertEqual(
                    state.buildings[lodge.data["building_id"]]
                    .production_remainder_numerator,
                    lodge_before.production_remainder_numerator,
                )
                self.assertEqual(state.resources.coal, coal)
                self.assertEqual(state.resources.wood, 200)
                self.assertEqual(state.resources.steel, 100)

    def test_heating_can_free_capacity_before_production_stage(self) -> None:
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
        for building_id, count in (
            (lodge.data["building_id"], 15),
            (canteen.data["building_id"], 5),
        ):
            self.execute(
                state,
                ASSIGN_COMMAND,
                {
                    "building_id": building_id,
                    "population_type": "workers",
                    "count": count,
                },
            )
        state.resources.coal = 400
        state.resources.wood = 200
        state.resources.steel = 100
        state.resources.raw_food = 0
        state.resources.cooked_food = 100
        state.daily_survival.storage_used = storage_used(state.resources)
        state.daily_survival.is_over_capacity = False

        projection = self.make_system(
            with_technology_rules=True
        ).project_food_inventory(state)
        execution = self.settle_day(
            state,
            self.make_engine(with_technology_rules=True),
            "heating-frees-storage",
        )
        production_log = next(
            item
            for item in execution.logs
            if item.code == "buildings.production.settled"
        )

        self.assertFalse(projection["production_blocked_by_storage"])
        self.assertLess(projection["storage_used_at_stage_start"], 800)
        self.assertEqual(projection["raw_food_produced"], 40)
        self.assertEqual(projection["cooked_food_produced"], 80)
        self.assertTrue(execution.result.accepted)
        self.assertFalse(
            production_log.payload["production_blocked_by_storage"]
        )
        self.assertEqual(production_log.payload["production"]["raw_food"], 40)

    def test_crossing_capacity_is_kept_then_blocks_next_day(self) -> None:
        state = self.make_state()
        state.technologies.researched_tech_ids.append("tech_wood_processing_1")
        built = self.execute(
            state,
            BUILD_COMMAND,
            {
                "building_type": "logging_camp",
                "zone": "outer_ring",
                "binding_id": "forest-zone-1",
            },
        )
        self.execute(
            state,
            ASSIGN_COMMAND,
            {
                "building_id": built.data["building_id"],
                "population_type": "workers",
                "count": 15,
            },
        )
        state.furnace.mode_id = "off"
        state.furnace.is_active = False
        state.resources.coal = 400
        state.resources.wood = 299
        state.resources.steel = 100
        state.resources.raw_food = 0
        state.resources.cooked_food = 0
        state.daily_survival.storage_used = storage_used(state.resources)
        state.daily_survival.is_over_capacity = False
        engine = self.make_engine(with_technology_rules=True)

        first = self.settle_day(state, engine, "cross-capacity")
        first_log = next(
            item
            for item in first.logs
            if item.code == "buildings.production.settled"
        )
        wood_after_first = state.resources.wood
        second = self.settle_day(state, engine, "blocked-next-day")
        second_log = next(
            item
            for item in second.logs
            if item.code == "buildings.production.settled"
        )

        self.assertTrue(first.result.accepted)
        self.assertFalse(first_log.payload["production_blocked_by_storage"])
        self.assertEqual(first_log.payload["production"]["wood"], 55)
        self.assertEqual(wood_after_first, 354)
        self.assertGreater(first_log.payload["storage_used_at_stage_start"] + 55, 800)
        formed_warning = next(
            warning
            for warning in first.warnings
            if warning.warning_id == "survival.storage_over_capacity_formed"
        )
        self.assertEqual(
            formed_warning.details,
            {
                "capacity": 800,
                "used_before_production": 799,
                "used_after_production": 854,
                "overage": 54,
                "today_production_retained": True,
                "ordinary_production_blocked_next_day_if_capacity_not_freed": True,
            },
        )
        self.assertIn(
            "survival.storage_over_capacity_formed",
            {
                warning["warning_id"]
                for warning in first.result.data["warnings"]
            },
        )
        formed_log = next(
            item
            for item in first.logs
            if item.code == "survival.storage_over_capacity.formed"
        )
        self.assertEqual(formed_log.payload, formed_warning.details)
        self.assertTrue(second.result.accepted)
        self.assertTrue(second_log.payload["production_blocked_by_storage"])
        self.assertEqual(second_log.payload["production"]["wood"], 0)
        self.assertEqual(state.resources.wood, wood_after_first)

    def test_final_frost_food_warning_matches_greenhouse_output_and_shutdown(self) -> None:
        operating = self.make_final_frost_food_state()
        operating.furnace.mode_id = "level_2"
        operating.furnace.is_active = True
        before_projection = deepcopy(operating)

        projection = self.make_system(
            with_technology_rules=True
        ).project_food_inventory(operating)
        warnings = SurvivalSystem(
            self.survival_rules,
            self.building_rules,
            self.technology_rules,
        ).evaluate_risks(operating)
        self.assertEqual(operating, before_projection)
        execution = self.make_engine(with_technology_rules=True).execute(
            operating, CommandRequest("end-operating", END_DAY_COMMAND)
        )

        self.assertNotIn(
            "survival.food_shortfall",
            {warning.warning_id for warning in warnings},
        )
        self.assertEqual(projection["available_food"], 130)
        self.assertEqual(projection["raw_food_produced"], 70)
        self.assertEqual(projection["raw_food_processed"], 60)
        self.assertEqual(projection["cooked_food_produced"], 120)
        self.assertTrue(execution.result.accepted)
        self.assertEqual(operating.daily_survival.food_shortfall, 0)
        self.assertEqual(operating.daily_survival.unfed_population, 0)

        shutdown = self.make_final_frost_food_state()
        shutdown.furnace.mode_id = "off"
        shutdown.furnace.is_active = False
        before_projection = deepcopy(shutdown)
        warnings = SurvivalSystem(
            self.survival_rules,
            self.building_rules,
            self.technology_rules,
        ).evaluate_risks(shutdown)
        food_warning = next(
            warning
            for warning in warnings
            if warning.warning_id == "survival.food_shortfall"
        )

        self.assertEqual(shutdown, before_projection)
        self.assertEqual(food_warning.details["current_available_food"], 0)
        self.assertEqual(food_warning.details["available_food"], 0)
        self.assertEqual(food_warning.details["raw_food_produced_today"], 0)
        self.assertEqual(food_warning.details["cooked_food_produced_today"], 0)
        self.assertEqual(food_warning.details["food_shortfall"], 80)
        engine = self.make_engine(with_technology_rules=True)
        preview = engine.execute(
            shutdown, CommandRequest("end-shutdown", END_DAY_COMMAND)
        )
        execution = self.confirm(
            engine, shutdown, preview, "confirm-shutdown"
        )
        self.assertTrue(execution.result.accepted)
        self.assertEqual(shutdown.daily_survival.food_shortfall, 80)

    def test_food_warning_reports_projected_partial_shortfall(self) -> None:
        state = self.make_final_frost_food_state()
        state.furnace.mode_id = "level_2"
        state.furnace.is_active = True
        first_greenhouse = next(
            building
            for building in state.buildings.values()
            if building.building_type == "greenhouse"
        )
        first_greenhouse.assigned_workers = 0
        before_projection = deepcopy(state)

        warnings = SurvivalSystem(
            self.survival_rules,
            self.building_rules,
            self.technology_rules,
        ).evaluate_risks(state)
        food_warning = next(
            warning
            for warning in warnings
            if warning.warning_id == "survival.food_shortfall"
        )

        self.assertEqual(state, before_projection)
        self.assertEqual(food_warning.details["current_available_food"], 0)
        self.assertEqual(food_warning.details["available_food"], 70)
        self.assertEqual(food_warning.details["raw_food_produced_today"], 35)
        self.assertEqual(food_warning.details["raw_food_processed_today"], 35)
        self.assertEqual(food_warning.details["cooked_food_produced_today"], 70)
        self.assertEqual(food_warning.details["food_shortfall"], 10)
        self.assertEqual(food_warning.details["unfed_population"], 10)

        engine = self.make_engine(with_technology_rules=True)
        preview = engine.execute(state, CommandRequest("end-partial", END_DAY_COMMAND))
        execution = self.confirm(engine, state, preview, "confirm-partial")
        self.assertTrue(execution.result.accepted)
        self.assertEqual(state.daily_survival.food_shortfall, 10)
        self.assertEqual(state.daily_survival.unfed_population, 10)

    def test_unaffordable_overload_cannot_hide_greenhouse_shortfall(self) -> None:
        state = self.make_final_frost_food_state(insulated=False)
        state.technologies.researched_tech_ids.extend(
            ["tech_furnace_power_stability_1", "tech_overload_tuning"]
        )
        state.furnace.mode_id = "level_2"
        state.furnace.is_active = True
        state.furnace.overload_level = 1
        state.resources.coal = 100
        state.daily_survival.storage_used = (
            state.resources.coal
            + state.resources.wood
            + state.resources.steel
        )
        before_projection = deepcopy(state)
        system = self.make_system(with_technology_rules=True)

        projection = system.project_food_inventory(state)
        warnings = SurvivalSystem(
            self.survival_rules,
            self.building_rules,
            self.technology_rules,
        ).evaluate_risks(state)
        food_warning = next(
            warning
            for warning in warnings
            if warning.warning_id == "survival.food_shortfall"
        )

        self.assertEqual(state, before_projection)
        self.assertEqual(projection["available_food"], 0)
        self.assertEqual(projection["raw_food_produced"], 0)
        self.assertEqual(food_warning.details["food_shortfall"], 80)
        self.assertIn(
            "survival.overload_fuel_shortfall",
            {warning.warning_id for warning in warnings},
        )

        engine = self.make_engine(with_technology_rules=True)
        preview = engine.execute(state, CommandRequest("end-overload", END_DAY_COMMAND))
        execution = self.confirm(engine, state, preview, "confirm-overload")
        self.assertTrue(execution.result.accepted)
        self.assertEqual(state.daily_survival.coal_paid, 85)
        self.assertEqual(state.daily_survival.effective_overload_level, 0)
        self.assertEqual(state.daily_survival.food_shortfall, 80)
        self.assertEqual(state.daily_survival.unfed_population, 80)

    def test_woodfuel_base_payment_does_not_reserve_coal_for_overload(self) -> None:
        state = self.make_final_frost_food_state(insulated=False)
        state.technologies.researched_tech_ids.extend(
            ["tech_furnace_power_stability_1", "tech_overload_tuning"]
        )
        state.furnace.mode_id = "level_2"
        state.furnace.is_active = True
        state.furnace.overload_level = 1
        state.resources.coal = 70
        state.building_management.woodfuel_confirmed_today = True
        state.daily_survival.storage_used = (
            state.resources.coal
            + state.resources.wood
            + state.resources.steel
        )

        projection = self.make_system(
            with_technology_rules=True
        ).project_food_inventory(state)
        food_warning = next(
            warning
            for warning in SurvivalSystem(
                self.survival_rules,
                self.building_rules,
                self.technology_rules,
            ).evaluate_risks(state)
            if warning.warning_id == "survival.food_shortfall"
        )

        self.assertEqual(projection["available_food"], 0)
        self.assertEqual(food_warning.details["food_shortfall"], 80)
        engine = self.make_engine(with_technology_rules=True)
        preview = engine.execute(state, CommandRequest("end-woodfuel", END_DAY_COMMAND))
        execution = self.confirm(engine, state, preview, "confirm-woodfuel")
        self.assertTrue(execution.result.accepted)
        self.assertEqual(state.daily_survival.coal_paid, 70)
        self.assertEqual(state.daily_survival.woodfuel_contribution, 15)
        self.assertEqual(state.daily_survival.effective_overload_level, 0)
        self.assertEqual(state.daily_survival.food_shortfall, 80)

    def test_unaffordable_overload_cannot_keep_canteen_running(self) -> None:
        state = self.make_final_frost_food_state(insulated=False)
        state.technologies.researched_tech_ids.extend(
            ["tech_furnace_power_stability_1", "tech_overload_tuning"]
        )
        state.calendar.current_day = 55
        seed_final_frost_history(state, through_day=54)
        state.furnace.mode_id = "level_2"
        state.furnace.is_active = True
        state.furnace.overload_level = 1
        state.resources.coal = 100
        state.resources.raw_food = 40
        for building in state.buildings.values():
            if building.building_type == "greenhouse":
                building.assigned_workers = 0
        state.daily_survival.storage_used = (
            state.resources.coal
            + state.resources.wood
            + state.resources.steel
            + state.resources.raw_food
        )
        before_projection = deepcopy(state)

        projection = self.make_system(
            with_technology_rules=True
        ).project_food_inventory(state)
        food_warning = next(
            warning
            for warning in SurvivalSystem(
                self.survival_rules,
                self.building_rules,
                self.technology_rules,
            ).evaluate_risks(state)
            if warning.warning_id == "survival.food_shortfall"
        )

        self.assertEqual(state, before_projection)
        self.assertEqual(projection["available_food"], 40)
        self.assertEqual(projection["raw_food_processed"], 0)
        self.assertEqual(projection["cooked_food_produced"], 0)
        self.assertEqual(food_warning.details["food_shortfall"], 40)
        engine = self.make_engine(with_technology_rules=True)
        preview = engine.execute(state, CommandRequest("end-canteen", END_DAY_COMMAND))
        execution = self.confirm(engine, state, preview, "confirm-canteen")
        self.assertTrue(execution.result.accepted)
        self.assertEqual(state.daily_survival.effective_overload_level, 0)
        self.assertEqual(state.daily_survival.raw_food_eaten, 40)
        self.assertEqual(state.daily_survival.food_shortfall, 40)

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

    def test_woodfuel_feedback_explains_zero_contribution_at_full_level_boundaries(self) -> None:
        system = self.make_system(with_technology_rules=True)
        state = self.make_state()
        state.technologies.researched_tech_ids.append(
            "tech_furnace_coal_saving_1"
        )
        state.furnace.mode_id = "level_2"
        state.furnace.is_active = True
        state.resources.coal = 47
        state.resources.wood = 15

        result = system.execute(
            state,
            CommandRequest(
                "woodfuel-zero",
                WOODFUEL_COMMAND,
                {"confirm": True},
                expected_state_sequence=state.command_sequence,
            ),
        )

        self.assertTrue(result.accepted)
        self.assertEqual(result.data["activation_outcome"], "armed_but_no_current_contribution")
        self.assertEqual(
            result.data["zero_contribution_reason"],
            "cannot_reach_next_full_furnace_level",
        )
        self.assertEqual(result.data["projected_target_furnace_level"], 2)
        self.assertEqual(result.data["projected_effective_furnace_level"], 1)
        self.assertEqual(result.data["projected_woodfuel_available"], 3)
        self.assertEqual(result.data["projected_woodfuel_contribution"], 0)
        self.assertEqual(result.data["projected_wood_burned"], 0)

    def test_d48_warning_discloses_next_day_forced_shutdown(self) -> None:
        state = self.make_state()
        state.calendar.current_day = 48
        built = self.execute(
            state,
            BUILD_COMMAND,
            {"building_type": "hunting_lodge", "zone": "outer_ring"},
        )

        warning = next(
            item
            for item in SurvivalSystem(
                self.survival_rules, self.building_rules
            ).evaluate_risks(state)
            if item.warning_id
            == "survival.final_frost_forced_shutdown_next_day"
        )

        self.assertEqual(warning.level.value, "B_STRONG")
        self.assertEqual(warning.details["shutdown_starts_day"], 49)
        self.assertIn(
            built.data["building_id"],
            warning.details["affected_building_ids"],
        )
        self.assertIn(
            "hunting_lodge",
            warning.details["forced_shutdown_building_types"],
        )
        self.assertTrue(
            warning.details["surface_resource_collection_shutdown"]
        )
        self.assertIn(
            "surface-steel-1",
            warning.details["affected_surface_resource_point_ids"],
        )

    def test_d48_surface_points_trigger_shutdown_warning_without_buildings(self) -> None:
        state = self.make_state()
        state.calendar.current_day = 48
        state.surface_resource_points["surface-steel-1"].assigned_workers = 5

        warning = next(
            item
            for item in SurvivalSystem(
                self.survival_rules, self.building_rules
            ).evaluate_risks(state)
            if item.warning_id
            == "survival.final_frost_forced_shutdown_next_day"
        )

        self.assertEqual(warning.details["affected_building_ids"], [])
        self.assertIn(
            "surface-steel-1",
            warning.details["affected_surface_resource_point_ids"],
        )

    def test_d49_boundary_synchronizes_forced_shutdown_operation_flags(self) -> None:
        state = self.make_state()
        hunting_lodge = self.execute(
            state,
            BUILD_COMMAND,
            {"building_type": "hunting_lodge", "zone": "outer_ring"},
        )
        canteen = self.execute(
            state,
            BUILD_COMMAND,
            {"building_type": "canteen", "zone": "inner_ring"},
        )
        state.buildings[hunting_lodge.data["building_id"]].is_operational = True
        state.buildings[canteen.data["building_id"]].is_operational = True
        state.calendar.current_day = 49

        self.make_system().prepare_new_day(state)

        self.assertFalse(
            state.buildings[hunting_lodge.data["building_id"]].is_operational
        )
        self.assertTrue(state.buildings[canteen.data["building_id"]].is_operational)

    def test_new_day_before_d49_does_not_rewrite_operation_flags(self) -> None:
        state = self.make_state()
        hunting_lodge = self.execute(
            state,
            BUILD_COMMAND,
            {"building_type": "hunting_lodge", "zone": "outer_ring"},
        )
        state.buildings[hunting_lodge.data["building_id"]].is_operational = True
        state.calendar.current_day = 48

        self.make_system().prepare_new_day(state)

        self.assertTrue(
            state.buildings[hunting_lodge.data["building_id"]].is_operational
        )

    def test_final_frost_assignment_cannot_reenable_shutdown_buildings(self) -> None:
        build_arguments = {
            "hunting_lodge": {
                "building_type": "hunting_lodge",
                "zone": "outer_ring",
            },
            "logging_camp": {
                "building_type": "logging_camp",
                "zone": "outer_ring",
                "binding_id": "forest-zone-1",
            },
            "small_coal_miner": {
                "building_type": "small_coal_miner",
                "zone": "outer_ring",
            },
            "small_steel_miner": {
                "building_type": "small_steel_miner",
                "zone": "outer_ring",
            },
        }
        required_tech = {
            "logging_camp": "tech_wood_processing_1",
            "small_coal_miner": "tech_coal_seam_support",
            "small_steel_miner": "tech_steel_screening",
        }
        for day in range(49, 56):
            for building_type, arguments in build_arguments.items():
                with self.subTest(day=day, building_type=building_type):
                    state = self.make_state()
                    state.calendar.current_day = day
                    seed_final_frost_history(state, through_day=day - 1)
                    if building_type in required_tech:
                        state.technologies.researched_tech_ids.append(
                            required_tech[building_type]
                        )
                    built = self.execute(
                        state,
                        BUILD_COMMAND,
                        arguments,
                        f"build-{day}-{building_type}",
                    )
                    self.assertEqual(built.code, ErrorCode.OK)

                    assigned = self.execute(
                        state,
                        ASSIGN_COMMAND,
                        {
                            "building_id": built.data["building_id"],
                            "population_type": "workers",
                            "count": 5,
                        },
                        f"assign-{day}-{building_type}",
                    )

                    self.assertEqual(assigned.code, ErrorCode.OK)
                    self.assertFalse(
                        state.buildings[
                            built.data["building_id"]
                        ].is_operational
                    )
                    unassigned = self.execute(
                        state,
                        UNASSIGN_COMMAND,
                        {
                            "building_id": built.data["building_id"],
                            "population_type": "workers",
                        },
                        f"unassign-{day}-{building_type}",
                    )
                    self.assertEqual(unassigned.code, ErrorCode.OK)
                    self.assertFalse(
                        state.buildings[
                            built.data["building_id"]
                        ].is_operational
                    )
                    reassigned = self.execute(
                        state,
                        ASSIGN_COMMAND,
                        {
                            "building_id": built.data["building_id"],
                            "population_type": "workers",
                            "count": 5,
                        },
                        f"reassign-{day}-{building_type}",
                    )
                    self.assertEqual(reassigned.code, ErrorCode.OK)
                    self.assertFalse(
                        state.buildings[
                            built.data["building_id"]
                        ].is_operational
                    )

    def test_final_frost_assignment_does_not_disable_other_buildings(self) -> None:
        state = self.make_state()
        state.calendar.current_day = 49
        FinalFrostSystem(
            load_final_frost_rules(REPOSITORY_ROOT / "data" / "final_frost.json"),
            self.building_rules,
            self.survival_rules,
            self.technology_rules,
        ).prepare_new_day(state)
        built = self.execute(
            state,
            BUILD_COMMAND,
            {"building_type": "research_institute", "zone": "middle_ring"},
        )

        assigned = self.execute(
            state,
            ASSIGN_COMMAND,
            {
                "building_id": built.data["building_id"],
                "population_type": "engineers",
                "count": 1,
            },
        )

        self.assertEqual(assigned.code, ErrorCode.OK)
        self.assertTrue(
            state.buildings[built.data["building_id"]].is_operational
        )

    def test_v14_final_frost_residual_operation_flag_is_normalized(self) -> None:
        state = self.make_state()
        built = self.execute(
            state,
            BUILD_COMMAND,
            {"building_type": "hunting_lodge", "zone": "outer_ring"},
        )
        state.calendar.current_day = 49
        FinalFrostSystem(
            load_final_frost_rules(REPOSITORY_ROOT / "data" / "final_frost.json"),
            self.building_rules,
            self.survival_rules,
            self.technology_rules,
        ).prepare_new_day(state)
        for event_id, resolved_day in (
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
                    resolved_day=resolved_day,
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
        state.buildings[built.data["building_id"]].assigned_workers = 5
        state.buildings[built.data["building_id"]].is_operational = True
        with tempfile.TemporaryDirectory() as directory:
            save_path = Path(directory) / "legacy-v14-d49.json"
            save_path.write_text(
                json.dumps(encode_game_state(state), ensure_ascii=False),
                encoding="utf-8",
            )
            loaded = GameSession.load(
                save_path,
                config_dir=REPOSITORY_ROOT / "data",
            )
            observation = to_primitive(loaded.observe())
        self.assertFalse(
            observation["state"]["buildings"][built.data["building_id"]][
                "is_operational"
            ]
        )

    def test_woodfuel_can_cover_the_shortfall_created_by_heat(self) -> None:
        state = self.make_state()
        state.calendar.current_day = 55
        seed_final_frost_history(state)
        state.furnace.mode_id = "level_2"
        state.furnace.is_active = True
        built = self.execute(
            state, BUILD_COMMAND, {"building_type": "canteen", "zone": "inner_ring"}
        )
        state.resources.coal = 85
        state.resources.wood = 80

        confirmed = self.execute(state, WOODFUEL_COMMAND, {"confirm": True})
        heated = self.execute(
            state, HEAT_COMMAND, {"building_id": built.data["building_id"]}
        )
        execution = self.settle_day(state)

        self.assertTrue(confirmed.accepted)
        self.assertTrue(heated.accepted)
        self.assertTrue(execution.result.accepted)
        self.assertEqual(state.daily_survival.effective_furnace_level, 2)
        self.assertEqual(state.daily_survival.coal_paid, 65)
        self.assertEqual(state.daily_survival.woodfuel_contribution, 20)
        self.assertEqual(state.daily_survival.woodfuel_wood_burned, 80)
        self.assertEqual((state.resources.coal, state.resources.wood), (0, 0))

        no_actual_shortfall = self.make_state()
        no_actual_shortfall.furnace.mode_id = "level_2"
        no_actual_shortfall.furnace.is_active = True
        no_actual_shortfall.resources.coal = 85
        no_actual_shortfall.resources.wood = 80
        confirmed = self.execute(
            no_actual_shortfall, WOODFUEL_COMMAND, {"confirm": True}
        )
        execution = self.settle_day(no_actual_shortfall)
        self.assertTrue(confirmed.accepted)
        self.assertTrue(execution.result.accepted)
        self.assertEqual(no_actual_shortfall.daily_survival.coal_paid, 85)
        self.assertEqual(no_actual_shortfall.daily_survival.woodfuel_wood_burned, 0)
        self.assertEqual(no_actual_shortfall.resources.wood, 80)

    def test_v2_save_migration_adds_patch_004_fields(self) -> None:
        state = self.make_state()
        legacy = encode_game_state(state)
        downgrade_to_pre_patch006_schema(legacy)
        legacy["save_data_version"] = 2
        legacy.get("technologies", {}).pop("research_profile_id", None)
        legacy.get("technologies", {}).pop("research_remainder_tenths", None)
        del legacy["building_management"]
        del legacy["surface_resource_points"]
        del legacy["daily_survival"]["woodfuel_wood_burned"]
        del legacy["daily_survival"]["woodfuel_contribution"]
        for building in legacy["buildings"].values():
            del building["bound_resource_id"]
            del building["production_remainder_numerator"]
            del building["production_multiplier_remainder_numerator"]
            del building["production_multiplier_remainder_denominator"]

        migrated = decode_game_state(legacy)

        self.assertEqual(migrated.save_data_version, CURRENT_SAVE_DATA_VERSION)
        self.assertEqual(migrated.building_management.zone_slots_used["inner_ring"], 4)
        self.assertEqual(len(migrated.buildings), 4)

    def test_surface_resource_points_collect_deplete_and_report_bound_shelter(self) -> None:
        state = self.make_state()
        point_id = "surface-steel-1"
        point = state.surface_resource_points[point_id]
        self.assertEqual(len(state.surface_resource_points), 12)
        self.assertEqual(
            sum(item.remaining_amount for item in state.surface_resource_points.values()),
            1100,
        )
        point.remaining_amount = 1
        shelter = self.execute(
            state,
            BUILD_COMMAND,
            {
                "building_type": "gathering_shelter",
                "zone": "outer_ring",
                "binding_id": point_id,
            },
        )
        assigned = self.execute(
            state,
            ASSIGN_RESOURCE_COMMAND,
            {
                "resource_point_id": point_id,
                "population_type": "engineers",
                "count": 1,
            },
        )

        execution = self.settle_day(state)
        production_log = next(
            item for item in execution.logs if item.code == "buildings.production.settled"
        )
        depletion_warning = next(
            item
            for item in execution.warnings
            if item.warning_id == "buildings.resource_points_depleted"
        )
        depletion_log = next(
            item
            for item in execution.logs
            if item.code == "buildings.resource_points.depleted"
        )

        self.assertTrue(shelter.accepted)
        self.assertTrue(assigned.accepted)
        self.assertTrue(execution.result.accepted)
        self.assertEqual(state.resources.steel, 36)
        point = state.surface_resource_points[point_id]
        self.assertTrue(point.is_depleted)
        self.assertEqual((point.assigned_workers, point.assigned_engineers), (0, 0))
        self.assertIn(point_id, production_log.payload["depleted_resource_point_ids"])
        self.assertIn(point_id, production_log.payload["shelter_removal_suggested_ids"])
        self.assertEqual(
            depletion_warning.assessment_stage.value,
            "settlement_result",
        )
        self.assertEqual(
            depletion_warning.details,
            {
                "resource_point_ids": [point_id],
                "resource_points": [
                    {
                        "resource_point_id": point_id,
                        "resource_type": "steel",
                        "released_workers": 0,
                        "released_engineers": 1,
                    }
                ],
                "released_workers_total": 0,
                "released_engineers_total": 1,
                "assignments_released_automatically": True,
                "unassign_required": False,
            },
        )
        serialized_warning = next(
            item
            for item in execution.result.data["warnings"]
            if item["warning_id"] == "buildings.resource_points_depleted"
        )
        self.assertEqual(serialized_warning["assessment_stage"], "settlement_result")
        self.assertEqual(serialized_warning["details"], depletion_warning.details)
        self.assertEqual(depletion_log.payload, depletion_warning.details)
        rejected = self.execute(
            state,
            ASSIGN_RESOURCE_COMMAND,
            {
                "resource_point_id": point_id,
                "population_type": "workers",
                "count": 1,
            },
        )
        self.assertEqual(rejected.data["reason"], "resource_point_depleted")
        self.assertFalse(rejected.data["accepts_assignments"])
        self.assertEqual(rejected.data["assigned_workers"], 0)
        self.assertEqual(rejected.data["assigned_engineers"], 0)

        before_unassign = deepcopy(state)
        unassign = self.execute(
            state,
            UNASSIGN_RESOURCE_COMMAND,
            {
                "resource_point_id": point_id,
                "population_type": "workers",
            },
        )
        self.assertEqual(unassign.data["reason"], "resource_point_depleted")
        self.assertTrue(unassign.data["assignments_released_automatically"])
        self.assertFalse(unassign.data["unassign_required"])
        self.assertEqual(unassign.data["assigned_workers"], 0)
        self.assertEqual(unassign.data["assigned_engineers"], 0)
        self.assertEqual(state, before_unassign)

    def test_depletion_fact_log_is_not_published_when_later_stage_rolls_back(
        self,
    ) -> None:
        state = self.make_state()
        point_id = "surface-steel-1"
        state.surface_resource_points[point_id].remaining_amount = 1
        assigned = self.execute(
            state,
            ASSIGN_RESOURCE_COMMAND,
            {
                "resource_point_id": point_id,
                "population_type": "engineers",
                "count": 1,
            },
        )
        before = deepcopy(state)
        engine = self.make_engine()

        def fail_after_production(_context) -> None:
            raise RuntimeError("test-only later-stage failure")

        engine.register_stage_handler(
            EndDayStage.RESOLVE_TRUST_AND_PANIC,
            fail_after_production,
        )
        execution = self.settle_day(state, engine, "depletion-rollback")

        self.assertTrue(assigned.accepted)
        self.assertEqual(execution.result.code, ErrorCode.INTERNAL_ERROR)
        self.assertEqual(state, before)
        self.assertEqual(
            state.surface_resource_points[point_id].remaining_amount,
            1,
        )
        self.assertEqual(
            state.surface_resource_points[point_id].assigned_engineers,
            1,
        )
        self.assertNotIn(
            "buildings.resource_points_depleted",
            {
                item["warning_id"]
                for item in execution.result.data["warnings"]
            },
        )
        self.assertNotIn(
            "buildings.resource_points.depleted",
            {item.code for item in execution.logs},
        )

    def test_fractional_production_uses_saved_integer_remainder(self) -> None:
        state = self.make_state()
        state.furnace.mode_id = "off"
        state.furnace.is_active = False
        state.technologies.researched_tech_ids.append("tech_wood_processing_1")
        built = self.execute(
            state,
            BUILD_COMMAND,
            {
                "building_type": "logging_camp",
                "zone": "outer_ring",
                "binding_id": "forest-zone-1",
            },
        )
        building_id = built.data["building_id"]
        self.execute(
            state,
            ASSIGN_COMMAND,
            {"building_id": building_id, "population_type": "workers", "count": 1},
        )

        outputs: list[int] = []
        remainders: list[int] = []
        previous_wood = state.resources.wood
        engine = self.make_engine()
        for day in range(1, 4):
            execution = self.settle_day(state, engine, f"fraction-{day}")
            self.assertTrue(execution.result.accepted)
            outputs.append(state.resources.wood - previous_wood)
            previous_wood = state.resources.wood
            remainders.append(
                state.buildings[building_id].production_remainder_numerator
            )

        self.assertEqual(outputs, [3, 4, 4])
        self.assertEqual(remainders, [10, 5, 0])
        restored = decode_game_state(encode_game_state(state))
        self.assertEqual(
            restored.buildings[building_id].production_remainder_numerator, 0
        )

    def test_engineers_can_fill_ordinary_jobs_but_workers_cannot_fill_research(self) -> None:
        state = self.make_state()
        canteen = self.execute(
            state, BUILD_COMMAND, {"building_type": "canteen", "zone": "inner_ring"}
        )
        research = self.execute(
            state,
            BUILD_COMMAND,
            {"building_type": "research_institute", "zone": "middle_ring"},
        )
        ordinary = self.execute(
            state,
            ASSIGN_COMMAND,
            {
                "building_id": canteen.data["building_id"],
                "population_type": "engineers",
                "count": 1,
            },
        )
        professional = self.execute(
            state,
            ASSIGN_COMMAND,
            {
                "building_id": research.data["building_id"],
                "population_type": "workers",
                "count": 1,
            },
        )

        self.assertTrue(ordinary.accepted)
        self.assertEqual(professional.data["reason"], "population_type_not_allowed")

    def test_heat_rejects_sufficient_temperature_and_exact_threshold(self) -> None:
        for day in (1, 36):
            with self.subTest(day=day):
                state = self.make_state()
                state.calendar.current_day = day
                built = self.execute(
                    state,
                    BUILD_COMMAND,
                    {"building_type": "canteen", "zone": "inner_ring"},
                )
                coal_before = state.resources.coal
                result = self.execute(
                    state, HEAT_COMMAND, {"building_id": built.data["building_id"]}
                )
                self.assertEqual(result.data["reason"], "temperature_already_sufficient")
                self.assertEqual(state.resources.coal, coal_before)

    def test_heat_requires_spare_coal_after_full_furnace_reserve(self) -> None:
        state = self.make_state()
        state.calendar.current_day = 55
        seed_final_frost_history(state)
        state.furnace.mode_id = "level_2"
        state.furnace.is_active = True
        state.resources.coal = 100
        built = self.execute(
            state, BUILD_COMMAND, {"building_type": "canteen", "zone": "inner_ring"}
        )
        before = deepcopy(state)
        result = self.execute(
            state, HEAT_COMMAND, {"building_id": built.data["building_id"]}
        )

        self.assertEqual(result.data["reason"], "insufficient_coal_after_furnace_reserve")
        self.assertEqual(result.data["furnace_coal_reserved"], 85)
        self.assertEqual(state, before)

    def test_heat_city_limit_is_two_and_school_is_heat_eligible(self) -> None:
        state = self.make_state()
        state.calendar.current_day = 49
        seed_final_frost_history(state)
        state.resources.coal = 500
        state.resources.wood = 500
        state.resources.steel = 500
        state.laws.signed_law_ids.extend(
            ["basic_medical_law", "child_school_law"]
        )
        ids = []
        for building_type, zone in (
            ("canteen", "inner_ring"),
            ("medical_station", "inner_ring"),
            ("school", "inner_ring"),
        ):
            built = self.execute(
                state,
                BUILD_COMMAND,
                {"building_type": building_type, "zone": zone},
            )
            ids.append(built.data["building_id"])

        first = self.execute(state, HEAT_COMMAND, {"building_id": ids[0]}, "heat-1")
        second = self.execute(state, HEAT_COMMAND, {"building_id": ids[1]}, "heat-2")
        third = self.execute(state, HEAT_COMMAND, {"building_id": ids[2]}, "heat-3")

        self.assertTrue(first.accepted)
        self.assertTrue(second.accepted)
        self.assertEqual(second.data["remaining_city_heat_uses"], 0)
        self.assertEqual(third.data["reason"], "daily_heat_limit_reached")
        self.assertTrue(self.building_rules.buildings["school"].can_heat)

    def test_residences_and_research_institute_cannot_heat(self) -> None:
        state = self.make_state()
        state.calendar.current_day = 49
        seed_final_frost_history(state)
        research = self.execute(
            state,
            BUILD_COMMAND,
            {"building_type": "research_institute", "zone": "middle_ring"},
        )
        for building_id in ("residence-start-001", research.data["building_id"]):
            with self.subTest(building_id=building_id):
                result = self.execute(state, HEAT_COMMAND, {"building_id": building_id})
                self.assertEqual(result.data["reason"], "building_cannot_heat")

    def test_heat_markers_and_city_counter_must_be_consistent(self) -> None:
        illegal_building = self.make_state()
        illegal_building.buildings["residence-start-001"].heated_today = True
        illegal_building.building_management.heat_uses_today = 1
        before = deepcopy(illegal_building)
        with self.assertRaises(SaveDataError):
            validate_game_state(
                illegal_building, self.building_rules, self.survival_rules
            )
        rejected = self.execute(
            illegal_building,
            BUILD_COMMAND,
            {"building_type": "canteen", "zone": "inner_ring"},
        )
        self.assertEqual(rejected.code, ErrorCode.INTERNAL_ERROR)
        self.assertEqual(illegal_building, before)

        inconsistent_count = self.make_state()
        built = self.execute(
            inconsistent_count,
            BUILD_COMMAND,
            {"building_type": "canteen", "zone": "inner_ring"},
        )
        inconsistent_count.buildings[built.data["building_id"]].heated_today = True
        with self.assertRaises(SaveDataError):
            validate_game_state(
                inconsistent_count, self.building_rules, self.survival_rules
            )

    def test_storage_building_limits_and_mutual_exclusion_are_validated(self) -> None:
        storage_tampered = self.make_state()
        storage_tampered.resources.storage_capacity = 1799
        with self.assertRaises(SaveDataError):
            validate_game_state(
                storage_tampered, self.building_rules, self.survival_rules
            )

        fixed_limit = self.make_state()
        built = self.execute(
            fixed_limit,
            BUILD_COMMAND,
            {"building_type": "canteen", "zone": "inner_ring"},
        )
        original = fixed_limit.buildings[built.data["building_id"]]
        duplicate = deepcopy(original)
        duplicate.building_id = "tampered-canteen"
        fixed_limit.buildings[duplicate.building_id] = duplicate
        fixed_limit.building_management.zone_slots_used[duplicate.zone] += duplicate.slot_size
        with self.assertRaisesRegex(SaveDataError, "configured limit"):
            validate_game_state(fixed_limit, self.building_rules, self.survival_rules)

        for building_type, arguments in (
            (
                "hunting_lodge",
                {"building_type": "hunting_lodge", "zone": "outer_ring"},
            ),
            (
                "logging_camp",
                {
                    "building_type": "logging_camp",
                    "zone": "outer_ring",
                    "binding_id": "forest-zone-1",
                },
            ),
        ):
            with self.subTest(building_type=building_type):
                dynamic_limit = self.make_state()
                if building_type == "logging_camp":
                    dynamic_limit.technologies.researched_tech_ids.append(
                        "tech_wood_processing_1"
                    )
                built = self.execute(dynamic_limit, BUILD_COMMAND, arguments)
                original = dynamic_limit.buildings[built.data["building_id"]]
                for suffix in ("a", "b"):
                    duplicate = deepcopy(original)
                    duplicate.building_id = f"tampered-{building_type}-{suffix}"
                    dynamic_limit.buildings[duplicate.building_id] = duplicate
                    dynamic_limit.building_management.zone_slots_used[
                        duplicate.zone
                    ] += duplicate.slot_size
                with self.assertRaisesRegex(SaveDataError, "configured limit"):
                    validate_game_state(
                        dynamic_limit, self.building_rules, self.survival_rules
                    )

        mutually_exclusive = self.make_state()
        mutually_exclusive.laws.signed_law_ids.append("cemetery_law")
        cemetery = self.execute(
            mutually_exclusive,
            BUILD_COMMAND,
            {"building_type": "cemetery", "zone": "outer_ring"},
        )
        cold_pit = deepcopy(mutually_exclusive.buildings[cemetery.data["building_id"]])
        cold_pit.building_id = "tampered-cold-pit"
        cold_pit.building_type = "cold_pit"
        mutually_exclusive.buildings[cold_pit.building_id] = cold_pit
        mutually_exclusive.building_management.zone_slots_used["outer_ring"] += 1
        with self.assertRaisesRegex(SaveDataError, "mutually exclusive"):
            validate_game_state(
                mutually_exclusive, self.building_rules, self.survival_rules
            )

    def test_zero_assignment_counts_are_rejected_without_state_changes(self) -> None:
        state = self.make_state()
        canteen = self.execute(
            state, BUILD_COMMAND, {"building_type": "canteen", "zone": "inner_ring"}
        )
        building_id = canteen.data["building_id"]
        self.execute(
            state,
            ASSIGN_COMMAND,
            {"building_id": building_id, "population_type": "workers", "count": 1},
        )
        self.execute(
            state,
            ASSIGN_RESOURCE_COMMAND,
            {
                "resource_point_id": "surface-coal-1",
                "population_type": "workers",
                "count": 1,
            },
        )
        cases = (
            (
                ASSIGN_COMMAND,
                {"building_id": building_id, "population_type": "workers", "count": 0},
            ),
            (
                UNASSIGN_COMMAND,
                {"building_id": building_id, "population_type": "workers", "count": 0},
            ),
            (
                ASSIGN_RESOURCE_COMMAND,
                {
                    "resource_point_id": "surface-coal-1",
                    "population_type": "workers",
                    "count": 0,
                },
            ),
            (
                UNASSIGN_RESOURCE_COMMAND,
                {
                    "resource_point_id": "surface-coal-1",
                    "population_type": "workers",
                    "count": 0,
                },
            ),
        )
        for index, (command_name, arguments) in enumerate(cases):
            with self.subTest(command_name=command_name):
                before = deepcopy(state)
                rejected = self.execute(
                    state, command_name, arguments, f"zero-count-{index}"
                )
                self.assertFalse(rejected.accepted)
                self.assertEqual(rejected.code, ErrorCode.INVALID_ARGUMENTS)
                self.assertEqual(state, before)

        unassigned = self.execute(
            state,
            UNASSIGN_COMMAND,
            {"building_id": building_id, "population_type": "workers"},
        )
        resource_unassigned = self.execute(
            state,
            UNASSIGN_RESOURCE_COMMAND,
            {
                "resource_point_id": "surface-coal-1",
                "population_type": "workers",
            },
        )
        self.assertTrue(unassigned.accepted)
        self.assertTrue(resource_unassigned.accepted)
        self.assertEqual(state.buildings[building_id].assigned_workers, 0)
        self.assertEqual(
            state.surface_resource_points["surface-coal-1"].assigned_workers, 0
        )

    def test_config_aware_validation_rejects_tampering_and_rolls_back(self) -> None:
        state = self.make_state()
        state.buildings["residence-start-001"].assigned_workers = 51
        with self.assertRaises(SaveDataError):
            validate_game_state(state, self.building_rules, self.survival_rules)
        before = deepcopy(state)
        result = self.execute(
            state,
            BUILD_COMMAND,
            {"building_type": "canteen", "zone": "inner_ring"},
        )
        self.assertEqual(result.code, ErrorCode.INTERNAL_ERROR)
        self.assertEqual(state, before)

        heat_tampered = self.make_state()
        heat_tampered.calendar.current_day = 49
        seed_final_frost_history(heat_tampered)
        heat_tampered.buildings["residence-start-001"].can_heat = True
        coal_before = heat_tampered.resources.coal
        result = self.execute(
            heat_tampered,
            HEAT_COMMAND,
            {"building_id": "residence-start-001"},
        )
        self.assertEqual(result.code, ErrorCode.INTERNAL_ERROR)
        self.assertEqual(heat_tampered.resources.coal, coal_before)

    def test_duplicate_bindings_and_tampered_map_capacity_are_rejected(self) -> None:
        state = self.make_state()
        first = self.execute(
            state,
            BUILD_COMMAND,
            {
                "building_type": "gathering_shelter",
                "zone": "outer_ring",
                "binding_id": "surface-coal-1",
            },
        )
        second = self.execute(
            state,
            BUILD_COMMAND,
            {
                "building_type": "gathering_shelter",
                "zone": "outer_ring",
                "binding_id": "surface-coal-2",
            },
        )
        state.buildings[second.data["building_id"]].bound_resource_id = "surface-coal-1"
        with self.assertRaises(SaveDataError):
            validate_game_state(state, self.building_rules, self.survival_rules)

        state = self.make_state()
        state.building_management.forest_zones = 99
        with self.assertRaises(SaveDataError):
            validate_game_state(state, self.building_rules, self.survival_rules)
        self.assertTrue(first.accepted)

    def test_end_day_rejects_config_tampering_without_mutating_state(self) -> None:
        state = self.make_state()
        state.buildings["residence-start-001"].slot_size = 0
        before = deepcopy(state)
        execution = self.settle_day(state)
        self.assertEqual(execution.result.code, ErrorCode.INTERNAL_ERROR)
        self.assertEqual(state, before)

    def test_late_end_day_config_tampering_rolls_back_before_autosave(self) -> None:
        state = self.make_state()
        before = deepcopy(state)
        autosaves: list[object] = []
        engine = self.make_engine(autosaves.append)

        def corrupt_storage(context) -> None:
            context.state.resources.storage_capacity = 1799

        engine.register_stage_handler(
            EndDayStage.RESOLVE_TRUST_AND_PANIC, corrupt_storage
        )
        execution = self.settle_day(state, engine, "late-config-tamper")

        self.assertEqual(execution.result.code, ErrorCode.INTERNAL_ERROR)
        self.assertEqual(execution.result.data["failed_stage"], "write_autosave")
        self.assertEqual(state, before)
        self.assertEqual(autosaves, [])
        self.assertIsNone(execution.autosave)
        self.assertIsNone(engine.last_autosave())

    def test_unfinished_buildings_are_rejected_and_commands_roll_back(self) -> None:
        cases = (
            (
                "basic_residence",
                None,
                "residence-start-001",
            ),
            (
                "small_warehouse",
                {"building_type": "small_warehouse", "zone": "storage_outer"},
                None,
            ),
            (
                "hunting_lodge",
                {"building_type": "hunting_lodge", "zone": "outer_ring"},
                None,
            ),
        )
        for building_type, build_arguments, existing_id in cases:
            with self.subTest(building_type=building_type):
                state = self.make_state()
                building_id = existing_id
                if build_arguments is not None:
                    built = self.execute(state, BUILD_COMMAND, build_arguments)
                    self.assertTrue(built.accepted)
                    building_id = built.data["building_id"]
                assert building_id is not None
                state.buildings[building_id].is_built = False
                before = deepcopy(state)

                with self.assertRaisesRegex(SaveDataError, "unfinished building"):
                    validate_game_state(
                        state, self.building_rules, self.survival_rules
                    )
                rejected = self.execute(
                    state,
                    BUILD_COMMAND,
                    {"building_type": "canteen", "zone": "inner_ring"},
                    f"unfinished-{building_type}",
                )
                self.assertEqual(rejected.code, ErrorCode.INTERNAL_ERROR)
                self.assertEqual(state, before)

    def test_v2_migration_preserves_non_contiguous_and_custom_residence_ids(self) -> None:
        for existing_id in ("residence-start-004", "custom-start-home"):
            with self.subTest(existing_id=existing_id):
                state = self.make_state()
                legacy = encode_game_state(state)
                downgrade_to_pre_patch006_schema(legacy)
                legacy["save_data_version"] = 2
                legacy.get("technologies", {}).pop("research_profile_id", None)
                legacy.get("technologies", {}).pop("research_remainder_tenths", None)
                del legacy["building_management"]
                del legacy["surface_resource_points"]
                del legacy["daily_survival"]["woodfuel_wood_burned"]
                del legacy["daily_survival"]["woodfuel_contribution"]
                source = legacy["buildings"]["residence-start-004"]
                source["building_id"] = existing_id
                del source["bound_resource_id"]
                del source["production_remainder_numerator"]
                del source["production_multiplier_remainder_numerator"]
                del source["production_multiplier_remainder_denominator"]
                legacy["buildings"] = {existing_id: source}

                migrated = decode_game_state(legacy)

                self.assertIn(existing_id, migrated.buildings)
                self.assertEqual(len(migrated.buildings), 4)
                self.assertEqual(
                    sum(
                        building.building_type == "basic_residence"
                        for building in migrated.buildings.values()
                    ),
                    4,
                )

    def test_building_config_cross_field_validation(self) -> None:
        source = json.loads((REPOSITORY_ROOT / "data" / "buildings.json").read_text(encoding="utf-8"))

        def assert_invalid(mutator) -> None:
            document = deepcopy(source)
            mutator(document)
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "buildings.json"
                path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
                with self.assertRaises(BuildingConfigError):
                    load_building_rules(path)

        mutations = (
            lambda item: item["buildings"]["logging_camp"].__setitem__("output_resource", "credits"),
            lambda item: item["buildings"]["canteen"].__setitem__("allowed_staff_types", ["aliens"]),
            lambda item: item["buildings"]["canteen"].update({"staff_capacity": 0, "allowed_staff_types": []}),
            lambda item: item["buildings"]["improved_residence"].__setitem__("slot_size", 2),
            lambda item: item["heat"].__setitem__("enhanced_temperature_bonus", 1),
            lambda item: item["woodfuel"].__setitem__("minimum_wood_unit", 3),
        )
        for index, mutator in enumerate(mutations):
            with self.subTest(index=index):
                assert_invalid(mutator)

    def test_boolean_command_sequence_never_leaks_as_machine_sequence(self) -> None:
        state = self.make_state()
        state.command_sequence = True
        result = self.make_system().execute(
            state,
            CommandRequest("bad", BUILD_COMMAND, {}),
        )
        self.assertEqual(result.state_sequence, 0)
        self.assertIsNot(result.state_sequence, True)

    def test_production_technology_hooks_use_configured_integer_outputs(self) -> None:
        cases = (
            ("logging_camp", "outer_ring", "forest-zone-1", "tech_wood_processing_1", "tech_wood_processing_2", "wood", 70, 15),
            ("small_coal_miner", "outer_ring", None, "tech_coal_seam_support", "tech_small_coal_mining_improvement", "coal", 90, 10),
            ("small_steel_miner", "outer_ring", None, "tech_steel_screening", "tech_small_steel_mining_improvement", "steel", 30, 10),
        )
        for building_type, zone, binding_id, prerequisite, enhancement, resource, expected, staff in cases:
            with self.subTest(building_type=building_type):
                state = self.make_state()
                state.resources.wood = 200
                state.resources.steel = 100
                state.technologies.researched_tech_ids.extend([prerequisite, enhancement])
                arguments = {"building_type": building_type, "zone": zone}
                if binding_id is not None:
                    arguments["binding_id"] = binding_id
                built = self.execute(state, BUILD_COMMAND, arguments)
                self.execute(
                    state,
                    ASSIGN_COMMAND,
                    {"building_id": built.data["building_id"], "population_type": "workers", "count": staff},
                )
                execution = self.settle_day(state)
                production_log = next(
                    item for item in execution.logs if item.code == "buildings.production.settled"
                )
                self.assertEqual(production_log.payload["production"][resource], expected)

        state = self.make_state()
        state.resources.raw_food = 200
        state.technologies.researched_tech_ids.append("tech_canteen_process_improvement")
        canteen = self.execute(
            state, BUILD_COMMAND, {"building_type": "canteen", "zone": "inner_ring"}
        )
        self.execute(
            state,
            ASSIGN_COMMAND,
            {"building_id": canteen.data["building_id"], "population_type": "workers", "count": 5},
        )
        execution = self.settle_day(state)
        production_log = next(
            item for item in execution.logs if item.code == "buildings.production.settled"
        )
        self.assertEqual(production_log.payload["raw_food_processed"], 80)

    def test_building_economy_runs_all_55_days_deterministically(self) -> None:
        def run(seed: int):
            state = create_initial_survival_state(
                self.survival_rules, self.building_rules, random_seed=seed
            )
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
            self.execute(
                state,
                ASSIGN_RESOURCE_COMMAND,
                {"resource_point_id": "surface-coal-1", "population_type": "workers", "count": 15},
            )
            engine = self.make_engine()
            all_logs = []
            for day in range(1, 56):
                execution = self.settle_day(state, engine, f"d{day}")
                self.assertTrue(execution.result.accepted)
                all_logs.extend(execution.logs)
            return state, all_logs

        first_state, first_logs = run(404)
        second_state, second_logs = run(404)
        self.assertEqual(first_state, second_state)
        self.assertEqual(first_logs, second_logs)
        self.assertEqual(first_state.calendar.current_day, 55)
        self.assertTrue(first_state.calendar.is_day_locked)

    def test_patch034_building_requirement_hints_are_exact(self) -> None:
        system = self.make_system(with_technology_rules=True)

        hospital_state = self.make_state()
        hospital = self.execute(
            hospital_state,
            BUILD_COMMAND,
            {"building_type": "hospital", "zone": "inner_ring"},
            system=system,
        )
        self.assertEqual(hospital.code, ErrorCode.ILLEGAL_COMMAND)
        self.assertEqual(
            hospital.data["requirement_text_id"],
            "building.hospital.missing_requirement_hint",
        )
        self.assertEqual(
            hospital.data["requirement_text"],
            "医院尚未解锁。需要先签署「基础医疗法」，并完成「医院标准化」研究。",
        )

        greenhouse_state = self.make_state()
        greenhouse_state.technologies.researched_tech_ids.extend(
            [
                "tech_drawing_board",
                "tech_drafting_instrument",
                "tech_mechanical_calculator",
                "tech_greenhouse_cultivation",
            ]
        )
        greenhouse = self.execute(
            greenhouse_state,
            BUILD_COMMAND,
            {"building_type": "greenhouse", "zone": "middle_ring"},
            system=system,
        )
        self.assertTrue(greenhouse.accepted)
        greenhouse_upgrade = self.execute(
            greenhouse_state,
            UPGRADE_COMMAND,
            {
                "building_id": greenhouse.data["building_id"],
                "upgrade_id": "greenhouse_to_improved",
            },
            system=system,
        )
        self.assertEqual(greenhouse_upgrade.code, ErrorCode.ILLEGAL_COMMAND)
        self.assertEqual(
            greenhouse_upgrade.data["requirement_text"],
            "温室还不能升级。需要先完成「温室改良」研究。",
        )

        housing_state = self.make_state()
        housing_upgrade = self.execute(
            housing_state,
            UPGRADE_COMMAND,
            {
                "building_id": "residence-start-001",
                "upgrade_id": "basic_to_improved_residence",
            },
            system=system,
        )
        self.assertEqual(housing_upgrade.code, ErrorCode.ILLEGAL_COMMAND)
        self.assertEqual(
            housing_upgrade.data["requirement_text"],
            "这座住宅还不能升级。需要先完成「改良住宅标准」研究。",
        )

        housing_state.technologies.researched_tech_ids.extend(
            [
                "tech_drawing_board",
                "tech_drafting_instrument",
                "tech_mechanical_calculator",
                "tech_housing_insulation_1",
                "tech_improved_housing_standard",
            ]
        )
        first_upgrade = self.execute(
            housing_state,
            UPGRADE_COMMAND,
            {
                "building_id": "residence-start-001",
                "upgrade_id": "basic_to_improved_residence",
            },
            system=system,
        )
        self.assertTrue(first_upgrade.accepted)
        advanced_upgrade = self.execute(
            housing_state,
            UPGRADE_COMMAND,
            {
                "building_id": "residence-start-001",
                "upgrade_id": "improved_to_advanced_residence",
            },
            system=system,
        )
        self.assertEqual(advanced_upgrade.code, ErrorCode.ILLEGAL_COMMAND)
        self.assertEqual(
            advanced_upgrade.data["requirement_text"],
            "这座住宅还不能升级。需要先完成「高级住宅标准」研究。",
        )

    def test_patch034_house_hint_never_uses_internal_id_without_tech_rules(self) -> None:
        state = self.make_state()
        result = self.execute(
            state,
            UPGRADE_COMMAND,
            {
                "building_id": "residence-start-001",
                "upgrade_id": "basic_to_improved_residence",
            },
        )

        self.assertEqual(result.code, ErrorCode.ILLEGAL_COMMAND)
        self.assertEqual(result.data["reason"], "prerequisite_missing")
        self.assertNotIn("requirement_text_id", result.data)
        self.assertNotIn("requirement_text", result.data)


if __name__ == "__main__":
    unittest.main()
