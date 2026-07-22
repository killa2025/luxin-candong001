from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

from furnace_winter.config import (
    TechnologyConfigError,
    load_building_rules,
    load_law_rules,
    load_survival_rules,
    load_technology_rules,
)
from furnace_winter.gameplay import (
    ASSIGN_COMMAND,
    BUILD_COMMAND,
    CANCEL_RESEARCH_COMMAND,
    CONFIRM_END_DAY_COMMAND,
    END_DAY_COMMAND,
    RESEARCH_COMMAND,
    SET_OVERLOAD_COMMAND,
    BuildingSystem,
    EndDayEngine,
    LawSystem,
    SurvivalSystem,
    TechnologySystem,
    create_initial_survival_state,
)
from furnace_winter.interface import CommandRequest, ErrorCode
from furnace_winter.models import (
    CURRENT_SAVE_DATA_VERSION,
    HardFailType,
    SaveDataError,
    decode_game_state,
    encode_game_state,
    validate_game_state,
)


ROOT = Path(__file__).resolve().parents[1]


class TechnologyPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.survival_rules = load_survival_rules(ROOT / "data" / "survival.json")
        cls.building_rules = load_building_rules(ROOT / "data" / "buildings.json")
        cls.law_rules = load_law_rules(ROOT / "data" / "laws.json")
        cls.technology_rules = load_technology_rules(
            ROOT / "data" / "technologies.json"
        )

    def make_state(self):
        return create_initial_survival_state(
            self.survival_rules, self.building_rules, random_seed=6006
        )

    def technology_system(self) -> TechnologySystem:
        return TechnologySystem(
            self.technology_rules,
            self.building_rules,
            self.survival_rules,
            self.law_rules,
        )

    @staticmethod
    def unlock_overload(state, level: int) -> None:
        completed = [
            "tech_drawing_board",
            "tech_drafting_instrument",
            "tech_mechanical_calculator",
            "tech_furnace_power_stability_1",
            "tech_overload_tuning",
        ]
        if level == 2:
            completed.extend(
                [
                    "tech_difference_engine",
                    "tech_overload_stability",
                ]
            )
        state.technologies.researched_tech_ids.extend(completed)
        state.furnace.overload_level = level

    def building_system(self) -> BuildingSystem:
        return BuildingSystem(
            self.building_rules,
            self.survival_rules,
            self.technology_rules,
        )

    def execute(self, system, state, name: str, arguments: dict | None = None):
        return system.execute(
            state,
            CommandRequest(
                f"command-{state.command_sequence}",
                name,
                arguments or {},
                expected_state_sequence=state.command_sequence,
            ),
        )

    def add_research_institute(
        self, state, *, engineers: int = 1, apprentices: int = 0
    ) -> str:
        built = self.execute(
            self.building_system(),
            state,
            BUILD_COMMAND,
            {"building_type": "research_institute", "zone": "middle_ring"},
        )
        self.assertEqual(built.code, ErrorCode.OK)
        building_id = built.data["building_id"]
        if engineers:
            assigned = self.execute(
                self.building_system(),
                state,
                ASSIGN_COMMAND,
                {
                    "building_id": building_id,
                    "population_type": "engineers",
                    "count": engineers,
                },
            )
            self.assertEqual(assigned.code, ErrorCode.OK)
        if apprentices:
            state.population.engineering_apprentices = apprentices
            assigned = self.execute(
                self.building_system(),
                state,
                ASSIGN_COMMAND,
                {
                    "building_id": building_id,
                    "population_type": "engineering_apprentices",
                    "count": apprentices,
                },
            )
            self.assertEqual(assigned.code, ErrorCode.OK)
        return building_id

    def engine(self) -> EndDayEngine:
        engine = EndDayEngine()
        SurvivalSystem(
            self.survival_rules,
            self.building_rules,
            self.technology_rules,
        ).install(engine)
        self.building_system().install(engine)
        LawSystem(
            self.law_rules,
            self.building_rules,
            self.survival_rules,
            self.technology_rules,
        ).install(engine)
        self.technology_system().install(engine)
        return engine

    @staticmethod
    def settle(engine: EndDayEngine, state):
        execution = engine.execute(
            state,
            CommandRequest(
                "end",
                END_DAY_COMMAND,
                expected_state_sequence=state.command_sequence,
            ),
        )
        if execution.result.code is ErrorCode.END_DAY_CONFIRMATION_REQUIRED:
            execution = engine.execute(
                state,
                CommandRequest(
                    "confirm",
                    CONFIRM_END_DAY_COMMAND,
                    execution.result.data["confirmation"],
                    expected_state_sequence=state.command_sequence,
                ),
            )
        return execution

    def test_research_requires_a_formal_engineer_not_an_apprentice(self) -> None:
        state = self.make_state()
        self.add_research_institute(state, engineers=0, apprentices=1)
        before = deepcopy(state)

        result = self.execute(
            self.technology_system(),
            state,
            RESEARCH_COMMAND,
            {"tech_id": "tech_drawing_board"},
        )

        self.assertEqual(result.code, ErrorCode.ILLEGAL_COMMAND)
        self.assertEqual(result.data["reason"], "staffed_research_institute_required")
        self.assertEqual(state, before)

    def test_start_pays_immediately_and_cancel_never_refunds(self) -> None:
        state = self.make_state()
        self.add_research_institute(state)
        wood_before, steel_before = state.resources.wood, state.resources.steel

        started = self.execute(
            self.technology_system(),
            state,
            RESEARCH_COMMAND,
            {"tech_id": "tech_drawing_board"},
        )
        cancelled = self.execute(
            self.technology_system(), state, CANCEL_RESEARCH_COMMAND
        )

        self.assertEqual((started.code, cancelled.code), (ErrorCode.OK, ErrorCode.OK))
        rule = self.technology_rules.technologies["tech_drawing_board"]
        self.assertEqual(state.resources.wood, wood_before - rule.wood_cost)
        self.assertEqual(state.resources.steel, steel_before - rule.steel_cost)
        self.assertIsNone(state.technologies.active_research_id)
        self.assertEqual(cancelled.data["refund"], {"wood": 0, "steel": 0})

    def test_one_queue_tiers_and_prerequisites_are_strict(self) -> None:
        state = self.make_state()
        self.add_research_institute(state)
        locked = self.execute(
            self.technology_system(),
            state,
            RESEARCH_COMMAND,
            {"tech_id": "tech_drafting_instrument"},
        )
        self.assertEqual(locked.code, ErrorCode.ILLEGAL_COMMAND)
        self.assertIn("tech_drawing_board", locked.data["missing_tech_ids"])

        started = self.execute(
            self.technology_system(),
            state,
            RESEARCH_COMMAND,
            {"tech_id": "tech_drawing_board"},
        )
        occupied = self.execute(
            self.technology_system(),
            state,
            RESEARCH_COMMAND,
            {"tech_id": "tech_furnace_coal_saving_1"},
        )
        self.assertEqual(started.code, ErrorCode.OK)
        self.assertEqual(occupied.data["reason"], "research_queue_occupied")

    def test_research_completes_only_at_end_day_research_stage(self) -> None:
        state = self.make_state()
        self.add_research_institute(state)
        started = self.execute(
            self.technology_system(),
            state,
            RESEARCH_COMMAND,
            {"tech_id": "tech_drawing_board"},
        )
        self.assertEqual(started.code, ErrorCode.OK)
        self.assertNotIn(
            "tech_drawing_board", state.technologies.researched_tech_ids
        )

        settled = self.settle(self.engine(), state)

        self.assertEqual(settled.result.code, ErrorCode.OK)
        self.assertIn("tech_drawing_board", state.technologies.researched_tech_ids)
        self.assertIsNone(state.technologies.active_research_id)
        self.assertFalse(
            any(item.building_type != "research_institute" for item in state.buildings.values() if item.building_id.startswith("building-"))
        )

    def test_second_institute_is_speed_only_and_uses_exact_one_point_five(self) -> None:
        state = self.make_state()
        self.add_research_institute(state)
        self.add_research_institute(state)
        state.technologies.researched_tech_ids.append("tech_drawing_board")
        started = self.execute(
            self.technology_system(),
            state,
            RESEARCH_COMMAND,
            {"tech_id": "tech_drafting_instrument"},
        )
        self.assertEqual(started.code, ErrorCode.OK)

        settled = self.settle(self.engine(), state)

        self.assertEqual(settled.result.code, ErrorCode.OK)
        self.assertEqual(state.technologies.research_progress_units, 6)
        self.assertEqual(state.technologies.research_required_units, 8)
        self.assertNotIn(
            "tech_drafting_instrument", state.technologies.researched_tech_ids
        )

    def test_research_state_tampering_rolls_back_end_day_and_autosave(self) -> None:
        state = self.make_state()
        self.add_research_institute(state)
        self.execute(
            self.technology_system(),
            state,
            RESEARCH_COMMAND,
            {"tech_id": "tech_drawing_board"},
        )
        state.technologies.research_required_units = 999
        before = deepcopy(state)
        engine = self.engine()

        result = self.settle(engine, state)

        self.assertEqual(result.result.code, ErrorCode.INTERNAL_ERROR)
        self.assertEqual(state, before)
        self.assertIsNone(engine.last_autosave())

    def test_overload_unlock_cost_temperature_pressure_and_cooling(self) -> None:
        state = self.make_state()
        unlocked = [
            "tech_drawing_board",
            "tech_drafting_instrument",
            "tech_mechanical_calculator",
            "tech_furnace_power_stability_1",
            "tech_overload_tuning",
        ]
        state.technologies.researched_tech_ids.extend(unlocked)
        selected = self.execute(
            self.technology_system(),
            state,
            SET_OVERLOAD_COMMAND,
            {"level": 1},
        )
        self.assertEqual(selected.code, ErrorCode.OK)
        coal_before = state.resources.coal

        settled = self.settle(self.engine(), state)

        self.assertEqual(settled.result.code, ErrorCode.OK)
        self.assertEqual(state.daily_survival.overload_coal_paid, 25)
        self.assertEqual(state.daily_survival.overload_temperature_bonus, 8)
        self.assertEqual(state.furnace.pressure, 18)
        self.assertEqual(coal_before - state.resources.coal, 70)

        state.furnace.overload_level = 0
        state.resources.coal = 70
        cooled = self.settle(self.engine(), state)
        self.assertEqual(cooled.result.code, ErrorCode.OK)
        self.assertEqual(state.furnace.pressure, 0)

    def test_base_heating_is_paid_before_overload_with_and_without_woodfuel(self) -> None:
        cases = (
            (False, 45, 0, 0),
            (True, 25, 80, 80),
        )
        for with_woodfuel, coal, wood, expected_wood_burned in cases:
            with self.subTest(with_woodfuel=with_woodfuel):
                state = self.make_state()
                self.unlock_overload(state, 1)
                state.resources.coal = coal
                state.resources.wood = wood
                state.building_management.woodfuel_confirmed_today = with_woodfuel

                engine = self.engine()
                result = self.settle(engine, state)

                self.assertEqual(result.result.code, ErrorCode.OK)
                self.assertEqual(state.daily_survival.effective_furnace_level, 1)
                self.assertEqual(state.daily_survival.effective_overload_level, 0)
                self.assertEqual(state.daily_survival.overload_coal_paid, 0)
                self.assertEqual(
                    state.daily_survival.woodfuel_wood_burned,
                    expected_wood_burned,
                )
                self.assertTrue(state.daily_survival.heating_shortfall)
                self.assertEqual(state.resources.coal, 0)
                self.assertIsNotNone(engine.last_autosave())
                validate_game_state(
                    state,
                    self.building_rules,
                    self.survival_rules,
                    self.technology_rules,
                )

    def test_level_three_base_heating_is_not_sacrificed_for_overload(self) -> None:
        state = self.make_state()
        self.unlock_overload(state, 1)
        state.furnace.mode_id = "level_3"
        state.resources.coal = self.survival_rules.furnace_levels[3].coal_cost
        state.resources.wood = 0

        result = self.settle(self.engine(), state)

        self.assertEqual(result.result.code, ErrorCode.OK)
        self.assertEqual(state.daily_survival.effective_furnace_level, 3)
        self.assertEqual(state.daily_survival.effective_overload_level, 0)
        self.assertEqual(state.resources.coal, 0)

    def test_pressure_warnings_use_projected_effective_overload_growth(self) -> None:
        cases = (
            (1, 60, "survival.furnace_high_pressure", 85),
            (1, 76, "survival.furnace_pressure_redline_risk", 101),
            (49, 79, "survival.furnace_high_pressure", 99),
        )
        for day, pressure, warning_id, projected_pressure in cases:
            with self.subTest(day=day, pressure=pressure):
                state = self.make_state()
                self.unlock_overload(state, 2)
                if day == 49:
                    state.technologies.researched_tech_ids.extend(
                        [
                            "tech_automatic_forming_machine",
                            "tech_furnace_coal_saving_1",
                            "tech_furnace_coal_saving_2",
                            "tech_building_insulation_1",
                            "tech_building_insulation_2",
                            "tech_final_furnace_stability",
                        ]
                    )
                state.calendar.current_day = day
                state.furnace.pressure = pressure
                state.resources.coal = 300

                warnings = SurvivalSystem(
                    self.survival_rules,
                    self.building_rules,
                    self.technology_rules,
                ).evaluate_risks(state)
                warning = next(item for item in warnings if item.warning_id == warning_id)

                self.assertEqual(
                    warning.details["projected_pressure"], projected_pressure
                )

    def test_continuing_overload_after_redline_causes_core_collapse(self) -> None:
        state = self.make_state()
        state.technologies.researched_tech_ids.extend(
            [
                "tech_drawing_board",
                "tech_drafting_instrument",
                "tech_mechanical_calculator",
                "tech_furnace_power_stability_1",
                "tech_overload_tuning",
            ]
        )
        state.furnace.overload_level = 1
        state.furnace.pressure = 100
        state.furnace.pressure_redline_warned = True
        state.resources.coal = 200

        result = self.settle(self.engine(), state)

        self.assertEqual(result.result.code, ErrorCode.OK)
        self.assertEqual(state.final_result.hard_fail_type, HardFailType.CORE_COLLAPSE)
        self.assertTrue(state.final_result.is_finalized)
        self.assertEqual(result.result.data["transition"], "hard_fail")

    def test_final_furnace_stability_combines_confirmed_effects(self) -> None:
        state = self.make_state()
        state.calendar.current_day = 49
        state.resources.coal = 200
        state.technologies.researched_tech_ids.extend(
            [
                "tech_drawing_board",
                "tech_drafting_instrument",
                "tech_mechanical_calculator",
                "tech_difference_engine",
                "tech_automatic_forming_machine",
                "tech_furnace_coal_saving_1",
                "tech_furnace_coal_saving_2",
                "tech_building_insulation_1",
                "tech_building_insulation_2",
                "tech_furnace_power_stability_1",
                "tech_overload_tuning",
                "tech_overload_stability",
                "tech_final_furnace_stability",
            ]
        )
        state.furnace.overload_level = 2
        coal_before = state.resources.coal

        result = self.settle(self.engine(), state)

        self.assertEqual(result.result.code, ErrorCode.OK)
        self.assertEqual(state.daily_survival.overload_temperature_bonus, 14)
        self.assertEqual(state.furnace.pressure, 20)
        self.assertEqual(coal_before - state.resources.coal, 90)
        self.assertEqual(
            state.daily_survival.zone_temperatures["inner_ring"],
            self.survival_rules.weather_for_day(49)
            + self.survival_rules.furnace_levels[1].heating
            + self.survival_rules.zone_modifiers["inner_ring"]
            + 14
            + 3,
        )

    def test_storage_expansion_updates_existing_and_future_warehouses(self) -> None:
        state = self.make_state()
        built = self.execute(
            self.building_system(),
            state,
            BUILD_COMMAND,
            {"building_type": "small_warehouse", "zone": "storage_outer"},
        )
        self.assertEqual(built.code, ErrorCode.OK)
        self.assertEqual(state.resources.storage_capacity, 1100)
        state.technologies.researched_tech_ids.extend(
            ["tech_drawing_board", "tech_drafting_instrument"]
        )
        rule = self.technology_rules.technologies["tech_storage_expansion"]
        state.technologies.active_research_id = rule.tech_id
        state.technologies.research_required_units = (
            rule.research_days * self.technology_rules.research.progress_units_per_day
        )
        state.technologies.research_progress_units = (
            state.technologies.research_required_units
            - self.technology_rules.research.progress_units_per_day
        )
        self.add_research_institute(state)

        completed = self.settle(self.engine(), state)
        self.assertEqual(completed.result.code, ErrorCode.OK)
        self.assertEqual(state.resources.storage_capacity, 1400)

        future = self.execute(
            self.building_system(),
            state,
            BUILD_COMMAND,
            {"building_type": "small_warehouse", "zone": "storage_outer"},
        )
        self.assertEqual(future.code, ErrorCode.OK)
        self.assertEqual(state.resources.storage_capacity, 2000)

    def test_save_v7_round_trip_and_v6_migration(self) -> None:
        state = self.make_state()
        state.furnace.pressure = 80
        encoded = encode_game_state(state)
        self.assertEqual(encoded["save_data_version"], CURRENT_SAVE_DATA_VERSION)
        self.assertEqual(decode_game_state(encoded), state)

        legacy = deepcopy(encoded)
        legacy["save_data_version"] = 6
        legacy["furnace"].pop("overload_level")
        legacy["furnace"].pop("pressure_redline_warned")
        for field in (
            "target_overload_level",
            "effective_overload_level",
            "overload_coal_paid",
            "overload_temperature_bonus",
        ):
            legacy["daily_survival"].pop(field)
        legacy["technologies"].pop("research_progress_units")
        legacy["technologies"].pop("research_required_units")
        legacy["technologies"]["research_progress_days"] = 0

        migrated = decode_game_state(legacy)
        self.assertEqual(migrated.save_data_version, CURRENT_SAVE_DATA_VERSION)
        self.assertEqual(migrated.furnace.overload_level, 0)
        self.assertFalse(migrated.furnace.pressure_redline_warned)

    def test_v6_schema_is_strict_and_pressure_boundary_migrates(self) -> None:
        current = encode_game_state(self.make_state())
        mislabeled = deepcopy(current)
        mislabeled["save_data_version"] = 6
        with self.assertRaises(SaveDataError):
            decode_game_state(mislabeled)

        for pressure, expected_warned in ((99, False), (100, True)):
            with self.subTest(pressure=pressure):
                legacy = deepcopy(current)
                legacy["save_data_version"] = 6
                legacy["furnace"].pop("overload_level")
                legacy["furnace"].pop("pressure_redline_warned")
                legacy["furnace"]["pressure"] = pressure
                for field in (
                    "target_overload_level",
                    "effective_overload_level",
                    "overload_coal_paid",
                    "overload_temperature_bonus",
                ):
                    legacy["daily_survival"].pop(field)
                legacy["technologies"].pop("research_progress_units")
                legacy["technologies"].pop("research_required_units")
                legacy["technologies"]["research_progress_days"] = 0

                migrated = decode_game_state(legacy)

                self.assertEqual(migrated.furnace.pressure, pressure)
                self.assertEqual(
                    migrated.furnace.pressure_redline_warned,
                    expected_warned,
                )

    def test_technology_config_rejects_cycles(self) -> None:
        data = json.loads((ROOT / "data" / "technologies.json").read_text("utf-8"))
        data["technologies"]["tech_drawing_board"]["prerequisite_tech_ids"] = [
            "tech_drafting_instrument"
        ]
        data["technologies"]["tech_drafting_instrument"][
            "prerequisite_tech_ids"
        ] = ["tech_drawing_board"]
        with TemporaryDirectory() as directory:
            path = Path(directory) / "technologies.json"
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(TechnologyConfigError):
                load_technology_rules(path)

    def test_technology_catalog_and_overload_semantics_are_strict(self) -> None:
        source = json.loads(
            (ROOT / "data" / "technologies.json").read_text("utf-8")
        )
        mutations = (
            lambda data: data["technologies"].pop("tech_hunting_equipment"),
            lambda data: data["technologies"].update(
                {"tech_extra": deepcopy(data["technologies"]["tech_hunting_equipment"])}
            ),
            lambda data: data["technologies"]["tech_hunting_equipment"].update(
                {"display_name": "绘图板"}
            ),
            lambda data: data["overload"]["levels"].update(
                {"01": data["overload"]["levels"].pop("1")}
            ),
            lambda data: data["overload"]["levels"]["0"].update(
                {"coal_cost": 1}
            ),
            lambda data: data["overload"].update({"redline_threshold": 101}),
            lambda data: data["technologies"]["tech_furnace_coal_saving_1"].update(
                {"effect_targets": ["wrong_target"]}
            ),
            lambda data: data["technologies"]["tech_furnace_coal_saving_1"].update(
                {"effect_kind": "unlock_command"}
            ),
            lambda data: data["technologies"]["tech_hunting_equipment"].update(
                {"effect_kind": "passive", "effect_status": "ACTIVE"}
            ),
            lambda data: data["technologies"]["tech_furnace_coal_saving_1"].update(
                {"tier": 1}
            ),
        )
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index), TemporaryDirectory() as directory:
                data = deepcopy(source)
                mutate(data)
                path = Path(directory) / "technologies.json"
                path.write_text(
                    json.dumps(data, ensure_ascii=False), encoding="utf-8"
                )
                with self.assertRaises(TechnologyConfigError):
                    load_technology_rules(path)

    def test_overload_daily_summary_is_strict_with_and_without_config(self) -> None:
        initial = encode_game_state(self.make_state())
        for field in ("overload_coal_paid", "overload_temperature_bonus"):
            with self.subTest(inactive_field=field):
                forged = deepcopy(initial)
                forged["daily_survival"][field] = 999
                with self.assertRaises(SaveDataError):
                    decode_game_state(forged)

        unsettled = deepcopy(initial)
        unsettled["daily_survival"]["target_overload_level"] = 1
        unsettled["daily_survival"]["heating_shortfall"] = True
        with self.assertRaises(SaveDataError):
            decode_game_state(unsettled)

        for level, expected_coal, expected_bonus in ((1, 25, 8), (2, 55, 14)):
            with self.subTest(valid_level=level):
                state = self.make_state()
                self.unlock_overload(state, level)
                state.resources.coal = 300
                result = self.settle(self.engine(), state)
                self.assertEqual(result.result.code, ErrorCode.OK)
                self.assertEqual(
                    state.daily_survival.overload_coal_paid, expected_coal
                )
                self.assertEqual(
                    state.daily_survival.overload_temperature_bonus,
                    expected_bonus,
                )
                validate_game_state(
                    state,
                    self.building_rules,
                    self.survival_rules,
                    self.technology_rules,
                )

                encoded = encode_game_state(state)
                for field in (
                    "overload_coal_paid",
                    "overload_temperature_bonus",
                ):
                    with self.subTest(level=level, forged_field=field):
                        forged = deepcopy(encoded)
                        forged["daily_survival"][field] += 1
                        decoded = decode_game_state(forged)
                        with self.assertRaises(SaveDataError):
                            validate_game_state(
                                decoded,
                                self.building_rules,
                                self.survival_rules,
                                self.technology_rules,
                            )

                no_base = deepcopy(encoded)
                no_base["daily_survival"]["effective_furnace_level"] = 0
                no_base["daily_survival"]["heating_shortfall"] = True
                with self.assertRaises(SaveDataError):
                    decode_game_state(no_base)

    def test_responsible_owner_technology_conflict_decisions_are_applied(self) -> None:
        greenhouse = self.technology_rules.technologies[
            "tech_greenhouse_cultivation"
        ]
        advanced_housing = self.technology_rules.technologies[
            "tech_advanced_housing_standard"
        ]

        self.assertEqual(greenhouse.prerequisite_tech_ids, ())
        self.assertEqual(advanced_housing.tier, 4)
        self.assertEqual(self.technology_rules.config_status.value, "TEST_NUMERIC")

    def test_unknown_or_unlocked_technology_state_is_rejected(self) -> None:
        state = self.make_state()
        state.technologies.researched_tech_ids.append("unknown")
        with self.assertRaises(SaveDataError):
            self.technology_system().validate_state(state)

        state = self.make_state()
        state.furnace.overload_level = 1
        with self.assertRaises(SaveDataError):
            self.technology_system().validate_state(state)


if __name__ == "__main__":
    unittest.main()
