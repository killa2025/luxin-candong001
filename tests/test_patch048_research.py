from __future__ import annotations

import json
import shutil
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

from furnace_winter import GameSession
from furnace_winter.config import (
    TechnologyConfigError,
    load_technology_rules,
    validate_config_tree,
)
from furnace_winter.gameplay.end_day import EndDayStage
from furnace_winter.interface import ErrorCode
from furnace_winter.models import SaveDataError, decode_game_state, encode_game_state, dumps

ROOT = Path(__file__).resolve().parents[1]


class ResearchStaffingTests(unittest.TestCase):
    def session(self, path=None):
        return GameSession.new(config_dir=ROOT / "data", save_path=path, seed=48048,
                               map_mode="manual", map_key="black_ash_lowland")

    def command(self, game, name, arguments=None):
        result = game.command(name, arguments or {})
        self.assertEqual(result.result.code, ErrorCode.OK, result.result)
        return result

    def institute(self, game, engineers=1):
        built = self.command(game, "game.build", {
            "building_type": "research_institute", "zone": "middle_ring",
        })
        key = built.result.data["building_id"]
        if engineers:
            self.command(game, "game.assign", {
                "building_id": key, "population_type": "engineers", "count": engineers,
            })
        return key

    def settle(self, game):
        result = game.command("game.end_day")
        if result.result.code == ErrorCode.END_DAY_CONFIRMATION_REQUIRED:
            result = game.command("game.confirm_end_day", result.result.data["confirmation"])
        return result

    def test_single_institute_scales_exactly_and_zero_staff_pauses(self):
        game = self.session()
        key = self.institute(game)
        for count, expected in [(1, 4), (2, 8), (5, 20), (7, 28), (10, 40)]:
            self.command(game, "game.assign", {
                "building_id": key, "population_type": "engineers", "count": count,
            })
            self.assertEqual(game.technologies.research_speed_view(game.state)["potential_progress_tenths"], expected)
        self.command(game, "game.unassign", {"building_id": key, "population_type": "engineers"})
        self.assertEqual(game.observe().research_view["potential_progress_tenths"], 0)

    def test_two_institutes_rank_after_target_only_overtime_without_id_bias(self):
        game = self.session()
        a, b = self.institute(game, 7), self.institute(game, 8)
        state = deepcopy(game.state)
        # Arithmetic fixtures isolate the research formula; no illegal state is saved.
        for counts, overtime, expected in [((1, 1), None, 6), ((10, 10), None, 60),
                                           ((10, 10), a, 80), ((7, 8), a, 58),
                                           ((10, 0), a, 60)]:
            state.buildings[a].assigned_engineers, state.buildings[b].assigned_engineers = counts
            state.buildings[a].is_operational = counts[0] > 0
            state.buildings[b].is_operational = counts[1] > 0
            state.social_policy.overtime_building_id = overtime
            view = game.technologies.research_speed_view(state)
            self.assertEqual(view["potential_progress_tenths"], expected)
            swapped = deepcopy(state)
            swapped.buildings[a], swapped.buildings[b] = swapped.buildings[b], swapped.buildings[a]
            self.assertEqual(game.technologies.research_speed_view(swapped)["potential_progress_tenths"], expected)
        state.buildings[a].is_operational = False
        self.assertEqual(game.technologies.research_speed_view(state)["potential_progress_tenths"], 0)

    def test_fractional_progress_survives_main_autosave_reload_and_replay(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "game.json"
            game = self.session(path)
            key = self.institute(game)
            self.command(game, "game.research", {"tech_id": "tech_drawing_board", "confirm": True})
            result = self.settle(game)
            self.assertEqual(result.result.code, ErrorCode.OK)
            self.assertEqual(game.state.technologies.research_progress_units, 0)
            self.assertEqual(game.state.technologies.research_remainder_tenths, 4)
            auto = json.loads(game.autosave_path.read_text(encoding="utf-8"))
            self.assertEqual(auto["state"]["technologies"]["research_remainder_tenths"], 4)
            self.assertEqual(auto["resume_stage"], "advance_day")
            replay = json.loads(dumps(game.replay_document()))
            advanced = [log for entry in replay["entries"] for log in entry["logs"]
                        if log["code"] == "technology.research.advanced"]
            self.assertEqual(advanced[-1]["payload"]["progress_added_tenths"], 4)
            loaded = GameSession.load(path, config_dir=ROOT / "data")
            self.assertEqual(encode_game_state(game.state), encode_game_state(loaded.state))
            for session in (game, loaded):
                self.command(session, "game.assign", {"building_id": key, "population_type": "engineers", "count": 10})
                result = self.settle(session)
                self.assertEqual(result.result.code, ErrorCode.OK)
                self.assertIn("tech_drawing_board", session.state.technologies.researched_tech_ids)
                self.assertEqual(session.state.technologies.research_remainder_tenths, 0)
                logs = json.loads(dumps(session.replay_document()))["entries"][-1]["logs"]
                advance = next(log["payload"] for log in logs if log["code"] == "technology.research.advanced")
                self.assertEqual(advance["discarded_completion_overflow_tenths"], 4)
                self.assertEqual(advance["research_remainder_tenths"], 0)
            self.assertEqual(encode_game_state(game.state), encode_game_state(loaded.state))

    def test_cancel_discards_fraction_and_does_not_transfer_or_refund(self):
        game = self.session()
        self.institute(game)
        self.command(game, "game.research", {"tech_id": "tech_drawing_board", "confirm": True})
        self.assertEqual(self.settle(game).result.code, ErrorCode.OK)
        wood = game.state.resources.wood
        self.command(game, "game.cancel_research", {"confirm": True})
        self.assertEqual(game.state.technologies.research_remainder_tenths, 0)
        self.assertEqual(game.state.resources.wood, wood)
        self.command(game, "game.research", {"tech_id": "tech_housing_insulation_1", "confirm": True})
        self.assertEqual(game.state.technologies.research_remainder_tenths, 0)

    def test_old_v18_progress_keeps_legacy_speed_and_frost_profile(self):
        with TemporaryDirectory() as temp:
            game = self.session()
            self.institute(game)
            self.command(game, "game.research", {"tech_id": "tech_drawing_board", "confirm": True})
            document = encode_game_state(game.state)
            document["save_data_version"] = 18
            document["technologies"].pop("research_profile_id")
            document["technologies"].pop("research_remainder_tenths")
            document["technologies"]["research_progress_units"] = 1
            path = Path(temp) / "legacy.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            loaded = GameSession.load(path, config_dir=ROOT / "data")
            self.assertEqual(loaded.state.technologies.research_progress_units, 1)
            self.assertEqual(loaded.state.technologies.research_profile_id, "legacy_fixed")
            self.assertEqual(loaded.state.final_frost.balance_profile_id, "patch045")
            self.assertEqual(loaded.observe().research_view["potential_progress_tenths"], 40)
            self.assertEqual(self.settle(loaded).result.code, ErrorCode.OK)
            self.assertIn("tech_drawing_board", loaded.state.technologies.researched_tech_ids)

    def test_strict_remainder_profile_and_version_tampering_rejected(self):
        game = self.session()
        self.institute(game)
        self.command(game, "game.research", {"tech_id": "tech_drawing_board", "confirm": True})
        valid = encode_game_state(game.state)
        for value in [-1, 10, True, 0.4, "4"]:
            document = deepcopy(valid)
            document["technologies"]["research_remainder_tenths"] = value
            with self.assertRaises(SaveDataError):
                decode_game_state(document)
        for mutation in ("missing", "unknown", "legacy_fraction", "inactive_fraction", "v18_forgery"):
            document = deepcopy(valid)
            tech = document["technologies"]
            if mutation == "missing": tech.pop("research_remainder_tenths")
            if mutation == "unknown": tech["research_profile_id"] = "anything"
            if mutation == "legacy_fraction":
                tech["research_profile_id"], tech["research_remainder_tenths"] = "legacy_fixed", 4
            if mutation == "inactive_fraction":
                tech["active_research_id"], tech["research_required_units"], tech["research_remainder_tenths"] = None, 0, 4
            if mutation == "v18_forgery": document["save_data_version"] = 18
            with self.subTest(mutation=mutation), self.assertRaises(SaveDataError):
                decode_game_state(document)

    def test_research_stage_uses_current_staff_and_all_surfaces_agree(self):
        game = self.session()
        key = self.institute(game, 10)
        self.command(game, "game.research", {"tech_id": "tech_drawing_board", "confirm": True})
        before = encode_game_state(game.state)
        view = game.observe().research_view
        self.assertEqual(view, game.rules_view("technologies")["interface_text"]["research_speed"])
        self.assertEqual(view, game.status()["research"]["speed_contract"])
        self.assertEqual(encode_game_state(game.state), before)
        # Simulates an earlier stage releasing staff. Research must not reuse its preview.
        def earlier_stage(context):
            context.state.buildings[key].assigned_engineers = 5
        game.end_day.register_stage_handler(EndDayStage.CLOSE_ACTION_EFFECTS, earlier_stage)
        self.assertEqual(self.settle(game).result.code, ErrorCode.OK)
        self.assertEqual(game.state.technologies.research_progress_units, 2)

    def test_save_or_late_validation_failure_rolls_back_fraction_and_can_retry(self):
        for failure in ("disk", "sink", "validator"):
            with self.subTest(failure=failure), TemporaryDirectory() as temp:
                path = Path(temp) / "game.json"
                game = self.session(path)
                self.institute(game)
                self.command(game, "game.research", {"tech_id": "tech_drawing_board", "confirm": True})
                before, data = encode_game_state(game.state), path.read_bytes()
                old_save, old_sink = game.save, game.end_day._autosave_sink
                def fail(*_): raise OSError("test only")
                def poison(context): context.state.technologies.research_remainder_tenths = 10
                if failure == "disk": game.save = fail
                if failure == "sink": game.end_day._autosave_sink = fail
                if failure == "validator": game.end_day.register_stage_handler(EndDayStage.CAPTURE_DAILY_RECORDS, poison)
                result = self.settle(game)
                self.assertEqual(result.result.code, ErrorCode.INTERNAL_ERROR)
                self.assertEqual(encode_game_state(game.state), before)
                self.assertEqual(path.read_bytes(), data)
                self.assertIsNone(game.end_day.last_autosave())
                self.assertFalse(game.autosave_path.exists())
                if failure != "validator":
                    game.save, game.end_day._autosave_sink = old_save, old_sink
                    self.assertEqual(self.settle(game).result.code, ErrorCode.OK)
                    self.assertEqual(game.state.technologies.research_remainder_tenths, 4)

    def test_configuration_rejects_unconfirmed_staffing_threshold(self):
        source = json.loads((ROOT / "data/technologies.json").read_text(encoding="utf-8"))
        with TemporaryDirectory() as temp:
            path = Path(temp) / "technologies.json"
            for value in [0, 5, 11, True, 10.0]:
                source["research"]["staffing_full_engineers"] = value
                path.write_text(json.dumps(source), encoding="utf-8")
                with self.assertRaises(TechnologyConfigError): load_technology_rules(path)

    def test_complete_config_tree_rejects_inexact_lawful_research_speed(self):
        with TemporaryDirectory() as temp:
            config_dir = Path(temp) / "data"
            shutil.copytree(ROOT / "data", config_dir)
            path = config_dir / "technologies.json"
            document = json.loads(path.read_text(encoding="utf-8"))
            document["research"]["progress_units_per_day"] = 2
            path.write_text(json.dumps(document), encoding="utf-8")

            report = validate_config_tree(config_dir)
            self.assertFalse(report.is_valid)
            self.assertTrue(any(
                issue.location == "$.research"
                and "科研人手精度跨配置校验失败" in issue.message
                for issue in report.issues
            ))
            save_path = Path(temp) / "must-not-exist.json"
            with self.assertRaises(TechnologyConfigError):
                GameSession.new(
                    config_dir=config_dir,
                    save_path=save_path,
                    seed=48048,
                    map_mode="manual",
                    map_key="black_ash_lowland",
                )
            self.assertFalse(save_path.exists())

    def test_overtime_research_speed_command_is_exact_and_atomic(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "game.json"
            game = self.session(path)
            first = self.institute(game, 1)
            self.institute(game, 2)
            self.command(game, "game.sign_law", {"law_id": "overtime_law"})
            before_state = encode_game_state(game.state)
            before_save = path.read_bytes()
            before_replay = game.replay_document()
            original_save = game.save

            def fail_save():
                raise OSError("test only")

            game.save = fail_save
            failed = game.command("game.overtime", {
                "building_id": first,
                "confirm": True,
            })
            self.assertEqual(failed.result.code, ErrorCode.INTERNAL_ERROR, failed.result)
            self.assertEqual(encode_game_state(game.state), before_state)
            self.assertEqual(path.read_bytes(), before_save)
            replay_after_failure = game.replay_document()
            self.assertEqual(replay_after_failure.entries[:-1], before_replay.entries)
            self.assertFalse(replay_after_failure.entries[-1].result.accepted)

            game.save = original_save
            succeeded = game.command("game.overtime", {
                "building_id": first,
                "confirm": True,
            })
            self.assertEqual(succeeded.result.code, ErrorCode.OK)
            self.assertEqual(
                game.status()["research"]["speed_contract"]["potential_progress_tenths"],
                11,
            )
            loaded = GameSession.load(path, config_dir=ROOT / "data")
            self.assertEqual(loaded.status(), game.status())

    def test_fixed_formal_d1_d55_paths_with_reduced_midgame_research(self):
        # Recorded construction probes, NOT blindplay or a runtime recommendation.
        # No state injection, free resources, research completion shortcuts or D56.
        for label, ending, score in [("switch7-v1", "standard_victory", 22),
                                     ("switch5-v1", "high_victory", 24)]:
            with self.subTest(label=label):
                game = GameSession.new(config_dir=ROOT / "data", seed=46047,
                                       map_mode="manual", map_key="black_ash_lowland")
                commands = json.loads((ROOT / "tests/fixtures" / f"patch048_{label}.json").read_text(encoding="utf-8"))
                days = []
                for request in commands:
                    if request["name"] == "game.end_day":
                        days.append(game.state.calendar.current_day)
                        result = self.settle(game)
                    else:
                        result = game.command(request["name"], request["arguments"])
                    self.assertEqual(result.result.code, ErrorCode.OK, result.result)
                self.assertEqual(days, list(range(1, 56)))
                self.assertEqual(game.state.final_result.ending_id, ending)
                self.assertEqual(game.state.final_result.total_score, score)
                self.assertEqual(game.state.population.population_alive, 148)
                self.assertEqual(game.state.population.population_dead, 0)
                self.assertEqual(game.state.calendar.current_day, 55)
                restored = decode_game_state(encode_game_state(game.state))
                self.assertEqual(restored, game.state)

    def test_zero_engineers_preserves_fraction_without_apprentice_contribution(self):
        game = self.session()
        key = self.institute(game)
        self.command(game, "game.research", {"tech_id": "tech_drawing_board", "confirm": True})
        self.assertEqual(self.settle(game).result.code, ErrorCode.OK)
        self.command(game, "game.unassign", {"building_id": key, "population_type": "engineers"})
        self.assertEqual(self.settle(game).result.code, ErrorCode.OK)
        self.assertEqual(game.state.technologies.research_remainder_tenths, 4)
        state = deepcopy(game.state)
        state.buildings[key].assigned_engineering_apprentices = 10
        state.buildings[key].is_operational = True
        self.assertEqual(game.technologies.research_speed_view(state)["potential_progress_tenths"], 0)


if __name__ == "__main__":
    unittest.main()
