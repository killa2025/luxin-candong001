from __future__ import annotations

from copy import deepcopy
from dataclasses import fields
from math import gcd, lcm
from typing import Any

from furnace_winter.config import BuildingRule, BuildingRules, SurvivalRules
from furnace_winter.gameplay.end_day import EndDayContext, EndDayEngine, EndDayStage
from furnace_winter.gameplay.survival import furnace_level, is_over_capacity, storage_used
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
from furnace_winter.models import BuildingState, GameState, SaveDataError, validate_game_state


BUILD_COMMAND = "game.build"
UPGRADE_COMMAND = "game.upgrade"
ASSIGN_COMMAND = "game.assign"
UNASSIGN_COMMAND = "game.unassign"
ASSIGN_RESOURCE_COMMAND = "game.assign_resource"
UNASSIGN_RESOURCE_COMMAND = "game.unassign_resource"
HEAT_COMMAND = "game.heat"
WOODFUEL_COMMAND = "game.woodfuel"

_STAFF_FIELDS = {
    "workers": "assigned_workers",
    "engineers": "assigned_engineers",
    "children": "assigned_children",
    "medical_apprentices": "assigned_medical_apprentices",
    "engineering_apprentices": "assigned_engineering_apprentices",
}
_POPULATION_FIELDS = {
    "workers": "workers",
    "engineers": "engineers",
    "children": "children",
    "medical_apprentices": "medical_apprentices",
    "engineering_apprentices": "engineering_apprentices",
}


def build_building_catalog(rules: BuildingRules | None = None) -> CommandCatalog:
    catalog = CommandCatalog()
    buildable_types = (
        tuple(sorted(key for key, rule in rules.buildings.items() if rule.buildable))
        if rules is not None
        else ()
    )
    upgrade_ids = tuple(sorted(rules.upgrades)) if rules is not None else ()
    catalog.register(
        CommandSpec(
            name=BUILD_COMMAND,
            required_arguments={
                "building_type": ArgumentKind.STRING,
                "zone": ArgumentKind.STRING,
            },
            optional_arguments={"binding_id": ArgumentKind.STRING},
            argument_options={
                **({"building_type": buildable_types} if buildable_types else {}),
                "zone": ("inner_ring", "middle_ring", "outer_ring", "storage_outer"),
            },
        )
    )
    catalog.register(
        CommandSpec(
            name=UPGRADE_COMMAND,
            required_arguments={
                "building_id": ArgumentKind.STRING,
                "upgrade_id": ArgumentKind.STRING,
            },
            argument_options={"upgrade_id": upgrade_ids} if upgrade_ids else {},
        )
    )
    catalog.register(
        CommandSpec(
            name=ASSIGN_COMMAND,
            required_arguments={
                "building_id": ArgumentKind.STRING,
                "population_type": ArgumentKind.STRING,
                "count": ArgumentKind.INTEGER,
            },
            argument_options={"population_type": tuple(_STAFF_FIELDS)},
        )
    )
    catalog.register(
        CommandSpec(
            name=UNASSIGN_COMMAND,
            required_arguments={
                "building_id": ArgumentKind.STRING,
                "population_type": ArgumentKind.STRING,
            },
            optional_arguments={"count": ArgumentKind.INTEGER},
            argument_options={"population_type": tuple(_STAFF_FIELDS)},
        )
    )
    catalog.register(
        CommandSpec(
            name=ASSIGN_RESOURCE_COMMAND,
            required_arguments={
                "resource_point_id": ArgumentKind.STRING,
                "population_type": ArgumentKind.STRING,
                "count": ArgumentKind.INTEGER,
            },
            argument_options={"population_type": ("workers", "engineers")},
        )
    )
    catalog.register(
        CommandSpec(
            name=UNASSIGN_RESOURCE_COMMAND,
            required_arguments={
                "resource_point_id": ArgumentKind.STRING,
                "population_type": ArgumentKind.STRING,
            },
            optional_arguments={"count": ArgumentKind.INTEGER},
            argument_options={"population_type": ("workers", "engineers")},
        )
    )
    catalog.register(
        CommandSpec(
            name=HEAT_COMMAND,
            required_arguments={"building_id": ArgumentKind.STRING},
        )
    )
    catalog.register(
        CommandSpec(
            name=WOODFUEL_COMMAND,
            required_arguments={"confirm": ArgumentKind.BOOLEAN},
        )
    )
    return catalog


class BuildingSystem:
    """Patch 004 manual building actions and deterministic daily operation."""

    def __init__(self, rules: BuildingRules, survival_rules: SurvivalRules) -> None:
        self.rules = rules
        self.survival_rules = survival_rules
        self._catalog = build_building_catalog(rules)
        self._validator = CommandValidator(self._catalog)

    def command_specs(self) -> tuple[CommandSpec, ...]:
        return self._catalog.specs()

    def execute(self, state: GameState, request: CommandRequest) -> CommandResult:
        command_id = request.command_id if isinstance(request, CommandRequest) and isinstance(request.command_id, str) else ""
        state_sequence = (
            state.command_sequence
            if isinstance(state, GameState)
            and isinstance(state.command_sequence, int)
            and not isinstance(state.command_sequence, bool)
            else 0
        )
        validation = self._validator.validate(request)
        if not validation.is_valid:
            return self._rejected(command_id, state_sequence, validation)
        try:
            validate_game_state(state, self.rules, self.survival_rules)
        except (SaveDataError, TypeError, ValueError) as exc:
            return self._error(command_id, state_sequence, "input_state_validation", exc)
        validation = self._validator.validate(request, state, self._legality)
        if not validation.is_valid:
            return self._rejected(command_id, state_sequence, validation)

        working = deepcopy(state)
        data: dict[str, Any]
        try:
            if request.name == BUILD_COMMAND:
                data = self._build(working, request)
            elif request.name == UPGRADE_COMMAND:
                data = self._upgrade(working, request)
            elif request.name in {ASSIGN_COMMAND, UNASSIGN_COMMAND}:
                data = self._assign(working, request)
            elif request.name in {ASSIGN_RESOURCE_COMMAND, UNASSIGN_RESOURCE_COMMAND}:
                data = self._assign_resource(working, request)
            elif request.name == HEAT_COMMAND:
                data = self._heat(working, request)
            elif request.name == WOODFUEL_COMMAND:
                data = self._woodfuel(working)
            else:
                return self._rejected(
                    command_id,
                    state_sequence,
                    CommandValidation(False, ErrorCode.ILLEGAL_COMMAND),
                )
            working.command_sequence += 1
            validate_game_state(working, self.rules, self.survival_rules)
        except (SaveDataError, TypeError, ValueError) as exc:
            return self._error(command_id, state_sequence, "result_state_validation", exc)

        for item in fields(GameState):
            setattr(state, item.name, deepcopy(getattr(working, item.name)))
        return CommandResult(
            command_id=command_id,
            accepted=True,
            code=ErrorCode.OK,
            state_changed=True,
            state_sequence=state.command_sequence,
            feedback=(FeedbackItem(FeedbackLevel.INFO, data=data),),
            data=data,
        )

    def _legality(self, state: GameState, request: CommandRequest) -> CommandValidation:
        blocked = self._planning_block(state)
        if blocked is not None:
            return blocked
        if request.name == BUILD_COMMAND:
            return self._build_legality(state, request)
        if request.name == UPGRADE_COMMAND:
            return self._upgrade_legality(state, request)
        if request.name in {ASSIGN_COMMAND, UNASSIGN_COMMAND}:
            return self._assign_legality(state, request)
        if request.name in {ASSIGN_RESOURCE_COMMAND, UNASSIGN_RESOURCE_COMMAND}:
            return self._assign_resource_legality(state, request)
        if request.name == HEAT_COMMAND:
            return self._heat_legality(state, request)
        if request.name == WOODFUEL_COMMAND:
            return self._woodfuel_legality(state, request)
        return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND)

    @staticmethod
    def _planning_block(state: GameState) -> CommandValidation | None:
        if state.final_result.hard_fail_type is not None:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "game_already_failed"})
        if state.calendar.is_day_locked or state.final_result.is_finalized:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "day_not_open_for_planning"})
        return None

    def _build_legality(self, state: GameState, request: CommandRequest) -> CommandValidation:
        building_type = request.arguments.get("building_type")
        zone = request.arguments.get("zone")
        rule = self.rules.buildings.get(building_type) if isinstance(building_type, str) else None
        if rule is None:
            return CommandValidation(False, ErrorCode.INVALID_ARGUMENTS, {"reason": "unknown_building_type"})
        if not rule.buildable:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "building_is_upgrade_only"})
        if zone not in rule.allowed_zones:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "zone_not_allowed", "allowed_zones": list(rule.allowed_zones)})
        signed_laws = set(state.laws.signed_law_ids)
        missing_laws = sorted(set(rule.required_law_ids) - signed_laws)
        missing_techs = sorted(set(rule.required_tech_ids) - set(state.technologies.researched_tech_ids))
        if missing_laws or missing_techs:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "prerequisite_missing", "missing_law_ids": missing_laws, "missing_tech_ids": missing_techs})
        if state.resources.wood < rule.wood_cost or state.resources.steel < rule.steel_cost:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "insufficient_resources", "required_wood": rule.wood_cost, "required_steel": rule.steel_cost})
        assert isinstance(zone, str)
        used = state.building_management.zone_slots_used[zone]
        capacity = state.building_management.zone_slot_capacity[zone]
        if used + rule.slot_size > capacity:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "insufficient_zone_slots", "used": used, "capacity": capacity})
        maximum = self._building_limit(state, rule)
        current = sum(1 for item in state.buildings.values() if item.building_type == rule.building_type)
        if maximum is not None and current >= maximum:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "building_limit_reached", "limit": maximum})
        if building_type == "cemetery" and self._has_type(state, "cold_pit") or building_type == "cold_pit" and self._has_type(state, "cemetery"):
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "mutually_exclusive_building_exists"})
        binding_id = request.arguments.get("binding_id")
        if rule.binding_kind is None:
            if binding_id is not None:
                return CommandValidation(False, ErrorCode.INVALID_ARGUMENTS, {"reason": "binding_not_supported"})
        else:
            valid_ids = self.rules.resource_anchors[rule.binding_kind]
            if binding_id not in valid_ids:
                return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "invalid_resource_binding", "binding_kind": rule.binding_kind})
            if any(item.bound_resource_id == binding_id for item in state.buildings.values()):
                return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "resource_anchor_already_bound"})
        return CommandValidation.valid()

    def _upgrade_legality(self, state: GameState, request: CommandRequest) -> CommandValidation:
        building_id = request.arguments.get("building_id")
        upgrade_id = request.arguments.get("upgrade_id")
        building = state.buildings.get(building_id) if isinstance(building_id, str) else None
        upgrade = self.rules.upgrades.get(upgrade_id) if isinstance(upgrade_id, str) else None
        if building is None or upgrade is None:
            return CommandValidation(False, ErrorCode.INVALID_ARGUMENTS, {"reason": "unknown_building_or_upgrade"})
        if building.building_type != upgrade.from_type:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "upgrade_not_supported_for_building"})
        if upgrade.required_tech_id not in state.technologies.researched_tech_ids:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "prerequisite_missing", "missing_tech_ids": [upgrade.required_tech_id]})
        if state.resources.wood < upgrade.wood_cost or state.resources.steel < upgrade.steel_cost:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "insufficient_resources", "required_wood": upgrade.wood_cost, "required_steel": upgrade.steel_cost})
        return CommandValidation.valid()

    def _assign_legality(self, state: GameState, request: CommandRequest) -> CommandValidation:
        building_id = request.arguments.get("building_id")
        population_type = request.arguments.get("population_type")
        building = state.buildings.get(building_id) if isinstance(building_id, str) else None
        if building is None or population_type not in _STAFF_FIELDS:
            return CommandValidation(False, ErrorCode.INVALID_ARGUMENTS, {"reason": "unknown_building_or_population_type"})
        rule = self.rules.buildings.get(building.building_type)
        if rule is None:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "building_type_not_in_catalog"})
        current = getattr(building, _STAFF_FIELDS[population_type])
        if request.name == UNASSIGN_COMMAND:
            remove_count = request.arguments.get("count")
            if remove_count is not None and (
                not isinstance(remove_count, int)
                or isinstance(remove_count, bool)
                or remove_count < 1
                or remove_count > current
            ):
                return CommandValidation(False, ErrorCode.INVALID_ARGUMENTS, {"reason": "invalid_unassign_count", "assigned_count": current})
            target = 0 if remove_count is None else current - remove_count
        else:
            target = request.arguments.get("count")
        if request.name == ASSIGN_COMMAND and (
            not isinstance(target, int) or isinstance(target, bool) or target < 1
        ):
            return CommandValidation(False, ErrorCode.INVALID_ARGUMENTS, {"reason": "count_must_be_positive"})
        if population_type not in rule.allowed_staff_types and target > 0:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "population_type_not_allowed"})
        field_name = _STAFF_FIELDS[population_type]
        assigned_total = self._assigned_total(building) - current + target
        if assigned_total > rule.staff_capacity:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "staff_capacity_exceeded", "capacity": rule.staff_capacity})
        population_available = getattr(state.population, _POPULATION_FIELDS[population_type])
        assigned_elsewhere = self._assigned_population(state, population_type) - current
        if assigned_elsewhere + target > population_available:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "population_not_available", "available": population_available - assigned_elsewhere})
        return CommandValidation.valid()

    def _assign_resource_legality(
        self, state: GameState, request: CommandRequest
    ) -> CommandValidation:
        resource_point_id = request.arguments.get("resource_point_id")
        population_type = request.arguments.get("population_type")
        point = (
            state.surface_resource_points.get(resource_point_id)
            if isinstance(resource_point_id, str)
            else None
        )
        if point is None or population_type not in {"workers", "engineers"}:
            return CommandValidation(
                False,
                ErrorCode.INVALID_ARGUMENTS,
                {"reason": "unknown_resource_point_or_population_type"},
            )
        if point.is_depleted:
            return CommandValidation(
                False,
                ErrorCode.ILLEGAL_COMMAND,
                {"reason": "resource_point_depleted"},
            )
        field_name = f"assigned_{population_type}"
        current = getattr(point, field_name)
        if request.name == UNASSIGN_RESOURCE_COMMAND:
            remove_count = request.arguments.get("count")
            if remove_count is not None and (
                not isinstance(remove_count, int)
                or isinstance(remove_count, bool)
                or remove_count < 1
                or remove_count > current
            ):
                return CommandValidation(
                    False,
                    ErrorCode.INVALID_ARGUMENTS,
                    {"reason": "invalid_unassign_count", "assigned_count": current},
                )
            target = 0 if remove_count is None else current - remove_count
        else:
            target = request.arguments.get("count")
        if request.name == ASSIGN_RESOURCE_COMMAND and (
            not isinstance(target, int) or isinstance(target, bool) or target < 1
        ):
            return CommandValidation(
                False,
                ErrorCode.INVALID_ARGUMENTS,
                {"reason": "count_must_be_positive"},
            )
        assigned_total = point.assigned_workers + point.assigned_engineers - current + target
        if assigned_total > point.staff_capacity:
            return CommandValidation(
                False,
                ErrorCode.ILLEGAL_COMMAND,
                {"reason": "staff_capacity_exceeded", "capacity": point.staff_capacity},
            )
        population_available = getattr(state.population, population_type)
        assigned_elsewhere = self._assigned_population(state, population_type) - current
        if assigned_elsewhere + target > population_available:
            return CommandValidation(
                False,
                ErrorCode.ILLEGAL_COMMAND,
                {
                    "reason": "population_not_available",
                    "available": population_available - assigned_elsewhere,
                },
            )
        return CommandValidation.valid()

    def _heat_legality(self, state: GameState, request: CommandRequest) -> CommandValidation:
        building_id = request.arguments.get("building_id")
        building = state.buildings.get(building_id) if isinstance(building_id, str) else None
        if building is None:
            return CommandValidation(False, ErrorCode.INVALID_ARGUMENTS, {"reason": "unknown_building"})
        rule = self.rules.buildings.get(building.building_type)
        if rule is None or not rule.can_heat:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "building_cannot_heat"})
        if building.heated_today:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "building_already_heated_today"})
        if state.building_management.heat_uses_today >= self.rules.heat.daily_city_limit:
            return CommandValidation(
                False,
                ErrorCode.ILLEGAL_COMMAND,
                {"reason": "daily_heat_limit_reached", "limit": self.rules.heat.daily_city_limit},
            )
        effective_level = self._projected_furnace_level(state)
        temperature = self._projected_building_temperature(
            state, building, effective_level, include_heat=False
        )
        assert rule.min_operating_temperature is not None
        if temperature >= rule.min_operating_temperature:
            return CommandValidation(
                False,
                ErrorCode.ILLEGAL_COMMAND,
                {
                    "reason": "temperature_already_sufficient",
                    "effective_temperature": temperature,
                    "minimum_temperature": rule.min_operating_temperature,
                },
            )
        furnace_coal_reserved = self._coal_reserved_for_level(state, effective_level)
        required_coal = furnace_coal_reserved + self.rules.heat.coal_cost
        if state.resources.coal < required_coal:
            return CommandValidation(
                False,
                ErrorCode.ILLEGAL_COMMAND,
                {
                    "reason": "insufficient_coal_after_furnace_reserve",
                    "furnace_coal_reserved": furnace_coal_reserved,
                    "heat_coal_required": self.rules.heat.coal_cost,
                    "required_coal": required_coal,
                },
            )
        return CommandValidation.valid()

    def _woodfuel_legality(self, state: GameState, request: CommandRequest) -> CommandValidation:
        if request.arguments.get("confirm") is not True:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "confirmation_required"})
        if not state.furnace.is_active:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "furnace_is_off"})
        if state.building_management.woodfuel_confirmed_today:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "woodfuel_already_confirmed_today"})
        level = int(state.furnace.mode_id[-1])
        required_coal = self.survival_rules.furnace_levels[level].coal_cost
        remaining_heat_uses = max(
            self.rules.heat.daily_city_limit
            - state.building_management.heat_uses_today,
            0,
        )
        projected_coal_after_heat = (
            state.resources.coal
            - remaining_heat_uses * self.rules.heat.coal_cost
        )
        if (
            state.resources.coal >= required_coal
            and projected_coal_after_heat >= required_coal
        ):
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "no_base_heating_shortfall"})
        if state.resources.wood < self.rules.woodfuel.minimum_wood_unit:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "insufficient_wood", "minimum_wood": self.rules.woodfuel.minimum_wood_unit})
        return CommandValidation.valid()

    def _build(self, state: GameState, request: CommandRequest) -> dict[str, Any]:
        building_type = str(request.arguments["building_type"])
        zone = str(request.arguments["zone"])
        rule = self.rules.buildings[building_type]
        sequence = state.building_management.next_building_sequence
        while True:
            building_id = f"building-{sequence:06d}"
            sequence += 1
            if building_id not in state.buildings:
                break
        state.building_management.next_building_sequence = sequence
        state.resources.wood -= rule.wood_cost
        state.resources.steel -= rule.steel_cost
        state.buildings[building_id] = BuildingState(
            building_id=building_id,
            building_type=building_type,
            zone=zone,
            slot_size=rule.slot_size,
            is_built=True,
            is_operational=rule.staff_capacity == 0,
            can_heat=rule.can_heat,
            bound_resource_id=request.arguments.get("binding_id"),
        )
        state.building_management.zone_slots_used[zone] += rule.slot_size
        state.housing.capacity += rule.housing_capacity
        if building_type == "basic_residence":
            state.housing.basic_residences += 1
        state.resources.storage_capacity += rule.storage_capacity_add
        self._sync_housing_population(state)
        second_hunting_area_unlocked = False
        if building_type == "hunting_lodge" and state.building_management.available_hunting_areas == 1:
            state.building_management.available_hunting_areas = 2
            second_hunting_area_unlocked = True
        return {
            "building_id": building_id,
            "building_type": building_type,
            "zone": zone,
            "wood_paid": rule.wood_cost,
            "steel_paid": rule.steel_cost,
            "second_hunting_area_unlocked": second_hunting_area_unlocked,
        }

    def _upgrade(self, state: GameState, request: CommandRequest) -> dict[str, Any]:
        building = state.buildings[str(request.arguments["building_id"])]
        upgrade = self.rules.upgrades[str(request.arguments["upgrade_id"])]
        old_rule = self.rules.buildings[upgrade.from_type]
        new_rule = self.rules.buildings[upgrade.to_type]
        state.resources.wood -= upgrade.wood_cost
        state.resources.steel -= upgrade.steel_cost
        building.building_type = upgrade.to_type
        building.slot_size = new_rule.slot_size
        building.can_heat = new_rule.can_heat
        state.housing.capacity += new_rule.housing_capacity - old_rule.housing_capacity
        if upgrade.from_type == "basic_residence":
            state.housing.basic_residences -= 1
        state.resources.storage_capacity += new_rule.storage_capacity_add - old_rule.storage_capacity_add
        self._sync_housing_population(state)
        return {
            "building_id": building.building_id,
            "upgrade_id": upgrade.upgrade_id,
            "building_type": upgrade.to_type,
            "wood_paid": upgrade.wood_cost,
            "steel_paid": upgrade.steel_cost,
            "instant": True,
        }

    def _assign(self, state: GameState, request: CommandRequest) -> dict[str, Any]:
        building = state.buildings[str(request.arguments["building_id"])]
        population_type = str(request.arguments["population_type"])
        if request.name == UNASSIGN_COMMAND:
            current = getattr(building, _STAFF_FIELDS[population_type])
            remove_count = request.arguments.get("count")
            target = 0 if remove_count is None else current - int(remove_count)
        else:
            target = int(request.arguments["count"])
        setattr(building, _STAFF_FIELDS[population_type], target)
        rule = self.rules.buildings[building.building_type]
        building.is_operational = rule.staff_capacity == 0 or self._assigned_total(building) > 0
        return {"building_id": building.building_id, "population_type": population_type, "assigned_count": target}

    @staticmethod
    def _assign_resource(state: GameState, request: CommandRequest) -> dict[str, Any]:
        point = state.surface_resource_points[str(request.arguments["resource_point_id"])]
        population_type = str(request.arguments["population_type"])
        field_name = f"assigned_{population_type}"
        if request.name == UNASSIGN_RESOURCE_COMMAND:
            current = getattr(point, field_name)
            remove_count = request.arguments.get("count")
            target = 0 if remove_count is None else current - int(remove_count)
        else:
            target = int(request.arguments["count"])
        setattr(point, field_name, target)
        return {
            "resource_point_id": point.resource_point_id,
            "population_type": population_type,
            "assigned_count": target,
        }

    def _heat(self, state: GameState, request: CommandRequest) -> dict[str, Any]:
        building = state.buildings[str(request.arguments["building_id"])]
        state.resources.coal -= self.rules.heat.coal_cost
        building.heated_today = True
        state.building_management.heat_uses_today += 1
        bonus = self._heat_bonus(state)
        return {
            "building_id": building.building_id,
            "coal_paid": self.rules.heat.coal_cost,
            "temperature_bonus": bonus,
            "remaining_city_heat_uses": self.rules.heat.daily_city_limit
            - state.building_management.heat_uses_today,
        }

    @staticmethod
    def _woodfuel(state: GameState) -> dict[str, Any]:
        state.building_management.woodfuel_confirmed_today = True
        return {"woodfuel_confirmed_today": True, "active_duration": "current_day_only"}

    def install(self, engine: EndDayEngine) -> None:
        engine.register_state_validator(self.validate_state)
        engine.register_stage_handler(EndDayStage.CALCULATE_BUILDING_TEMPERATURE, self.calculate_building_temperatures)
        engine.register_stage_handler(EndDayStage.RESOLVE_BUILDING_OPERATION, self.resolve_building_operation)
        engine.register_stage_handler(EndDayStage.RESOLVE_COLLECTION_AND_PRODUCTION, self.resolve_production)
        engine.register_stage_handler(EndDayStage.CLOSE_DAILY_EFFECTS, self.close_daily_effects)

    def validate_state(self, state: GameState) -> None:
        validate_game_state(state, self.rules, self.survival_rules)

    def calculate_building_temperatures(self, context: EndDayContext) -> None:
        state = context.state
        zones = state.daily_survival.zone_temperatures
        if not zones:
            context.abort(ErrorCode.INTERNAL_ERROR, {"reason": "zone_temperature_not_calculated"})
        for building in state.buildings.values():
            rule = self.rules.buildings.get(building.building_type)
            if rule is None:
                continue
            zone = "outer_ring" if building.zone == "storage_outer" else building.zone
            building.effective_temperature = (
                zones[zone]
                + self._building_insulation_bonus(state, building)
                + (self._heat_bonus(state) if building.heated_today else 0)
            )
        context.emit("buildings.temperature.calculated", {"building_count": len(state.buildings)})

    def resolve_building_operation(self, context: EndDayContext) -> None:
        for building in context.state.buildings.values():
            rule = self.rules.buildings.get(building.building_type)
            if rule is None:
                building.is_operational = False
                continue
            building.is_shutdown_by_temperature = (
                rule.min_operating_temperature is not None
                and building.effective_temperature < rule.min_operating_temperature
            )
            staffed = rule.staff_capacity == 0 or self._assigned_total(building) > 0
            building.is_operational = building.is_built and staffed and not building.is_shutdown_by_temperature
        context.emit(
            "buildings.operation.resolved",
            {"operational_count": sum(item.is_operational for item in context.state.buildings.values())},
        )

    def resolve_production(self, context: EndDayContext) -> None:
        state = context.state
        production: dict[str, int] = {"coal": 0, "wood": 0, "steel": 0, "raw_food": 0}
        depleted_points: list[str] = []
        sheltered_points = {
            building.bound_resource_id
            for building in state.buildings.values()
            if building.building_type == "gathering_shelter"
            and building.bound_resource_id is not None
        }
        for resource_point_id, point in state.surface_resource_points.items():
            if point.is_depleted:
                continue
            point_rule = self.rules.surface_resource_points[resource_point_id]
            assigned = point.assigned_workers + point.assigned_engineers
            output = self._accumulate_fractional_output(
                point,
                point_rule.output_per_day,
                assigned,
                point_rule.staff_capacity,
            )
            output = min(output, point.remaining_amount)
            point.remaining_amount -= output
            setattr(
                state.resources,
                point.resource_type,
                getattr(state.resources, point.resource_type) + output,
            )
            production[point.resource_type] += output
            if point.remaining_amount == 0:
                point.is_depleted = True
                point.assigned_workers = 0
                point.assigned_engineers = 0
                point.production_remainder_numerator = 0
                depleted_points.append(resource_point_id)
        canteens: list[tuple[BuildingState, BuildingRule]] = []
        for building in state.buildings.values():
            rule = self.rules.buildings.get(building.building_type)
            if rule is None or not building.is_operational:
                continue
            if rule.raw_food_processing_cap:
                canteens.append((building, rule))
                continue
            if rule.output_resource is None or rule.output_per_day == 0:
                continue
            full_output = rule.output_per_day
            if building.building_type == "logging_camp" and "tech_wood_processing_2" in state.technologies.researched_tech_ids:
                full_output = 70
            elif building.building_type == "small_coal_miner" and "tech_small_coal_mining_improvement" in state.technologies.researched_tech_ids:
                full_output = 90
            elif building.building_type == "small_steel_miner" and "tech_small_steel_mining_improvement" in state.technologies.researched_tech_ids:
                full_output = 30
            output = self._accumulate_fractional_output(
                building,
                full_output,
                self._assigned_total(building),
                rule.staff_capacity,
            )
            multiplier = self._production_multiplier(state, building.building_id)
            output = self._apply_production_multiplier(
                building, output, multiplier[0], multiplier[1]
            )
            setattr(state.resources, rule.output_resource, getattr(state.resources, rule.output_resource) + output)
            production[rule.output_resource] += output

        raw_processed = 0
        cooked_produced = 0
        for building, rule in canteens:
            cap = 80 if "tech_canteen_process_improvement" in state.technologies.researched_tech_ids else rule.raw_food_processing_cap
            staffed_cap = self._accumulate_fractional_output(
                building,
                cap,
                self._assigned_total(building),
                rule.staff_capacity,
            )
            multiplier = self._production_multiplier(state, building.building_id)
            staffed_cap = self._apply_production_multiplier(
                building, staffed_cap, multiplier[0], multiplier[1]
            )
            processed = min(staffed_cap, state.resources.raw_food)
            state.resources.raw_food -= processed
            cooked = processed * self.survival_rules.raw_to_cooked_ratio
            state.resources.cooked_food += cooked
            raw_processed += processed
            cooked_produced += cooked
        state.daily_survival.storage_used = storage_used(state.resources)
        state.daily_survival.is_over_capacity = is_over_capacity(state.resources)
        context.emit(
            "buildings.production.settled",
            {
                "production": production,
                "raw_food_processed": raw_processed,
                "cooked_food_produced": cooked_produced,
                "depleted_resource_point_ids": depleted_points,
                "sheltered_resource_point_ids": sorted(
                    point_id
                    for point_id in sheltered_points
                    if point_id in state.surface_resource_points
                ),
                "shelter_removal_suggested_ids": sorted(
                    set(depleted_points) & sheltered_points
                ),
            },
        )

    @staticmethod
    def close_daily_effects(context: EndDayContext) -> None:
        for building in context.state.buildings.values():
            building.heated_today = False
        context.state.building_management.woodfuel_confirmed_today = False
        context.state.building_management.heat_uses_today = 0
        context.emit(
            "buildings.daily_effects.closed",
            {"heat_reset": True, "heat_city_uses_reset": True, "woodfuel_reset": True},
        )

    def _building_limit(self, state: GameState, rule: BuildingRule) -> int | None:
        if rule.max_count_source == "hunting_areas":
            return state.building_management.available_hunting_areas
        if rule.max_count_source == "forest_zones":
            return state.building_management.forest_zones
        return rule.max_buildings

    def _heat_bonus(self, state: GameState) -> int:
        return self.rules.heat.enhanced_temperature_bonus if self.rules.heat.enhancement_tech_id in state.technologies.researched_tech_ids else self.rules.heat.temperature_bonus

    def _projected_furnace_level(self, state: GameState) -> int:
        target_level = furnace_level(state.furnace.mode_id)
        available_fuel = state.resources.coal + self._woodfuel_available(state)
        return max(
            level
            for level in range(target_level + 1)
            if self.survival_rules.furnace_levels[level].coal_cost <= available_fuel
        )

    @staticmethod
    def _production_multiplier(state: GameState, building_id: str) -> tuple[int, int]:
        if state.social_policy.overtime_building_id == building_id:
            return (
                state.social_policy.overtime_output_numerator,
                state.social_policy.overtime_output_denominator,
            )
        return (
            state.social_policy.worktime_output_numerator,
            state.social_policy.worktime_output_denominator,
        )

    def _woodfuel_available(self, state: GameState) -> int:
        if not state.building_management.woodfuel_confirmed_today:
            return 0
        rule = self.rules.woodfuel
        usable_wood = min(state.resources.wood, rule.daily_wood_limit)
        usable_wood -= usable_wood % rule.minimum_wood_unit
        return usable_wood // rule.wood_per_fuel

    def _coal_reserved_for_level(self, state: GameState, level: int) -> int:
        required_fuel = self.survival_rules.furnace_levels[level].coal_cost
        return max(required_fuel - self._woodfuel_available(state), 0)

    def _building_insulation_bonus(
        self, state: GameState, building: BuildingState
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

    def _projected_building_temperature(
        self,
        state: GameState,
        building: BuildingState,
        effective_furnace_level: int,
        *,
        include_heat: bool,
    ) -> int:
        zone = "outer_ring" if building.zone == "storage_outer" else building.zone
        return (
            self.survival_rules.weather_for_day(state.calendar.current_day)
            + self.survival_rules.furnace_levels[effective_furnace_level].heating
            + self.survival_rules.zone_modifiers[zone]
            + self._building_insulation_bonus(state, building)
            + (self._heat_bonus(state) if include_heat else 0)
        )

    @staticmethod
    def _accumulate_fractional_output(
        owner: Any, full_output: int, assigned_staff: int, staff_capacity: int
    ) -> int:
        numerator = (
            owner.production_remainder_numerator + full_output * assigned_staff
        )
        output = numerator // staff_capacity
        owner.production_remainder_numerator = numerator % staff_capacity
        return output

    @staticmethod
    def _apply_production_multiplier(
        building: BuildingState,
        output: int,
        multiplier_numerator: int,
        multiplier_denominator: int,
    ) -> int:
        remainder_denominator = (
            building.production_multiplier_remainder_denominator
        )
        common_denominator = lcm(remainder_denominator, multiplier_denominator)
        numerator = (
            building.production_multiplier_remainder_numerator
            * (common_denominator // remainder_denominator)
            + output
            * multiplier_numerator
            * (common_denominator // multiplier_denominator)
        )
        whole, remainder = divmod(numerator, common_denominator)
        if remainder:
            divisor = gcd(remainder, common_denominator)
            building.production_multiplier_remainder_numerator = remainder // divisor
            building.production_multiplier_remainder_denominator = (
                common_denominator // divisor
            )
        else:
            building.production_multiplier_remainder_numerator = 0
            building.production_multiplier_remainder_denominator = 1
        return whole

    @staticmethod
    def _has_type(state: GameState, building_type: str) -> bool:
        return any(item.building_type == building_type for item in state.buildings.values())

    @staticmethod
    def _assigned_total(building: BuildingState) -> int:
        return sum(getattr(building, field_name) for field_name in _STAFF_FIELDS.values())

    @staticmethod
    def _assigned_population(state: GameState, population_type: str) -> int:
        field_name = _STAFF_FIELDS[population_type]
        total = sum(getattr(building, field_name) for building in state.buildings.values())
        if population_type in {"workers", "engineers"}:
            point_field = f"assigned_{population_type}"
            total += sum(
                getattr(point, point_field)
                for point in state.surface_resource_points.values()
            )
        return total

    @staticmethod
    def _sync_housing_population(state: GameState) -> None:
        housed = min(state.population.population_alive, state.housing.capacity)
        state.population.housed_population = housed
        state.population.homeless_population = state.population.population_alive - housed

    @staticmethod
    def _rejected(command_id: str, sequence: int, validation: CommandValidation) -> CommandResult:
        return CommandResult(
            command_id=command_id,
            accepted=False,
            code=validation.code,
            state_sequence=sequence,
            feedback=(FeedbackItem(FeedbackLevel.ERROR, data=validation.details),),
            data=validation.details,
        )

    @staticmethod
    def _error(command_id: str, sequence: int, stage: str, exc: Exception) -> CommandResult:
        details = {"failed_stage": stage, "exception_type": type(exc).__name__}
        return CommandResult(
            command_id=command_id,
            accepted=False,
            code=ErrorCode.INTERNAL_ERROR,
            state_sequence=sequence,
            feedback=(FeedbackItem(FeedbackLevel.ERROR, data=details),),
            data=details,
        )
