from __future__ import annotations

import sys
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def downgrade_to_pre_patch006_schema(document: dict) -> dict:
    """Remove v7-only fields so migration tests use a genuine legacy schema."""

    final_frost = document.get("final_frost")
    if isinstance(final_frost, dict):
        final_frost.pop("balance_profile_id", None)
    furnace = document.get("furnace")
    if isinstance(furnace, dict):
        furnace.pop("overload_level", None)
        furnace.pop("pressure_redline_warned", None)
    daily = document.get("daily_survival")
    if isinstance(daily, dict):
        for field in (
            "target_overload_level",
            "effective_overload_level",
            "overload_coal_paid",
            "overload_temperature_bonus",
        ):
            daily.pop(field, None)
    technologies = document.get("technologies")
    if isinstance(technologies, dict):
        technologies.pop("research_progress_units", None)
        technologies.pop("research_required_units", None)
        technologies["research_progress_days"] = 0
    return document


def seed_final_frost_history(state, through_day: int | None = None) -> None:
    """Give isolated pre-Patch-009 tests a canonical no-loss frost prefix."""

    from furnace_winter.models import FrostDayRecord

    frost = state.final_frost
    if not frost.entered:
        population = state.population
        frost.entered = True
        frost.baseline_day = 49
        frost.baseline_alive_population = population.population_alive
        frost.baseline_healthy_population = population.healthy_population
        frost.baseline_sick_population = population.sick_population
        frost.baseline_critical_population = population.critical_population
        frost.baseline_disabled_population = population.disabled_population
        frost.baseline_workable_population = (
            population.workers + population.engineers
        )
    if through_day is None:
        through_day = min(55, state.calendar.current_day - 1)
    previous_population = (
        frost.daily_records[str(through_day)].population_end
        if str(through_day) in frost.daily_records
        else frost.baseline_alive_population
    )
    for day in range(49, through_day + 1):
        if str(day) in frost.daily_records:
            previous_population = frost.daily_records[str(day)].population_end
            continue
        base_cap = min(22, 12 + max(0, previous_population - 80) // 35)
        frost.daily_records[str(day)] = FrostDayRecord(
            day=day,
            real_temperature=0,
            display_label=f"D{day}",
            population_start=previous_population,
            population_end=state.population.population_alive,
            base_natural_death_cap=base_cap,
            applied_natural_death_cap=base_cap,
        )
        previous_population = state.population.population_alive
    records = list(frost.daily_records.values())
    frost.frost_hunger_days = sum(
        record.unfed_population > 0 for record in records
    )
    frost.frost_unfed_person_days = sum(
        record.unfed_population for record in records
    )
    frost.frost_population_person_days = sum(
        record.population_start for record in records
    )
    frost.frost_hunger_deaths = sum(record.food_deaths for record in records)
    peak = None
    for candidate in records:
        if candidate.unfed_population == 0:
            continue
        if peak is None or (
            candidate.unfed_population * peak.population_start
            > peak.unfed_population * candidate.population_start
        ) or (
            candidate.unfed_population * peak.population_start
            == peak.unfed_population * candidate.population_start
            and candidate.unfed_population > peak.unfed_population
        ):
            peak = candidate
    frost.frost_peak_unfed_count = peak.unfed_population if peak else 0
    frost.frost_peak_population_start = peak.population_start if peak else 0


def install_final_frost_history_stub(engine) -> None:
    """Maintain strict v11 history in tests that intentionally omit Patch 009."""

    from furnace_winter.gameplay import EndDayStage

    def capture_baseline(state) -> None:
        if state.calendar.current_day == 49:
            seed_final_frost_history(state, 48)
        elif 50 <= state.calendar.current_day <= 55:
            seed_final_frost_history(
                state,
                state.calendar.current_day - 1,
            )

    def capture_record(context) -> None:
        if 49 <= context.settled_day <= 55:
            legal_settled_day = max(
                context.state.calendar.current_day - 1,
                context.state.daily_survival.settled_day or 0,
            )
            seed_final_frost_history(
                context.state,
                min(context.settled_day, legal_settled_day),
            )

    engine.register_stage_handler(
        EndDayStage.UPDATE_PROMISE_TARGETS,
        capture_record,
    )
    engine.register_new_day_handler(capture_baseline)
