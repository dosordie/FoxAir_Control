# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem


MAIN_TABLE_COLUMN_WIDTHS = {
    "Reg": 58, "Code": 68, "Name": 280, "Typ": 65,
    "Rohwert": 125, "Letzter Wert": 115, "Signed": 76, "Wert": 130,
    "Frame": 75, "Bus": 55, "Zeit": 85,
    "Cloud Wert": 150, "Cloud vorher": 130, "Cloud Code": 110, "Cloud Abruf": 130,
}


class PersistentTableColumnWidths(QObject):
    """Restore interactive widths by header name and debounce settings writes."""

    SETTINGS_KEY = "main_table_column_widths"

    def __init__(self, table: QTableWidget, settings: dict[str, Any],
                 defaults: dict[str, int], save: Callable[[], None]):
        super().__init__(table)
        self.table = table
        self.settings = settings
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(400)
        self.save_timer.timeout.connect(save)
        header = table.horizontalHeader()
        header.setSectionsMovable(False)
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(40)
        header.setMaximumSectionSize(4096)
        header.setSectionResizeMode(QHeaderView.Interactive)
        saved = settings.get(self.SETTINGS_KEY, {})
        if not isinstance(saved, dict):
            saved = {}
        widths = {}
        for column in range(table.columnCount()):
            name = table.horizontalHeaderItem(column).text()
            width = saved.get(name)
            if type(width) is not int or not 0 < width <= header.maximumSectionSize():
                width = defaults[name]
            width = max(header.minimumSectionSize(), width)
            table.setColumnWidth(column, width)
            widths[name] = width
        settings[self.SETTINGS_KEY] = widths
        header.sectionResized.connect(self._section_resized)

    def _section_resized(self, column: int, _old: int, width: int) -> None:
        name = self.table.horizontalHeaderItem(column).text()
        self.settings[self.SETTINGS_KEY][name] = width
        self.save_timer.start()

    def stop_pending_save(self) -> None:
        """The owning window persists the in-memory widths during normal close."""
        self.save_timer.stop()


def set_table_row_values(table: QTableWidget, row: int, values: list[Any]) -> None:
    """Small shared helper for simple read-only table rows."""
    for column, value in enumerate(values):
        table.setItem(row, column, QTableWidgetItem(str(value)))
