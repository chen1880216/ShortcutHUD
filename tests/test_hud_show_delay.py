"""Tests for the configurable hold-to-show delay."""

import json
import tempfile
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication

from scripts.config_manager import ConfigManager
from scripts.hud_show_delay import (
    DEFAULT_SHOW_DELAY_MS,
    MAX_SHOW_DELAY_MS,
    MIN_SHOW_DELAY_MS,
    SHOW_DELAY_SETTING,
    WIN_ONLY_MIN_SHOW_DELAY_MS,
    normalize_show_delay_ms,
    resolve_show_delay_ms,
)
from scripts.settings_dialog import SettingsDialog


class NormalizeShowDelayTests(unittest.TestCase):
    def test_accepts_integer_milliseconds(self) -> None:
        self.assertEqual(normalize_show_delay_ms(750), 750)

    def test_accepts_float_milliseconds_by_rounding(self) -> None:
        self.assertEqual(normalize_show_delay_ms(249.6), 250)

    def test_invalid_values_fall_back_to_the_default(self) -> None:
        for value in (None, "300", True, False, [], {}, float("nan"), float("inf")):
            with self.subTest(value=value):
                self.assertEqual(normalize_show_delay_ms(value), DEFAULT_SHOW_DELAY_MS)

    def test_clamps_to_documented_range(self) -> None:
        self.assertEqual(normalize_show_delay_ms(-500), MIN_SHOW_DELAY_MS)
        self.assertEqual(normalize_show_delay_ms(60_000), MAX_SHOW_DELAY_MS)

    def test_custom_default_is_honoured_for_invalid_values(self) -> None:
        self.assertEqual(normalize_show_delay_ms("nope", default=20), 20)


class ResolveShowDelayTests(unittest.TestCase):
    def test_plain_modifier_uses_the_configured_value(self) -> None:
        self.assertEqual(resolve_show_delay_ms(120), 120)

    def test_win_only_hold_keeps_the_safety_floor(self) -> None:
        self.assertEqual(
            resolve_show_delay_ms(10, win_only=True), WIN_ONLY_MIN_SHOW_DELAY_MS
        )

    def test_win_only_hold_keeps_a_longer_configured_value(self) -> None:
        self.assertEqual(resolve_show_delay_ms(900, win_only=True), 900)

    def test_invalid_value_degrades_to_default_then_floor(self) -> None:
        self.assertEqual(resolve_show_delay_ms("", win_only=True), 300)


class ConfigManagerShowDelayTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        root = Path(self._temp_dir.name)
        self.settings_path = root / "settings.json"
        self.manager = ConfigManager(str(root / "shortcuts.json"), str(self.settings_path))
        self.manager.initialize_configs()

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def _write_settings(self, payload: dict) -> None:
        self.settings_path.write_text(json.dumps(payload), encoding="utf-8")

    def test_fresh_settings_file_gets_the_default_delay(self) -> None:
        self.assertEqual(
            self.manager.get_setting(SHOW_DELAY_SETTING), DEFAULT_SHOW_DELAY_MS
        )

    def test_existing_value_is_preserved_on_load(self) -> None:
        self._write_settings({"opacity": 70, SHOW_DELAY_SETTING: 900})
        self.manager.initialize_configs()
        self.assertEqual(self.manager.get_setting(SHOW_DELAY_SETTING), 900)

    def test_invalid_stored_value_is_repaired_on_load(self) -> None:
        self._write_settings({SHOW_DELAY_SETTING: "soon"})
        self.manager.initialize_configs()
        self.assertEqual(
            self.manager.get_setting(SHOW_DELAY_SETTING), DEFAULT_SHOW_DELAY_MS
        )

    def test_update_settings_normalizes_out_of_range_values(self) -> None:
        self.manager.update_settings({SHOW_DELAY_SETTING: -20})
        self.assertEqual(self.manager.get_setting(SHOW_DELAY_SETTING), MIN_SHOW_DELAY_MS)

        self.manager.update_settings({SHOW_DELAY_SETTING: 999_999})
        self.assertEqual(self.manager.get_setting(SHOW_DELAY_SETTING), MAX_SHOW_DELAY_MS)

    def test_update_settings_persists_the_value(self) -> None:
        self.manager.update_settings({SHOW_DELAY_SETTING: 420})
        stored = json.loads(self.settings_path.read_text(encoding="utf-8"))
        self.assertEqual(stored[SHOW_DELAY_SETTING], 420)


class SettingsDialogShowDelayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.qt_application = QApplication.instance() or QApplication([])

    def test_spin_box_reflects_the_stored_delay_in_seconds(self) -> None:
        dialog = SettingsDialog({SHOW_DELAY_SETTING: 900})
        try:
            self.assertAlmostEqual(dialog.show_delay_spin.value(), 0.9, places=2)
        finally:
            dialog.deleteLater()

    def test_spin_box_defaults_when_the_setting_is_missing(self) -> None:
        dialog = SettingsDialog({})
        try:
            self.assertAlmostEqual(
                dialog.show_delay_spin.value(), DEFAULT_SHOW_DELAY_MS / 1000.0, places=2
            )
        finally:
            dialog.deleteLater()

    def test_editing_the_spin_box_emits_milliseconds(self) -> None:
        dialog = SettingsDialog({})
        emitted: list[dict] = []
        dialog.settings_changed.connect(emitted.append)
        try:
            dialog.show_delay_spin.setValue(0.45)
        finally:
            dialog.deleteLater()

        self.assertTrue(emitted)
        self.assertEqual(emitted[-1][SHOW_DELAY_SETTING], 450)

    def test_dialog_settings_dict_carries_the_delay(self) -> None:
        dialog = SettingsDialog({SHOW_DELAY_SETTING: 2000})
        try:
            self.assertEqual(
                dialog.get_current_settings_from_dialog()[SHOW_DELAY_SETTING], 2000
            )
        finally:
            dialog.deleteLater()


if __name__ == "__main__":
    unittest.main()
