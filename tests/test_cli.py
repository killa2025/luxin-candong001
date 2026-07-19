from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from furnace_winter.cli import main


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


if __name__ == "__main__":
    unittest.main()
