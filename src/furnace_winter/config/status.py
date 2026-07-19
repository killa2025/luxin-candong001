from __future__ import annotations

from enum import StrEnum


class ConfigStatus(StrEnum):
    FINAL = "FINAL"
    USER_OVERRIDE = "USER_OVERRIDE"
    TEST_NUMERIC = "TEST_NUMERIC"
    PENDING = "PENDING"
    DEPRECATED = "DEPRECATED"
    TODO_TEXT = "TODO_TEXT"

    @property
    def is_runtime(self) -> bool:
        return self in {
            ConfigStatus.FINAL,
            ConfigStatus.USER_OVERRIDE,
            ConfigStatus.TEST_NUMERIC,
        }
