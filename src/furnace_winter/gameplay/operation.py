from __future__ import annotations

from furnace_winter.models import BuildingState, GameState


FINAL_FROST_SHUTDOWN_BUILDING_TYPES = frozenset(
    {
        "hunting_lodge",
        "logging_camp",
        "small_coal_miner",
        "small_steel_miner",
    }
)
FINAL_FROST_COLLECTION_START_DAY = 49
FINAL_FROST_COLLECTION_END_DAY = 55


def is_final_frost_collection_shutdown(day: int) -> bool:
    return FINAL_FROST_COLLECTION_START_DAY <= day <= FINAL_FROST_COLLECTION_END_DAY


def is_building_forced_shutdown(
    state: GameState, building: BuildingState
) -> bool:
    return (
        is_final_frost_collection_shutdown(state.calendar.current_day)
        and building.building_type in FINAL_FROST_SHUTDOWN_BUILDING_TYPES
    )


def final_frost_affected_surface_resource_point_ids(
    state: GameState,
) -> tuple[str, ...]:
    return tuple(
        sorted(
            point.resource_point_id
            for point in state.surface_resource_points.values()
            if not point.is_depleted
            or point.assigned_workers + point.assigned_engineers > 0
        )
    )
