import unittest

from PySide6.QtWidgets import QApplication, QLabel

from scripts.hud_entry_limits import (
    DEFAULT_HUD_ENTRY_LIMIT,
    get_hud_entry_limit,
)
from scripts.shortcut_hud import ShortcutHudWindow
from scripts.shortcut_resolver import ShortcutEntry


class HudEntryLimitTests(unittest.TestCase):
    def test_browser_ctrl_overrides_normalize_app_and_modifier(self) -> None:
        self.assertEqual(
            get_hud_entry_limit(
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                "ctrl",
            ),
            9,
        )
        self.assertEqual(get_hud_entry_limit("chrome.exe", "Ctrl"), 9)

    def test_non_override_pairs_use_default_limit(self) -> None:
        self.assertEqual(
            get_hud_entry_limit("MSEDGE.EXE", "Ctrl+Shift"),
            DEFAULT_HUD_ENTRY_LIMIT,
        )
        self.assertEqual(
            get_hud_entry_limit("WINWORD.EXE", "Ctrl"),
            DEFAULT_HUD_ENTRY_LIMIT,
        )
        self.assertEqual(
            get_hud_entry_limit("MSEDGE.EXE", "Ctrl+"),
            DEFAULT_HUD_ENTRY_LIMIT,
        )

    def test_netcatty_groups_show_every_row(self) -> None:
        self.assertEqual(
            get_hud_entry_limit(r"C:\Program Files\Netcatty\Netcatty.exe", "ctrl"),
            27,
        )
        self.assertEqual(get_hud_entry_limit("netcatty.exe", "Ctrl+Shift"), 15)
        self.assertEqual(
            get_hud_entry_limit("NETCATTY.EXE", "Alt"),
            DEFAULT_HUD_ENTRY_LIMIT,
        )

    def test_show_all_returns_no_limit(self) -> None:
        for application_name, modifier in (
            ("WINWORD.EXE", "Ctrl"),
            ("NETCATTY.EXE", "Ctrl"),
            ("MSEDGE.EXE", "Ctrl"),
            ("UNKNOWN.EXE", "Alt"),
        ):
            with self.subTest(application_name=application_name):
                self.assertIsNone(
                    get_hud_entry_limit(
                        application_name,
                        modifier,
                        show_all=True,
                    )
                )

    def test_show_all_is_off_by_default(self) -> None:
        self.assertEqual(
            get_hud_entry_limit("WINWORD.EXE", "Ctrl"),
            DEFAULT_HUD_ENTRY_LIMIT,
        )


class HudEntryLimitPresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.qt_application = QApplication.instance() or QApplication([])

    def test_browser_ctrl_renders_nine_and_ordinary_app_renders_eight(self) -> None:
        entries = [
            ShortcutEntry(str(index), f"Action {index}", "APP")
            for index in range(10)
        ]

        for application_name, modifier, expected_rows in (
            ("MSEDGE.EXE", "Ctrl", 9),
            ("CHROME.EXE", "Ctrl", 9),
            ("PHOTOSHOP.EXE", "Ctrl", 8),
        ):
            with self.subTest(application_name=application_name):
                hud = ShortcutHudWindow()
                hud.set_entries(
                    application_name,
                    modifier,
                    entries,
                    "en_US",
                )
                self.assertEqual(hud._entries_layout.count(), expected_rows)
                hud.deleteLater()


    def test_global_rows_are_pinned_beyond_local_app_limit(self) -> None:
        entries = [
            ShortcutEntry(str(index), f"Local {index}", "APP")
            for index in range(10)
        ] + [
            ShortcutEntry("Tab", "Switch windows", "GLOBAL"),
            ShortcutEntry("F4", "Close current window", "GLOBAL"),
        ]

        for application_name, expected_local_count in (
            ("MSEDGE.EXE", 9),
            ("CHROME.EXE", 9),
            ("PHOTOSHOP.EXE", 8),
        ):
            with self.subTest(application_name=application_name):
                hud = ShortcutHudWindow()
                hud.set_entries(application_name, "Ctrl", entries, "en_US")
                key_texts = [
                    label.text()
                    for label in hud.findChildren(QLabel)
                    if label.objectName() == "shortcutHudKey"
                ]

                self.assertEqual(
                    key_texts,
                    [str(index) for index in range(expected_local_count)]
                    + ["Tab", "F4"],
                )
                hud.deleteLater()


    def test_netcatty_renders_every_configured_row(self) -> None:
        entries = [
            ShortcutEntry(str(index), f"Action {index}", "APP")
            for index in range(40)
        ]

        for modifier, expected_rows in (("Ctrl", 27), ("Ctrl+Shift", 15)):
            with self.subTest(modifier=modifier):
                hud = ShortcutHudWindow()
                hud.set_entries("NETCATTY.EXE", modifier, entries, "en_US")
                self.assertEqual(hud._entries_layout.count(), expected_rows)
                hud.deleteLater()

    def test_show_all_renders_every_entry(self) -> None:
        entries = [
            ShortcutEntry(str(index), f"Action {index}", "APP")
            for index in range(12)
        ]

        hud = ShortcutHudWindow()
        hud.set_entries("WINWORD.EXE", "Ctrl", entries, "en_US", show_all=True)

        self.assertEqual(hud._entries_layout.count(), 12)
        hud.deleteLater()


if __name__ == "__main__":
    unittest.main()
