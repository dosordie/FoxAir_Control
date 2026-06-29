# -*- coding: utf-8 -*-
from __future__ import annotations

PUBLIC_WARNING_TEXT = "Inoffizielles Tool. Register schreiben auf eigene Gefahr. Vor Änderungen Backup erstellen."
APP_ICON_FILE = "app_icon.png"

LIGHT_THEME_QSS = """
QWidget { background: #f2f2f2; color: #111111; }
QMainWindow, QDialog { background: #f2f2f2; color: #111111; }
QLabel { color: #111111; }
QGroupBox { color: #111111; border: 1px solid #c8c8c8; border-radius: 4px; margin-top: 10px; padding-top: 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 3px; background: #f2f2f2; }
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox { background: #ffffff; color: #111111; border: 1px solid #b8b8b8; selection-background-color: #2a82da; selection-color: #ffffff; }
QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled { background: #e4e4e4; color: #777777; border-color: #c8c8c8; }
QComboBox:disabled QAbstractItemView { background: #e4e4e4; color: #777777; }
QPushButton { background: #f8f8f8; color: #111111; border: 1px solid #b8b8b8; border-radius: 3px; padding: 3px 8px; }
QPushButton:hover { background: #e9f2ff; border-color: #7aa7d9; }
QPushButton:checked { background: #ffd7c2; border-color: #c36a3a; }
QPushButton:disabled { background: #e4e4e4; color: #777777; }
QCheckBox { color: #111111; }
QHeaderView::section { background: #e9e9e9; color: #111111; border: 1px solid #c8c8c8; padding: 3px; }
QTableWidget, QTableView { background: #fff4a8; alternate-background-color: #fff0c6; color: #111111; gridline-color: #d0c78a; selection-background-color: #2a82da; selection-color: #ffffff; }
QTableWidget::item, QTableView::item { color: #111111; }
QTextEdit#log_view { background: #ffffff; color: #111111; border: 1px solid #b8b8b8; }
QScrollArea { background: #f2f2f2; }
"""

DARK_THEME_QSS = """
QWidget { background: #202124; color: #eeeeee; }
QMainWindow, QDialog { background: #202124; color: #eeeeee; }
QLabel { color: #eeeeee; }
QGroupBox { color: #eeeeee; border: 1px solid #555555; border-radius: 4px; margin-top: 10px; padding-top: 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 3px; background: #202124; }
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox { background: #2b2b2b; color: #eeeeee; border: 1px solid #666666; selection-background-color: #4a6984; selection-color: #ffffff; }
QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled { background: #2a2a2a; color: #888888; border-color: #555555; }
QComboBox:disabled QAbstractItemView { background: #2a2a2a; color: #888888; }
QPushButton { background: #303134; color: #eeeeee; border: 1px solid #666666; border-radius: 3px; padding: 3px 8px; }
QPushButton:hover { background: #3a3d41; border-color: #8ab4f8; }
QPushButton:checked { background: #7a3f2a; border-color: #d98b5f; }
QPushButton:disabled { background: #2a2a2a; color: #888888; }
QCheckBox { color: #eeeeee; }
QHeaderView::section { background: #303134; color: #ffffff; border: 1px solid #555555; padding: 3px; }
QTableWidget, QTableView { background: #252525; alternate-background-color: #2d2d2d; color: #eeeeee; gridline-color: #444444; selection-background-color: #4a6984; selection-color: #ffffff; }
QTableWidget::item, QTableView::item { color: #eeeeee; }
QTextEdit#log_view { background: #111111; color: #e6e6e6; }
QScrollArea { background: #202124; }
"""



def get_app_stylesheet(theme: str = "light") -> str:
    """Return the application stylesheet for the selected theme."""
    return DARK_THEME_QSS if str(theme or "light").lower().strip() == "dark" else LIGHT_THEME_QSS


SPLASH_STYLESHEET = """
QDialog#StartupSplash { background: #111820; border: 1px solid #2d3b48; }
QDialog#StartupSplash QLabel { background: transparent; border: none; }
QDialog#StartupSplash QLabel#title { color: #ffffff; font-size: 24px; font-weight: bold; background: transparent; }
QDialog#StartupSplash QLabel#version { color: #d7e6f5; font-size: 14px; background: transparent; }
QDialog#StartupSplash QLabel#hint { color: #9fb2c4; font-size: 11px; background: transparent; }
QDialog#StartupSplash QLabel#brand { color: #d7e6f5; font-size: 13px; font-weight: bold; background: transparent; }
"""

SPLASH_CLOSE_BUTTON_STYLESHEET = """
QPushButton {
    color: #d7e6f5;
    background: transparent;
    border: 1px solid #53677a;
    border-radius: 4px;
    font-size: 16px;
    font-weight: bold;
}
QPushButton:hover { background: #263747; }
"""

SPLASH_LABEL_STYLESHEETS = {
    "logo": "background: transparent; border: none;",
    "title": "background: transparent; color: #ffffff; font-size: 24px; font-weight: bold;",
    "version": "background: transparent; color: #d7e6f5; font-size: 14px;",
    "brand": "background: transparent; color: #d7e6f5; font-size: 13px; font-weight: bold;",
}


def get_splash_stylesheet() -> str:
    return SPLASH_STYLESHEET


def get_splash_close_button_stylesheet() -> str:
    return SPLASH_CLOSE_BUTTON_STYLESHEET


def get_splash_label_stylesheet(name: str) -> str:
    return SPLASH_LABEL_STYLESHEETS.get(name, "")
