"""Application-wide styling helpers."""
from __future__ import annotations

from PySide6.QtGui import QColor, QPalette, QFont
from PySide6.QtWidgets import QApplication

PRIMARY_BG = "#0f1115"
SECONDARY_BG = "#0b0d12"
BORDER_COLOR = "#262b36"
ACCENT = "#1f6feb"
ACCENT_HOVER = "#2b7bff"
DISABLED_BG = "#334155"
DISABLED_TEXT = "#9aa4b2"
TEXT_PRIMARY = "#e6e6e6"

STYLE_SHEET = f"""
QWidget {{
  background: {PRIMARY_BG};
  color: {TEXT_PRIMARY};
  font-size: 14px;
}}

QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QListView, QTableView, QTreeView {{
  background: {SECONDARY_BG};
  border: 1px solid {BORDER_COLOR};
  border-radius: 10px;
  padding: 10px;
  selection-background-color: {ACCENT};
}}

QPushButton {{
  background: {ACCENT};
  border: none;
  padding: 10px 16px;
  border-radius: 10px;
}}

QPushButton:hover {{
  background: {ACCENT_HOVER};
}}

QPushButton:disabled {{
  background: {DISABLED_BG};
  color: {DISABLED_TEXT};
}}

QLabel[role="hint"] {{
  color: {DISABLED_TEXT};
}}

QScrollBar:vertical {{
  background: {PRIMARY_BG};
  width: 12px;
  margin: 0px;
}}

QScrollBar::handle:vertical {{
  background: {ACCENT};
  min-height: 20px;
  border-radius: 6px;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
  height: 0px;
}}

QScrollBar:horizontal {{
  background: {PRIMARY_BG};
  height: 12px;
  margin: 0px;
}}

QScrollBar::handle:horizontal {{
  background: {ACCENT};
  min-width: 20px;
  border-radius: 6px;
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
  width: 0px;
}}

QTableWidget {{
  background: {SECONDARY_BG};
  border: 1px solid {BORDER_COLOR};
  border-radius: 10px;
  gridline-color: {BORDER_COLOR};
}}

QHeaderView::section {{
  background: {SECONDARY_BG};
  color: {TEXT_PRIMARY};
  border: none;
  padding: 8px;
}}

QStatusBar {{
  background: {PRIMARY_BG};
}}
"""


def apply_theme(app: QApplication) -> None:
    """Apply the global color palette and stylesheet."""

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(PRIMARY_BG))
    palette.setColor(QPalette.WindowText, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.Base, QColor(SECONDARY_BG))
    palette.setColor(QPalette.AlternateBase, QColor(SECONDARY_BG))
    palette.setColor(QPalette.ToolTipBase, QColor(SECONDARY_BG))
    palette.setColor(QPalette.ToolTipText, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.Text, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.Button, QColor(ACCENT))
    palette.setColor(QPalette.ButtonText, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.Highlight, QColor(ACCENT))
    palette.setColor(QPalette.HighlightedText, QColor(TEXT_PRIMARY))

    app.setPalette(palette)
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    app.setStyleSheet(STYLE_SHEET)
