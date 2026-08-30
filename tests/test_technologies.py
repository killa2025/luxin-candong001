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
from furnace_winter.gameplay.survival import (
    furnace_coal_cost,
    projected_building_insulation_bonus,
    projected_heat_bonus,
    projected_overload_pressure_growth,
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
from tests import install_final_frost_history_stub, seed_final_frost_history


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

    def test_irreversible_steel_supply_lock_is_visible_and_strongly_warned(self) -> None:
        state = self.make_state()
        state.resources.steel = 2
        for point in state.surface_resource_points.values():
            if point.resource_type == "steel":
                point.remaining_amount = 0
                point.is_depleted = True
                point.assigned_workers = 0
                point.assigned_engineers = 0
        system = self.technology_system()

        warning = system.evaluate_risks(state)
        view = {
            item["tech_id"]: item for item in system.view(state)
        }["tech_steel_screening"]

        self.assertEqual(len(warning), 1)
        self.assertEqual(
            warning[0].warning_id,
            "technology.steel_supply_irreversibly_locked",
        )
        self.assertEqual(warning[0].level.value, "B_STRONG")
        self.assertEqual(warning[0].details["required_steel"], 5)
        self.assertEqual(warning[0].details["recoverable_steel"], 2)
        self.assertEqual(warning[0].details["steel_shortfall"], 3)
        self.assertEqual(
            view["irreversible_resource_lock"], warning[0].details
        )

        recoverable = self.make_state()
        recoverable.resources.steel = 2
        steel_point = next(
            point
            for point in recoverable.surface_resource_points.values()
            if point.resource_type == "steel"
        )
        steel_point.remaining_amount = 3
        self.assertEqual(system.evaluate_risks(recoverable), ())

    def test_final_frost_excludes_uncollectable_surface_steel(self) -> None:
        system = self.technology_system()
        d48 = self.make_state()
        d48.calendar.current_day = 48
        d48.resources.steel = 0
        self._deplete_surface_resource(d48, "steel")
        point = d48.surface_resource_points["surface-steel-1"]
        point.remaining_amount = 5
        point.is_depleted = False

        d48_view = {
            item["tech_id"]: item for item in system.view(d48)
        }["tech_steel_screening"]["irreversible_resource_lock"]
        self.assertIsNone(d48_view)
        self.assertEqual(system.evaluate_risks(d48), ())

        point.remaining_amount = 4
        warning = system.evaluate_risks(d48)
        self.assertEqual(len(warning), 1)
        self.assertEqual(warning[0].details["recoverable_surface_steel"], 4)
        self.assertEqual(warning[0].details["recoverable_steel"], 4)

        d49 = self.make_state()
        d49.calendar.current_day = 49
        d49.resources.steel = 0
        d49.surface_resource_points["surface-steel-1"].assigned_workers = 0
        warning = system.evaluate_risks(d49)
        d49_lock = {
            item["tech_id"]: item for item in system.view(d49)
        }["tech_steel_screening"]["irreversible_resource_lock"]

        self.assertEqual(len(warning), 1)
        self.assertEqual(d49_lock["remaining_surface_steel"], 120)
        self.assertEqual(d49_lock["recoverable_surface_steel"], 0)
        self.assertEqual(d49_lock["recoverable_steel"], 0)

    def test_irreversible_wood_supply_lock_uses_remaining_chain_costs(self) -> None:
        system = self.technology_system()
        state = self.make_state()
        state.resources.wood = 49
        self._deplete_surface_resource(state, "wood")

        warning = next(
            item
            for item in system.evaluate_risks(state)
            if item.warning_id
            == "technology.wood_supply_irreversibly_locked"
        )
        view = {
            item["tech_id"]: item for item in system.view(state)
        }["tech_wood_processing_1"]

        self.assertEqual(warning.level.value, "B_STRONG")
        self.assertEqual(warning.details["remaining_technology_wood_cost"], 15)
        self.assertEqual(warning.details["logging_camp_wood_cost"], 35)
        self.assertEqual(warning.details["required_wood"], 50)
        self.assertEqual(warning.details["recoverable_wood"], 49)
        self.assertEqual(warning.details["wood_shortfall"], 1)
        self.assertFalse(warning.details["technology_cost_paid"])
        self.assertEqual(view["irreversible_resource_lock"], warning.details)

        state.technologies.active_research_id = "tech_wood_processing_1"
        state.resources.wood = 34
        active_warning = next(
            item
            for item in system.evaluate_risks(state)
            if item.warning_id
            == "technology.wood_supply_irreversibly_locked"
        )
        self.assertTrue(active_warning.details["technology_cost_paid"])
        self.assertEqual(
            active_warning.details["remaining_technology_wood_cost"], 0
        )
        self.assertEqual(active_warning.details["required_wood"], 35)

    def test_wood_supply_lock_respects_recoverable_surface_wood_and_existing_camp(self) -> None:
        system = self.technology_system()
        recoverable = self.make_state()
        recoverable.resources.wood = 49
        self._deplete_surface_resource(recoverable, "wood")
        point = recoverable.surface_resource_points["surface-wood-1"]
        point.remaining_amount = 1
        point.is_depleted = False
        self.assertFalse(
            any(
                item.warning_id
                == "technology.wood_supply_irreversibly_locked"
                for item in system.evaluate_risks(recoverable)
            )
        )

        established = self.make_state()
        established.technologies.researched_tech_ids.append(
            "tech_wood_processing_1"
        )
        built = self.execute(
            self.building_system(),
            established,
            BUILD_COMMAND,
            {
                "building_type": "logging_camp",
                "zone": "outer_ring",
                "binding_id": "forest-zone-1",
            },
        )
        self.assertTrue(built.accepted)
        established.resources.wood = 0
        self._deplete_surface_resource(established, "wood")
        self.assertFalse(
            any(
                item.warning_id
                == "technology.wood_supply_irreversibly_locked"
                for item in system.evaluate_risks(established)
            )
        )

    def test_final_frost_boundary_excludes_uncollectable_surface_wood(self) -> None:
        system = self.technology_system()
        state = self.make_state()
        state.calendar.current_day = 48
        state.resources.wood = 49
        self._deplete_surface_resource(state, "wood")
        point = state.surface_resource_points["surface-wood-1"]
        point.remaining_amount = 100
        point.is_depleted = False

        self.assertFalse(
            any(
                item.warning_id
                == "technology.wood_supply_irreversibly_locked"
                for item in system.evaluate_risks(state)
            )
        )

        point.remaining_amount = 0
        point.is_depleted = True
        self.assertTrue(
            any(
                item.warning_id
                == "technology.wood_supply_irreversibly_locked"
                for item in system.evaluate_risks(state)
            )
        )

        state.calendar.current_day = 49
        point.remaining_amount = 100
        point.is_depleted = False
        warning = next(
            item
            for item in system.evaluate_risks(state)
            if item.warning_id
            == "technology.wood_supply_irreversibly_locked"
        )
        self.assertEqual(warning.details["remaining_surface_wood"], 100)
        self.assertEqual(warning.details["recoverable_surface_wood"], 0)
        self.assertEqual(warning.details["recoverable_wood"], 49)

    def test_wood_supply_lock_is_exposed_in_formal_end_day_preview(self) -> None:
        state = self.make_state()
        state.resources.wood = 49
        self._deplete_surface_resource(state, "wood")

        execution = self.engine().execute(
            state,
            CommandRequest(
                "wood-lock-preview",
                END_DAY_COMMAND,
                expected_state_sequence=state.command_sequence,
            ),
        )

        self.assertEqual(
            execution.result.code,
            ErrorCode.END_DAY_CONFIRMATION_REQUIRED,
        )
        warning = next(
            item
            for item in execution.warnings
            if item.warning_id
            == "technology.wood_supply_irreversibly_locked"
        )
        self.assertEqual(warning.details["required_wood"], 50)
        self.assertEqual(warning.details["recoverable_wood"], 49)
        self.assertEqual(state.command_sequence, 0)

    @staticmethod
    def _deplete_surface_resource(state, resource_type: str) -> None:
        for point in state.surface_resource_points.values():
            if point.resource_type != resource_type:
                continue
            point.remaining_amount = 0
            point.is_depleted = True
            point.assigned_workers = 0
            point.assigned_engineers = 0

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
        install_final_frost_history_stub(engine)
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
            {"tech_id": "tech_drawing_board", "confirm": True},
        )
        cancelled = self.execute(
            self.technology_system(),
            state,
            CANCEL_RESEARCH_COMMAND,
            {"confirm": True},
        )

        self.assertEqual((started.code, cancelled.code), (ErrorCode.OK, ErrorCode.OK))
        rule = self.technology_rules.technologies["tech_drawing_board"]
        self.assertEqual(state.resources.wood, wood_before - rule.wood_cost)
        self.assertEqual(state.resources.steel, steel_before - rule.steel_cost)
        self.assertIsNone(state.technologies.active_research_id)
        self.assertEqual(cancelled.data["refund"], {"wood": 0, "steel": 0})

    def test_patch038_start_research_requires_fact_complete_confirmation(self) -> None:
        state = self.make_state()
        self.add_research_institute(state)
        system = self.technology_system()
        before = deepcopy(state)

        preview = self.execute(
            system,
            state,
            RESEARCH_COMMAND,
            {"tech_id": "tech_drawing_board"},
        )

        self.assertEqual(preview.code, ErrorCode.ILLEGAL_COMMAND)
        self.assertEqual(preview.data["reason"], "confirmation_required")
        self.assertEqual(
            preview.data["confirmation_text_id"],
            "research.confirm.body",
        )
        self.assertEqual(
            preview.data["confirmation_text"],
            "确认开始研究「绘图板」？本次研究将立即投入 10 木材与 0 钢材。"
            "研究完成前，这些资源不会返还；若中途取消，"
            "已经投入的资源与研究进度都将损失。",
        )
        self.assertEqual(preview.data["technology_id"], "tech_drawing_board")
        self.assertEqual(preview.data["technology_name"], "绘图板")
        self.assertEqual(preview.data["resource_cost"], {"wood": 10, "steel": 0})
        self.assertEqual(preview.data["research_days"], 1)
        self.assertEqual(preview.data["research_required_units"], 4)
        self.assertEqual(preview.data["payment_timing"], "on_start")
        self.assertEqual(
            preview.data["cancellation_refund"],
            {"wood": 0, "steel": 0},
        )
        self.assertFalse(preview.data["cancellation_progress_retained"])
        self.assertEqual(state, before)

        explicit_false = self.execute(
            system,
            state,
            RESEARCH_COMMAND,
            {"tech_id": "tech_drawing_board", "confirm": False},
        )
        self.assertEqual(explicit_false.code, ErrorCode.ILLEGAL_COMMAND)
        self.assertEqual(
            explicit_false.data["reason"],
            "confirm_false_is_not_preview",
        )
        self.assertEqual(state, before)

        spec = next(
            item for item in system.command_specs() if item.name == RESEARCH_COMMAND
        )
        self.assertEqual(spec.optional_arguments["confirm"].value, "BOOLEAN")
        self.assertEqual(
            spec.argument_semantics["confirm"],
            "explicit_true_only_never_preview",
        )

        accepted = self.execute(
            system,
            state,
            RESEARCH_COMMAND,
            {"tech_id": "tech_drawing_board", "confirm": True},
        )
        self.assertEqual(accepted.code, ErrorCode.OK)
        self.assertEqual(
            state.technologies.active_research_id,
            "tech_drawing_board",
        )
        self.assertEqual(state.resources.wood, before.resources.wood - 10)
        self.assertEqual(state.resources.steel, before.resources.steel)

    def test_patch037_cancel_research_requires_fact_complete_confirmation(self) -> None:
        state = self.make_state()
        self.add_research_institute(state)
        system = self.technology_system()
        started = self.execute(
            system,
            state,
            RESEARCH_COMMAND,
            {"tech_id": "tech_drawing_board", "confirm": True},
        )
        self.assertEqual(started.code, ErrorCode.OK)
        state.technologies.research_progress_units = 2
        before = deepcopy(state)

        preview = self.execute(system, state, CANCEL_RESEARCH_COMMAND)

        self.assertEqual(preview.code, ErrorCode.ILLEGAL_COMMAND)
        self.assertEqual(preview.data["reason"], "confirmation_required")
        self.assertEqual(
            preview.data["confirmation_text_id"],
            "research.cancel.confirm",
        )
        self.assertEqual(
            preview.data["confirmation_text"],
            "确认取消正在进行的「绘图板」研究？"
            "已经投入的木材与钢材不会返还，当前研究进度也会清零。",
        )
        self.assertEqual(preview.data["active_research_id"], "tech_drawing_board")
        self.assertEqual(preview.data["active_research_name"], "绘图板")
        self.assertEqual(preview.data["paid_resources"], {"wood": 10, "steel": 0})
        self.assertEqual(preview.data["research_progress_units"], 2)
        self.assertEqual(preview.data["research_required_units"], 4)
        self.assertEqual(preview.data["refund"], {"wood": 0, "steel": 0})
        self.assertEqual(state, before)

        explicit_false = self.execute(
            system,
            state,
            CANCEL_RESEARCH_COMMAND,
            {"confirm": False},
        )
        self.assertEqual(explicit_false.code, ErrorCode.ILLEGAL_COMMAND)
        self.assertEqual(
            explicit_false.data["reason"],
            "confirm_false_is_not_preview",
        )
        self.assertEqual(state, before)

        spec = next(
            item
            for item in system.command_specs()
            if item.name == CANCEL_RESEARCH_COMMAND
        )
        self.assertNotIn("confirm", spec.required_arguments)
        self.assertEqual(spec.optional_arguments["confirm"].value, "BOOLEAN")
        self.assertEqual(spec.pre_execution_text_id, "research.cancel.confirm")
        self.assertEqual(
            spec.argument_semantics["confirm"],
            "explicit_true_only_never_preview",
        )

        cancelled = self.execute(
            system,
            state,
            CANCEL_RESEARCH_COMMAND,
            {"confirm": True},
        )
        self.assertEqual(cancelled.code, ErrorCode.OK)
        self.assertIsNone(state.technologies.active_research_id)
        self.assertEqual(state.technologies.research_progress_units, 0)
        self.assertEqual(cancelled.data["refund"], {"wood": 0, "steel": 0})

        no_active = self.execute(
            system,
            state,
            CANCEL_RESEARCH_COMMAND,
        )
        self.assertEqual(no_active.code, ErrorCode.ILLEGAL_COMMAND)
        self.assertEqual(no_active.data["reason"], "no_active_research")

    def test_patch034_research_notice_and_resource_failure_text_are_exact(self) -> None:
        state = self.make_state()
        self.add_research_institute(state)
        state.resources.wood = 0
        state.resources.steel = 0
        before = deepcopy(state)
        system = self.technology_system()

        rejected = self.execute(
            system,
            state,
            RESEARCH_COMMAND,
            {"tech_id": "tech_furnace_coal_saving_1"},
        )

        self.assertEqual(rejected.code, ErrorCode.ILLEGAL_COMMAND)
        self.assertEqual(rejected.data["reason"], "insufficient_resources")
        self.assertEqual(
            rejected.data["missing_resources"],
            {"wood": 20, "steel": 5},
        )
        self.assertEqual(
            rejected.data["feedback_text_id"],
            "research.resource.not_enough",
        )
        self.assertEqual(
            rejected.data["feedback_text"],
            "当前资源不足，无法开始这项研究。还缺少：木材 20、钢材 5。",
        )
        self.assertEqual(state, before)

        research_spec = next(
            spec
            for spec in system.command_specs()
            if spec.name == RESEARCH_COMMAND
        )
        self.assertNotIn("confirm", research_spec.required_arguments)
        self.assertEqual(
            research_spec.optional_arguments["confirm"].value,
            "BOOLEAN",
        )
        self.assertEqual(
            research_spec.pre_execution_text_id,
            "research.confirm.body",
        )
        self.assertEqual(
            system.research_start_notice()["confirmation_required"],
            True,
        )

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
            {"tech_id": "tech_drawing_board", "confirm": True},
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
            {"tech_id": "tech_drawing_board", "confirm": True},
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

    def test_patch039_structural_deferred_research_unlocks_overload_without_own_effect(self) -> None:
        state = self.make_state()
        self.add_research_institute(state)
        state.technologies.researched_tech_ids.append("tech_drawing_board")
        system = self.technology_system()
        before = deepcopy(state)
        sample_building = next(iter(state.buildings.values()))

        started = self.execute(
            system,
            state,
            RESEARCH_COMMAND,
            {"tech_id": "tech_furnace_power_stability_1", "confirm": True},
        )

        self.assertEqual(started.code, ErrorCode.OK)
        view = {
            item["tech_id"]: item for item in system.view(state)
        }["tech_furnace_power_stability_1"]
        self.assertEqual(view["status"], "researching")
        self.assertEqual(view["technology_class"], "structural_prerequisite")
        self.assertTrue(view["new_research_allowed"])
        self.assertEqual(view["effect_status"], "DEFERRED")

        state.technologies.research_progress_units = (
            state.technologies.research_required_units
            - self.technology_rules.research.progress_units_per_day
        )
        completed = self.settle(self.engine(), state)

        self.assertEqual(completed.result.code, ErrorCode.OK)
        self.assertIn(
            "tech_furnace_power_stability_1",
            state.technologies.researched_tech_ids,
        )
        state.technologies.researched_tech_ids.extend(
            ["tech_drafting_instrument", "tech_mechanical_calculator"]
        )
        state.resources.wood = max(state.resources.wood, 100)
        state.resources.steel = max(state.resources.steel, 100)
        reachable = self.execute(
            system,
            state,
            RESEARCH_COMMAND,
            {"tech_id": "tech_overload_tuning"},
        )
        self.assertEqual(reachable.code, ErrorCode.ILLEGAL_COMMAND)
        self.assertEqual(reachable.data["reason"], "confirmation_required")

        after = deepcopy(before)
        after.technologies.researched_tech_ids.append(
            "tech_furnace_power_stability_1"
        )
        self.assertEqual(
            furnace_coal_cost(before, self.survival_rules, 2),
            furnace_coal_cost(after, self.survival_rules, 2),
        )
        self.assertEqual(
            projected_building_insulation_bonus(before, sample_building),
            projected_building_insulation_bonus(after, sample_building),
        )
        self.assertEqual(
            projected_heat_bonus(before, self.building_rules),
            projected_heat_bonus(after, self.building_rules),
        )
        self.assertEqual(
            projected_overload_pressure_growth(
                before, self.technology_rules, 1, 20
            ),
            projected_overload_pressure_growth(
                after, self.technology_rules, 1, 20
            ),
        )

    def test_patch039_ordinary_deferred_technologies_cannot_start(self) -> None:
        deferred_ids = {
            "tech_scattered_gathering_tools",
            "tech_sheltered_gathering_shed_improvement",
            "tech_deep_well_mine_frame",
            "tech_deep_coal_seam_extraction",
            "tech_deep_steel_seam_extraction",
            "tech_hunting_equipment",
            "tech_field_cold_weather_equipment",
        }
        system = self.technology_system()

        for tech_id in sorted(deferred_ids):
            with self.subTest(tech_id=tech_id):
                state = self.make_state()
                before = deepcopy(state)
                result = self.execute(
                    system,
                    state,
                    RESEARCH_COMMAND,
                    {"tech_id": tech_id, "confirm": True},
                )
                view = {
                    item["tech_id"]: item for item in system.view(state)
                }[tech_id]

                self.assertEqual(result.code, ErrorCode.ILLEGAL_COMMAND)
                self.assertEqual(
                    result.data["reason"],
                    "technology_not_available_for_application",
                )
                self.assertEqual(
                    result.data["feedback_text"],
                    "该研究目前尚无法投入实际应用。",
                )
                self.assertEqual(result.data["availability"], "unavailable")
                self.assertEqual(state, before)
                self.assertEqual(view["status"], "unavailable")
                self.assertEqual(view["effect_status"], "DEFERRED")
                self.assertEqual(
                    view["technology_class"], "unavailable_application"
                )
                self.assertFalse(view["new_research_allowed"])
                self.assertEqual(
                    view["description_text"],
                    "该研究目前尚无法投入实际应用。",
                )

    def test_patch039_legacy_completed_and_active_deferred_research_are_preserved(self) -> None:
        system = self.technology_system()
        completed_state = self.make_state()
        completed_state.technologies.researched_tech_ids.append(
            "tech_hunting_equipment"
        )

        restored = decode_game_state(encode_game_state(completed_state))
        system.validate_state(restored)
        completed_view = {
            item["tech_id"]: item for item in system.view(restored)
        }["tech_hunting_equipment"]
        self.assertEqual(completed_view["status"], "completed")
        self.assertFalse(completed_view["new_research_allowed"])

        active_state = self.make_state()
        self.add_research_institute(active_state)
        rule = self.technology_rules.technologies["tech_hunting_equipment"]
        active_state.technologies.active_research_id = rule.tech_id
        active_state.technologies.research_required_units = (
            rule.research_days
            * self.technology_rules.research.progress_units_per_day
        )
        active_state.technologies.research_progress_units = (
            active_state.technologies.research_required_units
            - self.technology_rules.research.progress_units_per_day
        )
        active_state = decode_game_state(encode_game_state(active_state))
        active_view = {
            item["tech_id"]: item for item in system.view(active_state)
        }[rule.tech_id]
        self.assertEqual(active_view["status"], "researching")

        settled = self.settle(self.engine(), active_state)

        self.assertEqual(settled.result.code, ErrorCode.OK)
        self.assertIn(rule.tech_id, active_state.technologies.researched_tech_ids)
        self.assertIsNone(active_state.technologies.active_research_id)

    def test_second_institute_is_speed_only_and_uses_exact_one_point_five(self) -> None:
        state = self.make_state()
        self.add_research_institute(state)
        self.add_research_institute(state)
        state.technologies.researched_tech_ids.append("tech_drawing_board")
        started = self.execute(
            self.technology_system(),
            state,
            RESEARCH_COMMAND,
            {"tech_id": "tech_drafting_instrument", "confirm": True},
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
            {"tech_id": "tech_drawing_board", "confirm": True},
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
        seed_final_frost_history(state)
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
        del legacy["final_frost"]["balance_profile_id"]
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
                del legacy["final_frost"]["balance_profile_id"]
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
            lambda data: data["technologies"][
                "tech_field_cold_weather_equipment"
            ].update({"effect_kind": "passive", "effect_status": "ACTIVE"}),
            lambda data: data["technologies"][
                "tech_furnace_power_stability_1"
            ].update({"effect_kind": "passive", "effect_status": "ACTIVE"}),
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

    def test_settled_overload_cannot_fall_back_to_a_lower_active_level(self) -> None:
        state = self.make_state()
        self.unlock_overload(state, 2)
        state.resources.coal = 300
        result = self.settle(self.engine(), state)
        self.assertEqual(result.result.code, ErrorCode.OK)

        forged = encode_game_state(state)
        forged["daily_survival"].update(
            {
                "effective_overload_level": 1,
                "overload_coal_paid": 25,
                "overload_temperature_bonus": 8,
                "heating_shortfall": True,
            }
        )

        with self.assertRaises(SaveDataError):
            decode_game_state(forged)

    def test_daily_target_overload_must_be_unlocked(self) -> None:
        state = self.make_state()
        state.resources.coal = 300
        result = self.settle(self.engine(), state)
        self.assertEqual(result.result.code, ErrorCode.OK)

        forged = encode_game_state(state)
        forged["daily_survival"].update(
            {
                "target_overload_level": 2,
                "heating_shortfall": True,
            }
        )
        decoded = decode_game_state(forged)

        with self.assertRaises(SaveDataError):
            validate_game_state(
                decoded,
                self.building_rules,
                self.survival_rules,
                self.technology_rules,
            )

    def test_unlocked_target_overload_can_fail_as_a_whole(self) -> None:
        state = self.make_state()
        self.unlock_overload(state, 2)
        state.resources.coal = self.survival_rules.furnace_levels[1].coal_cost

        result = self.settle(self.engine(), state)

        self.assertEqual(result.result.code, ErrorCode.OK)
        self.assertEqual(state.daily_survival.target_overload_level, 2)
        self.assertEqual(state.daily_survival.effective_overload_level, 0)
        self.assertEqual(state.daily_survival.overload_coal_paid, 0)
        self.assertEqual(state.daily_survival.overload_temperature_bonus, 0)
        validate_game_state(
            state,
            self.building_rules,
            self.survival_rules,
            self.technology_rules,
        )

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
