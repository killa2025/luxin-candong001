from __future__ import annotations

from dataclasses import dataclass

from furnace_winter.config.buildings import BuildingRules
from furnace_winter.config.final_frost import FinalFrostRules
from furnace_winter.config.survival import SurvivalRules
from furnace_winter.config.technologies import TechnologyRules
from furnace_winter.gameplay.end_day import EndDayContext, EndDayEngine, EndDayStage
from furnace_winter.gameplay.survival import furnace_coal_cost
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
            EndDayStage.UPDATE_PROMISE_TARGETS,
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
        frost = state.final_frost
        if state.calendar.current_day >= self.rules.start_day and not frost.entered:
            raise ValueError("D49+ state must retain its final-frost baseline")
        record_days = sorted(int(day) for day in frost.daily_records)
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
        for day in record_days:
            record = frost.daily_records[str(day)]
            expected = self.rules.temperatures[day]
            if (
                record.real_temperature != expected.real
                or record.display_label != expected.display_label
            ):
                raise ValueError("final-frost record temperature is not canonical")
        if frost.final_score_day is not None and record_days != list(
            range(self.rules.start_day, self.rules.end_day + 1)
        ):
            raise ValueError("D55 scoring requires all seven final-frost records")

    def prepare_new_day(self, state: GameState) -> None:
        if state.calendar.current_day == self.rules.start_day:
            self._capture_baseline(state)

    def resolve_frost_health(self, context: EndDayContext) -> None:
        if not self.rules.is_frost_day(context.settled_day):
            return
        state = context.state
        if not state.final_frost.entered:
            self._capture_baseline(state)
        population_start = (
            state.final_frost.daily_records[
                str(context.settled_day - 1)
            ].population_end
            if str(context.settled_day - 1)
            in state.final_frost.daily_records
            else state.final_frost.baseline_alive_population
        )
        exposure = self._exposure(state)
        damage = self.rules.damage

        requested_sick = 0
        for level, people, _homeless in exposure:
            if level <= 0 or people <= 0:
                continue
            amount = (people // damage["exposure_population_unit"]) * min(level, 4)
            if level >= 3 and people >= damage["small_group_minimum"]:
                amount = max(amount, 1)
            requested_sick += amount
        new_sick = min(requested_sick, state.population.healthy_population)
        state.population.healthy_population -= new_sick
        state.population.sick_population += new_sick

        critical_before = state.population.critical_population
        sick_before = state.population.sick_population
        capacity = state.medical.effective_capacity
        treated_critical = min(critical_before, capacity)
        treated_sick = min(sick_before, max(capacity - treated_critical, 0))
        untreated_critical = critical_before - treated_critical
        untreated_sick = sick_before - treated_sick

        critical_recovery_numerator = (
            treated_critical + state.medical.critical_treatment_progress
        )
        critical_recovered = min(
            treated_critical,
            critical_recovery_numerator
            // damage["treated_critical_recovery_divisor"],
        )
        state.medical.critical_treatment_progress = (
            critical_recovery_numerator
            % damage["treated_critical_recovery_divisor"]
        )
        sick_recovery_numerator = (
            treated_sick + state.medical.sick_treatment_progress
        )
        sick_recovered = min(
            treated_sick,
            sick_recovery_numerator // damage["treated_sick_recovery_divisor"],
        )
        state.medical.sick_treatment_progress = (
            sick_recovery_numerator % damage["treated_sick_recovery_divisor"]
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
        disease_deaths = min(
            critical_before,
            untreated_critical // damage["untreated_critical_death_divisor"]
            + untreated_critical
            // damage["untreated_critical_extra_death_divisor"]
            + treated_critical // treated_death_divisor,
        )
        remaining_critical = max(
            critical_before - critical_recovered, 0
        )
        new_critical = min(
            untreated_sick // damage["untreated_sick_severe_divisor"]
            + (
                treated_sick // damage["treated_sick_severe_divisor"]
                if state.medical.medical_pressure >= 10
                else 0
            ),
            max(sick_before - sick_recovered, 0),
        )
        new_disabled = min(
            remaining_critical,
            untreated_critical
            // damage["untreated_critical_disability_divisor"],
        )

        state.population.critical_population = (
            remaining_critical + new_critical - new_disabled
        )
        state.population.sick_population = max(
            sick_before - sick_recovered - new_critical, 0
        )
        state.population.healthy_population += (
            sick_recovered + critical_recovered
        )
        state.population.disabled_population = min(
            state.population.disabled_population + new_disabled,
            state.population.population_alive,
        )

        exposure_disability = 0
        cold_deaths = 0
        medical_buffer = max(capacity - critical_before - sick_before, 0)
        for level, people, homeless in exposure:
            divisor = (
                damage["cold_disability_level_4_divisor"]
                if level >= 4
                else damage["cold_disability_level_3_divisor"]
                if level == 3
                else damage["cold_disability_level_2_divisor"]
            )
            if level >= 2:
                exposure_disability += people // divisor
            if level >= 4:
                death_divisor = (
                    damage["homeless_cold_death_divisor"]
                    if homeless
                    else damage["housed_cold_death_divisor"]
                )
                cold_deaths += (
                    people // death_divisor
                    + people // damage["frost_extra_cold_death_divisor"]
                )
        prevented = medical_buffer // damage[
            "medical_buffer_per_prevented_disability"
        ]
        exposure_disability = max(exposure_disability - prevented, 0)
        exposure_disability = self._apply_disabilities(
            state, exposure_disability
        )

        cold_deaths = min(
            cold_deaths,
            max(state.population.population_alive - disease_deaths, 0),
        )
        disease_deaths = self._apply_deaths(
            state, disease_deaths, "disease"
        )
        cold_deaths = self._apply_deaths(state, cold_deaths, "cold")
        self._settle_new_bodies(state, disease_deaths + cold_deaths)
        state.medical.medical_pressure = max(
            state.population.sick_population
            + state.population.critical_population
            - state.medical.effective_capacity,
            0,
        )

        metrics = state.events.metrics
        metrics[f"{_FROST_METRIC_PREFIX}population_start"] = population_start
        metrics[f"{_FROST_METRIC_PREFIX}new_sick"] = new_sick
        metrics[f"{_FROST_METRIC_PREFIX}new_critical"] = new_critical
        metrics[f"{_FROST_METRIC_PREFIX}new_disabled"] = (
            new_disabled + exposure_disability
        )
        metrics[f"{_FROST_METRIC_PREFIX}disease_deaths"] = disease_deaths
        metrics[f"{_FROST_METRIC_PREFIX}cold_deaths"] = cold_deaths
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
        context.emit(
            "final_frost.health.resolved",
            {
                "day": context.settled_day,
                "new_sick": new_sick,
                "new_critical": new_critical,
                "new_disabled": new_disabled + exposure_disability,
                "disease_deaths": disease_deaths,
                "cold_deaths": cold_deaths,
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
        cold_housed = metrics.get(f"{_FROST_METRIC_PREFIX}cold_housed", 0)
        mass_exposure = metrics.get(
            f"{_FROST_METRIC_PREFIX}mass_exposure", 0
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
            homeless_exposure_population=metrics.get(
                f"{_FROST_METRIC_PREFIX}homeless_exposure", 0
            ),
            mass_cold_exposure_population=mass_exposure,
            food_shortage=state.daily_survival.food_shortfall > 0,
            starvation=state.daily_survival.unfed_population > 0,
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
            food_deaths=food_deaths,
            disease_deaths=disease_deaths,
            cold_deaths=cold_deaths,
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
        state.final_frost.frost_deaths += total_population_loss
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
            return
        scores = self._score(state)
        total = sum(scores.values())
        ending_id = self._result_for_total(total)
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

    def observe(self, state: GameState) -> dict[str, object]:
        self.validate_state(state)
        return {
            "active": self.rules.is_frost_day(state.calendar.current_day),
            "start_day": self.rules.start_day,
            "end_day": self.rules.end_day,
            "baseline_day": state.final_frost.baseline_day,
            "preparation_tags": list(state.final_frost.preparation_tags),
            "settled_days": sorted(int(day) for day in state.final_frost.daily_records),
            "frost_deaths": state.final_frost.frost_deaths,
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
        coal_days = state.resources.coal // max(
            furnace_coal_cost(state, self.survival_rules, 3), 1
        )
        food_days = (
            state.resources.cooked_food + state.resources.raw_food
        ) // max(population.population_alive, 1)
        trust = state.trust_panic.trust or 0
        panic = state.trust_panic.panic or 0
        pressure = state.furnace.pressure
        prep = self.rules.preparation
        checks = (
            coal_days >= prep["prepared_coal_days"],
            food_days >= prep["prepared_food_days"],
            population.homeless_population == 0,
            state.medical.medical_pressure == 0,
            trust >= prep["prepared_trust"] and panic <= prep["prepared_panic"],
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
            trust < prep["unprepared_trust"] or panic > prep["unprepared_panic"],
            pressure >= prep["unprepared_pressure"],
        )
        frost.prepared_item_count = sum(checks)
        frost.unprepared_item_count = sum(weak)
        if frost.prepared_item_count >= prep["prepared_required_items"]:
            frost.preparation_tags.append("prepared_for_frost")
        elif frost.unprepared_item_count >= prep["unprepared_required_items"]:
            frost.preparation_tags.append("unprepared_frost")

    def _exposure(self, state: GameState) -> list[tuple[int, int, bool]]:
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
                    self._exposure_level(building.effective_temperature),
                    people,
                    False,
                )
            )
        if alive_to_assign > 0:
            groups.append(
                (
                    self.rules.damage["minimum_exposure_level"],
                    alive_to_assign,
                    False,
                )
            )
        groups.append(
            (
                self.rules.damage["minimum_exposure_level"],
                state.population.homeless_population,
                True,
            )
        )
        return groups

    def _exposure_level(self, temperature: int) -> int:
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
        if original < 2:
            return original
        return min(
            max(
                original + self.rules.damage["extra_exposure_level"],
                self.rules.damage["minimum_exposure_level"],
            ),
            self.rules.damage["exposure_level_cap"],
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
        if cause == "cold":
            state.events.cold_exposure_deaths_total += deaths
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
        if (
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
        elif furnace_off >= 3 or coal_shortage >= 6 or redline >= 3:
            coal = 0
        else:
            coal = 1

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

        alive = max(state.population.population_alive, 1)
        cover = state.housing.capacity * 100 // alive
        cold_days = count("cold_houses_population")
        cold_death_days = sum(record.cold_deaths > 0 for record in records)
        frozen_days = count("critical_building_frozen")
        if cover >= 100 and state.population.homeless_population == 0 and cold_days <= 1 and cold_death_days == 0 and frozen_days == 0:
            housing = 4
        elif cover >= 95 and state.population.homeless_population <= 5 and cold_days <= 2 and cold_death_days == 0:
            housing = 3
        elif cover >= 80 and state.population.homeless_population <= 20 and cold_days <= 4 and cold_death_days <= 1:
            housing = 2
        elif state.population.homeless_population > 40 or cold_days >= 5 or cold_death_days >= 2 or frozen_days >= 4:
            housing = 0
        else:
            housing = 1

        patients = state.population.sick_population + state.population.critical_population
        medical_cover = state.medical.effective_capacity * 100 // max(patients, 1)
        critical_ratio = state.population.critical_population * 100 // alive
        overflow = count("medical_overflow")
        collapse = count("medical_collapse")
        disease_deaths = sum(record.disease_deaths for record in records)
        if medical_cover >= 100 and critical_ratio <= 5 and overflow <= 1 and disease_deaths == 0:
            medical = 4
        elif medical_cover >= 80 and critical_ratio <= 10 and overflow <= 2:
            medical = 3
        elif medical_cover >= 50 and critical_ratio <= 18 and collapse <= 1:
            medical = 2
        elif collapse >= 4 or (self._medical_buildings_exist(state) and count("hospital_shutdown") >= 4):
            medical = 0
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

    def _result_for_total(self, total: int) -> str:
        minimums = self.rules.scoring["result_score_minimums"]
        return next(
            result for result in _RESULT_ORDER if total >= minimums[result]
        )

    def _apply_result_caps(
        self, state: GameState, scores: dict[str, int], result: str
    ) -> str:
        cap = "high_victory"
        death_ratio = (
            state.population.population_dead * 100
            // max(state.population.population_total, 1)
        )
        zeros = sum(score == 0 for score in scores.values())
        if any(score == 0 for score in scores.values()) or death_ratio > self.rules.scoring["high_victory_death_ratio_percent"]:
            cap = "standard_victory"
        if scores["coal_and_core"] <= 1 or scores["population_and_death"] <= 1:
            cap = "bitter_victory"
        if zeros >= 3:
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
        starvation_days = sum(item.starvation for item in records)
        add("famine_survivor", starvation_days > 0)
        add(
            "famine_city",
            starvation_days >= 3
            or any(item.food_deaths > 0 for item in records),
        )
        add("cold_houses", sum(item.cold_houses_population > 0 for item in records) >= 2)
        add("frozen_homeless", any(item.homeless_exposure_population > 0 and (item.new_sick + item.new_disabled + item.cold_deaths) > 0 for item in records))
        add("medical_collapse", sum(item.medical_collapse for item in records) >= 2 or scores["medical_and_disease"] == 0)
        add("silent_hospital", sum(item.hospital_shutdown for item in records) >= 2)
        add("mass_death", any(item.mass_death for item in records))
        grave_line = max(20, state.population.population_total * 25 // 100)
        add("grave_city", state.population.population_dead >= grave_line)
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
        add("frost_survived_clean", all(score >= 3 for score in scores.values()) and state.final_frost.frost_deaths == 0)
        add("frost_survived_broken", any(score == 0 for score in scores.values()))
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
            any(choice != "reject" for choice in arrival_choices)
            and (
                scores["food"] <= 1
                or scores["housing_and_temperature"] <= 1
                or scores["medical_and_disease"] <= 1
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
        completed = len(state.promises.completed_promise_ids)
        failed = len(state.promises.failed_promise_ids)
        add("promise_keeper", completed >= 2 and failed == 0)
        add("promise_breaker", failed >= 2)
        failed_types = {
            settlement.promise_type
            for settlement in state.promises.settlement_history
            if settlement.outcome == "failed"
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
        add("old_city_promise_failed", state.old_city.promise_outcome == "failed")
        for tag in state.oath_order.ending_tag_candidates:
            add(tag, tag in self.rules.tag_severity)
        for tag in state.social_policy.ending_tag_candidates:
            add(tag, tag in self.rules.tag_severity)
        return [tag for tag in self.rules.tag_severity if tag in tags]
