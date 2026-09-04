from copy import deepcopy
from io import StringIO
import json
import inspect
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_buildings as fixtures
from furnace_winter import GameSession
from furnace_winter.cli import main
from furnace_winter.gameplay import BUILD_COMMAND, HEAT_COMMAND
from furnace_winter.interface import CommandRequest, ErrorCode
from furnace_winter.interface.observation import Observation
from tests import seed_final_frost_history

ROOT = Path(__file__).resolve().parents[1]


class HeatDiscoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.BuildingPatchTests.setUpClass()

    def setup_target(self, day=55, coal=500):
        fixture = fixtures.BuildingPatchTests()
        state = fixture.make_state()
        state.calendar.current_day = day
        if day >= 49:
            seed_final_frost_history(state)
        state.resources.coal = coal
        state.resources.wood = 500
        state.resources.steel = 500
        system = fixture.make_system()
        result = system.execute(state, CommandRequest("build", BUILD_COMMAND, {
            "building_type": "canteen", "zone": "inner_ring"}))
        self.assertTrue(result.accepted, result)
        return state, system, result.data["building_id"]

    def target(self, system, state, building_id):
        before = deepcopy(state)
        contract = system.heat_target_contract(state)
        self.assertEqual(state, before)
        return next(item for item in contract["targets"] if item["building_id"] == building_id)

    def test_temperature_below_equal_above_threshold_matches_command(self):
        for offset in (-1, 0, 1):
            state, system, bid = self.setup_target()
            threshold = system.rules.buildings["canteen"].min_operating_temperature
            with patch.object(type(system), "_projected_building_temperature", return_value=threshold + offset):
                target = self.target(system, state, bid)
                self.assertEqual(target["eligible_now"], offset < 0)
                self.assertEqual(target["projected_temperature_without_heat"], threshold + offset)
                before = deepcopy(state)
                result = system.execute(state, CommandRequest("heat", HEAT_COMMAND, {"building_id": bid}))
                self.assertEqual(result.accepted, target["eligible_now"])
                if offset >= 0:
                    self.assertEqual(target["first_blocking_reason"], "temperature_already_sufficient")
                    self.assertEqual(result.data, target["blocking_details"])
                    self.assertEqual(state, before)

    def test_real_warm_and_coal_reserve_and_day_lock(self):
        state, system, bid = self.setup_target(day=1)
        self.assertEqual(self.target(system, state, bid)["first_blocking_reason"], "temperature_already_sufficient")
        state, system, bid = self.setup_target(coal=100)
        state.furnace.mode_id = "level_2"
        state.furnace.is_active = True
        target = self.target(system, state, bid)
        self.assertEqual(target["first_blocking_reason"], "insufficient_coal_after_furnace_reserve")
        result = system.execute(state, CommandRequest("heat", HEAT_COMMAND, {"building_id": bid}))
        self.assertEqual(result.data, target["blocking_details"])
        state.calendar.is_day_locked = True
        self.assertEqual(self.target(system, state, bid)["first_blocking_reason"], "day_not_open_for_planning")

    def test_success_then_building_and_city_limits_and_unsupported_type(self):
        state, system, bid = self.setup_target()
        state.laws.signed_law_ids.extend(["basic_medical_law", "child_school_law"])
        ids = [bid]
        for kind in ("medical_station", "school"):
            result = system.execute(state, CommandRequest("build-" + kind, BUILD_COMMAND, {
                "building_type": kind, "zone": "inner_ring"}))
            self.assertTrue(result.accepted, result)
            ids.append(result.data["building_id"])
        self.assertEqual(self.target(system, state, "residence-start-001")["first_blocking_reason"], "building_cannot_heat")
        for index, target_id in enumerate(ids[:2]):
            self.assertTrue(self.target(system, state, target_id)["eligible_now"])
            result = system.execute(state, CommandRequest(f"heat-{index}", HEAT_COMMAND, {"building_id": target_id}))
            self.assertTrue(result.accepted, result)
            self.assertEqual(self.target(system, state, target_id)["first_blocking_reason"], "building_already_heated_today")
        self.assertEqual(self.target(system, state, ids[2])["first_blocking_reason"], "daily_heat_limit_reached")
        result = system.execute(state, CommandRequest("heat-3", HEAT_COMMAND, {"building_id": ids[2]}))
        self.assertEqual(result.data["reason"], "daily_heat_limit_reached")

    def test_session_query_and_rejection_leave_save_and_state_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "main.json"
            session = GameSession.new(config_dir=ROOT / "data", save_path=path, seed=47047)
            built = session.execute_payload({"name": BUILD_COMMAND, "arguments": {"building_type": "canteen", "zone": "inner_ring"}})
            bid = built.result.data["building_id"]
            before = path.read_bytes()
            state = deepcopy(session.state)
            replay = deepcopy(session.replay_document())
            expected = session.observe().heat_view
            view = session.rules_view("buildings")
            self.assertEqual(view["interface_text"]["heat_target_contract"], expected)
            self.assertEqual(view["document"], json.loads((ROOT / "data/buildings.json").read_text(encoding="utf-8-sig")))
            view["interface_text"]["heat_target_contract"]["targets"].clear()
            self.assertEqual(session.observe().heat_view, expected)
            self.assertEqual(session.replay_document(), replay)
            rejected = session.execute_payload({"name": HEAT_COMMAND, "arguments": {"building_id": bid}})
            self.assertEqual(rejected.result.code, ErrorCode.ILLEGAL_COMMAND)
            self.assertEqual(rejected.result.data["reason"], "temperature_already_sufficient")
            self.assertEqual(session.state, state)
            self.assertEqual(path.read_bytes(), before)
            loaded = GameSession.load(path, config_dir=ROOT / "data")
            self.assertEqual(loaded.observe().heat_view, expected)
            self.assertEqual(path.read_bytes(), before)

    def test_formal_json_lines_query_has_same_heat_contract(self):
        self.assertEqual(inspect.signature(Observation).parameters["heat_view"].kind, inspect.Parameter.KEYWORD_ONLY)
        legacy = Observation(1, None, (), (), (), None, (), (), None, None, (), None, None, None, {"legacy": True})
        self.assertEqual(legacy.ending_report_view, {"legacy": True})
        self.assertIsNone(legacy.heat_view)
        with tempfile.TemporaryDirectory() as directory:
            stream = StringIO()
            with patch("sys.stdin", StringIO('{"type":"rules","section":"buildings"}\n{"type":"quit"}\n')), redirect_stdout(stream):
                code = main(["play", str(Path(directory) / "cli.json"), "--data-dir", str(ROOT / "data"), "--new"])
            lines = [json.loads(line) for line in stream.getvalue().splitlines()]
            self.assertEqual(code, 0)
            self.assertEqual(lines[0]["observation"]["heat_view"], lines[1]["rules"]["interface_text"]["heat_target_contract"])
            self.assertFalse(lines[0]["observation"]["heat_view"]["contains_strategy_recommendations"])
