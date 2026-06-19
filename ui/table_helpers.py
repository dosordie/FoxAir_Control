# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QTableWidget, QTableWidgetItem


def set_table_row_values(table: QTableWidget, row: int, values: list[Any]) -> None:
    """Small shared helper for simple read-only table rows."""
    for column, value in enumerate(values):
        table.setItem(row, column, QTableWidgetItem(str(value)))
