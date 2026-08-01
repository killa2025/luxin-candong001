from __future__ import annotations

from furnace_winter.models.state import GameState


_REMOVAL_ORDER = (
    "none_population",
    "light_population",
    "severe_population",
    "starving_population",
)


def add_population_to_hunger_none(state: GameState, amount: int) -> None:
    """Add newly counted residents to the no-hunger overlay pool."""

    if amount < 0:
        raise ValueError("hunger population addition must be non-negative")
    state.hunger.none_population += amount


def remove_non_hunger_deaths_or_departures(
    state: GameState, amount: int
) -> None:
    """Keep the overlay total canonical after non-starvation population loss.

    The population model has no per-person health/hunger cross product.  The
    Patch 013's user-confirmed deterministic fallback removes no-hunger
    residents first, then progressively deeper hunger pools.  A future
    identity/health/hunger cross table must replace this fallback with the
    affected residents' actual hunger states.
    """

    if amount < 0:
        raise ValueError("hunger population removal must be non-negative")
    remaining = amount
    for name in _REMOVAL_ORDER:
        value = getattr(state.hunger, name)
        removed = min(value, remaining)
        setattr(state.hunger, name, value - removed)
        remaining -= removed
        if remaining == 0:
            break
    if remaining:
        raise ValueError("hunger pools cannot cover population removal")
    clear_inactive_hunger_remainders(state)


def remove_starvation_deaths(state: GameState, amount: int) -> None:
    if amount < 0 or amount > state.hunger.starving_population:
        raise ValueError("starvation deaths must come from hunger_starving")
    state.hunger.starving_population -= amount
    clear_inactive_hunger_remainders(state)


def clear_inactive_hunger_remainders(state: GameState) -> None:
    hunger = state.hunger
    if (
        hunger.light_population
        + hunger.severe_population
        + hunger.starving_population
        == 0
    ):
        hunger.illness_remainder = 0
        hunger.severe_remainder = 0
        hunger.death_remainder = 0
        hunger.trust_remainder = 0
        hunger.panic_remainder = 0
        return
    if hunger.severe_population + 2 * hunger.starving_population == 0:
        hunger.severe_remainder = 0
    if hunger.starving_population == 0:
        hunger.death_remainder = 0


def hunger_population_total(state: GameState) -> int:
    hunger = state.hunger
    return (
        hunger.none_population
        + hunger.light_population
        + hunger.severe_population
        + hunger.starving_population
    )
