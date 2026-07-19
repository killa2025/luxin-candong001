from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from furnace_winter.config import validate_config_file, validate_config_tree


class ConfigValidatorTests(unittest.TestCase):
    PROJECT_ROOT = Path(__file__).resolve().parents[1]

    def test_repository_data_tree_is_valid(self) -> None:
        report = validate_config_tree(self.PROJECT_ROOT / "data")

        self.assertTrue(report.is_valid)

    def test_empty_config_directory_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report = validate_config_tree(Path(temp_dir))

        self.assertTrue(report.is_valid)
        self.assertEqual(report.files_checked, 0)

    def test_valid_json_config_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.json"
            path.write_text(
                json.dumps({"status": "FINAL", "value": 1}),
                encoding="utf-8",
            )
            issues = validate_config_file(path)

        self.assertEqual(issues, [])

    def test_invalid_json_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "broken.json"
            path.write_text("{", encoding="utf-8")
            issues = validate_config_file(path)

        self.assertEqual(len(issues), 1)
        self.assertIn("JSON 格式错误", issues[0].message)

    def test_deprecated_field_is_rejected_at_any_depth(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "deprecated.json"
            path.write_text(
                json.dumps({"ending": {"terminal_fail": True}}),
                encoding="utf-8",
            )
            issues = validate_config_file(path)

        self.assertEqual(len(issues), 1)
        self.assertIn("作废字段", issues[0].message)

    def test_non_runtime_status_values_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "pending.json"
            path.write_text(
                json.dumps(
                    {
                        "numeric": "PENDING_NUMERIC",
                        "text": "TODO_TEXT",
                        "old": "DEPRECATED",
                    }
                ),
                encoding="utf-8",
            )
            issues = validate_config_file(path)

        self.assertEqual(len(issues), 3)
        self.assertTrue(all("不得进入运行配置" in issue.message for issue in issues))

    def test_missing_config_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "missing"
            report = validate_config_tree(missing)

        self.assertFalse(report.is_valid)
        self.assertEqual(report.files_checked, 0)


if __name__ == "__main__":
    unittest.main()
