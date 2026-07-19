from __future__ import annotations

from dataclasses import dataclass


RANDOM_ALGORITHM = "splitmix64-v1"
_MASK_64 = (1 << 64) - 1
_INCREMENT = 0x9E3779B97F4A7C15


@dataclass(frozen=True, slots=True)
class RandomState:
    """A compact, JSON-safe snapshot of the sole game random stream."""

    seed: int
    internal_state: int
    draws: int = 0
    algorithm: str = RANDOM_ALGORITHM

    def __post_init__(self) -> None:
        if not isinstance(self.seed, int) or isinstance(self.seed, bool):
            raise TypeError("random seed must be an integer")
        if (
            not isinstance(self.internal_state, int)
            or isinstance(self.internal_state, bool)
            or not 0 <= self.internal_state <= _MASK_64
        ):
            raise ValueError("random internal_state must be an unsigned 64-bit integer")
        if (
            not isinstance(self.draws, int)
            or isinstance(self.draws, bool)
            or self.draws < 0
        ):
            raise ValueError("random draws must be a non-negative integer")
        if not isinstance(self.algorithm, str) or not self.algorithm:
            raise ValueError("random algorithm must not be blank")

    @classmethod
    def initial(cls, seed: int) -> RandomState:
        normalized_seed = seed & _MASK_64
        return cls(seed=seed, internal_state=normalized_seed)


class DeterministicRandom:
    """Versioned deterministic PRNG used by all future game randomness."""

    def __init__(self, seed: int) -> None:
        if not isinstance(seed, int) or isinstance(seed, bool):
            raise TypeError("random seed must be an integer")
        self._seed = seed
        self._state = seed & _MASK_64
        self._draws = 0

    @classmethod
    def from_state(cls, state: RandomState) -> DeterministicRandom:
        if state.algorithm != RANDOM_ALGORITHM:
            raise ValueError(f"unsupported random algorithm: {state.algorithm}")
        if not 0 <= state.internal_state <= _MASK_64:
            raise ValueError("random internal_state must be an unsigned 64-bit integer")
        if state.draws < 0:
            raise ValueError("random draws must not be negative")

        instance = cls(state.seed)
        instance._state = state.internal_state
        instance._draws = state.draws
        return instance

    def snapshot(self) -> RandomState:
        return RandomState(
            seed=self._seed,
            internal_state=self._state,
            draws=self._draws,
        )

    def next_u64(self) -> int:
        """Return the next unsigned 64-bit value from the unified stream."""

        self._state = (self._state + _INCREMENT) & _MASK_64
        value = self._state
        value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & _MASK_64
        value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & _MASK_64
        self._draws += 1
        return (value ^ (value >> 31)) & _MASK_64

    def random(self) -> float:
        """Return a deterministic float in the half-open interval [0, 1)."""

        return (self.next_u64() >> 11) * (1.0 / (1 << 53))

    def randint(self, start: int, stop: int) -> int:
        """Return a deterministic integer in the inclusive interval."""

        if (
            not isinstance(start, int)
            or isinstance(start, bool)
            or not isinstance(stop, int)
            or isinstance(stop, bool)
        ):
            raise TypeError("randint bounds must be integers and not booleans")
        if start > stop:
            raise ValueError("start must not be greater than stop")
        width = stop - start + 1
        if width > 1 << 64:
            raise ValueError("interval is wider than the random generator range")

        limit = (1 << 64) - ((1 << 64) % width)
        while True:
            value = self.next_u64()
            if value < limit:
                return start + (value % width)
