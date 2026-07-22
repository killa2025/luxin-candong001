from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from furnace_winter.cli import main


ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def test_validate_config_success_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, redirect_stdout(StringIO()):
            exit_code = main(["validate-config", temp_dir])

        self.assertEqual(exit_code, 0)

    def test_validate_config_failure_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "broken.json"
            path.write_text("{", encoding="utf-8")
            with redirect_stdout(StringIO()):
                exit_code = main(["validate-config", temp_dir])

        self.assertEqual(exit_code, 1)

    def test_validate_config_rejects_document_loader_would_reject(self) -> None:
        invalid_documents = (
            {"value": 1},
            {"config_status": "UNKNOWN"},
            ["not-an-object"],
            {"config_status": "FINAL", "PENDING_NUMERIC": 10},
        )
        for document in invalid_documents:
            with self.subTest(document=document), tempfile.TemporaryDirectory() as temp_dir:
                path = Path(temp_dir) / "invalid.json"
                path.write_text(json.dumps(document), encoding="utf-8")
                with redirect_stdout(StringIO()):
                    exit_code = main(["validate-config", temp_dir])

            self.assertEqual(exit_code, 1)

    def test_validate_config_checks_building_technology_links_both_ways(self) -> None:
        buildings_source = json.loads(
            (ROOT / "data" / "buildings.json").read_text("utf-8")
        )
        technologies_source = json.loads(
            (ROOT / "data" / "technologies.json").read_text("utf-8")
        )

        def unknown_building_tech(buildings, technologies):
            buildings["buildings"]["hospital"]["required_tech_ids"] = [
                "tech_unknown"
            ]

        def misspelled_building_target(buildings, technologies):
            technologies["technologies"]["tech_greenhouse_cultivation"][
                "effect_targets"
            ] = ["greenhoues"]

        def misspelled_upgrade_target(buildings, technologies):
            technologies["technologies"]["tech_advanced_housing_standard"][
                "effect_targets"
            ] = ["improved_to_advanced_residense"]

        def missing_reverse_building_link(buildings, technologies):
            buildings["buildings"]["greenhouse"]["required_tech_ids"] = []

        def mismatched_heat_link(buildings, technologies):
            buildings["heat"]["enhancement_tech_id"] = "tech_drawing_board"

        mutations = (
            unknown_building_tech,
            misspelled_building_target,
            misspelled_upgrade_target,
            missing_reverse_building_link,
            mismatched_heat_link,
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate.__name__), tempfile.TemporaryDirectory() as temp_dir:
                buildings = deepcopy(buildings_source)
                technologies = deepcopy(technologies_source)
                mutate(buildings, technologies)
                Path(temp_dir, "buildings.json").write_text(
                    json.dumps(buildings, ensure_ascii=False), encoding="utf-8"
                )
                Path(temp_dir, "technologies.json").write_text(
                    json.dumps(technologies, ensure_ascii=False), encoding="utf-8"
                )

                with redirect_stdout(StringIO()):
                    exit_code = main(["validate-config", temp_dir])

                self.assertEqual(exit_code, 1)

    def test_validate_config_rejects_event_contract_mutation(self) -> None:
        events = json.loads((ROOT / "data" / "events.json").read_text("utf-8"))
        events["fixed_arrivals"]["arrival_day6"]["day"] = 19
        events["fixed_arrivals"]["arrival_day19"]["day"] = 6

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "events.json").write_text(
                json.dumps(events, ensure_ascii=False), encoding="utf-8"
            )
            with redirect_stdout(StringIO()):
                exit_code = main(["validate-config", temp_dir])

        self.assertEqual(exit_code, 1)


if __name__ == "__main__":
    unittest.main()
