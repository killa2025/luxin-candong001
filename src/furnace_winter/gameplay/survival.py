from __future__ import annotations

from copy import deepcopy
from dataclasses import fields

from furnace_winter.config import BuildingRules, SurvivalRules, TechnologyRules
from furnace_winter.gameplay.end_day import (
    EndDayContext,
    EndDayEngine,
    EndDayStage,
    RiskWarning,
    RiskWarningLevel,
)
from furnace_winter.interface import (
    ArgumentKind,
    CommandCatalog,
    CommandRequest,
    CommandResult,
    CommandSpec,
    CommandValidation,
    CommandValidator,
    ErrorCode,
    FeedbackItem,
    FeedbackLevel,
)
from furnace_winter.models import (
    BuildingState,
    DailySurvivalState,
    GameState,
    HardFailType,
    HousingState,
    PopulationState,
    ResourceState,
    SaveDataError,
    SurfaceResourcePointState,
    TrustPanicState,
    validate_game_state,
)


SET_FURNACE_COMMAND = "game.set_furnace"
FURNACE_LEVEL_ARGUMENT = "level"


def furnace_mode_id(level: int) -> str:
    if level not in {0, 1, 2, 3}:
        raise ValueError("furnace level must be between 0 and 3")
    return "off" if level == 0 else f"level_{level}"


def furnace_level(mode_id: str) -> int:
    if mode_id == "off":
        return 0
    if mode_id in {"level_1", "level_2", "level_3"}:
        return int(mode_id[-1])
    raise ValueError(f"unsupported furnace mode: {mode_id!r}")


def storage_used(resources: ResourceState) -> int:
    return (
        resources.coal
        + resources.wood
        + resources.steel
        + resources.raw_food
        + resources.cooked_food
    )


def is_over_capacity(resources: ResourceState) -> bool:
    return storage_used(resources) > resources.storage_capacity


def projected_woodfuel_available(
    state: GameState,
    building_rules: BuildingRules | None,
) -> int:
    if (
        building_rules is None
        or not state.building_management.woodfuel_confirmed_today
    ):
        return 0
    rule = building_rules.woodfuel
    usable_wood = min(state.resources.wood, rule.daily_wood_limit)
    usable_wood -= usable_wood % rule.minimum_wood_unit
    return usable_wood // rule.wood_per_fuel


def projected_furnace_level(
    state: GameState,
    survival_rules: SurvivalRules,
    building_rules: BuildingRules | None,
    technology_rules: TechnologyRules | None = None,
) -> int:
    target_level = furnace_level(state.furnace.mode_id)
    reserved_overload_coal = 0
    if technology_rules is not None and target_level > 0:
        overload = technology_rules.overload.levels[state.furnace.overload_level]
        if state.resources.coal >= overload.coal_cost:
            reserved_overload_coal = overload.coal_cost
    available_fuel = state.resources.coal - reserved_overload_coal + projected_woodfuel_available(
        state, building_rules
    )
    return max(
        level
        for level in range(target_level + 1)
        if furnace_coal_cost(state, survival_rules, level) <= available_fuel
    )


def furnace_coal_cost(
    state: GameState, survival_rules: SurvivalRules, level: int
) -> int:
    if level == 0:
        return 0
    researched = set(state.technologies.researched_tech_ids)
    if "tech_furnace_coal_saving_2" in researched:
        return {1: 35, 2: 68, 3: 120}[level]
    if "tech_furnace_coal_saving_1" in researched:
        return {1: 40, 2: 75, 3: 135}[level]
    return survival_rules.furnace_levels[level].coal_cost


def projected_building_insulation_bonus(
    state: GameState,
    building: BuildingState,
) -> int:
    bonus = 0
    researched = set(state.technologies.researched_tech_ids)
    if building.building_type in {
        "basic_residence",
        "improved_residence",
        "advanced_residence",
    }:
        if "tech_housing_insulation_1" in researched:
            bonus += 4
    elif building.building_type not in {
        "small_warehouse",
        "cemetery",
        "cold_pit",
        "gathering_shelter",
    }:
        if "tech_building_insulation_2" in researched:
            bonus += 12
        elif "tech_building_insulation_1" in researched:
            bonus += 6
    if (
        building.building_type in {"medical_station", "hospital"}
        and "tech_medical_building_insulation" in researched
    ):
        bonus += 8
    return bonus


def projected_heat_bonus(state: GameState, building_rules: BuildingRules) -> int:
    heat = building_rules.heat
    return (
        heat.enhanced_temperature_bonus
        if heat.enhancement_tech_id in state.technologies.researched_tech_ids
        else heat.temperature_bonus
    )


def projected_building_temperature(
    state: GameState,
    building: BuildingState,
    building_rules: BuildingRules,
    survival_rules: SurvivalRules,
    effective_furnace_level: int,
    technology_rules: TechnologyRules | None = None,
    *,
    include_heat: bool,
) -> int:
    zone = "outer_ring" if building.zone == "storage_outer" else building.zone
    overload_bonus = (
        technology_rules.overload.levels[state.furnace.overload_level].temperature_bonus
        if technology_rules is not None
        and effective_furnace_level > 0
        and state.resources.coal
        >= technology_rules.overload.levels[state.furnace.overload_level].coal_cost
        else 0
    )
    final_bonus = (
        3
        if 49 <= state.calendar.current_day <= 55
        and effective_furnace_level > 0
        and "tech_final_furnace_stability"
        in state.technologies.researched_tech_ids
        else 0
    )
    return (
        survival_rules.weather_for_day(state.calendar.current_day)
        + survival_rules.furnace_levels[effective_furnace_level].heating
        + survival_rules.zone_modifiers[zone]
        + overload_bonus
        + final_bonus
        + projected_building_insulation_bonus(state, building)
        + (projected_heat_bonus(state, building_rules) if include_heat else 0)
    )


def is_building_expected_operational(
    state: GameState,
    building: BuildingState,
    building_rules: BuildingRules,
    survival_rules: SurvivalRules,
    technology_rules: TechnologyRules | None = None,
) -> bool:
    """Return whether a built and staffed building is expected to run today."""

    rule = building_rules.buildings.get(building.building_type)
    if rule is None or not building.is_built:
        return False
    assigned = sum(
        (
            building.assigned_workers,
            building.assigned_engineers,
            building.assigned_children,
            building.assigned_medical_apprentices,
            building.assigned_engineering_apprentices,
        )
    )
    if rule.staff_capacity > 0 and assigned <= 0:
        return False
    if rule.min_operating_temperature is None:
        return True
    effective_level = projected_furnace_level(
        state, survival_rules, building_rules, technology_rules
    )
    temperature = projected_building_temperature(
        state,
        building,
        building_rules,
        survival_rules,
        effective_level,
        technology_rules,
        include_heat=building.heated_today,
    )
    return temperature >= rule.min_operating_temperature


def create_initial_survival_state(
    rules: SurvivalRules,
    building_rules: BuildingRules | None = None,
    *,
    random_seed: int = 0,
) -> GameState:
    state = GameState.initial(random_seed=random_seed)
    total = rules.population.total
    housing_capacity = rules.starting_housing_capacity
    state.population = PopulationState(
        population_total=total,
        population_alive=total,
        population_dead=0,
        workers=rules.population.workers,
        engineers=rules.population.engineers,
        children=rules.population.children,
        healthy_population=total,
        sick_population=0,
        critical_population=0,
        disabled_population=0,
        housed_population=min(total, housing_capacity),
        homeless_population=max(total - housing_capacity, 0),
    )
    state.resources = ResourceState(
        coal=rules.resources.coal,
        wood=rules.resources.wood,
        steel=rules.resources.steel,
        raw_food=rules.resources.raw_food,
        cooked_food=rules.resources.cooked_food,
        storage_capacity=rules.resources.storage_capacity,
    )
    state.housing = HousingState(
        basic_residences=rules.basic_residences,
        capacity=housing_capacity,
    )
    if building_rules is not None:
        state.building_management.zone_slot_capacity = dict(
            building_rules.zone_slot_capacity
        )
        state.building_management.total_hunting_areas = len(
            building_rules.resource_anchors["hunting_area"]
        )
        state.building_management.available_hunting_areas = 1
        state.building_management.forest_zones = len(
            building_rules.resource_anchors["forest_zone"]
        )
        state.surface_resource_points = {
            resource_point_id: SurfaceResourcePointState(
                resource_point_id=resource_point_id,
                resource_type=point_rule.resource_type,
                remaining_amount=point_rule.total_amount,
                staff_capacity=point_rule.staff_capacity,
            )
            for resource_point_id, point_rule in building_rules.surface_resource_points.items()
        }
    for index in range(1, rules.basic_residences + 1):
        building_id = f"residence-start-{index:03d}"
        state.buildings[building_id] = BuildingState(
            building_id=building_id,
            building_type="basic_residence",
            zone="inner_ring",
            slot_size=1,
            is_built=True,
            is_operational=True,
            can_heat=False,
        )
    state.building_management.zone_slots_used["inner_ring"] = rules.basic_residences
    state.furnace.is_active = rules.starting_furnace_level > 0
    state.furnace.mode_id = furnace_mode_id(rules.starting_furnace_level)
    state.trust_panic = TrustPanicState(
        trust=rules.starting_trust,
        panic=rules.starting_panic,
    )
    state.daily_survival.storage_used = storage_used(state.resources)
    state.daily_survival.is_over_capacity = is_over_capacity(state.resources)
    validate_game_state(state, building_rules, rules)
    return state


def build_survival_catalog() -> CommandCatalog:
    catalog = CommandCatalog()
    catalog.register(
        CommandSpec(
            name=SET_FURNACE_COMMAND,
            required_arguments={FURNACE_LEVEL_ARGUMENT: ArgumentKind.INTEGER},
        )
    )
    return catalog


class SurvivalSystem:
    """Patch 003 population, resource, food, housing, and furnace foundation."""

    def __init__(
        self,
        rules: SurvivalRules,
        building_rules: BuildingRules | None = None,
        technology_rules: TechnologyRules | None = None,
    ) -> None:
        self.rules = rules
        self.building_rules = building_rules
        self.technology_rules = technology_rules
        self._catalog = build_survival_catalog()
        self._validator = CommandValidator(self._catalog)

    def command_specs(self) -> tuple[CommandSpec, ...]:
        return self._catalog.specs()

    def execute(self, state: GameState, request: CommandRequest) -> CommandResult:
        request_validation = self._validator.validate(request)
        command_id = (
            request.command_id
            if isinstance(request, CommandRequest)
            and isinstance(request.command_id, str)
            else ""
        )
        state_sequence = (
            state.command_sequence
            if isinstance(state, GameState)
            and isinstance(state.command_sequence, int)
            and not isinstance(state.command_sequence, bool)
            else 0
        )
        if not request_validation.is_valid:
            return CommandResult(
                command_id=command_id,
                accepted=False,
                code=request_validation.code,
                state_sequence=state_sequence,
                feedback=(
                    FeedbackItem(FeedbackLevel.ERROR, data=request_validation.details),
                ),
                data=request_validation.details,
            )

        try:
            validate_game_state(
                state,
                self.building_rules,
                self.rules,
                self.technology_rules,
            )
        except (SaveDataError, TypeError, ValueError) as exc:
            details = {
                "failed_stage": "input_state_validation",
                "exception_type": type(exc).__name__,
            }
            return CommandResult(
                command_id=command_id,
                accepted=False,
                code=ErrorCode.INTERNAL_ERROR,
                state_sequence=state_sequence,
                feedback=(FeedbackItem(FeedbackLevel.ERROR, data=details),),
                data=details,
            )

        validation = self._validator.validate(
            request,
            state,
            self._furnace_legality,
        )
        if not validation.is_valid:
            return CommandResult(
                command_id=command_id,
                accepted=False,
                code=validation.code,
                state_sequence=state_sequence,
                feedback=(FeedbackItem(FeedbackLevel.ERROR, data=validation.details),),
                data=validation.details,
            )

        level = request.arguments[FURNACE_LEVEL_ARGUMENT]
        assert isinstance(level, int) and not isinstance(level, bool)
        working = deepcopy(state)
        working.furnace.is_active = level > 0
        working.furnace.mode_id = furnace_mode_id(level)
        if level == 0:
            working.furnace.overload_level = 0
        working.command_sequence += 1
        try:
            validate_game_state(
                working,
                self.building_rules,
                self.rules,
                self.technology_rules,
            )
        except (SaveDataError, TypeError, ValueError) as exc:
            details = {
                "failed_stage": "result_state_validation",
                "exception_type": type(exc).__name__,
            }
            return CommandResult(
                command_id=command_id,
                accepted=False,
                code=ErrorCode.INTERNAL_ERROR,
                state_sequence=state_sequence,
                feedback=(FeedbackItem(FeedbackLevel.ERROR, data=details),),
                data=details,
            )
        for item in fields(GameState):
            setattr(state, item.name, deepcopy(getattr(working, item.name)))
        return CommandResult(
            command_id=request.command_id,
            accepted=True,
            code=ErrorCode.OK,
            state_changed=True,
            state_sequence=state.command_sequence,
            feedback=(FeedbackItem(FeedbackLevel.INFO, data={"furnace_level": level}),),
            data={"furnace_level": level},
        )

    @staticmethod
    def _furnace_legality(
        state: GameState,
        request: CommandRequest,
    ) -> CommandValidation:
        if request.name != SET_FURNACE_COMMAND:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND)
        if state.final_result.hard_fail_type is not None:
            return CommandValidation(
                False,
                ErrorCode.ILLEGAL_COMMAND,
                {"reason": "game_already_failed"},
            )
        if state.calendar.is_day_locked or state.final_result.is_finalized:
            return CommandValidation(
                False,
                ErrorCode.ILLEGAL_COMMAND,
                {"reason": "day_not_open_for_planning"},
            )
        level = request.arguments.get(FURNACE_LEVEL_ARGUMENT)
        if level not in {0, 1, 2, 3}:
            return CommandValidation(
                False,
                ErrorCode.INVALID_ARGUMENTS,
                {"invalid_furnace_level": level},
            )
        return CommandValidation.valid()

    def install(self, engine: EndDayEngine) -> None:
        engine.register_risk_evaluator(self.evaluate_risks)
        engine.register_stage_handler(
            EndDayStage.PAY_HEATING_AND_OVERLOAD,
            self.settle_heating,
        )
        engine.register_stage_handler(
            EndDayStage.RESOLVE_ACTUAL_HEATING,
            self.resolve_actual_heating,
        )
        if self.technology_rules is not None:
            engine.register_stage_handler(
                EndDayStage.UPDATE_FURNACE_PRESSURE,
                self.update_furnace_pressure,
            )
        engine.register_stage_handler(
            EndDayStage.CALCULATE_ZONE_TEMPERATURE,
            self.calculate_zone_temperatures,
        )
        engine.register_stage_handler(
            EndDayStage.RESOLVE_FOOD_CHAIN,
            self.settle_food,
        )
        engine.register_stage_handler(
            EndDayStage.RESOLVE_HOUSING_COLD_AND_HUNGER,
            self.settle_housing,
        )

    def evaluate_risks(self, state: GameState) -> tuple[RiskWarning, ...]:
        warnings: list[RiskWarning] = []
        target_level = furnace_level(state.furnace.mode_id)
        required_coal = furnace_coal_cost(state, self.rules, target_level)
        overload_rule = (
            self.technology_rules.overload.levels[state.furnace.overload_level]
            if self.technology_rules is not None
            else None
        )
        if overload_rule is not None:
            required_coal += overload_rule.coal_cost
        affordable_level = self._affordable_level(target_level, state)
        if target_level == 0:
            warnings.append(
                RiskWarning(
                    "survival.furnace_off",
                    RiskWarningLevel.B_STRONG,
                    {"target_level": 0},
                )
            )
        elif affordable_level < target_level:
            warnings.append(
                RiskWarning(
                    "survival.heating_fuel_shortfall",
                    RiskWarningLevel.B_STRONG,
                    {
                        "available_coal": state.resources.coal,
                        "required_coal": required_coal,
                        "target_level": target_level,
                        "affordable_level": affordable_level,
                    },
                )
            )
        if overload_rule is not None and overload_rule.level > 0:
            if state.resources.coal < overload_rule.coal_cost:
                warnings.append(
                    RiskWarning(
                        "survival.overload_fuel_shortfall",
                        RiskWarningLevel.B_STRONG,
                        {
                            "available_coal": state.resources.coal,
                            "required_overload_coal": overload_rule.coal_cost,
                            "target_overload_level": overload_rule.level,
                        },
                    )
                )
            pressure = state.furnace.pressure
            threshold = self.technology_rules.overload.redline_threshold
            if state.furnace.pressure_redline_warned and pressure >= threshold:
                warnings.append(
                    RiskWarning(
                        "survival.overload_after_redline",
                        RiskWarningLevel.B_STRONG,
                        {"pressure": pressure, "overload_level": overload_rule.level},
                    )
                )
            elif pressure >= self.technology_rules.overload.high_pressure_threshold:
                warnings.append(
                    RiskWarning(
                        "survival.furnace_high_pressure",
                        RiskWarningLevel.B_STRONG,
                        {"pressure": pressure, "overload_level": overload_rule.level},
                    )
                )

        ration_mode, ration_numerator, ration_denominator = self._effective_ration(
            state
        )
        food_required = self._food_required(
            state.population.population_alive,
            ration_numerator,
            ration_denominator,
        )
        available_food = state.resources.cooked_food + state.resources.raw_food
        if available_food < food_required:
            food_eaten = max(available_food, 0)
            warnings.append(
                RiskWarning(
                    "survival.food_shortfall",
                    RiskWarningLevel.B_STRONG,
                    {
                        "available_food": available_food,
                        "required_food": food_required,
                        "ration_mode_used": ration_mode,
                        "food_shortfall": food_required - food_eaten,
                        "unfed_population": self._unfed_population(
                            state.population.population_alive,
                            food_eaten,
                            ration_numerator,
                            ration_denominator,
                        ),
                    },
                )
            )
        if state.population.homeless_population > 0:
            warnings.append(
                RiskWarning(
                    "survival.housing_shortfall",
                    RiskWarningLevel.A_INFO,
                    {"homeless_population": state.population.homeless_population},
                )
            )
        if is_over_capacity(state.resources):
            warnings.append(
                RiskWarning(
                    "survival.storage_over_capacity",
                    RiskWarningLevel.A_INFO,
                    {
                        "capacity": state.resources.storage_capacity,
                        "used": storage_used(state.resources),
                    },
                )
            )
        return tuple(warnings)

    def _affordable_level(self, target_level: int, state: GameState) -> int:
        projected = projected_furnace_level(
            state, self.rules, self.building_rules, self.technology_rules
        )
        return min(projected, target_level)

    def _woodfuel_available(self, state: GameState) -> int:
        return projected_woodfuel_available(state, self.building_rules)

    def settle_heating(self, context: EndDayContext) -> None:
        state = context.state
        target_level = furnace_level(state.furnace.mode_id)
        target_base_cost = furnace_coal_cost(state, self.rules, target_level)
        target_overload_level = state.furnace.overload_level
        target_overload_rule = (
            self.technology_rules.overload.levels[target_overload_level]
            if self.technology_rules is not None
            else None
        )
        effective_overload_level = 0
        overload_paid = 0
        if (
            target_overload_rule is not None
            and target_level > 0
            and state.resources.coal >= target_overload_rule.coal_cost
        ):
            effective_overload_level = target_overload_level
            overload_paid = target_overload_rule.coal_cost
        effective_level = self._affordable_level(target_level, state)
        effective_base_cost = furnace_coal_cost(state, self.rules, effective_level)
        if effective_level == 0:
            overload_paid = 0
        state.resources.coal -= overload_paid
        coal_paid = min(state.resources.coal, effective_base_cost)
        contribution = effective_base_cost - coal_paid
        wood_burned = 0
        if contribution:
            if self.building_rules is None:
                context.abort(ErrorCode.INTERNAL_ERROR, {"reason": "woodfuel_rules_missing"})
            wood_burned = contribution * self.building_rules.woodfuel.wood_per_fuel
            state.resources.wood -= wood_burned
        state.resources.coal -= coal_paid
        state.daily_survival = DailySurvivalState(
            settled_day=context.settled_day,
            base_temperature=self.rules.weather_for_day(context.settled_day),
            target_furnace_level=target_level,
            effective_furnace_level=effective_level,
            required_coal=target_base_cost + (
                target_overload_rule.coal_cost if target_overload_rule else 0
            ),
            coal_paid=coal_paid,
            woodfuel_wood_burned=wood_burned,
            woodfuel_contribution=contribution,
            target_overload_level=target_overload_level,
            effective_overload_level=effective_overload_level if effective_level > 0 else 0,
            overload_coal_paid=overload_paid if effective_level > 0 else 0,
            overload_temperature_bonus=(
                self.technology_rules.overload.levels[effective_overload_level].temperature_bonus
                if self.technology_rules is not None and effective_level > 0
                else 0
            ),
            heating_shortfall=(
                effective_level < target_level
                or effective_overload_level < target_overload_level
            ),
            storage_used=storage_used(state.resources),
            is_over_capacity=is_over_capacity(state.resources),
        )
        context.emit(
            "survival.heating.settled",
            {
                "target_level": target_level,
                "effective_level": effective_level,
                "required_coal": target_base_cost
                + (target_overload_rule.coal_cost if target_overload_rule else 0),
                "coal_paid": coal_paid,
                "overload_coal_paid": overload_paid if effective_level > 0 else 0,
                "woodfuel_wood_burned": wood_burned,
                "woodfuel_contribution": contribution,
                "heating_shortfall": state.daily_survival.heating_shortfall,
            },
        )

    @staticmethod
    def resolve_actual_heating(context: EndDayContext) -> None:
        summary = context.state.daily_survival
        if summary.settled_day != context.settled_day:
            context.abort(ErrorCode.INTERNAL_ERROR, {"reason": "heating_not_settled"})
        effective_level = summary.effective_furnace_level
        context.state.furnace.mode_id = furnace_mode_id(effective_level)
        context.state.furnace.is_active = effective_level > 0
        context.state.furnace.overload_level = summary.effective_overload_level
        context.emit(
            "survival.heating.actual_level_resolved",
            {"effective_level": effective_level},
        )

    def update_furnace_pressure(self, context: EndDayContext) -> None:
        assert self.technology_rules is not None
        state = context.state
        pressure_before = state.furnace.pressure
        overload_level = state.daily_survival.effective_overload_level
        if overload_level > 0:
            if (
                state.furnace.pressure_redline_warned
                and pressure_before >= self.technology_rules.overload.redline_threshold
            ):
                state.final_result.hard_fail_type = HardFailType.CORE_COLLAPSE
                state.final_result.is_finalized = True
            rule = self.technology_rules.overload.levels[overload_level]
            growth = (
                rule.stabilized_pressure_growth
                if "tech_overload_stability" in state.technologies.researched_tech_ids
                else rule.pressure_growth
            )
            if (
                49 <= context.settled_day <= 55
                and "tech_final_furnace_stability"
                in state.technologies.researched_tech_ids
            ):
                growth = max(growth - 5, 0)
            state.furnace.pressure += growth
        else:
            cooling = (
                self.technology_rules.overload.active_cooling
                if state.furnace.is_active
                else self.technology_rules.overload.furnace_off_cooling
            )
            state.furnace.pressure = max(state.furnace.pressure - cooling, 0)
        if state.furnace.pressure >= self.technology_rules.overload.redline_threshold:
            state.furnace.pressure_redline_warned = True
        else:
            state.furnace.pressure_redline_warned = False
        context.emit(
            "survival.furnace_pressure.updated",
            {
                "pressure_before": pressure_before,
                "pressure_after": state.furnace.pressure,
                "overload_level": overload_level,
                "redline_warned": state.furnace.pressure_redline_warned,
            },
        )

    def calculate_zone_temperatures(self, context: EndDayContext) -> None:
        summary = context.state.daily_survival
        if summary.base_temperature is None:
            context.abort(ErrorCode.INTERNAL_ERROR, {"reason": "heating_not_settled"})
        heating = (
            self.rules.furnace_levels[summary.effective_furnace_level].heating
            + summary.overload_temperature_bonus
            + (
                3
                if 49 <= context.settled_day <= 55
                and summary.effective_furnace_level > 0
                and "tech_final_furnace_stability"
                in context.state.technologies.researched_tech_ids
                else 0
            )
        )
        summary.zone_temperatures = {
            zone: summary.base_temperature + heating + modifier
            for zone, modifier in self.rules.zone_modifiers.items()
        }
        context.emit(
            "survival.temperature.calculated",
            {
                "base_temperature": summary.base_temperature,
                "furnace_heating": heating,
                "zones": summary.zone_temperatures,
            },
        )

    def settle_food(self, context: EndDayContext) -> None:
        state = context.state
        ration_mode, ration_numerator, ration_denominator = self._effective_ration(
            state
        )
        required = self._food_required(
            state.population.population_alive,
            ration_numerator,
            ration_denominator,
        )
        cooked_eaten = min(required, state.resources.cooked_food)
        state.resources.cooked_food -= cooked_eaten
        remaining = required - cooked_eaten
        raw_eaten = min(remaining, state.resources.raw_food)
        state.resources.raw_food -= raw_eaten
        food_eaten = cooked_eaten + raw_eaten
        shortfall = required - food_eaten
        unfed = self._unfed_population(
            state.population.population_alive,
            food_eaten,
            ration_numerator,
            ration_denominator,
        )
        state.daily_survival.ration_mode_used = ration_mode
        state.daily_survival.food_required = required
        state.daily_survival.cooked_food_eaten = cooked_eaten
        state.daily_survival.raw_food_eaten = raw_eaten
        state.daily_survival.food_shortfall = shortfall
        state.daily_survival.unfed_population = unfed
        state.daily_survival.storage_used = storage_used(state.resources)
        state.daily_survival.is_over_capacity = is_over_capacity(state.resources)
        context.emit(
            "survival.food.settled",
            {
                "required_food": required,
                "ration_mode_used": ration_mode,
                "cooked_food_eaten": cooked_eaten,
                "raw_food_eaten": raw_eaten,
                "food_shortfall": shortfall,
                "unfed_population": unfed,
            },
        )

    def _food_required(
        self,
        population_alive: int,
        ration_numerator: int,
        ration_denominator: int,
    ) -> int:
        numerator = (
            population_alive * self.rules.food_per_person * ration_numerator
        )
        return (numerator + ration_denominator - 1) // ration_denominator

    def _unfed_population(
        self,
        population_alive: int,
        food_eaten: int,
        ration_numerator: int,
        ration_denominator: int,
    ) -> int:
        per_person_numerator = self.rules.food_per_person * ration_numerator
        fed_population = min(
            population_alive,
            (food_eaten * ration_denominator) // per_person_numerator,
        )
        return population_alive - fed_population

    def _effective_ration(self, state: GameState) -> tuple[str, int, int]:
        selected_mode = state.social_policy.current_ration_mode
        canteen_available = any(
            building.building_type == "canteen"
            and (
                is_building_expected_operational(
                    state, building, self.building_rules, self.rules
                )
                if self.building_rules is not None
                else building.is_operational
            )
            for building in state.buildings.values()
        )
        if selected_mode != "normal" and not canteen_available:
            return "normal", 100, 100
        return (
            selected_mode,
            state.social_policy.ration_food_numerator,
            state.social_policy.ration_food_denominator,
        )

    @staticmethod
    def settle_housing(context: EndDayContext) -> None:
        state = context.state
        alive = state.population.population_alive
        housed = min(alive, state.housing.capacity)
        state.population.housed_population = housed
        state.population.homeless_population = alive - housed
        context.emit(
            "survival.housing.settled",
            {
                "housing_capacity": state.housing.capacity,
                "housed_population": housed,
                "homeless_population": alive - housed,
            },
        )
