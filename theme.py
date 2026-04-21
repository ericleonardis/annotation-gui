"""Dark theme for the annotation GUI.

Exports:
    THEME  — dict of hex colors used by custom-painted widgets.
    apply_theme(app) — sets Fusion style, palette, and QSS on a QApplication.
"""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QApplication

THEME = {
    "bg": "#f6f7fa",
    "panel": "#ffffff",
    "panel_alt": "#eef1f5",
    "panel_border": "#d6dae1",
    "text": "#1f2937",
    "text_muted": "#6b7280",
    "accent": "#2563eb",
    "accent_hover": "#1d4ed8",
    "accent_pressed": "#1e40af",
    "playhead": "#ef4444",
    "selection": "#f59e0b",
    "row_divider": "#e3e7ed",
    "timeline_bg": "#ffffff",
    "timeline_row_alt": "#f7f9fc",
    "conflict": "#f97316",
}


_QSS_TEMPLATE = """
QMainWindow, QWidget {{
    background-color: {bg};
    color: {text};
    font-family: -apple-system, "SF Pro Text", "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}}

QLabel {{
    color: {text};
}}

QFrame#panel {{
    background-color: {panel};
    border: 1px solid {panel_border};
    border-radius: 6px;
}}

QPushButton {{
    background-color: {panel_alt};
    color: {text};
    border: 1px solid {panel_border};
    border-radius: 4px;
    padding: 6px 12px;
    font-weight: 500;
}}
QPushButton:hover {{
    background-color: {accent};
    color: white;
    border: 1px solid {accent};
}}
QPushButton:pressed {{
    background-color: {accent_pressed};
}}
QPushButton:disabled {{
    background-color: {panel};
    color: {text_muted};
}}

QPushButton#primary {{
    background-color: {accent};
    color: white;
    border: 1px solid {accent};
}}
QPushButton#primary:hover {{
    background-color: {accent_hover};
}}

QListWidget {{
    background-color: {panel};
    color: {text};
    border: 1px solid {panel_border};
    border-radius: 4px;
    outline: 0;
}}
QListWidget::item {{
    padding: 6px 8px;
    border-bottom: 1px solid {row_divider};
}}
QListWidget::item:selected {{
    background-color: {accent};
    color: white;
}}
QListWidget::item:hover {{
    background-color: {panel_alt};
}}

QTableWidget {{
    background-color: {panel};
    alternate-background-color: {panel_alt};
    color: {text};
    gridline-color: {row_divider};
    border: 1px solid {panel_border};
    border-radius: 4px;
    selection-background-color: {accent};
    selection-color: white;
}}
QTableWidget::item {{
    padding: 4px 6px;
}}
QHeaderView::section {{
    background-color: {panel_alt};
    color: {text};
    padding: 6px 8px;
    border: 0;
    border-right: 1px solid {panel_border};
    border-bottom: 1px solid {panel_border};
    font-weight: 600;
}}

QMenuBar {{
    background-color: {panel};
    color: {text};
    border-bottom: 1px solid {panel_border};
    padding: 2px;
}}
QMenuBar::item {{
    padding: 4px 10px;
    background: transparent;
    border-radius: 3px;
}}
QMenuBar::item:selected {{
    background: {accent};
    color: white;
}}
QMenu {{
    background-color: {panel};
    color: {text};
    border: 1px solid {panel_border};
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 18px;
    border-radius: 3px;
}}
QMenu::item:selected {{
    background-color: {accent};
    color: white;
}}

QSplitter::handle {{
    background-color: {panel_border};
}}
QSplitter::handle:horizontal {{
    width: 4px;
}}
QSplitter::handle:vertical {{
    height: 4px;
}}

QLabel#video_display {{
    background-color: {timeline_bg};
    color: {text_muted};
    border: 1px solid {panel_border};
    border-radius: 6px;
}}

QScrollBar:vertical {{
    background: {panel};
    width: 10px;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: {panel_border};
    border-radius: 4px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{
    background: {accent};
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0; width: 0;
}}
"""


def apply_theme(app: QApplication) -> None:
    """Apply the dark theme to a QApplication.

    Sets Fusion style, configures a dark QPalette for controls that ignore
    stylesheets, and applies the global stylesheet.
    """
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(THEME["bg"]))
    palette.setColor(QPalette.WindowText, QColor(THEME["text"]))
    palette.setColor(QPalette.Base, QColor(THEME["panel"]))
    palette.setColor(QPalette.AlternateBase, QColor(THEME["panel_alt"]))
    palette.setColor(QPalette.ToolTipBase, QColor(THEME["panel"]))
    palette.setColor(QPalette.ToolTipText, QColor(THEME["text"]))
    palette.setColor(QPalette.Text, QColor(THEME["text"]))
    palette.setColor(QPalette.Button, QColor(THEME["panel_alt"]))
    palette.setColor(QPalette.ButtonText, QColor(THEME["text"]))
    palette.setColor(QPalette.Highlight, QColor(THEME["accent"]))
    palette.setColor(QPalette.HighlightedText, Qt.white)
    palette.setColor(QPalette.BrightText, Qt.white)
    palette.setColor(QPalette.Link, QColor(THEME["accent"]))
    palette.setColor(QPalette.PlaceholderText, QColor(THEME["text_muted"]))
    app.setPalette(palette)

    qss = _QSS_TEMPLATE.format(**THEME)
    app.setStyleSheet(qss)
