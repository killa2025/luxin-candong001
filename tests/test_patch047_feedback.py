from __future__ import annotations

import itertools
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

import test_final_frost as frost_tests
from furnace_winter import GameSession
from furnace_winter.gameplay import EndDayStage, SurvivalSystem
from furnace_winter.interface import ArgumentKind, CommandCatalog, CommandSpec, ErrorCode
from furnace_winter.models import decode_game_state, encode_game_state
from furnace_winter.text import build_event_text_registry


ROOT = Path(__file__).resolve().parents[1]


class Patch047FeedbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        frost_tests.FinalFrostPatchTests.setUpClass()

    def setUp(self):
        self.fixture = frost_tests.FinalFrostPatchTests()
        self.system = self.fixture.system()

    def prepared_state(self):
        state = self.fixture.make_state(day=48)
        self.fixture.set_population(state, healthy=20, housed=20)
        state.resources.coal = 1400
        state.resources.cooked_food = 200
        state.furnace.is_active = True
        state.furnace.mode_id = "level_3"
        # A complete, legal late-game configuration; no gameplay balance override.
        state.technologies.researched_tech_ids = sorted(self.fixture.technology.technologies)
        state.old_city.is_unlocked = True
        state.old_city.reference_population = 20
        state.old_city.low_threshold = 10
        state.old_city.middle_threshold = 18
        state.old_city.high_threshold = 28
        state.old_city.stage_events_seen = ["southern_letter", "rumors", "public_gathering", "countdown"]
        state.old_city.countdown_day = 48
        state.old_city.resolved = True
        state.old_city.result_id = "scattered"
        state.old_city.settlement_day = 48
        state.old_city.settlement_member_count = 8
        state.old_city.settlement_resource_losses = dict.fromkeys(
            ["coal", "wood", "steel", "cooked_food"], 0
        )
        return state

    def test_base_coal_shortage_ignores_overload_but_not_unpaid_base_or_woodfuel(self):
        # Full payment, unpaid optional overload, true base shortage, woodfuel,
        # no overload, and furnace-off cases use the real heating settlement.
        for coal, level, overload, woodfuel, expected in (
            (200, 3, 1, False, False),
            (200, 3, 2, False, False),
            (120, 3, 2, False, False),
            (119, 3, 0, False, True),
            (119, 3, 2, False, True),
            (119, 3, 0, True, True),
            (120, 3, 0, False, False),
            (0, 0, 0, False, False),
        ):
            with self.subTest(coal=coal, overload=overload, woodfuel=woodfuel):
                state = self.prepared_state()
                state.calendar.current_day = 49
                state.resources.coal = coal
                state.resources.wood = 100
                state.furnace.mode_id = f"level_{level}" if level else "off"
                state.furnace.is_active = level > 0
                state.furnace.overload_level = overload
                state.building_management.woodfuel_confirmed_today = woodfuel
                context = self.fixture.context(state, 49, EndDayStage.READ_FINAL_PLAN)
                survival = SurvivalSystem(self.fixture.survival, self.fixture.buildings, self.fixture.technology)
                survival.settle_heating(context)
                self.system.capture_daily_record(context)
                self.assertEqual(state.final_frost.daily_records["49"].coal_shortage, expected)
                if coal == 120 and overload == 2:
                    self.assertEqual(state.daily_survival.overload_coal_paid, 0)

    def test_full_d48_d55_overload_pipeline_save_logs_and_rollback(self):
        state = self.prepared_state()
        engine, events, oath = self.fixture.full_engine()
        events.initialize_day(state)
        before_55 = None
        for day in range(48, 56):
            self.fixture.resolve_active_events(events, state)
            self.fixture.resolve_pending_old_city(oath, state)
            state.furnace.overload_level = 1 if day < 54 else 2
            if day == 55:
                before_55 = deepcopy(state)
            execution = self.fixture.settle(engine, state, f"p047-day-{day}")
            self.assertEqual(execution.result.code, ErrorCode.OK, execution.result.data)
            self.assertEqual(decode_game_state(encode_game_state(state)), state)
            if day >= 49:
                self.assertFalse(state.final_frost.daily_records[str(day)].coal_shortage)
                log = next(item for item in execution.logs if item.code == "final_frost.day.recorded")
                self.assertEqual(log.payload["base_coal_required"], 120)
                self.assertEqual(log.payload["base_coal_paid"], 120)
                self.assertFalse(log.payload["coal_shortage"])
        self.assertGreater(state.final_result.system_scores["coal_and_core"], 0)
        self.assertNotIn("coal_desperate", state.final_result.ending_tags)
        self.assertEqual(state.calendar.current_day, 55)

        failed = deepcopy(before_55)
        failed_engine, _, _ = self.fixture.full_engine(autosave_sink=lambda _: (_ for _ in ()).throw(OSError("test")))
        execution = self.fixture.settle(failed_engine, failed, "p047-fail-save")
        self.assertEqual(execution.result.code, ErrorCode.INTERNAL_ERROR)
        self.assertEqual(failed, before_55)
        self.assertNotIn("55", failed.final_frost.daily_records)

    def test_old_records_and_generated_report_are_not_recalculated_on_load(self):
        state = self.prepared_state()
        engine, events, oath = self.fixture.full_engine()
        events.initialize_day(state)
        for day in range(48, 56):
            self.fixture.resolve_active_events(events, state)
            self.fixture.resolve_pending_old_city(oath, state)
            execution = self.fixture.settle(engine, state, f"legacy-{day}")
            self.assertEqual(execution.result.code, ErrorCode.OK, execution.result.data)
            if day == 49:
                # Old saved fact is deliberately retained, not inferred from later stocks.
                state.final_frost.daily_records["49"].coal_shortage = True
        before = encode_game_state(state)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.json"
            path.write_text(json.dumps(before), encoding="utf-8")
            original = path.read_bytes()
            session = GameSession.load(path, config_dir=ROOT / "data")
            observation = session.observe()
            self.assertTrue(observation.state.final_frost.daily_records["49"].coal_shortage)
            self.assertEqual(encode_game_state(observation.state), before)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(observation.state.final_result.report, state.final_result.report)

    def test_cap_contract_matches_previous_logic_for_all_score_combinations(self):
        order = ["high_victory", "standard_victory", "bitter_victory", "collapse_survival", "ember_survival"]
        state = self.prepared_state()
        keys = ["coal_and_core", "food", "housing_and_temperature", "medical_and_disease", "trust_and_panic", "population_and_death"]
        for profile in ("legacy_patch021", "patch022", "patch045"):
            state.final_frost.balance_profile_id = profile
            for values in itertools.product(range(5), repeat=6):
                scores = dict(zip(keys, values))
                zeros = values.count(0)
                cap = 0
                if zeros or (profile != "legacy_patch021" and min(values) < 3):
                    cap = 1
                if values[0] <= 1 or values[5] <= 1:
                    cap = 2
                if zeros >= 3:
                    cap = 3
                if zeros >= 5:
                    cap = 4
                base = self.system._result_for_total(state, sum(values))
                self.assertEqual(self.system._apply_result_caps(state, scores, base), order[max(order.index(base), cap)])

    def test_death_boundary_and_wood_lock_preserve_worst_cap(self):
        state = self.prepared_state()
        scores = dict.fromkeys(["coal_and_core", "food", "housing_and_temperature", "medical_and_disease", "trust_and_panic", "population_and_death"], 4)
        state.population.population_total_ever = 100
        for profile in ("legacy_patch021", "patch022", "patch045"):
            state.final_frost.balance_profile_id = profile
            check = next(item for item in self.system._result_cap_checks(state, scores) if item["id"] == "death_ratio")
            limit = check["death_ratio_percent"]
            state.population.population_dead = limit
            self.assertEqual(self.system._apply_result_caps(state, scores, "high_victory"), "high_victory")
            state.population.population_dead = limit + 1
            self.assertEqual(self.system._apply_result_caps(state, scores, "high_victory"), "standard_victory")
            state.final_frost.wood_supply_locked = True
            self.assertEqual(self.system._apply_result_caps(state, scores, "high_victory"), "collapse_survival")
            self.assertEqual(self.system._apply_result_caps(state, dict.fromkeys(scores, 0), "high_victory"), "ember_survival")
            state.final_frost.wood_supply_locked = False

    def test_cap_explanation_discloses_actual_downgrade_without_rescoring(self):
        state = self.prepared_state()
        final = state.final_result
        final.is_finalized = True
        final.system_scores = dict.fromkeys(["coal_and_core", "food", "housing_and_temperature", "medical_and_disease", "trust_and_panic", "population_and_death"], 4)
        final.system_scores["coal_and_core"] = 0
        final.total_score = 20
        final.ending_id = "bitter_victory"
        before = deepcopy(state)
        explanation = self.system.score_explanation(state)
        self.assertEqual(explanation["total_score_result_id"], "standard_victory")
        self.assertEqual(explanation["recorded_result_id"], "bitter_victory")
        self.assertEqual(explanation["downgrading_cap_ids"], ["coal_system_critical"])
        self.assertEqual(state, before)

    def test_normal_memorial_and_request_shape_are_discoverable_without_rejection(self):
        session = GameSession.new(config_dir=ROOT / "data", seed=47047)
        before = deepcopy(session.observe().state)
        contract = session.observe().protocol_contract["play_envelopes"]["command_request_contract"]
        self.assertEqual(contract["request_fields"]["required"], ["name"])
        self.assertEqual(contract["request_shape"]["arguments"], "OBJECT")
        self.assertNotIn("game.set_furnace", json.dumps(contract))
        memorial = session.rules_view("laws")["interface_text"]["action_rules"]["memorial"]
        self.assertTrue(memorial["requires_recorded_death"])
        self.assertFalse(memorial["recorded_death_requirement_satisfied"])
        self.assertEqual(memorial["requires_built_building_type"], "cemetery")
        specs = {spec.name: spec for spec in session.command_specs()}
        for name in ("game.assign", "game.unassign", "game.assign_resource", "game.unassign_resource"):
            self.assertEqual(specs[name].argument_minimums, {"count": 1})
        self.assertEqual(session.observe().state, before)

    def test_minimum_metadata_rejects_noninteger_and_unknown_fields(self):
        for arguments, minimums in (({}, {"count": 1}), ({"count": ArgumentKind.STRING}, {"count": 1}), ({"count": ArgumentKind.INTEGER}, {"count": True})):
            with self.assertRaises(ValueError):
                CommandCatalog().register(CommandSpec(name="test.minimum", required_arguments=arguments, argument_minimums=minimums))

    def test_d49_acknowledge_has_user_confirmed_text_and_authoritative_source(self):
        state = self.fixture.make_state(day=49)
        self.system.prepare_new_day(state)
        _, events, _ = self.fixture.full_engine()
        events.initialize_day(state)
        view = next(view for view in events.active_event_views(state) if view["event_id"] == "seventh_frost_start")
        self.assertEqual(view["options"][0]["text"], "守住炉城。")
        entry = build_event_text_registry().require("event.seventh_frost_start.option_a")
        self.assertIn("PATCH-047", entry.source)
        self.assertIn("> 守住炉城。", (ROOT / entry.source).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
