from __future__ import annotations

import unittest

from furnace_winter.config import ConfigStatus
from furnace_winter.text import (
    DeprecatedEntry,
    DeprecatedRegistry,
    MissingTextError,
    PendingEntry,
    PendingRegistry,
    TextEntry,
    TextRegistry,
    TextRegistryError,
    TextVisibility,
)


def confirmed_entry(text_id: str = "test.confirmed") -> TextEntry:
    return TextEntry(
        text_id=text_id,
        text="测试文本",
        status=ConfigStatus.FINAL,
        visibility=TextVisibility.PLAYER_VISIBLE,
        source="tests",
    )


class TextRegistryTests(unittest.TestCase):
    def test_confirmed_text_can_be_looked_up(self) -> None:
        registry = TextRegistry()
        entry = confirmed_entry()
        registry.register(entry)

        self.assertEqual(registry.require(entry.text_id), entry)

    def test_missing_text_is_reported_and_raises_on_require(self) -> None:
        registry = TextRegistry()
        registry.register(confirmed_entry())

        report = registry.report_missing(["test.confirmed", "test.missing"])

        self.assertFalse(report.is_complete)
        self.assertEqual(report.missing_ids, ("test.missing",))
        with self.assertRaises(MissingTextError):
            registry.require("test.missing")

    def test_pending_todo_and_deprecated_are_isolated(self) -> None:
        pending = PendingRegistry()
        pending.register(
            PendingEntry("text.pending", ConfigStatus.PENDING, source="tests")
        )
        pending.register(
            PendingEntry("text.todo", ConfigStatus.TODO_TEXT, source="tests")
        )
        deprecated = DeprecatedRegistry()
        deprecated.register(DeprecatedEntry("text.old", source="tests"))

        runtime = TextRegistry()

        self.assertEqual(pending.todo_text_ids(), ("text.todo",))
        self.assertTrue(deprecated.contains("text.old"))
        self.assertEqual(runtime.entries(), ())

    def test_non_runtime_and_internal_text_are_rejected(self) -> None:
        registry = TextRegistry()
        with self.assertRaises(TextRegistryError):
            registry.register(
                TextEntry(
                    "text.todo",
                    "未完成",
                    ConfigStatus.TODO_TEXT,
                    TextVisibility.PLAYER_VISIBLE,
                    "tests",
                )
            )
        with self.assertRaises(TextRegistryError):
            registry.register(
                TextEntry(
                    "text.internal",
                    "内部",
                    ConfigStatus.FINAL,
                    TextVisibility.SYSTEM_INTERNAL,
                    "tests",
                )
            )

    def test_blank_text_and_non_normalized_text_ids_are_rejected(self) -> None:
        registry = TextRegistry()
        for entry in (
            TextEntry(
                "text.blank",
                "   ",
                ConfigStatus.FINAL,
                TextVisibility.PLAYER_VISIBLE,
                "tests",
            ),
            confirmed_entry(""),
            confirmed_entry("   "),
            confirmed_entry(" text.spaced"),
            confirmed_entry("text.spaced "),
        ):
            with self.subTest(entry=entry), self.assertRaises(TextRegistryError):
                registry.register(entry)

    def test_pending_and_deprecated_ids_must_be_normalized(self) -> None:
        for entry_id in ("", "   ", " pending.id", "deprecated.id "):
            with self.subTest(entry_id=entry_id):
                with self.assertRaises(ValueError):
                    PendingRegistry().register(
                        PendingEntry(entry_id, ConfigStatus.PENDING, source="tests")
                    )
                with self.assertRaises(ValueError):
                    DeprecatedRegistry().register(
                        DeprecatedEntry(entry_id, source="tests")
                    )
if __name__ == "__main__":
    unittest.main()
