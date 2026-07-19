from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from furnace_winter.config import validate_config_file, validate_config_tree


def runtime_document(**values: object) -> dict[str, object]:
    return {"config_status": "FINAL", **values}


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
                json.dumps(runtime_document(value=1)),
                encoding="utf-8",
            )
            issues = validate_config_file(path)

        self.assertEqual(issues, [])

    def test_utf8_bom_json_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bom.json"
            path.write_text(
                json.dumps(runtime_document(value=1)), encoding="utf-8-sig"
            )
            issues = validate_config_file(path)

        self.assertEqual(issues, [])

    def test_invalid_utf8_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "invalid-utf8.json"
            path.write_bytes(b'{"config_status":"FINAL","value":"\xff"}')
            issues = validate_config_file(path)

        self.assertEqual(len(issues), 1)
        self.assertIn("不是有效 UTF-8", issues[0].message)

    def test_invalid_json_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "broken.json"
            path.write_text("{", encoding="utf-8")
            issues = validate_config_file(path)

        self.assertEqual(len(issues), 1)
        self.assertIn("JSON 格式错误", issues[0].message)

    def test_non_finite_json_numbers_are_rejected(self) -> None:
        for token in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(token=token), tempfile.TemporaryDirectory() as temp_dir:
                path = Path(temp_dir) / "non-finite.json"
                path.write_text(
                    f'{{"config_status":"FINAL","value":{token}}}',
                    encoding="utf-8",
                )
                issues = validate_config_file(path)

            self.assertEqual(len(issues), 1)
            self.assertIn(token, issues[0].message)

    def test_all_deprecated_fields_are_rejected_at_any_depth(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "deprecated.json"
            path.write_text(
                json.dumps(
                    runtime_document(
                        ending={
                            "terminal_fail": True,
                            "trust_fail": True,
                            "panic_fail": True,
                            "hope_state": 50,
                        }
                    )
                ),
                encoding="utf-8",
            )
            issues = validate_config_file(path)

        self.assertEqual(len(issues), 4)
        self.assertTrue(all("作废字段" in issue.message for issue in issues))

    def test_non_runtime_markers_are_rejected_as_values(self) -> None:
        markers = (
            "PENDING",
            "PENDING_NUMERIC",
            "DEPRECATED",
            "TODO_TEXT",
            "TODO_VALUE",
            "TODO_SYSTEM",
            "待确认",
            "待判定",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "pending.json"
            path.write_text(
                json.dumps(
                    runtime_document(
                        values={str(index): marker for index, marker in enumerate(markers)}
                    )
                ),
                encoding="utf-8",
            )
            issues = validate_config_file(path)

        self.assertEqual(len(issues), len(markers))
        self.assertTrue(all("不得进入运行配置" in issue.message for issue in issues))

    def test_annotated_non_runtime_markers_are_rejected(self) -> None:
        markers = (
            "PENDING: fill later",
            "PENDING_NUMERIC - fill later",
            "DEPRECATED - old",
            "TODO_TEXT: fill later",
            "TODO_VALUE（缺数值）",
            "TODO_SYSTEM [later]",
            "待确认：缺数值",
            "待判定 - later",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "annotated.json"
            path.write_text(
                json.dumps(
                    runtime_document(
                        values={str(index): marker for index, marker in enumerate(markers)}
                    )
                ),
                encoding="utf-8",
            )
            issues = validate_config_file(path)

        self.assertEqual(len(issues), len(markers))

    def test_non_runtime_markers_are_rejected_as_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "marker-keys.json"
            path.write_text(
                json.dumps(
                    runtime_document(
                        values={"TODO_TEXT": "x", "PENDING_NUMERIC": 10}
                    )
                ),
                encoding="utf-8",
            )
            issues = validate_config_file(path)

        self.assertEqual(len(issues), 2)
        self.assertTrue(all("标记字段" in issue.message for issue in issues))

    def test_marker_like_words_without_boundary_are_accepted(self) -> None:
        values = (
            "PENDINGLY",
            "DEPRECATEDLY",
            "TODO_TEXTBOOK",
            "待确认书",
            "待判定规则",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "ordinary-text.json"
            path.write_text(
                json.dumps(runtime_document(values=list(values))), encoding="utf-8"
            )
            issues = validate_config_file(path)

        self.assertEqual(issues, [])

    def test_missing_unknown_and_non_string_status_are_rejected(self) -> None:
        documents = ({"value": 1}, {"config_status": "UNKNOWN"}, {"config_status": 1})
        for index, document in enumerate(documents):
            with self.subTest(document=document), tempfile.TemporaryDirectory() as temp_dir:
                path = Path(temp_dir) / f"invalid-{index}.json"
                path.write_text(json.dumps(document), encoding="utf-8")
                issues = validate_config_file(path)

            self.assertTrue(issues)
            self.assertTrue(any(issue.location == "$.config_status" for issue in issues))

    def test_array_top_level_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "array.json"
            path.write_text(json.dumps([runtime_document()]), encoding="utf-8")
            issues = validate_config_file(path)

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].location, "$")

    def test_config_tree_scans_nested_directories_and_counts_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            nested = root / "nested"
            nested.mkdir()
            source = json.dumps(runtime_document())
            (root / "root.json").write_text(source, encoding="utf-8")
            (nested / "child.json").write_text(source, encoding="utf-8")
            report = validate_config_tree(root)

        self.assertTrue(report.is_valid)
        self.assertEqual(report.files_checked, 2)

    def test_missing_config_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "missing"
            report = validate_config_tree(missing)

        self.assertFalse(report.is_valid)
        self.assertEqual(report.files_checked, 0)


if __name__ == "__main__":
    unittest.main()
