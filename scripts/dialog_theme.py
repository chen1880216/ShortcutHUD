"""Readable dark styling shared by the dialogs opened over dark surfaces.

The overlay forces its own dark palette on the widgets it owns, and Qt lets
children inherit that palette. Dialogs that did not style themselves therefore
rendered editable fields and hints as light text on light backgrounds on some
Windows themes, which is unreadable. Every dialog that can be opened from the
tray now pulls its colours from here instead of relying on the system palette.
"""
from __future__ import annotations

from PySide6.QtWidgets import QWidget

DIALOG_BACKGROUND_COLOR = "#2E2E3A"
DIALOG_TEXT_COLOR = "#D8DEE9"
DIALOG_MUTED_TEXT_COLOR = "#C8D0DE"
FIELD_BACKGROUND_COLOR = "#4A4E5A"
FIELD_BORDER_COLOR = "#5A5E6A"
FIELD_TEXT_COLOR = "#F2F5FA"
TABLE_BACKGROUND_COLOR = "#333742"
TABLE_ALTERNATE_BACKGROUND_COLOR = "#3A3E4A"
TABLE_TEXT_COLOR = "#E6E9F0"
HEADER_BACKGROUND_COLOR = "#3F4450"
HEADER_TEXT_COLOR = "#F2F5FA"
GRID_LINE_COLOR = "#454A56"
SELECTION_BACKGROUND_COLOR = "#3D6EA8"
DISABLED_TEXT_COLOR = "#7E8391"

DIALOG_STYLESHEET = f"""
    QDialog {{
        background-color: {DIALOG_BACKGROUND_COLOR};
        color: {DIALOG_TEXT_COLOR};
    }}
    QLabel {{
        color: {DIALOG_TEXT_COLOR};
        background: transparent;
    }}
    QLabel:disabled {{
        color: {DISABLED_TEXT_COLOR};
    }}
    QGroupBox {{
        color: {DIALOG_TEXT_COLOR};
        border: 1px solid {GRID_LINE_COLOR};
        border-radius: 4px;
        margin-top: 12px;
        padding: 10px 5px 5px 5px;
    }}
    QGroupBox::title {{
        color: {DIALOG_TEXT_COLOR};
        subcontrol-origin: margin;
        subcontrol-position: top center;
        padding: 0 5px;
        background-color: transparent;
    }}
    QCheckBox, QRadioButton {{
        color: {DIALOG_TEXT_COLOR};
        background: transparent;
    }}
    QCheckBox:disabled, QRadioButton:disabled {{
        color: {DISABLED_TEXT_COLOR};
    }}
    QLineEdit, QKeySequenceEdit, QComboBox, QSpinBox, QTextEdit, QPlainTextEdit {{
        color: {FIELD_TEXT_COLOR};
        background-color: {FIELD_BACKGROUND_COLOR};
        border: 1px solid {FIELD_BORDER_COLOR};
        border-radius: 3px;
        padding: 3px 5px;
        selection-background-color: {SELECTION_BACKGROUND_COLOR};
        selection-color: #FFFFFF;
    }}
    QLineEdit:focus, QKeySequenceEdit:focus, QComboBox:focus {{
        border-color: {SELECTION_BACKGROUND_COLOR};
    }}
    QKeySequenceEdit QLineEdit {{
        color: {FIELD_TEXT_COLOR};
        background-color: {FIELD_BACKGROUND_COLOR};
        border: 1px solid {FIELD_BORDER_COLOR};
        border-radius: 3px;
        padding: 4px 6px;
    }}
    QComboBox QAbstractItemView, QListView, QTreeView {{
        color: {FIELD_TEXT_COLOR};
        background-color: {DIALOG_BACKGROUND_COLOR};
        border: 1px solid {FIELD_BORDER_COLOR};
        selection-background-color: {SELECTION_BACKGROUND_COLOR};
        selection-color: #FFFFFF;
        outline: 0;
    }}
    QTabWidget::pane {{
        border: 1px solid {GRID_LINE_COLOR};
        background-color: {DIALOG_BACKGROUND_COLOR};
    }}
    QTabBar::tab {{
        color: {DIALOG_MUTED_TEXT_COLOR};
        background-color: {TABLE_ALTERNATE_BACKGROUND_COLOR};
        border: 1px solid {GRID_LINE_COLOR};
        border-bottom: none;
        padding: 6px 12px;
    }}
    QTabBar::tab:selected {{
        color: #FFFFFF;
        background-color: {FIELD_BACKGROUND_COLOR};
    }}
    QTabBar::tab:hover {{
        background-color: #434855;
    }}
    QTableWidget, QTableView {{
        color: {TABLE_TEXT_COLOR};
        background-color: {TABLE_BACKGROUND_COLOR};
        alternate-background-color: {TABLE_ALTERNATE_BACKGROUND_COLOR};
        gridline-color: {GRID_LINE_COLOR};
        border: 1px solid {GRID_LINE_COLOR};
        selection-background-color: {SELECTION_BACKGROUND_COLOR};
        selection-color: #FFFFFF;
    }}
    QHeaderView::section {{
        color: {HEADER_TEXT_COLOR};
        background-color: {HEADER_BACKGROUND_COLOR};
        border: none;
        border-right: 1px solid #4C5160;
        border-bottom: 1px solid #4C5160;
        padding: 5px 6px;
        font-weight: 600;
    }}
    QTableCornerButton::section {{
        background-color: {HEADER_BACKGROUND_COLOR};
        border: none;
    }}
    QListWidget {{
        color: {TABLE_TEXT_COLOR};
        background-color: {TABLE_BACKGROUND_COLOR};
        border: 1px solid {GRID_LINE_COLOR};
        outline: 0;
    }}
    QListWidget::item:selected {{
        color: #FFFFFF;
        background-color: {SELECTION_BACKGROUND_COLOR};
    }}
    QPushButton {{
        color: {FIELD_TEXT_COLOR};
        background-color: {FIELD_BACKGROUND_COLOR};
        border: 1px solid {FIELD_BORDER_COLOR};
        border-radius: 3px;
        padding: 5px 10px;
    }}
    QPushButton:hover {{
        background-color: #555A68;
    }}
    QPushButton:pressed {{
        background-color: {HEADER_BACKGROUND_COLOR};
    }}
    QPushButton:disabled {{
        color: {DISABLED_TEXT_COLOR};
        background-color: {TABLE_ALTERNATE_BACKGROUND_COLOR};
    }}
    QDialogButtonBox QPushButton {{
        min-width: 72px;
    }}
    QSplitter::handle {{
        background-color: {TABLE_ALTERNATE_BACKGROUND_COLOR};
    }}
    QToolTip {{
        color: {FIELD_TEXT_COLOR};
        background-color: {HEADER_BACKGROUND_COLOR};
        border: 1px solid {FIELD_BORDER_COLOR};
    }}
"""


def apply_readable_theme(widget: QWidget, extra: str = "") -> None:
    """Apply the shared readable dark theme to ``widget`` and its children.

    ``extra`` lets a dialog keep its own rules; those come last so they win.
    """
    stylesheet = DIALOG_STYLESHEET
    if extra:
        stylesheet = f"{stylesheet}\n{extra}"
    widget.setStyleSheet(stylesheet)
