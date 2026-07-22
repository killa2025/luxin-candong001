from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from furnace_winter.config import (
    ConfigLoadError,
    ConfigStatus,
    load_config_file,
    load_config_tree,
)


class ConfigLoaderTests(unittest.TestCase):
    PROJECT_ROOT = Path(__file__).resolve().parents[1]

    def test_repository_manifest_loads(self) -> None:
        documents = load_config_tree(self.PROJECT_ROOT / "data")

        self.assertEqual(len(documents), 6)
        self.assertEqual(
            [item.status for item in documents],
            [
                ConfigStatus.TEST_NUMERIC,
                ConfigStatus.TEST_NUMERIC,
                ConfigStatus.TEST_NUMERIC,
                ConfigStatus.FINAL,
                ConfigStatus.FINAL,
                ConfigStatus.TEST_NUMERIC,
            ],
        )
        self.assertEqual(
            [item.data["schema_version"] for item in documents],
            [2, 1, 1, 1, 1, 1],
        )

    def test_test_numeric_status_is_explicitly_identifiable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "test-numeric.json"
            path.write_text(
                json.dumps({"config_status": "TEST_NUMERIC", "value": 1}),
                encoding="utf-8",
            )

            loaded = load_config_file(path)

        self.assertEqual(loaded.status, ConfigStatus.TEST_NUMERIC)

    def test_pending_status_is_not_loadable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "pending.json"
            path.write_text(
                json.dumps({"config_status": "PENDING"}),
                encoding="utf-8",
            )

            with self.assertRaises(ConfigLoadError):
                load_config_file(path)

    def test_todo_text_marker_scan_blocks_runtime_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "todo.json"
            path.write_text(
                json.dumps(
                    {"config_status": "FINAL", "text": "TODO_TEXT: not sealed"}
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ConfigLoadError):
                load_config_tree(Path(temp_dir))

    def test_validator_and_loader_reject_the_same_invalid_documents(self) -> None:
        documents = (
            {"value": 1},
            {"config_status": "UNKNOWN"},
            {"config_status": 1},
            {"config_status": "FINAL", "TODO_TEXT": "x"},
        )
        for index, document in enumerate(documents):
            with self.subTest(document=document), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                path = root / f"invalid-{index}.json"
                path.write_text(json.dumps(document), encoding="utf-8")

                with self.assertRaises(ConfigLoadError):
                    load_config_tree(root)


if __name__ == "__main__":
    unittest.main()
