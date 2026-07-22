from __future__ import annotations

import sys
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def downgrade_to_pre_patch006_schema(document: dict) -> dict:
    """Remove v7-only fields so migration tests use a genuine legacy schema."""

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
