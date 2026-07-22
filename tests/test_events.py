from __future__ import annotations

import unittest
from copy import deepcopy
from pathlib import Path

from furnace_winter.config import (
    load_building_rules,
    load_event_rules,
    load_law_rules,
    load_survival_rules,
    load_technology_rules,
)
from furnace_winter.gameplay import (
    CONFIRM_END_DAY_COMMAND,
    END_DAY_COMMAND,
    RESOLVE_EVENT_COMMAND,
    BuildingSystem,
    EndDayEngine,
    EndDayContext,
    EndDayStage,
    EventSystem,
    LawSystem,
    SurvivalSystem,
    TechnologySystem,
    create_initial_survival_state,
    storage_used,
)
from furnace_winter.interface import CommandRequest, ErrorCode
from furnace_winter.models import (
    CURRENT_SAVE_DATA_VERSION,
    PromiseRecord,
    DeterministicRandom,
    SaveDataError,
    decode_game_state,
    encode_game_state,
)


ROOT = Path(__file__).resolve().parents[1]


class EventPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.survival_rules = load_survival_rules(ROOT / "data" / "survival.json")
        cls.building_rules = load_building_rules(ROOT / "data" / "buildings.json")
        cls.law_rules = load_law_rules(ROOT / "data" / "laws.json")
        cls.technology_rules = load_technology_rules(
            ROOT / "data" / "technologies.json"
        )
        cls.event_rules = load_event_rules(ROOT / "data" / "events.json")

    def make_state(self, *, day: int = 1):
        state = create_initial_survival_state(
            self.survival_rules,
            self.building_rules,
            random_seed=7007,
        )
        state.calendar.current_day = day
        return state

    def event_system(self) -> EventSystem:
        return EventSystem(
            self.event_rules,
            self.building_rules,
            self.survival_rules,
            self.technology_rules,
        )

    def law_system(self) -> LawSystem:
        return LawSystem(
            self.law_rules,
            self.building_rules,
            self.survival_rules,
            self.technology_rules,
        )

    def full_engine(self, autosave_sink=None) -> EndDayEngine:
        engine = EndDayEngine(autosave_sink=autosave_sink)
        SurvivalSystem(
            self.survival_rules,
            self.building_rules,
            self.technology_rules,
        ).install(engine)
        BuildingSystem(
            self.building_rules,
            self.survival_rules,
            self.technology_rules,
        ).install(engine)
        self.law_system().install(engine)
        TechnologySystem(
            self.technology_rules,
            self.building_rules,
            self.survival_rules,
            self.law_rules,
        ).install(engine)
        self.event_system().install(engine)
        return engine

    @staticmethod
    def settle(engine: EndDayEngine, state):
        execution = engine.execute(
            state,
            CommandRequest(
                "end-day",
                END_DAY_COMMAND,
                expected_state_sequence=state.command_sequence,
            ),
        )
        if execution.result.code is ErrorCode.END_DAY_CONFIRMATION_REQUIRED:
            execution = engine.execute(
                state,
                CommandRequest(
                    "confirm-end-day",
                    CONFIRM_END_DAY_COMMAND,
                    execution.result.data["confirmation"],
                    expected_state_sequence=state.command_sequence,
                ),
            )
        return execution

    @staticmethod
    def execute(system, state, event_id: str, option_id: str):
        return system.execute(
            state,
            CommandRequest(
                f"event-{state.command_sequence}",
                RESOLVE_EVENT_COMMAND,
                {"event_id": event_id, "option_id": option_id},
                expected_state_sequence=state.command_sequence,
            ),
        )

    @staticmethod
    def assigned_population(state) -> int:
        return sum(
            building.assigned_workers
            + building.assigned_engineers
            + building.assigned_children
            + building.assigned_medical_apprentices
            + building.assigned_engineering_apprentices
            for building in state.buildings.values()
        ) + sum(
            point.assigned_workers + point.assigned_engineers
            for point in state.surface_resource_points.values()
        )

    def make_empty_pot_state(self, *, day: int = 1):
        state = self.make_state(day=day)
        state.resources.raw_food = 10
        state.resources.cooked_food = 10
        state.daily_survival.storage_used = storage_used(state.resources)
        state.events.metrics["food_warning_streak"] = 1
        return state

    def test_fixed_arrival_is_blocking_and_never_auto_assigns_workers(self) -> None:
        state = self.make_state(day=6)
        system = self.event_system()
        system.initialize_day(state)

        self.assertIn("arrival_day6", state.events.active_events)
        self.assertTrue(state.events.active_events["arrival_day6"].is_blocking)
        engine = EndDayEngine()
        system.install(engine)
        blocked = engine.execute(
            state,
            CommandRequest(
                "end-day",
                END_DAY_COMMAND,
                expected_state_sequence=state.command_sequence,
            ),
        )
        self.assertEqual(blocked.result.code, ErrorCode.END_DAY_BLOCKED)

        assigned_before = self.assigned_population(state)
        alive_before = state.population.population_alive
        result = self.execute(system, state, "arrival_day6", "accept_all")

        self.assertEqual(result.code, ErrorCode.OK)
        self.assertEqual(state.population.population_alive, alive_before + 12)
        self.assertEqual(self.assigned_population(state), assigned_before)
        self.assertEqual(state.population.homeless_population, 52)
        self.assertEqual(state.medical.medical_pressure, 0)
        self.assertEqual(state.population.sick_population, 2)
        self.assertEqual(state.population.critical_population, 1)
        self.assertEqual(
            state.events.fixed_arrival_choices["arrival_day6"], "accept_all"
        )
        self.assertEqual(state.events.resolution_history[-1].option_id, "accept_all")
        self.assertEqual(state.events.resolution_history[-1].resolved_day, 6)

    def test_day37_negative_old_city_delta_is_valid_save_data(self) -> None:
        state = self.make_state(day=37)
        state.old_city.is_unlocked = True
        system = self.event_system()
        system.initialize_day(state)

        result = self.execute(system, state, "arrival_day37", "accept_all")

        self.assertEqual(result.code, ErrorCode.OK)
        self.assertEqual(state.events.metrics["pending_old_city_arrival_delta"], -5)
        self.assertEqual(decode_game_state(encode_game_state(state)), state)

    def test_queue_selects_one_major_and_one_normal_without_hidden_effects(self) -> None:
        state = self.make_state(day=34)
        state.trust_panic.trust = 30
        state.trust_panic.panic = 75
        resources_before = deepcopy(state.resources)
        population_before = deepcopy(state.population)
        morale_before = deepcopy(state.trust_panic)
        system = self.event_system()

        system.initialize_day(state)

        major = [item for item in state.events.active_events.values() if item.is_blocking]
        normal = [item for item in state.events.active_events.values() if not item.is_blocking]
        self.assertEqual([item.event_id for item in major], ["black_frost_echo"])
        self.assertEqual(len(normal), 1)
        self.assertTrue(state.events.suppressed_event_ids_today)
        self.assertEqual(state.resources, resources_before)
        self.assertEqual(state.population, population_before)
        self.assertEqual(state.trust_panic, morale_before)
        self.assertEqual(state.promises.active_promises, {})
        self.assertEqual(state.events.resolved_event_ids, [])

    def test_ignored_normal_event_counts_as_shown_without_hidden_resolution(self) -> None:
        state = self.make_state(day=5)
        system = self.event_system()
        system.initialize_day(state)
        self.assertIn("children_request", state.events.active_events)
        self.assertEqual(state.events.occurrence_counts["children_request"], 1)

        state.calendar.current_day = 6
        system.begin_new_day(state)

        self.assertNotIn("children_request", state.events.active_events)
        self.assertNotIn("children_request", state.events.resolved_event_ids)
        self.assertEqual(state.promises.active_promises, {})

    def test_promise_deadline_day_remains_usable_and_failure_is_next_day(self) -> None:
        state = self.make_empty_pot_state()
        system = self.event_system()
        system.initialize_day(state)
        result = self.execute(system, state, "empty_pot", "promise_food")
        self.assertEqual(result.code, ErrorCode.OK)
        promise_id = result.data["promise_id"]
        self.assertEqual(state.promises.active_promises[promise_id].deadline_day, 4)

        state.calendar.current_day = 4
        system.begin_new_day(state)
        self.assertIn(promise_id, state.promises.active_promises)

        trust_before = state.trust_panic.trust
        panic_before = state.trust_panic.panic
        state.calendar.current_day = 5
        system.begin_new_day(state)
        self.assertNotIn(promise_id, state.promises.active_promises)
        self.assertIn(promise_id, state.promises.failed_promise_ids)
        self.assertEqual(
            state.promises.settlement_history[-1].outcome, "failure"
        )
        self.assertEqual(state.trust_panic.trust, trust_before - 6)
        self.assertEqual(state.trust_panic.panic, panic_before + 6)

    def test_promise_settlement_precedes_new_day_event_priority(self) -> None:
        state = self.make_state()
        state.trust_panic.trust = 20
        state.events.generated_for_day = 1
        state.promises.active_promises["promise-0001"] = PromiseRecord(
            promise_id="promise-0001",
            promise_type="trust",
            source_event_id="trust_crack",
            created_day=1,
            deadline_day=1,
            severity="serious",
            target={"trust_at_creation": 20, "panic_at_creation": 20},
        )
        state.promises.next_sequence = 2
        state.calendar.current_day = 2

        self.event_system().begin_new_day(state)

        self.assertEqual(state.trust_panic.trust, 12)
        self.assertIn("promise-0001", state.promises.failed_promise_ids)
        self.assertTrue(state.events.active_events["trust_crack"].is_blocking)

    def test_late_promise_is_capped_at_day48_and_day49_opens_none(self) -> None:
        state = self.make_state(day=46)
        state.trust_panic.trust = 30
        system = self.event_system()
        system.initialize_day(state)
        self.assertIn("trust_crack", state.events.active_events)

        result = self.execute(system, state, "trust_crack", "promise_trust")
        self.assertEqual(result.code, ErrorCode.OK)
        self.assertEqual(
            state.promises.active_promises[result.data["promise_id"]].deadline_day,
            48,
        )

        frost_state = self.make_state(day=49)
        frost_state.trust_panic.trust = 30
        system.initialize_day(frost_state)
        self.assertEqual(set(frost_state.events.active_events), {"seventh_frost_start"})
        self.assertTrue(frost_state.events.seventh_frostfall_active)

    def test_day48_eve_is_nonblocking_status_without_options(self) -> None:
        state = self.make_state(day=48)
        state.population.children = 0
        state.population.workers += 15
        system = self.event_system()

        system.initialize_day(state)

        self.assertTrue(state.events.frostfall_eve_status_shown)
        self.assertIn("event.frost_eve", state.events.status_ids)
        self.assertFalse(
            any(item.is_blocking for item in state.events.active_events.values())
        )
        self.assertNotIn("event.frost_eve", state.events.active_events)

    def test_old_city_day24_is_only_an_activation_interface(self) -> None:
        state = self.make_state(day=24)
        self.event_system().initialize_day(state)

        self.assertTrue(state.old_city.activation_pending)
        self.assertFalse(state.old_city.is_unlocked)
        self.assertIsNone(state.old_city.active_stage_id)
        self.assertIn("old_city.activation_pending", state.events.status_ids)

    def test_pressure_100_bypasses_an_existing_redline_cooldown_once(self) -> None:
        state = self.make_state(day=10)
        state.furnace.pressure = 100
        state.furnace.pressure_redline_warned = True
        state.events.cooldown_until_day["furnace_redline"] = 20
        system = self.event_system()

        system.initialize_day(state)

        self.assertIn("furnace_redline", state.events.active_events)
        self.assertEqual(state.events.metrics["furnace_forced_redline_shown"], 1)

    def test_cold_house_requires_exposure_and_normal_phase_warning_delay(self) -> None:
        state = self.make_state(day=4)
        state.events.metrics["cold_exposure_level"] = 3
        system = self.event_system()

        system.initialize_day(state)
        self.assertNotIn("cold_house_night", state.events.active_events)

        state.events.metrics["cold_exposure_warning_streak"] = 1
        state.calendar.current_day = 5
        system.begin_new_day(state)
        self.assertIn("cold_house_night", state.events.active_events)

    def test_event_views_expose_text_ids_options_and_exact_previews(self) -> None:
        state = self.make_state(day=6)
        system = self.event_system()
        system.initialize_day(state)

        view = next(
            item
            for item in system.active_event_views(state)
            if item["event_id"] == "arrival_day6"
        )

        self.assertEqual(view["title_text_id"], "arrival.day6.title")
        self.assertEqual(view["body_status"], "TODO_TEXT")
        accept_all = next(
            item for item in view["options"] if item["option_id"] == "accept_all"
        )
        self.assertEqual(accept_all["text_id"], "arrival.option.accept_all")
        self.assertEqual(accept_all["preview"]["population_added"], 12)
        self.assertEqual(accept_all["preview"]["resource_changes"]["coal"], 0)
        self.assertEqual(state.population.population_alive, 80)

    def test_event_view_and_rejection_explain_unavailable_option(self) -> None:
        state = self.make_empty_pot_state()
        state.promises.active_promises["promise-0001"] = PromiseRecord(
            promise_id="promise-0001",
            promise_type="food",
            source_event_id="empty_pot",
            created_day=1,
            deadline_day=4,
            severity="serious",
            target={"trust_at_creation": 50, "panic_at_creation": 20},
        )
        state.promises.next_sequence = 2
        system = self.event_system()
        system.initialize_day(state)

        view = system.active_event_views(state)[0]
        promise_option = next(
            item
            for item in view["unavailable_extra_options"]
            if item["option_id"] == "promise_food"
        )
        self.assertEqual(
            promise_option["reason"],
            "same_promise_type_already_active",
        )
        self.assertNotIn(
            "promise_food", [item["option_id"] for item in view["options"]]
        )
        rejected = self.execute(system, state, "empty_pot", "promise_food")
        self.assertEqual(rejected.code, ErrorCode.ILLEGAL_COMMAND)
        self.assertEqual(
            rejected.feedback[0].data["unavailable_reason"],
            "same_promise_type_already_active",
        )

    def test_overtime_risk_points_alone_do_not_fake_actual_harm(self) -> None:
        state = self.make_state(day=10)
        state.daily_survival.overtime_accident_risk_points = 1
        system = self.event_system()

        system.initialize_day(state)

        self.assertNotIn("overtime_empty_post", state.events.active_events)

        harmed = self.make_state(day=10)
        harmed.events.metrics["overtime_harm_today"] = 1
        system.initialize_day(harmed)
        self.assertIn("overtime_empty_post", harmed.events.active_events)

    def test_long_shift_event_suspends_only_the_following_day(self) -> None:
        state = self.make_state()
        state.laws.signed_law_ids.extend(["overtime_law", "long_shift_law"])
        state.social_policy.current_worktime_mode = "long_shift"
        state.social_policy.worktime_output_numerator = (
            self.law_rules.worktime.long_shift_output_numerator
        )
        state.social_policy.worktime_output_denominator = (
            self.law_rules.worktime.long_shift_output_denominator
        )
        state.social_policy.consecutive_long_shift_days = 3
        events = self.event_system()
        events.initialize_day(state)
        result = self.execute(
            events, state, "long_shift_collapse", "suspend_long_shift"
        )
        self.assertEqual(result.code, ErrorCode.OK)
        self.assertEqual(
            state.events.metrics["long_shift_suspended_until_day"], 2
        )

        laws = self.law_system()
        state.calendar.current_day = 2
        events.begin_new_day(state)
        laws.prepare_new_day(state)
        laws.validate_state(state)
        self.assertEqual(state.social_policy.worktime_output_numerator, 100)
        state.calendar.current_day = 3
        events.begin_new_day(state)
        laws.prepare_new_day(state)
        laws.validate_state(state)
        self.assertEqual(
            state.social_policy.worktime_output_numerator,
            self.law_rules.worktime.long_shift_output_numerator,
        )

    def test_v7_migration_expands_empty_event_and_promise_state(self) -> None:
        legacy = encode_game_state(self.make_state())
        legacy["save_data_version"] = 7
        legacy["events"] = {
            "active_event_ids": [],
            "resolved_event_ids": ["legacy-resolved"],
        }
        legacy["promises"] = {
            "active_promise_ids": [],
            "completed_promise_ids": [],
            "failed_promise_ids": [],
        }
        legacy["old_city"] = {"is_unlocked": False, "active_stage_id": None}

        migrated = decode_game_state(legacy)

        self.assertEqual(migrated.save_data_version, CURRENT_SAVE_DATA_VERSION)
        self.assertEqual(migrated.events.resolved_event_ids, ["legacy-resolved"])
        self.assertEqual(migrated.events.active_events, {})
        self.assertEqual(migrated.promises.active_promises, {})
        self.assertEqual(migrated.old_city.trigger_day, 24)

        legacy["events"]["active_event_ids"] = ["cannot-reconstruct"]
        with self.assertRaises(SaveDataError):
            decode_game_state(legacy)

    def test_hidden_cold_death_achievement_is_nonblocking_and_once_per_game(self) -> None:
        state = self.make_state()
        state.events.deaths_today_by_cause["cold_exposure"] = 1
        resources_before = deepcopy(state.resources)
        morale_before = deepcopy(state.trust_panic)
        emitted: list[tuple[str, dict]] = []
        context = EndDayContext(
            state=state,
            random=DeterministicRandom.from_state(state.random),
            settled_day=1,
            stage=EndDayStage.CHECK_HIDDEN_ACHIEVEMENTS,
            _emit=lambda code, data: emitted.append((code, dict(data))),
        )
        system = self.event_system()

        system.check_hidden_achievements(context)
        state.events.deaths_today_by_cause["freezing"] = 1
        system.check_hidden_achievements(context)

        self.assertEqual(
            state.events.hidden_achievements_unlocked, ["cold_death_solution"]
        )
        self.assertEqual(
            state.events.hidden_achievement_popup_queue, ["cold_death_solution"]
        )
        self.assertEqual(len(emitted), 1)
        self.assertEqual(state.events.active_events, {})
        self.assertEqual(state.resources, resources_before)
        self.assertEqual(state.trust_panic, morale_before)

    def test_invalid_new_day_state_rolls_back_and_writes_no_autosave(self) -> None:
        state = self.make_state()
        system = self.event_system()
        system.initialize_day(state)
        before = deepcopy(state)
        saved = []
        engine = EndDayEngine(autosave_sink=saved.append)
        system.install(engine)
        engine.register_new_day_handler(
            lambda working: setattr(working.resources, "storage_capacity", 1799)
        )

        execution = engine.execute(
            state,
            CommandRequest(
                "end-day",
                END_DAY_COMMAND,
                expected_state_sequence=state.command_sequence,
            ),
        )

        self.assertEqual(execution.result.code, ErrorCode.INTERNAL_ERROR)
        self.assertEqual(state, before)
        self.assertEqual(saved, [])
        self.assertIsNone(engine.last_autosave())

    def test_full_end_day_pipeline_generates_next_day_events_transactionally(self) -> None:
        state = self.make_state()
        self.event_system().initialize_day(state)
        saved = []

        execution = self.settle(self.full_engine(saved.append), state)

        self.assertEqual(execution.result.code, ErrorCode.OK)
        self.assertEqual(state.calendar.current_day, 2)
        self.assertEqual(state.events.generated_for_day, 2)
        self.assertIn("coal_bottom", state.events.active_events)
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0].settled_day, 1)


if __name__ == "__main__":
    unittest.main()
