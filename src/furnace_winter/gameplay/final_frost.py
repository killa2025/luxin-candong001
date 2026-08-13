from __future__ import annotations

from dataclasses import dataclass

from furnace_winter.config.buildings import BuildingRules
from furnace_winter.config.final_frost import FinalFrostRules
from furnace_winter.config.survival import SurvivalRules
from furnace_winter.config.technologies import TechnologyRules
from furnace_winter.gameplay.end_day import EndDayContext, EndDayEngine, EndDayStage
from furnace_winter.gameplay.hunger import (
    clear_inactive_hunger_remainders,
    remove_non_hunger_deaths_or_departures,
    remove_starvation_deaths,
)
from furnace_winter.gameplay.operation import (
    FINAL_FROST_SHUTDOWN_BUILDING_TYPES,
    final_frost_affected_surface_resource_point_ids,
    is_final_frost_collection_shutdown,
)
from furnace_winter.gameplay.survival import (
    furnace_coal_cost,
    is_building_expected_operational,
)
from furnace_winter.models.save import validate_game_state
from furnace_winter.models.state import FrostDayRecord, GameState


_FROST_METRIC_PREFIX = "patch009_"
_SYSTEM_ORDER = (
    "coal_and_core",
    "food",
    "housing_and_temperature",
    "medical_and_disease",
    "trust_and_panic",
    "population_and_death",
)
_RESULT_ORDER = (
    "high_victory",
    "standard_victory",
    "bitter_victory",
    "collapse_survival",
    "ember_survival",
)
_LEGACY_PATCH_021_RESULT_SCORE_MINIMUMS = {
    "high_victory": 20,
    "standard_victory": 15,
    "bitter_victory": 10,
    "collapse_survival": 5,
    "ember_survival": 0,
}
_LEGACY_PATCH_021_HIGH_VICTORY_DEATH_RATIO_PERCENT = 20
_LEGACY_PATCH_021_PREPARATION = {
    "prepared_required_items": 5,
    "prepared_coal_days": 5,
    "prepared_food_days": 5,
    "prepared_trust": 50,
    "prepared_panic": 50,
    "unprepared_required_items": 3,
    "unprepared_coal_days": 3,
    "unprepared_food_days": 3,
    "unprepared_trust": 40,
    "unprepared_panic": 65,
    "unprepared_pressure": 80,
}


@dataclass(slots=True)
class FinalFrostSystem:
    rules: FinalFrostRules
    building_rules: BuildingRules
    survival_rules: SurvivalRules
    technology_rules: TechnologyRules

    def install(self, engine: EndDayEngine) -> None:
        engine.register_state_validator(self.validate_state)
        engine.register_stage_handler(
            EndDayStage.RESOLVE_HOUSING_COLD_AND_HUNGER,
            self.resolve_frost_health,
        )
        engine.register_stage_handler(
            EndDayStage.RESOLVE_TRUST_AND_PANIC,
            self.apply_hunger_social_pressure,
        )
        engine.register_stage_handler(
            EndDayStage.CAPTURE_DAILY_RECORDS,
            self.capture_daily_record,
        )
        engine.register_stage_handler(
            EndDayStage.RECORD_DAILY_LOG_AND_ENDING_TAGS,
            self.finalize_day_55,
        )
        engine.register_new_day_handler(self.prepare_new_day)

    def validate_state(self, state: GameState) -> None:
        validate_game_state(
            state,
            self.building_rules,
            self.survival_rules,
            self.technology_rules,
        )
        for day, temperature in self.rules.temperatures.items():
            if self.survival_rules.weather_for_day(day) != temperature.real:
                raise ValueError("final-frost temperature differs from survival weather")
        self._validate_cold_exposure_remainders(state)
        frost = state.final_frost
        if state.calendar.current_day >= self.rules.start_day and not frost.entered:
            raise ValueError("D49+ state must retain its final-frost baseline")
        if not frost.entered:
            if (
                frost.wood_supply_check_day is not None
                or frost.wood_supply_surface_exhausted
                or frost.wood_supply_logging_camp_available
                or frost.wood_supply_wood_stock != 0
                or frost.wood_supply_logging_cost != 0
                or frost.wood_supply_alternative_available
                or frost.wood_supply_legacy_exempt
                or frost.wood_supply_locked
            ):
                raise ValueError(
                    "pre-frost state cannot retain a wood-supply check"
                )
        else:
            expected_logging_cost = self.building_rules.buildings[
                "logging_camp"
            ].wood_cost
            expected_lock = (
                frost.wood_supply_surface_exhausted
                and not frost.wood_supply_logging_camp_available
                and frost.wood_supply_wood_stock < expected_logging_cost
                and not frost.wood_supply_alternative_available
                and not frost.wood_supply_legacy_exempt
            )
            if (
                frost.wood_supply_check_day != self.rules.start_day
                or frost.wood_supply_logging_cost != expected_logging_cost
                or frost.wood_supply_locked != expected_lock
            ):
                raise ValueError("wood-supply lock summary is inconsistent")
        record_days = sorted(int(day) for day in frost.daily_records)
        legacy_record_days = frost.legacy_hunger_record_days
        if (
            frost.legacy_hunger_history_unknown != bool(legacy_record_days)
            or legacy_record_days != sorted(set(legacy_record_days))
            or legacy_record_days != record_days[: len(legacy_record_days)]
            or (
                legacy_record_days
                and not frost.wood_supply_legacy_exempt
            )
        ):
            raise ValueError(
                "legacy hunger-history compatibility requires migrated frost records"
            )
        if record_days and record_days != list(
            range(self.rules.start_day, record_days[-1] + 1)
        ):
            raise ValueError("final-frost daily records must form a contiguous prefix")
        legal_settled_day = max(
            state.calendar.current_day - 1,
            state.daily_survival.settled_day or 0,
        )
        if record_days and record_days[-1] > legal_settled_day:
            raise ValueError("final-frost record cannot come from an unsettled day")
        known_service_history_started = False
        for day in record_days:
            record = frost.daily_records[str(day)]
            expected = self.rules.temperatures[day]
            if (
                record.real_temperature != expected.real
                or record.display_label != expected.display_label
            ):
                raise ValueError("final-frost record temperature is not canonical")
            if record.service_history_known:
                known_service_history_started = True
                if (
                    record.medical_operational_building_count == 0
                ) != (record.medical_building_capacity == 0):
                    raise ValueError(
                        "known final-frost medical service facts are inconsistent"
                    )
                if (
                    record.medical_building_capacity
                    < record.medical_operational_building_count
                ):
                    raise ValueError(
                        "known final-frost medical capacity is below its "
                        "operational building count"
                    )
            elif (
                known_service_history_started
                or record.canteen_operational
                or record.medical_operational_building_count
                or record.medical_building_capacity
            ):
                raise ValueError(
                    "unknown final-frost service history must be an empty prefix"
                )
            expected_cold_houses_day = (
                record.population_start > 0
                and record.cold_houses_population * 100
                >= record.population_start
                * self.rules.daily_thresholds[
                    "cold_houses_population_percent"
                ]
            )
            expected_mass_exposure_day = (
                record.population_start > 0
                and record.mass_cold_exposure_population * 100
                >= record.population_start
                * self.rules.daily_thresholds[
                    "mass_cold_exposure_percent"
                ]
            )
            expected_mass_death = (
                record.population_start - record.population_end
                >= max(
                    self.rules.daily_thresholds["mass_death_minimum"],
                    record.population_start
                    * self.rules.daily_thresholds[
                        "mass_death_population_percent"
                    ]
                    // 100,
                )
            )
            if (
                record.cold_houses_day != expected_cold_houses_day
                or record.mass_cold_exposure_day
                != expected_mass_exposure_day
                or record.mass_death != expected_mass_death
            ):
                raise ValueError(
                    "final-frost daily threshold facts are inconsistent"
                )
        if frost.final_score_day is not None and record_days != list(
            range(self.rules.start_day, self.rules.end_day + 1)
        ):
            raise ValueError("D55 scoring requires all seven final-frost records")
        final = state.final_result
        if (
            final.is_finalized
            and final.hard_fail_type is None
            and final.ending_id is not None
        ):
            scores = self._score(state)
            total = sum(scores.values())
            ending_id = self._apply_result_caps(
                state,
                scores,
                self._result_for_total(state, total),
            )
            tags = self._ending_tags(state, scores)
            major = [
                tag
                for tag in tags
                if self.rules.tag_severity.get(tag) == "major"
            ]
            defining = [
                tag
                for tag in tags
                if self.rules.tag_severity.get(tag) == "defining"
            ]
            if (
                final.system_scores != scores
                or final.total_score != total
                or final.ending_id != ending_id
                or final.major_tags != major
                or final.defining_tags != defining
                or final.ending_tags
                != [ending_id, *major, *defining]
            ):
                raise ValueError(
                    "final result must be derived from canonical frost history"
                )

    def _validate_cold_exposure_remainders(self, state: GameState) -> None:
        damage = self.rules.damage
        exposure = state.cold_exposure
        for values in (
            exposure.housed_disability_remainders,
            exposure.homeless_disability_remainders,
        ):
            for key, remainder in values.items():
                level = int(key)
                divisor = (
                    damage["cold_disability_level_4_divisor"]
                    if level >= 4
                    else damage["cold_disability_level_3_divisor"]
                    if level == 3
                    else damage["cold_disability_level_2_divisor"]
                )
                if remainder >= divisor:
                    raise ValueError(
                        "cold disability remainder exceeds its divisor"
                    )
        for homeless, values in (
            (False, exposure.housed_death_remainders),
            (True, exposure.homeless_death_remainders),
        ):
            for key, remainder in values.items():
                divisor = (
                    damage["frost_extra_cold_death_divisor"]
                    if key.endswith("_frost_extra")
                    else damage["homeless_cold_death_divisor"]
                    if homeless
                    else damage["housed_cold_death_divisor"]
                )
                if remainder >= divisor:
                    raise ValueError(
                        "cold death remainder exceeds its divisor"
                    )

    def prepare_new_day(self, state: GameState) -> None:
        if state.calendar.current_day == self.rules.start_day:
            self._capture_baseline(state)

    def resolve_frost_health(self, context: EndDayContext) -> None:
        state = context.state
        is_frost_day = self.rules.is_frost_day(context.settled_day)
        if is_frost_day and not state.final_frost.entered:
            self._capture_baseline(state)
        population_start = (
            state.final_frost.daily_records[
                str(context.settled_day - 1)
            ].population_end
            if is_frost_day and str(context.settled_day - 1)
            in state.final_frost.daily_records
            else state.final_frost.baseline_alive_population
            if is_frost_day
            else state.population.population_alive
        )
        exposure = self._exposure(state, is_frost_day=is_frost_day)
        damage = self.rules.damage
        exposure_level = max(
            (level for level, people, _homeless in exposure if people > 0),
            default=0,
        )

        hunger_effects = self._settle_hunger_pools(
            state, population_start=population_start
        )
        raw_hunger_deaths = hunger_effects["raw_deaths"]

        requested_housed_sick = 0
        requested_homeless_sick = 0
        for level, people, homeless in exposure:
            if level <= 0 or people <= 0:
                continue
            amount = (people // damage["exposure_population_unit"]) * min(level, 4)
            if level >= 3 and people >= damage["small_group_minimum"]:
                amount = max(amount, 1)
            if homeless:
                requested_homeless_sick += amount
            else:
                requested_housed_sick += amount
        housed_new_sick = min(
            requested_housed_sick,
            state.population.healthy_population,
        )
        homeless_new_sick = min(
            requested_homeless_sick,
            state.population.healthy_population - housed_new_sick,
        )
        cold_new_sick = housed_new_sick + homeless_new_sick
        state.population.healthy_population -= cold_new_sick
        state.population.sick_population += cold_new_sick

        critical_before = state.population.critical_population
        sick_before = state.population.sick_population
        capacity = state.medical.effective_capacity
        treated_critical = min(critical_before, capacity)
        treated_sick = min(sick_before, max(capacity - treated_critical, 0))
        untreated_critical = critical_before - treated_critical
        untreated_sick = sick_before - treated_sick

        critical_progress_total = (
            treated_critical + state.medical.critical_treatment_progress
        )
        critical_recovered = min(
            critical_before,
            critical_progress_total
            // damage["treated_critical_recovery_divisor"],
        )
        state.medical.critical_treatment_progress = (
            critical_progress_total
            % damage["treated_critical_recovery_divisor"]
        )
        sick_progress_total = (
            treated_sick + state.medical.sick_treatment_progress
        )
        sick_recovered = min(
            sick_before,
            sick_progress_total // damage["treated_sick_recovery_divisor"],
        )
        state.medical.sick_treatment_progress = (
            sick_progress_total % damage["treated_sick_recovery_divisor"]
        )

        hospital_running = any(
            building.building_type == "hospital" and building.is_operational
            for building in state.buildings.values()
        )
        treated_death_divisor = (
            damage["hospital_treated_critical_death_divisor"]
            if hospital_running
            else damage["treated_critical_death_divisor"]
        )
        raw_disease_deaths = (
            untreated_critical // damage["untreated_critical_death_divisor"]
            + untreated_critical
            // damage["untreated_critical_extra_death_divisor"]
            + treated_critical // treated_death_divisor
        )
        if (
            untreated_critical > 0
            and capacity == 0
            and exposure_level >= 3
        ):
            raw_disease_deaths = max(raw_disease_deaths, 1)
        raw_disease_deaths = min(
            raw_disease_deaths,
            max(critical_before - critical_recovered, 0),
        )
        untreated_divisor = (
            damage["untreated_sick_severe_level_4_divisor"]
            if exposure_level >= 4
            else damage["untreated_sick_severe_level_3_divisor"]
            if exposure_level == 3
            else damage["untreated_sick_severe_level_2_divisor"]
            if exposure_level == 2
            else damage["untreated_sick_severe_divisor"]
        )
        disease_new_critical = min(
            untreated_sick // untreated_divisor
            + (
                untreated_sick
                // damage["frost_untreated_sick_extra_severe_divisor"]
                if is_frost_day
                else 0
            )
            + (
                untreated_sick
                // damage["frost_untreated_sick_extra_severe_divisor"]
                if state.daily_survival.heating_shortfall
                else 0
            )
            + (
                treated_sick // damage["treated_sick_severe_divisor"]
                if state.medical.medical_pressure >= 10
                else 0
            ),
            max(sick_before - sick_recovered, 0),
        )
        if untreated_sick >= 6 and exposure_level >= 3:
            disease_new_critical = max(disease_new_critical, 1)

        housed_exposure_disability = 0
        homeless_exposure_disability = 0
        raw_housed_cold_deaths = 0
        raw_homeless_cold_deaths = 0
        medical_buffer = max(capacity - critical_before - sick_before, 0)
        grouped_exposure: dict[tuple[int, bool], int] = {}
        for level, people, homeless in exposure:
            grouped_exposure[(level, homeless)] = (
                grouped_exposure.get((level, homeless), 0) + people
            )
        self._update_exposure_streaks(state, grouped_exposure)
        for (level, homeless), people in sorted(grouped_exposure.items()):
            if people <= 0:
                continue
            divisor = (
                damage["cold_disability_level_4_divisor"]
                if level >= 4
                else damage["cold_disability_level_3_divisor"]
                if level == 3
                else damage["cold_disability_level_2_divisor"]
            )
            if level >= 2:
                disability = self._fractional_exposure_amount(
                    state,
                    people=people,
                    divisor=divisor,
                    homeless=homeless,
                    kind="disability",
                    key=str(level),
                )
                if homeless:
                    homeless_exposure_disability += disability
                else:
                    housed_exposure_disability += disability
            if level >= 4:
                death_divisor = (
                    damage["homeless_cold_death_divisor"]
                    if homeless
                    else damage["housed_cold_death_divisor"]
                )
                group_deaths = self._fractional_exposure_amount(
                    state,
                    people=people,
                    divisor=death_divisor,
                    homeless=homeless,
                    kind="death",
                    key=f"level_{level}_base",
                )
                if is_frost_day:
                    group_deaths += self._fractional_exposure_amount(
                        state,
                        people=people,
                        divisor=damage["frost_extra_cold_death_divisor"],
                        homeless=homeless,
                        kind="death",
                        key=f"level_{level}_frost_extra",
                    )
                if homeless:
                    raw_homeless_cold_deaths += group_deaths
                else:
                    raw_housed_cold_deaths += group_deaths
            elif homeless and (
                state.daily_survival.effective_furnace_level == 0
                or state.daily_survival.heating_shortfall
            ):
                raw_homeless_cold_deaths += self._fractional_exposure_amount(
                    state,
                    people=people,
                    divisor=damage["homeless_cold_death_divisor"],
                    homeless=True,
                    kind="death",
                    key=f"level_{level}_base",
                )
        raw_cold_deaths = raw_housed_cold_deaths + raw_homeless_cold_deaths

        extreme_conditions = self._extreme_crisis_conditions(
            state,
            exposure,
            untreated_critical,
        )
        base_cap = min(
            damage["natural_death_cap_maximum"],
            damage["natural_death_cap_base"]
            + max(
                0,
                population_start
                - damage["natural_death_cap_population_baseline"],
            )
            // damage["natural_death_cap_population_divisor"],
        )
        applied_cap = (
            (base_cap * 3 + 1) // 2
            if is_frost_day and len(extreme_conditions) >= 2
            else base_cap
        )
        actual_disease_deaths = min(raw_disease_deaths, applied_cap)
        remaining_cap = applied_cap - actual_disease_deaths
        nonstarving_hunger_population = (
            state.hunger.none_population
            + state.hunger.light_population
            + state.hunger.severe_population
        )
        starving_after_disease = max(
            state.hunger.starving_population
            - max(
                actual_disease_deaths - nonstarving_hunger_population,
                0,
            ),
            0,
        )
        raw_hunger_deaths = min(
            raw_hunger_deaths,
            starving_after_disease,
            max(state.population.population_alive - actual_disease_deaths, 0),
        )
        actual_hunger_deaths = min(raw_hunger_deaths, remaining_cap)
        remaining_cap -= actual_hunger_deaths
        raw_cold_deaths = min(
            raw_cold_deaths,
            max(
                state.population.population_alive
                - actual_disease_deaths
                - actual_hunger_deaths,
                0,
            ),
        )
        if context.settled_day == 1:
            raw_cold_deaths = min(
                raw_cold_deaths, damage["d1_cold_death_cap"]
            )
        actual_cold_deaths = min(raw_cold_deaths, remaining_cap)
        capped_housed_cold_deaths = min(
            raw_housed_cold_deaths,
            raw_cold_deaths,
        )
        homeless_cold_deaths = max(
            actual_cold_deaths - capped_housed_cold_deaths,
            0,
        )
        disease_overflow = raw_disease_deaths - actual_disease_deaths
        cold_overflow = raw_cold_deaths - actual_cold_deaths
        hunger_overflow = raw_hunger_deaths - actual_hunger_deaths
        overflow_pressure = disease_overflow + cold_overflow + hunger_overflow

        available_critical_for_disability = max(
            critical_before
            - critical_recovered
            - raw_disease_deaths,
            0,
        )
        new_disabled = min(
            available_critical_for_disability,
            untreated_critical
            // damage["untreated_critical_disability_divisor"],
        )
        state.population.critical_population = (
            critical_before
            - critical_recovered
            - actual_disease_deaths
            - new_disabled
            + disease_new_critical
        )
        state.population.sick_population = max(
            sick_before
            - sick_recovered
            - disease_new_critical
            + critical_recovered,
            0,
        )
        state.population.healthy_population += sick_recovered
        state.population.disabled_population += new_disabled
        self._record_preallocated_deaths(
            state,
            actual_disease_deaths,
            "disease",
        )
        remove_non_hunger_deaths_or_departures(
            state, actual_disease_deaths
        )

        hunger_new_sick = min(
            state.population.healthy_population,
            hunger_effects["illness_quota"],
        )
        state.population.healthy_population -= hunger_new_sick
        state.population.sick_population += hunger_new_sick
        hunger_new_critical = min(
            state.population.sick_population,
            hunger_effects["severe_quota"],
        )
        state.population.sick_population -= hunger_new_critical
        state.population.critical_population += hunger_new_critical
        new_sick = cold_new_sick + hunger_new_sick
        new_critical = disease_new_critical + hunger_new_critical

        prevented = medical_buffer // damage[
            "medical_buffer_per_prevented_disability"
        ]
        prevented_housed_disability = min(
            housed_exposure_disability,
            prevented,
        )
        housed_exposure_disability -= prevented_housed_disability
        prevented -= prevented_housed_disability
        homeless_exposure_disability = max(
            homeless_exposure_disability - prevented,
            0,
        )
        requested_exposure_disability = (
            housed_exposure_disability + homeless_exposure_disability
        )
        exposure_disability = self._apply_disabilities(
            state, requested_exposure_disability
        )
        homeless_new_disabled = max(
            exposure_disability - housed_exposure_disability,
            0,
        )
        actual_hunger_deaths = self._apply_deaths(
            state,
            actual_hunger_deaths,
            "starvation",
        )
        remove_starvation_deaths(state, actual_hunger_deaths)
        state.hunger.hunger_deaths_total += actual_hunger_deaths
        actual_cold_deaths = self._apply_deaths(
            state,
            actual_cold_deaths,
            "cold_exposure",
        )
        remove_non_hunger_deaths_or_departures(state, actual_cold_deaths)
        clear_inactive_hunger_remainders(state)
        self._settle_new_bodies(
            state,
            actual_disease_deaths
            + actual_cold_deaths
            + actual_hunger_deaths,
        )
        if state.population.sick_population == 0:
            state.medical.sick_treatment_progress = 0
        if state.population.critical_population == 0:
            state.medical.critical_treatment_progress = 0
        state.medical.medical_pressure = max(
            state.population.sick_population
            + state.population.critical_population
            - state.medical.effective_capacity,
            0,
        )

        metrics = state.events.metrics
        self._write_cold_exposure_snapshot(
            state,
            settled_day=context.settled_day,
            is_frost_day=is_frost_day,
            exposure=exposure,
        )
        metrics[f"{_FROST_METRIC_PREFIX}population_start"] = population_start
        metrics[f"{_FROST_METRIC_PREFIX}new_sick"] = new_sick
        metrics[f"{_FROST_METRIC_PREFIX}new_critical"] = new_critical
        metrics[f"{_FROST_METRIC_PREFIX}new_disabled"] = (
            new_disabled + exposure_disability
        )
        metrics[f"{_FROST_METRIC_PREFIX}homeless_new_sick"] = (
            homeless_new_sick
        )
        metrics[f"{_FROST_METRIC_PREFIX}homeless_new_disabled"] = (
            homeless_new_disabled
        )
        metrics[f"{_FROST_METRIC_PREFIX}homeless_cold_deaths"] = (
            homeless_cold_deaths
        )
        metrics[f"{_FROST_METRIC_PREFIX}disease_deaths"] = (
            actual_disease_deaths
        )
        metrics[f"{_FROST_METRIC_PREFIX}cold_deaths"] = actual_cold_deaths
        metrics[f"{_FROST_METRIC_PREFIX}hunger_deaths"] = (
            actual_hunger_deaths
        )
        metrics[f"{_FROST_METRIC_PREFIX}raw_hunger_deaths"] = (
            raw_hunger_deaths
        )
        metrics[f"{_FROST_METRIC_PREFIX}hunger_death_overflow"] = (
            hunger_overflow
        )
        metrics[f"{_FROST_METRIC_PREFIX}raw_disease_deaths"] = (
            raw_disease_deaths
        )
        metrics[f"{_FROST_METRIC_PREFIX}disease_death_overflow"] = (
            disease_overflow
        )
        metrics[f"{_FROST_METRIC_PREFIX}raw_cold_deaths"] = raw_cold_deaths
        metrics[f"{_FROST_METRIC_PREFIX}cold_death_overflow"] = cold_overflow
        metrics[f"{_FROST_METRIC_PREFIX}base_natural_death_cap"] = base_cap
        metrics[f"{_FROST_METRIC_PREFIX}applied_natural_death_cap"] = (
            applied_cap
        )
        metrics[f"{_FROST_METRIC_PREFIX}natural_death_overflow_pressure"] = (
            overflow_pressure
        )
        metrics[f"{_FROST_METRIC_PREFIX}extreme_crisis_count"] = len(
            extreme_conditions
        )
        state.final_frost.pending_extreme_crisis_conditions = (
            list(extreme_conditions) if is_frost_day else []
        )
        metrics[f"{_FROST_METRIC_PREFIX}cold_housed"] = sum(
            people
            for level, people, homeless in exposure
            if level >= 2 and not homeless
        )
        metrics[f"{_FROST_METRIC_PREFIX}homeless_exposure"] = (
            state.population.homeless_population
        )
        metrics[f"{_FROST_METRIC_PREFIX}mass_exposure"] = sum(
            people for level, people, _homeless in exposure if level >= 4
        )
        if overflow_pressure > 0 and is_frost_day:
            day_key = str(context.settled_day)
            state.events.natural_death_overflow_candidates[day_key] = (
                overflow_pressure
            )
            context.emit(
                "final_frost.natural_death_overflow.candidate",
                {
                    "day": context.settled_day,
                    "pressure": overflow_pressure,
                    "raw_disease_deaths": raw_disease_deaths,
                    "raw_cold_deaths": raw_cold_deaths,
                    "raw_hunger_deaths": raw_hunger_deaths,
                },
            )
        context.emit(
            "final_frost.health.resolved",
            {
                "day": context.settled_day,
                "new_sick": new_sick,
                "new_critical": new_critical,
                "new_disabled": new_disabled + exposure_disability,
                "disease_deaths": actual_disease_deaths,
                "cold_deaths": actual_cold_deaths,
                "hunger_deaths": actual_hunger_deaths,
                "natural_death_overflow_pressure": overflow_pressure,
            },
        )

    def _settle_hunger_pools(
        self, state: GameState, *, population_start: int
    ) -> dict[str, int]:
        hunger = state.hunger
        unfed = state.daily_survival.unfed_population
        fed_remaining = max(population_start - unfed, 0)
        old_none = hunger.none_population
        old_light = hunger.light_population
        old_severe = hunger.severe_population
        old_starving = hunger.starving_population

        fed_starving = min(old_starving, fed_remaining)
        fed_remaining -= fed_starving
        fed_severe = min(old_severe, fed_remaining)
        fed_remaining -= fed_severe
        fed_light = min(old_light, fed_remaining)
        fed_remaining -= fed_light
        fed_none = min(old_none, fed_remaining)

        unfed_starving = old_starving - fed_starving
        unfed_severe = old_severe - fed_severe
        unfed_light = old_light - fed_light
        unfed_none = old_none - fed_none
        hunger.none_population = fed_none + fed_light
        hunger.light_population = unfed_none + fed_severe
        hunger.severe_population = unfed_light + fed_starving
        hunger.starving_population = unfed_severe + unfed_starving

        illness_units = (
            hunger.light_population
            + hunger.severe_population
            + hunger.starving_population
        )
        if illness_units == 0:
            hunger.illness_remainder = 0
            illness_quota = 0
        else:
            illness_quota, hunger.illness_remainder = divmod(
                hunger.illness_remainder + illness_units,
                self.rules.hunger["illness_divisor"],
            )
        severe_units = (
            hunger.severe_population + 2 * hunger.starving_population
        )
        if severe_units == 0:
            hunger.severe_remainder = 0
            severe_quota = 0
        else:
            severe_quota, hunger.severe_remainder = divmod(
                hunger.severe_remainder + severe_units,
                self.rules.hunger["severe_divisor"],
            )
        if hunger.starving_population == 0:
            hunger.death_remainder = 0
            raw_deaths = 0
        else:
            raw_deaths, hunger.death_remainder = divmod(
                hunger.death_remainder + hunger.starving_population,
                self.rules.hunger["death_divisor"],
            )

        social_units = (
            hunger.light_population
            + 2 * hunger.severe_population
            + 3 * hunger.starving_population
        )
        if social_units == 0:
            hunger.trust_remainder = 0
            hunger.panic_remainder = 0
            trust_loss = 0
            panic_gain = 0
        else:
            trust_total = hunger.trust_remainder + social_units
            trust_loss = min(
                self.rules.hunger["trust_daily_cap"],
                trust_total // self.rules.hunger["trust_divisor"],
            )
            hunger.trust_remainder = (
                trust_total % self.rules.hunger["trust_divisor"]
            )
            panic_total = hunger.panic_remainder + social_units
            panic_gain = min(
                self.rules.hunger["panic_daily_cap"],
                panic_total // self.rules.hunger["panic_divisor"],
            )
            hunger.panic_remainder = (
                panic_total % self.rules.hunger["panic_divisor"]
            )

        if unfed > 0:
            hunger.total_hunger_days += 1
            hunger.total_unfed_person_days += unfed
            old_peak_population = hunger.peak_unfed_population_start
            old_peak_count = hunger.peak_unfed_count
            if (
                old_peak_population == 0
                or unfed * old_peak_population
                > old_peak_count * population_start
                or (
                    unfed * old_peak_population
                    == old_peak_count * population_start
                    and unfed > old_peak_count
                )
            ):
                hunger.peak_unfed_count = unfed
                hunger.peak_unfed_population_start = population_start

        metrics = state.events.metrics
        metrics["patch013_hunger_illness_quota"] = illness_quota
        metrics["patch013_hunger_severe_quota"] = severe_quota
        metrics["patch013_hunger_raw_deaths"] = raw_deaths
        metrics["patch013_hunger_trust_loss"] = trust_loss
        metrics["patch013_hunger_panic_gain"] = panic_gain
        return {
            "illness_quota": illness_quota,
            "severe_quota": severe_quota,
            "raw_deaths": raw_deaths,
            "trust_loss": trust_loss,
            "panic_gain": panic_gain,
        }

    def apply_hunger_social_pressure(self, context: EndDayContext) -> None:
        state = context.state
        trust_loss = state.events.metrics.get(
            "patch013_hunger_trust_loss", 0
        )
        panic_gain = state.events.metrics.get(
            "patch013_hunger_panic_gain", 0
        )
        if state.trust_panic.trust is not None:
            state.trust_panic.trust = max(
                state.trust_panic.trust - trust_loss, 0
            )
        if state.trust_panic.panic is not None:
            state.trust_panic.panic = min(
                state.trust_panic.panic + panic_gain, 100
            )
        context.emit(
            "hunger.social_pressure.applied",
            {
                "trust_loss": trust_loss,
                "panic_gain": panic_gain,
            },
        )

    def capture_daily_record(self, context: EndDayContext) -> None:
        day = context.settled_day
        if not self.rules.is_frost_day(day):
            return
        state = context.state
        metrics = state.events.metrics
        population_start = metrics.get(
            f"{_FROST_METRIC_PREFIX}population_start",
            state.population.population_alive,
        )
        new_sick = metrics.get(f"{_FROST_METRIC_PREFIX}new_sick", 0)
        new_critical = metrics.get(f"{_FROST_METRIC_PREFIX}new_critical", 0)
        disease_deaths = metrics.get(
            f"{_FROST_METRIC_PREFIX}disease_deaths", 0
        )
        cold_deaths = metrics.get(f"{_FROST_METRIC_PREFIX}cold_deaths", 0)
        raw_disease_deaths = metrics.get(
            f"{_FROST_METRIC_PREFIX}raw_disease_deaths", 0
        )
        disease_death_overflow = metrics.get(
            f"{_FROST_METRIC_PREFIX}disease_death_overflow", 0
        )
        raw_hunger_deaths = metrics.get(
            f"{_FROST_METRIC_PREFIX}raw_hunger_deaths", 0
        )
        hunger_death_overflow = metrics.get(
            f"{_FROST_METRIC_PREFIX}hunger_death_overflow", 0
        )
        raw_cold_deaths = metrics.get(
            f"{_FROST_METRIC_PREFIX}raw_cold_deaths", 0
        )
        cold_death_overflow = metrics.get(
            f"{_FROST_METRIC_PREFIX}cold_death_overflow", 0
        )
        base_natural_death_cap = metrics.get(
            f"{_FROST_METRIC_PREFIX}base_natural_death_cap", 0
        )
        applied_natural_death_cap = metrics.get(
            f"{_FROST_METRIC_PREFIX}applied_natural_death_cap", 0
        )
        natural_death_overflow_pressure = metrics.get(
            f"{_FROST_METRIC_PREFIX}natural_death_overflow_pressure", 0
        )
        thresholds = self.rules.daily_thresholds
        critical_frozen = any(
            building.is_shutdown_by_temperature
            and building.building_type
            not in self.rules.shutdown_building_types
            for building in state.buildings.values()
        )
        hospital_exists = any(
            building.building_type == "hospital"
            for building in state.buildings.values()
        )
        hospital_running = any(
            building.building_type == "hospital" and building.is_operational
            for building in state.buildings.values()
        )
        medical_operational_building_count = sum(
            1
            for building in state.buildings.values()
            if building.is_built
            and building.building_type in {"medical_station", "hospital"}
            and building.is_operational
        )
        cold_housed = metrics.get(f"{_FROST_METRIC_PREFIX}cold_housed", 0)
        mass_exposure = metrics.get(
            f"{_FROST_METRIC_PREFIX}mass_exposure", 0
        )
        cold_houses_day = (
            population_start > 0
            and cold_housed * 100
            >= population_start
            * thresholds["cold_houses_population_percent"]
        )
        mass_cold_exposure_day = (
            population_start > 0
            and mass_exposure * 100
            >= population_start
            * thresholds["mass_cold_exposure_percent"]
        )
        food_deaths = sum(
            amount
            for cause, amount in state.events.deaths_today_by_cause.items()
            if cause in {"hunger", "starvation"}
        )
        total_population_loss = max(
            population_start - state.population.population_alive, 0
        )
        record = FrostDayRecord(
            day=day,
            real_temperature=self.rules.temperatures[day].real,
            display_label=self.rules.temperatures[day].display_label,
            population_start=population_start,
            population_end=state.population.population_alive,
            furnace_off=state.daily_survival.effective_furnace_level == 0,
            heating_shortfall=state.daily_survival.heating_shortfall,
            coal_shortage=(
                state.daily_survival.coal_paid
                < state.daily_survival.required_coal
            ),
            furnace_underheated=(
                state.daily_survival.heating_shortfall or critical_frozen
            ),
            overload_used=state.daily_survival.effective_overload_level > 0,
            overload_redline=(
                state.furnace.pressure >= thresholds["overload_redline"]
            ),
            core_near_collapse=(
                state.furnace.pressure >= thresholds["core_near_collapse"]
            ),
            heat_uses=state.building_management.heat_uses_today,
            critical_building_frozen=critical_frozen,
            cold_houses_population=cold_housed,
            cold_houses_day=cold_houses_day,
            homeless_exposure_population=metrics.get(
                f"{_FROST_METRIC_PREFIX}homeless_exposure", 0
            ),
            mass_cold_exposure_population=mass_exposure,
            mass_cold_exposure_day=mass_cold_exposure_day,
            food_shortage=state.daily_survival.food_shortfall > 0,
            starvation=state.daily_survival.unfed_population > 0,
            unfed_population=state.daily_survival.unfed_population,
            medical_gap=state.medical.medical_pressure,
            medical_overflow=(
                state.medical.medical_pressure
                >= thresholds["medical_overflow_gap"]
            ),
            medical_collapse=(
                state.medical.medical_pressure
                >= thresholds["medical_collapse_gap"]
                or (
                    self._medical_buildings_exist(state)
                    and not self._medical_buildings_running(state)
                )
            ),
            hospital_shutdown=hospital_exists and not hospital_running,
            service_history_known=True,
            canteen_operational=any(
                building.is_built
                and building.building_type == "canteen"
                and building.is_operational
                for building in state.buildings.values()
            ),
            medical_operational_building_count=(
                medical_operational_building_count
            ),
            medical_building_capacity=state.medical.building_capacity,
            disease_spike=(
                new_sick + new_critical
                >= max(
                    thresholds["disease_spike_minimum"],
                    population_start
                    * thresholds["disease_spike_population_percent"]
                    // 100,
                )
            ),
            new_sick=new_sick,
            new_critical=new_critical,
            new_disabled=metrics.get(
                f"{_FROST_METRIC_PREFIX}new_disabled", 0
            ),
            homeless_new_sick=metrics.get(
                f"{_FROST_METRIC_PREFIX}homeless_new_sick", 0
            ),
            homeless_new_disabled=metrics.get(
                f"{_FROST_METRIC_PREFIX}homeless_new_disabled", 0
            ),
            homeless_cold_deaths=metrics.get(
                f"{_FROST_METRIC_PREFIX}homeless_cold_deaths", 0
            ),
            food_deaths=food_deaths,
            disease_deaths=disease_deaths,
            cold_deaths=cold_deaths,
            raw_disease_deaths=raw_disease_deaths,
            actual_disease_deaths=disease_deaths,
            disease_death_overflow=disease_death_overflow,
            raw_hunger_deaths=raw_hunger_deaths,
            hunger_death_overflow=hunger_death_overflow,
            raw_cold_deaths=raw_cold_deaths,
            actual_cold_deaths=cold_deaths,
            cold_death_overflow=cold_death_overflow,
            base_natural_death_cap=base_natural_death_cap,
            applied_natural_death_cap=applied_natural_death_cap,
            extreme_crisis_conditions=list(
                state.final_frost.pending_extreme_crisis_conditions
            ),
            natural_death_overflow_pressure=(
                natural_death_overflow_pressure
            ),
            mass_death=(
                total_population_loss
                >= max(
                    thresholds["mass_death_minimum"],
                    population_start
                    * thresholds["mass_death_population_percent"]
                    // 100,
                )
            ),
            trust_crisis=(
                (state.trust_panic.trust or 0)
                <= thresholds["trust_crisis"]
            ),
            panic_crisis=(
                (state.trust_panic.panic or 0)
                >= thresholds["panic_crisis"]
            ),
        )
        state.final_frost.daily_records[str(day)] = record
        state.final_frost.pending_extreme_crisis_conditions.clear()
        state.final_frost.frost_deaths += total_population_loss
        state.final_frost.frost_population_person_days += population_start
        state.final_frost.frost_unfed_person_days += record.unfed_population
        state.final_frost.frost_hunger_deaths += record.food_deaths
        if record.unfed_population > 0:
            state.final_frost.frost_hunger_days += 1
            old_peak_population = (
                state.final_frost.frost_peak_population_start
            )
            old_peak_count = state.final_frost.frost_peak_unfed_count
            if (
                old_peak_population == 0
                or record.unfed_population * old_peak_population
                > old_peak_count * record.population_start
                or (
                    record.unfed_population * old_peak_population
                    == old_peak_count * record.population_start
                    and record.unfed_population > old_peak_count
                )
            ):
                state.final_frost.frost_peak_unfed_count = (
                    record.unfed_population
                )
                state.final_frost.frost_peak_population_start = (
                    record.population_start
                )
        context.emit(
            "final_frost.day.recorded",
            {
                "day": day,
                "population_end": record.population_end,
                "daily_deaths": total_population_loss,
            },
        )

    def finalize_day_55(self, context: EndDayContext) -> None:
        if context.settled_day != self.rules.final_settlement_day:
            return
        state = context.state
        if state.final_result.hard_fail_type is not None:
            state.final_result.is_finalized = True
            state.final_result.ending_id = "hard_fail"
            state.final_result.ending_tags = [
                "hard_fail",
                state.final_result.hard_fail_type.value,
            ]
            context.emit(
                "final_frost.result.finalized",
                {"ending_id": "hard_fail"},
            )
            from furnace_winter.gameplay.ending_report import EndingReportSystem

            EndingReportSystem().generate(state)
            return
        scores = self._score(state)
        total = sum(scores.values())
        ending_id = self._result_for_total(state, total)
        ending_id = self._apply_result_caps(state, scores, ending_id)
        tags = self._ending_tags(state, scores)
        major = [
            tag
            for tag in tags
            if self.rules.tag_severity.get(tag) == "major"
        ]
        defining = [
            tag
            for tag in tags
            if self.rules.tag_severity.get(tag) == "defining"
        ]
        state.final_frost.final_score_day = context.settled_day
        result = state.final_result
        result.is_finalized = True
        result.ending_id = ending_id
        result.system_scores = scores
        result.total_score = total
        result.major_tags = major
        result.defining_tags = defining
        result.ending_tags = [ending_id, *major, *defining]
        context.emit(
            "final_frost.result.finalized",
            {
                "ending_id": ending_id,
                "system_scores": scores,
                "total_score": total,
                "major_tags": major,
                "defining_tags": defining,
            },
        )
        from furnace_winter.gameplay.ending_report import EndingReportSystem

        EndingReportSystem().generate(state)

    def observe(self, state: GameState) -> dict[str, object]:
        self.validate_state(state)
        return {
            "active": self.rules.is_frost_day(state.calendar.current_day),
            "balance_profile_id": state.final_frost.balance_profile_id,
            "balance_status": self.rules.config_status.value,
            "start_day": self.rules.start_day,
            "end_day": self.rules.end_day,
            "baseline_day": state.final_frost.baseline_day,
            "preparation_tags": list(state.final_frost.preparation_tags),
            "settled_days": sorted(int(day) for day in state.final_frost.daily_records),
            "daily_service_history": {
                str(day): {
                    "known": record.service_history_known,
                    "canteen_operational": record.canteen_operational,
                    "medical_operational_building_count": (
                        record.medical_operational_building_count
                    ),
                    "medical_building_capacity": (
                        record.medical_building_capacity
                    ),
                }
                for day, record in sorted(
                    (
                        (int(day), record)
                        for day, record in state.final_frost.daily_records.items()
                    ),
                    key=lambda item: item[0],
                )
            },
            "forced_shutdown": {
                "starts_day": self.rules.start_day,
                "building_types": sorted(
                    FINAL_FROST_SHUTDOWN_BUILDING_TYPES
                ),
                "affected_building_ids": sorted(
                    building.building_id
                    for building in state.buildings.values()
                    if building.is_built
                    and building.building_type
                    in FINAL_FROST_SHUTDOWN_BUILDING_TYPES
                ),
                "surface_resource_collection_shutdown": (
                    is_final_frost_collection_shutdown(
                        state.calendar.current_day
                    )
                ),
                "affected_surface_resource_point_ids": list(
                    final_frost_affected_surface_resource_point_ids(state)
                ),
            },
            "frost_deaths": state.final_frost.frost_deaths,
            "wood_supply": {
                "checked_day": state.final_frost.wood_supply_check_day,
                "surface_exhausted": (
                    state.final_frost.wood_supply_surface_exhausted
                ),
                "logging_camp_available": (
                    state.final_frost.wood_supply_logging_camp_available
                ),
                "wood_stock": state.final_frost.wood_supply_wood_stock,
                "logging_cost": state.final_frost.wood_supply_logging_cost,
                "alternative_available": (
                    state.final_frost.wood_supply_alternative_available
                ),
                "wood_supply_locked": state.final_frost.wood_supply_locked,
            },
            "hunger_statistics": {
                "legacy_history_unknown": (
                    state.final_frost.legacy_hunger_history_unknown
                ),
                "legacy_record_days": list(
                    state.final_frost.legacy_hunger_record_days
                ),
                "frost_hunger_days": state.final_frost.frost_hunger_days,
                "frost_unfed_person_days": (
                    state.final_frost.frost_unfed_person_days
                ),
                "frost_population_person_days": (
                    state.final_frost.frost_population_person_days
                ),
                "frost_peak_unfed_count": (
                    state.final_frost.frost_peak_unfed_count
                ),
                "frost_peak_population_start": (
                    state.final_frost.frost_peak_population_start
                ),
                "frost_peak_unfed_ratio": {
                    "numerator": state.final_frost.frost_peak_unfed_count,
                    "denominator": (
                        state.final_frost.frost_peak_population_start
                    ),
                },
                "frost_hunger_deaths": (
                    state.final_frost.frost_hunger_deaths
                ),
            },
            "final_result": {
                "is_finalized": state.final_result.is_finalized,
                "ending_id": state.final_result.ending_id,
                "system_scores": dict(state.final_result.system_scores),
                "total_score": state.final_result.total_score,
                "major_tags": list(state.final_result.major_tags),
                "defining_tags": list(state.final_result.defining_tags),
            },
        }

    def _capture_baseline(self, state: GameState) -> None:
        frost = state.final_frost
        if frost.entered:
            return
        population = state.population
        frost.entered = True
        frost.baseline_day = self.rules.start_day
        frost.baseline_alive_population = population.population_alive
        frost.baseline_healthy_population = population.healthy_population
        frost.baseline_sick_population = population.sick_population
        frost.baseline_critical_population = population.critical_population
        frost.baseline_disabled_population = population.disabled_population
        frost.baseline_workable_population = (
            population.workers + population.engineers
        )
        self._capture_wood_supply_lock(state)
        coal_days = state.resources.coal // max(
            furnace_coal_cost(state, self.survival_rules, 3), 1
        )
        food_equivalent = state.resources.cooked_food
        if self._canteen_operational_for_preparation(state):
            food_equivalent += state.resources.raw_food * 2
        food_days = food_equivalent // max(population.population_alive, 1)
        trust = state.trust_panic.trust or 0
        panic = state.trust_panic.panic or 0
        pressure = state.furnace.pressure
        prep = (
            {
                **_LEGACY_PATCH_021_PREPARATION,
                "key_technology_ids": self.rules.preparation[
                    "key_technology_ids"
                ],
            }
            if frost.balance_profile_id == "legacy_patch021"
            else self.rules.preparation
        )
        checks = (
            coal_days >= prep["prepared_coal_days"],
            food_days >= prep["prepared_food_days"],
            population.homeless_population == 0,
            state.medical.effective_capacity
            >= population.sick_population + population.critical_population,
            trust >= prep["prepared_trust"],
            panic <= prep["prepared_panic"],
            not state.old_city.is_unlocked
            or state.old_city.resolved
            or state.old_city.member_count < state.old_city.low_threshold,
            bool(
                set(prep["key_technology_ids"])
                & set(state.technologies.researched_tech_ids)
            ),
        )
        weak = (
            coal_days < prep["unprepared_coal_days"],
            food_days < prep["unprepared_food_days"],
            population.homeless_population > 0,
            state.medical.medical_pressure > 0,
            trust < prep["unprepared_trust"],
            panic > prep["unprepared_panic"],
            state.old_city.is_unlocked
            and not state.old_city.resolved
            and state.old_city.member_count
            >= state.old_city.middle_threshold,
            pressure >= prep["unprepared_pressure"],
        )
        frost.prepared_item_count = sum(checks)
        frost.unprepared_item_count = sum(weak)
        if frost.unprepared_item_count >= prep["unprepared_required_items"]:
            frost.preparation_tags.append("unprepared_frost")
        elif frost.prepared_item_count >= prep["prepared_required_items"]:
            frost.preparation_tags.append("prepared_for_frost")

    def _capture_wood_supply_lock(self, state: GameState) -> None:
        wood_points = [
            point
            for point in state.surface_resource_points.values()
            if point.resource_type == "wood"
        ]
        surface_wood_exhausted = bool(wood_points) and all(
            point.remaining_amount == 0 for point in wood_points
        )
        has_logging_camp = any(
            building.building_type == "logging_camp"
            and building.is_built
            and building.bound_resource_id is not None
            and is_building_expected_operational(
                state,
                building,
                self.building_rules,
                self.survival_rules,
                self.technology_rules,
                # This D49 snapshot asks whether a valid renewable supply
                # chain existed, not whether collection runs during frost.
                respect_forced_shutdown=False,
            )
            for building in state.buildings.values()
        )
        logging_cost = self.building_rules.buildings["logging_camp"].wood_cost
        # V1 has no construction queue and no other sealed renewable wood
        # source. A built, legally bound camp therefore covers both the
        # completed and valid-construction-path cases in the confirmed rule.
        frost = state.final_frost
        frost.wood_supply_check_day = self.rules.start_day
        frost.wood_supply_surface_exhausted = surface_wood_exhausted
        frost.wood_supply_logging_camp_available = has_logging_camp
        frost.wood_supply_wood_stock = state.resources.wood
        frost.wood_supply_logging_cost = logging_cost
        frost.wood_supply_alternative_available = False
        frost.wood_supply_legacy_exempt = False
        frost.wood_supply_locked = (
            surface_wood_exhausted
            and not has_logging_camp
            and state.resources.wood < logging_cost
        )

    def _canteen_operational_for_preparation(self, state: GameState) -> bool:
        for building in state.buildings.values():
            if building.building_type != "canteen":
                continue
            rule = self.building_rules.buildings["canteen"]
            assignments = {
                "workers": building.assigned_workers,
                "engineers": building.assigned_engineers,
                "children": building.assigned_children,
                "medical_apprentices": (
                    building.assigned_medical_apprentices
                ),
                "engineering_apprentices": (
                    building.assigned_engineering_apprentices
                ),
            }
            assigned = sum(assignments.values())
            legal_staffing = (
                assigned <= rule.staff_capacity
                and all(
                    count == 0
                    for population_type, count in assignments.items()
                    if population_type not in rule.allowed_staff_types
                )
            )
            staffed = (
                legal_staffing
                and (rule.staff_capacity == 0 or assigned > 0)
            )
            if (
                building.is_built
                and staffed
                and is_building_expected_operational(
                    state,
                    building,
                    self.building_rules,
                    self.survival_rules,
                    self.technology_rules,
                )
            ):
                return True
        return False

    def _exposure(
        self, state: GameState, *, is_frost_day: bool
    ) -> list[tuple[int, int, bool]]:
        alive_to_assign = min(
            state.population.housed_population,
            state.population.population_alive,
        )
        groups: list[tuple[int, int, bool]] = []
        for building in sorted(state.buildings.values(), key=lambda item: item.building_id):
            rule = self.building_rules.buildings.get(building.building_type)
            if rule is None or rule.housing_capacity <= 0 or alive_to_assign <= 0:
                continue
            people = min(rule.housing_capacity, alive_to_assign)
            alive_to_assign -= people
            groups.append(
                (
                    self._exposure_level(
                        building.effective_temperature,
                        is_frost_day=is_frost_day,
                    ),
                    people,
                    False,
                )
            )
        if alive_to_assign > 0:
            groups.append(
                (
                    self._exposure_level(
                        min(state.daily_survival.zone_temperatures.values()),
                        is_frost_day=is_frost_day,
                    ),
                    alive_to_assign,
                    False,
                )
            )
        groups.append(
            (
                self._homeless_exposure_level(
                    state, is_frost_day=is_frost_day
                ),
                state.population.homeless_population,
                True,
            )
        )
        return groups

    def _exposure_level(self, temperature: int, *, is_frost_day: bool) -> int:
        original = (
            0
            if temperature >= -25
            else 1
            if temperature >= -35
            else 2
            if temperature >= -45
            else 3
            if temperature >= -55
            else 4
        )
        if not is_frost_day or original < 2:
            return original
        return min(
            max(
                original + self.rules.damage["extra_exposure_level"],
                self.rules.damage["minimum_exposure_level"],
            ),
            self.rules.damage["exposure_level_cap"],
        )

    def _homeless_exposure_level(
        self, state: GameState, *, is_frost_day: bool
    ) -> int:
        base_temperature = state.daily_survival.base_temperature
        if base_temperature is None:
            day = state.daily_survival.settled_day or state.calendar.current_day
            frost_temperature = self.rules.temperatures.get(day)
            if frost_temperature is not None:
                base_temperature = frost_temperature.real
            else:
                base_temperature = self.survival_rules.weather_for_day(day)
        heating = (
            self.survival_rules.furnace_levels[
                state.daily_survival.effective_furnace_level
            ].heating
            + state.daily_survival.overload_temperature_bonus
            + (
                3
                if is_frost_day
                and state.daily_survival.effective_furnace_level > 0
                and "tech_final_furnace_stability"
                in state.technologies.researched_tech_ids
                else 0
            )
        )
        temperature = base_temperature + heating // 2
        level = (
            1
            if temperature >= -20
            else 2
            if temperature >= -35
            else 3
            if temperature >= -50
            else 4
        )
        if state.daily_survival.effective_furnace_level == 0:
            level += 1
        if state.daily_survival.heating_shortfall:
            level += 1
        if is_frost_day:
            level += 1
        return min(level, self.rules.damage["exposure_level_cap"])

    def _write_cold_exposure_snapshot(
        self,
        state: GameState,
        *,
        settled_day: int,
        is_frost_day: bool,
        exposure: list[tuple[int, int, bool]] | None = None,
    ) -> None:
        homeless_population = state.population.homeless_population
        state.events.metrics["cold_exposure_snapshot_day"] = settled_day
        state.events.metrics["homeless_population"] = homeless_population
        if homeless_population == 0:
            level = 0
        elif exposure is not None:
            level = max(
                (
                    exposure_level
                    for exposure_level, people, homeless in exposure
                    if homeless and people > 0
                ),
                default=0,
            )
        else:
            level = self._homeless_exposure_level(
                state, is_frost_day=is_frost_day
            )
        state.events.metrics["cold_exposure_level"] = level

    @staticmethod
    def _update_exposure_streaks(
        state: GameState,
        grouped_exposure: dict[tuple[int, bool], int],
    ) -> None:
        for homeless in (False, True):
            streaks = (
                state.cold_exposure.homeless_level_streaks
                if homeless
                else state.cold_exposure.housed_level_streaks
            )
            active_levels = {
                str(level)
                for (level, group_is_homeless), people in grouped_exposure.items()
                if group_is_homeless == homeless and people > 0
            }
            for level in set(streaks) | active_levels:
                streaks[level] = streaks.get(level, 0) + 1 if level in active_levels else 0
            for level in [key for key, value in streaks.items() if value == 0]:
                del streaks[level]

    @staticmethod
    def _exposure_streak(
        state: GameState, *, homeless: bool, level: int
    ) -> int:
        streaks = (
            state.cold_exposure.homeless_level_streaks
            if homeless
            else state.cold_exposure.housed_level_streaks
        )
        return streaks.get(str(level), 0)

    @staticmethod
    def _fractional_exposure_amount(
        state: GameState,
        *,
        people: int,
        divisor: int,
        homeless: bool,
        kind: str,
        key: str,
    ) -> int:
        if kind == "disability":
            remainders = (
                state.cold_exposure.homeless_disability_remainders
                if homeless
                else state.cold_exposure.housed_disability_remainders
            )
        elif kind == "death":
            remainders = (
                state.cold_exposure.homeless_death_remainders
                if homeless
                else state.cold_exposure.housed_death_remainders
            )
        else:
            raise ValueError("unsupported cold-exposure remainder kind")
        amount, remainder = divmod(remainders.get(key, 0) + people, divisor)
        remainders[key] = remainder
        return amount

    def _extreme_crisis_conditions(
        self,
        state: GameState,
        exposure: list[tuple[int, int, bool]],
        untreated_critical: int,
    ) -> list[str]:
        conditions: list[str] = []

        def add(condition_id: str, active: bool) -> None:
            if active:
                conditions.append(condition_id)

        level_four_population = sum(
            people
            for level, people, _homeless in exposure
            if level >= 4
        )
        homeless_level = max(
            (
                level
                for level, people, homeless in exposure
                if homeless and people > 0
            ),
            default=0,
        )
        critical_building_shutdown = any(
            building.is_shutdown_by_temperature
            and building.building_type
            not in self.rules.shutdown_building_types
            for building in state.buildings.values()
        )
        add(
            "furnace_off",
            state.daily_survival.effective_furnace_level == 0,
        )
        add("heating_shortfall", state.daily_survival.heating_shortfall)
        add("mass_exposure_level_4", level_four_population >= 40)
        add(
            "mass_homeless_exposure",
            state.population.homeless_population >= 40
            and homeless_level >= 3,
        )
        add(
            "medical_capacity_zero_with_critical",
            state.medical.effective_capacity == 0
            and state.population.critical_population > 0,
        )
        add(
            "untreated_critical_at_least_10",
            untreated_critical >= 10,
        )
        add(
            "food_shortage_population_at_least_60",
            state.daily_survival.unfed_population >= 60,
        )
        add("critical_building_shutdown", critical_building_shutdown)
        add(
            "overload_redline_continued",
            state.daily_survival.effective_overload_level > 0
            and state.furnace.pressure
            >= self.rules.daily_thresholds["overload_redline"],
        )
        return sorted(conditions)

    @staticmethod
    def _record_preallocated_deaths(
        state: GameState, deaths: int, cause: str
    ) -> None:
        if deaths <= 0:
            return
        if sum(
            (
                state.population.healthy_population,
                state.population.sick_population,
                state.population.critical_population,
                state.population.disabled_population,
            )
        ) != state.population.population_alive - deaths:
            raise ValueError(
                "preallocated deaths must already be removed from health pools"
            )
        state.population.population_alive -= deaths
        state.population.population_dead += deaths
        FinalFrostSystem._trim_occupations(state, deaths)
        state.events.deaths_today_by_cause[cause] = (
            state.events.deaths_today_by_cause.get(cause, 0) + deaths
        )
        state.population.housed_population = min(
            state.population.housed_population,
            state.population.population_alive,
        )
        state.population.homeless_population = (
            state.population.population_alive
            - state.population.housed_population
        )

    @staticmethod
    def _apply_deaths(state: GameState, requested: int, cause: str) -> int:
        deaths = min(max(requested, 0), state.population.population_alive)
        remaining = deaths
        for field in (
            "critical_population",
            "sick_population",
            "healthy_population",
            "disabled_population",
        ):
            pool = getattr(state.population, field)
            removed = min(pool, remaining)
            setattr(state.population, field, pool - removed)
            remaining -= removed
        if remaining:
            raise ValueError("health pools cannot cover final-frost deaths")
        state.population.population_alive -= deaths
        state.population.population_dead += deaths
        FinalFrostSystem._trim_occupations(state, deaths)
        state.events.deaths_today_by_cause[cause] = (
            state.events.deaths_today_by_cause.get(cause, 0) + deaths
        )
        state.population.housed_population = min(
            state.population.housed_population,
            state.population.population_alive,
        )
        state.population.homeless_population = (
            state.population.population_alive
            - state.population.housed_population
        )
        return deaths

    @staticmethod
    def _apply_disabilities(state: GameState, requested: int) -> int:
        disabilities = min(
            max(requested, 0),
            state.population.healthy_population
            + state.population.sick_population
            + state.population.critical_population,
        )
        remaining = disabilities
        for field in (
            "healthy_population",
            "sick_population",
            "critical_population",
        ):
            pool = getattr(state.population, field)
            moved = min(pool, remaining)
            setattr(state.population, field, pool - moved)
            remaining -= moved
        state.population.disabled_population += disabilities
        return disabilities

    @staticmethod
    def _trim_occupations(state: GameState, deaths: int) -> None:
        population = state.population
        unclassified = max(
            population.population_alive
            + deaths
            - population.workers
            - population.engineers
            - population.children,
            0,
        )
        remaining = max(deaths - unclassified, 0)
        for role, field in (
            ("workers", "assigned_workers"),
            ("engineers", "assigned_engineers"),
            ("children", "assigned_children"),
        ):
            pool = getattr(population, role)
            removed = min(pool, remaining)
            setattr(population, role, pool - removed)
            remaining -= removed
            if removed:
                FinalFrostSystem._trim_assignments(
                    state, field, getattr(population, role)
                )
        population.medical_apprentices = min(
            population.medical_apprentices, population.children
        )
        population.engineering_apprentices = min(
            population.engineering_apprentices,
            population.children - population.medical_apprentices,
        )
        FinalFrostSystem._trim_assignments(
            state,
            "assigned_medical_apprentices",
            population.medical_apprentices,
        )
        FinalFrostSystem._trim_assignments(
            state,
            "assigned_engineering_apprentices",
            population.engineering_apprentices,
        )

    @staticmethod
    def _trim_assignments(state: GameState, field: str, maximum: int) -> None:
        targets: list[object] = [
            *sorted(state.buildings.values(), key=lambda item: item.building_id),
            *sorted(
                state.surface_resource_points.values(),
                key=lambda item: item.resource_point_id,
            ),
        ]
        if field in {"assigned_workers", "assigned_engineers"}:
            targets.extend(
                (state.oath_order.oath_hall, state.oath_order.patrol_office)
            )
        assigned = sum(getattr(item, field, 0) for item in targets)
        excess = max(assigned - maximum, 0)
        for item in reversed(targets):
            if not hasattr(item, field) or excess == 0:
                continue
            value = getattr(item, field)
            removed = min(value, excess)
            setattr(item, field, value - removed)
            excess -= removed

    @staticmethod
    def _settle_new_bodies(state: GameState, deaths: int) -> None:
        state.social_policy.unhandled_bodies += deaths
        if any(
            building.building_type == "cemetery"
            for building in state.buildings.values()
        ):
            state.social_policy.buried_bodies += state.social_policy.unhandled_bodies
            state.social_policy.unhandled_bodies = 0
        elif any(
            building.building_type == "cold_pit"
            for building in state.buildings.values()
        ):
            state.social_policy.stored_bodies += state.social_policy.unhandled_bodies
            state.social_policy.unhandled_bodies = 0

    @staticmethod
    def _medical_buildings_exist(state: GameState) -> bool:
        return any(
            item.building_type in {"medical_station", "hospital"}
            for item in state.buildings.values()
        )

    @staticmethod
    def _medical_buildings_running(state: GameState) -> bool:
        return any(
            item.building_type in {"medical_station", "hospital"}
            and item.is_operational
            for item in state.buildings.values()
        )

    def _score(self, state: GameState) -> dict[str, int]:
        records = list(state.final_frost.daily_records.values())
        count = lambda name: sum(bool(getattr(record, name)) for record in records)
        coal_shortage = count("coal_shortage")
        furnace_off = count("furnace_off")
        underheated = count("furnace_underheated")
        redline = count("overload_redline")
        coal_collapsed = (
            furnace_off >= 3 or coal_shortage >= 6 or redline >= 3
        )
        if coal_collapsed:
            coal = 0
        elif (
            furnace_off == 0
            and coal_shortage == 0
            and underheated <= 1
            and redline == 0
            and state.resources.coal > 0
            and state.furnace.pressure < 70
        ):
            coal = 4
        elif furnace_off == 0 and coal_shortage <= 1 and underheated <= 2 and redline <= 1 and state.furnace.pressure < 85:
            coal = 3
        elif furnace_off <= 1 and coal_shortage <= 3 and underheated <= 4 and state.furnace.pressure < 95:
            coal = 2
        else:
            coal = 1

        frost = state.final_frost
        if frost.legacy_hunger_history_unknown:
            shortage = count("food_shortage")
            starvation = count("starvation")
            edible_x100 = (
                (state.resources.cooked_food + state.resources.raw_food) * 100
                // max(state.population.population_alive, 1)
            )
            food_deaths = sum(record.food_deaths for record in records)
            if starvation == 0 and shortage <= 1 and edible_x100 >= 200:
                food = 4
            elif starvation == 0 and shortage <= 2 and edible_x100 >= 100:
                food = 3
            elif starvation <= 1 and shortage <= 4 and food_deaths == 0:
                food = 2
            elif starvation >= 4 or food_deaths >= 5:
                food = 0
            else:
                food = 1
        else:
            hunger_rules = self.rules.hunger
            hunger_days = frost.frost_hunger_days
            hunger_day_score = (
                4
                if hunger_days == 0
                else 3
                if hunger_days <= hunger_rules["score_hunger_days_three_max"]
                else 2
                if hunger_days <= hunger_rules["score_hunger_days_two_max"]
                else 1
                if hunger_days <= hunger_rules["score_hunger_days_one_max"]
                else 0
            )
            peak_count = frost.frost_peak_unfed_count
            peak_population = frost.frost_peak_population_start
            peak_score = (
                4
                if peak_count == 0
                else 3
                if peak_count * 100
                < peak_population * hunger_rules["score_peak_three_percent"]
                else 2
                if peak_count * 100
                < peak_population * hunger_rules["score_peak_two_percent"]
                else 1
                if peak_count * 100
                < peak_population * hunger_rules["score_peak_one_percent"]
                else 0
            )
            unfed_person_days = frost.frost_unfed_person_days
            population_person_days = frost.frost_population_person_days
            cumulative_score = (
                4
                if unfed_person_days == 0
                else 3
                if unfed_person_days * 100
                < population_person_days
                * hunger_rules["score_cumulative_three_percent"]
                else 2
                if unfed_person_days * 100
                < population_person_days
                * hunger_rules["score_cumulative_two_percent"]
                else 1
                if unfed_person_days * 100
                < population_person_days
                * hunger_rules["score_cumulative_one_percent"]
                else 0
            )
            food = min(hunger_day_score, peak_score, cumulative_score)
            if frost.frost_hunger_deaths > 0:
                food = min(food, hunger_rules["score_frost_death_cap"])

        alive = max(state.population.population_alive, 1)
        cover = state.housing.capacity * 100 // alive
        cold_days = count("cold_houses_day")
        cold_death_days = sum(record.cold_deaths > 0 for record in records)
        frozen_days = count("critical_building_frozen")
        housing_collapsed = (
            state.population.homeless_population > 40
            or cold_days >= 5
            or cold_death_days >= 2
            or frozen_days >= 4
        )
        if housing_collapsed:
            housing = 0
        elif cover >= 100 and state.population.homeless_population == 0 and cold_days <= 1 and cold_death_days == 0 and frozen_days == 0:
            housing = 4
        elif cover >= 95 and state.population.homeless_population <= 5 and cold_days <= 2 and cold_death_days == 0:
            housing = 3
        elif cover >= 80 and state.population.homeless_population <= 20 and cold_days <= 4 and cold_death_days <= 1:
            housing = 2
        else:
            housing = 1

        patients = state.population.sick_population + state.population.critical_population
        medical_cover = state.medical.effective_capacity * 100 // max(patients, 1)
        critical_ratio = state.population.critical_population * 100 // alive
        overflow = count("medical_overflow")
        collapse = count("medical_collapse")
        disease_deaths = sum(record.disease_deaths for record in records)
        medical_collapsed = (
            collapse >= 4
            or (
                self._medical_buildings_exist(state)
                and count("hospital_shutdown") >= 4
            )
        )
        if medical_collapsed:
            medical = 0
        elif medical_cover >= 100 and critical_ratio <= 5 and overflow <= 1 and disease_deaths == 0:
            medical = 4
        elif medical_cover >= 80 and critical_ratio <= 10 and overflow <= 2:
            medical = 3
        elif medical_cover >= 50 and critical_ratio <= 18 and collapse <= 1:
            medical = 2
        else:
            medical = 1

        trust = state.trust_panic.trust or 0
        panic = state.trust_panic.panic or 0
        trust_crisis = count("trust_crisis")
        panic_crisis = count("panic_crisis")
        old_departed = state.old_city.result_id in {
            "partial_exodus",
            "large_exodus",
        }
        if trust >= 70 and panic <= 30 and trust_crisis == 0 and panic_crisis == 0 and not old_departed:
            society = 4
        elif trust >= 50 and panic <= 50 and trust_crisis <= 1 and panic_crisis <= 1:
            society = 3
        elif trust >= 30 and panic <= 75 and trust_crisis <= 3 and panic_crisis <= 3:
            society = 2
        elif (trust == 0 and state.oath_order.final_oath_active) or (panic == 100 and state.oath_order.highest_order_active) or (old_departed and (trust < 30 or panic > 75)):
            society = 0
        else:
            society = 1
        if old_departed:
            society = min(society, 2)

        baseline = max(state.final_frost.baseline_alive_population, 1)
        survival = state.population.population_alive * 100 // baseline
        continuity = max(
            self.rules.scoring["city_continuity_minimum"],
            baseline * self.rules.scoring["city_continuity_population_percent"] // 100,
        )
        mass_death_days = count("mass_death")
        if survival >= 90 and mass_death_days == 0 and state.population.population_alive >= continuity * 2:
            population = 4
        elif survival >= 75 and mass_death_days <= 1 and state.population.population_alive >= continuity:
            population = 3
        elif survival >= 55 and state.population.population_alive >= continuity:
            population = 2
        elif survival < 35 or state.population.population_alive < continuity * 60 // 100:
            population = 0
        else:
            population = 1
        return dict(
            zip(
                _SYSTEM_ORDER,
                (coal, food, housing, medical, society, population),
                strict=True,
            )
        )

    def _result_for_total(self, state: GameState, total: int) -> str:
        minimums = (
            _LEGACY_PATCH_021_RESULT_SCORE_MINIMUMS
            if state.final_frost.balance_profile_id == "legacy_patch021"
            else self.rules.scoring["result_score_minimums"]
        )
        return next(
            result for result in _RESULT_ORDER if total >= minimums[result]
        )

    def _apply_result_caps(
        self, state: GameState, scores: dict[str, int], result: str
    ) -> str:
        cap = "high_victory"
        zeros = sum(score == 0 for score in scores.values())
        high_victory_death_ratio_percent = (
            _LEGACY_PATCH_021_HIGH_VICTORY_DEATH_RATIO_PERCENT
            if state.final_frost.balance_profile_id == "legacy_patch021"
            else self.rules.scoring["high_victory_death_ratio_percent"]
        )
        if (
            any(score == 0 for score in scores.values())
            or (
                state.final_frost.balance_profile_id == "patch022"
                and any(score < 3 for score in scores.values())
            )
            or (
                state.population.population_dead * 100
                > max(state.population.population_total_ever, 1)
                * high_victory_death_ratio_percent
            )
        ):
            cap = "standard_victory"
        if scores["coal_and_core"] <= 1 or scores["population_and_death"] <= 1:
            cap = "bitter_victory"
        if zeros >= 3:
            cap = "collapse_survival"
        if state.final_frost.wood_supply_locked:
            cap = "collapse_survival"
        if zeros >= 5:
            cap = "ember_survival"
        return _RESULT_ORDER[max(_RESULT_ORDER.index(result), _RESULT_ORDER.index(cap))]

    def _ending_tags(
        self, state: GameState, scores: dict[str, int]
    ) -> list[str]:
        records = list(state.final_frost.daily_records.values())
        tags = list(state.final_frost.preparation_tags)
        add = lambda tag, condition: tags.append(tag) if condition and tag not in tags else None
        add("coal_desperate", sum(item.coal_shortage for item in records) >= 3)
        add("cold_engine", sum(item.furnace_underheated for item in records) >= 3)
        add("redline_survivor", any(item.overload_redline for item in records))
        add("wood_supply_locked", state.final_frost.wood_supply_locked)
        starvation_days = sum(item.starvation for item in records)
        add("famine_survivor", starvation_days > 0)
        add(
            "famine_city",
            starvation_days >= 3
            or any(item.food_deaths > 0 for item in records),
        )
        add("cold_houses", sum(item.cold_houses_day for item in records) >= 2)
        add(
            "frozen_homeless",
            any(
                item.homeless_exposure_population > 0
                and (
                    item.homeless_new_sick
                    + item.homeless_new_disabled
                    + item.homeless_cold_deaths
                )
                > 0
                for item in records
            ),
        )
        add("medical_collapse", sum(item.medical_collapse for item in records) >= 2 or scores["medical_and_disease"] == 0)
        add("silent_hospital", sum(item.hospital_shutdown for item in records) >= 2)
        add(
            "mass_death",
            sum(item.mass_death for item in records) >= 2
            or state.final_frost.frost_deaths * 100
            > state.final_frost.baseline_alive_population
            * self.rules.scoring["mass_death_frost_ratio_percent"],
        )
        add(
            "grave_city",
            state.population.population_dead * 100
            > state.population.population_total_ever
            * self.rules.scoring["grave_city_death_ratio_percent"],
        )
        add("broken_society", scores["trust_and_panic"] == 0)
        add("oath_carried_zero_trust", (state.trust_panic.trust or 0) == 0 and state.oath_order.final_oath_active)
        add("decree_carried_panic", (state.trust_panic.panic or 0) == 100 and state.oath_order.highest_order_active)
        continuity = max(
            self.rules.scoring["city_continuity_minimum"],
            state.final_frost.baseline_alive_population
            * self.rules.scoring["city_continuity_population_percent"]
            // 100,
        )
        add("city_continuity_broken", 0 < state.population.population_alive < continuity)
        zero_scores = sum(score == 0 for score in scores.values())
        insufficient_scores = sum(score == 1 for score in scores.values())
        low_scores = sum(score <= 1 for score in scores.values())
        mass_death_day = any(item.mass_death for item in records)
        city_continuity_broken = (
            0 < state.population.population_alive < continuity
        )
        survived = (
            state.population.population_alive > 0
            and state.final_result.hard_fail_type is None
        )
        broken_survival = survived and (
            zero_scores >= 2
            or sum(scores.values()) <= 9
            or city_continuity_broken
            or (mass_death_day and low_scores >= 2)
        )
        if broken_survival:
            add("frost_survived_broken", True)
        else:
            add(
                "frost_survived_clean",
                survived
                and zero_scores == 0
                and insufficient_scores <= 1
                and not mass_death_day,
            )
        add("old_city_stabilized", state.old_city.result_id == "scattered")
        add(
            "old_city_departed",
            state.old_city.result_id in {"partial_exodus", "large_exodus"},
        )
        add(
            "old_city_persuaded",
            "stay_persuasion" in state.oath_order.action_last_used_day,
        )
        add(
            "old_city_suppressed",
            "registry_check" in state.oath_order.action_last_used_day,
        )
        add(
            "old_city_unresolved",
            state.old_city.result_id
            not in {"scattered", "partial_exodus", "large_exodus"},
        )
        arrival_choices = list(state.events.fixed_arrival_choices.values())
        add("opened_gates", arrival_choices.count("accept_all") >= 2)
        add("closed_gates", arrival_choices.count("reject") >= 2)
        add(
            "refugee_pressure",
            any(
                len(state.events.fixed_arrival_pressure_days.get(event_id, []))
                >= 3
                for event_id, choice in state.events.fixed_arrival_choices.items()
                if choice != "reject"
            ),
        )
        signed_route_laws = set(state.oath_order.signed_law_ids)
        for law_id, tag in (
            ("mourning_bell", "mourning_bell"),
            ("ember_roster", "ember_register"),
            ("stay_oath", "stay_oath"),
            ("morning_roll_call", "morning_rollcall"),
            ("unified_announcement", "unified_notice"),
            ("household_registry_check", "census_control"),
        ):
            add(tag, law_id in signed_route_laws)
        add(
            "shared_meal_oath",
            "shared_meal" in signed_route_laws
            and "shared_meal" in state.oath_order.action_last_used_day,
        )
        add("final_oath", state.oath_order.final_oath_active)
        add(
            "detention_used",
            "detain" in state.oath_order.action_last_used_day,
        )
        add("final_decree", state.oath_order.highest_order_active)
        promise_history = state.promises.settlement_history
        key_successes = sum(
            item.outcome == "success"
            and item.severity in {"serious", "critical"}
            for item in promise_history
        )
        failures = [
            item for item in promise_history if item.outcome == "failure"
        ]
        serious_failures = sum(
            item.severity in {"serious", "critical"} for item in failures
        )
        add(
            "promise_keeper",
            key_successes >= 4 and serious_failures == 0,
        )
        add(
            "promise_breaker",
            len(failures) >= 3 or serious_failures >= 2,
        )
        failed_types = {
            settlement.promise_type
            for settlement in promise_history
            if settlement.outcome == "failure"
        }
        add(
            "medical_promise_failed",
            "medical" in failed_types
            and scores["medical_and_disease"] <= 1,
        )
        add(
            "food_promise_failed",
            "food" in failed_types and scores["food"] <= 1,
        )
        add(
            "children_promise_failed",
            "children" in failed_types
            and state.population.disabled_population > 0,
        )
        old_city_failure_advanced = (
            state.old_city.promise_outcome == "failure"
            and state.old_city.promise_settled_day is not None
            and (
                (
                    state.old_city.countdown_day is not None
                    and state.old_city.countdown_day
                    >= state.old_city.promise_settled_day
                )
                or (
                    state.old_city.result_id
                    in {"partial_exodus", "large_exodus"}
                    and state.old_city.settlement_day is not None
                    and state.old_city.settlement_day
                    >= state.old_city.promise_settled_day
                )
            )
        )
        add("old_city_promise_failed", old_city_failure_advanced)
        for tag in state.oath_order.ending_tag_candidates:
            add(tag, tag in self.rules.tag_severity)
        for tag in state.social_policy.ending_tag_candidates:
            add(tag, tag in self.rules.tag_severity)
        return [tag for tag in self.rules.tag_severity if tag in tags]
