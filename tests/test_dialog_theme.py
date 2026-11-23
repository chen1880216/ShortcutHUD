"""The dialogs opened from the tray must never inherit the overlay palette."""
import unittest

from PySide6.QtWidgets import QApplication

from scripts.dialog_theme import (
    DIALOG_BACKGROUND_COLOR,
    DIALOG_STYLESHEET,
    FIELD_BACKGROUND_COLOR,
    FIELD_TEXT_COLOR,
    HEADER_TEXT_COLOR,
    apply_readable_theme,
)
from scripts.full_guide_settings import FullGuideSettingsDialog
from scripts.user_shortcut_manager_dialog import ShortcutEditDialog


class DialogThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.qt_application = QApplication.instance() or QApplication([])

    def test_shared_stylesheet_covers_fields_headers_and_buttons(self) -> None:
        sheet = DIALOG_STYLESHEET

        for selector in (
            "QDialog",
            "QLabel",
            "QLineEdit",
            "QKeySequenceEdit QLineEdit",
            "QComboBox",
            "QTableWidget",
            "QHeaderView::section",
            "QTableCornerButton::section",
            "QListWidget",
            "QTabBar::tab",
            "QPushButton",
        ):
            self.assertIn(selector, sheet)

        for colour in (
            DIALOG_BACKGROUND_COLOR,
            FIELD_BACKGROUND_COLOR,
            FIELD_TEXT_COLOR,
            HEADER_TEXT_COLOR,
        ):
            self.assertIn(colour, sheet)

    def test_apply_readable_theme_keeps_dialog_specific_rules_last(self) -> None:
        dialog = ShortcutEditDialog()
        self.addCleanup(dialog.close)
        apply_readable_theme(dialog, "QLabel { color: #FFCC66; }")

        sheet = dialog.styleSheet()
        self.assertTrue(sheet.rstrip().endswith("QLabel { color: #FFCC66; }"))
        self.assertIn("QHeaderView::section", sheet)

    def test_hotkey_dialog_styles_its_key_sequence_editor(self) -> None:
        dialog = FullGuideSettingsDialog("Ctrl+Shift+F10", lambda _text: (True, ""))
        self.addCleanup(dialog.close)

        sheet = dialog.styleSheet()
        self.assertIn("QKeySequenceEdit", sheet)
        self.assertIn(FIELD_BACKGROUND_COLOR, sheet)
        self.assertIn(FIELD_TEXT_COLOR, sheet)

    def test_shortcut_edit_dialog_is_styled(self) -> None:
        dialog = ShortcutEditDialog(modifier="Ctrl", key="S", zh="保存", en="Save")
        self.addCleanup(dialog.close)

        self.assertIn(DIALOG_BACKGROUND_COLOR, dialog.styleSheet())


if __name__ == "__main__":
    unittest.main()
