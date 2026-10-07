"""Main table sizing and Cloud activity rendering, without pixel assertions."""
import json
import time

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView, QTableWidget

import foxair_phnix_control as gui
from core.foxair_phnix_core import DecodedRegister
from ui.table_helpers import MAIN_TABLE_COLUMN_WIDTHS, PersistentTableColumnWidths
from test_cloud_single_read_and_values import cloud_row
from test_csv_logger_transport import wait_for
from test_warmlink_request_scheduler import application, window


def test_main_columns_are_interactive_with_bounded_defaults(window):
    table = window.register_table
    header = table.horizontalHeader()
    assert not header.sectionsMovable() and not header.stretchLastSection()
    assert header.minimumSectionSize() == 40
    assert table.textElideMode() == Qt.TextElideMode.ElideRight
    assert not table.wordWrap()
    for column in range(table.columnCount()):
        assert header.sectionResizeMode(column) == QHeaderView.Interactive
        name = table.horizontalHeaderItem(column).text()
        assert table.columnWidth(column) == MAIN_TABLE_COLUMN_WIDTHS[name]
    table.setColumnWidth(11, 165)
    assert table.columnWidth(11) == 165
    assert window.settings["main_table_column_widths"]["Cloud Wert"] == 165


@pytest.mark.parametrize("saved", [None, [], [150] * 15, "legacy",
    {"Cloud Wert": "wide"}, {"Cloud Wert": -1}, {"Cloud Wert": 0},
    {"Cloud Wert": True}, {"Cloud Wert": 150.5}, {"Cloud Wert": 100000}])
def test_invalid_column_settings_fall_back_to_defaults(application, saved):
    table = QTableWidget(0, len(MAIN_TABLE_COLUMN_WIDTHS))
    table.setHorizontalHeaderLabels(list(MAIN_TABLE_COLUMN_WIDTHS))
    settings = {"main_table_column_widths": saved}
    controller = PersistentTableColumnWidths(table, settings, MAIN_TABLE_COLUMN_WIDTHS, lambda: None)
    assert table.columnWidth(11) == 150
    assert not controller.save_timer.isActive()
    table.deleteLater()


def test_partial_column_settings_and_minimum_width(application):
    table = QTableWidget(0, len(MAIN_TABLE_COLUMN_WIDTHS))
    table.setHorizontalHeaderLabels(list(MAIN_TABLE_COLUMN_WIDTHS))
    settings = {"main_table_column_widths": {"Name": 250, "Reg": 10, "removed column": 400}}
    controller = PersistentTableColumnWidths(table, settings, MAIN_TABLE_COLUMN_WIDTHS, lambda: None)
    assert table.columnWidth(2) == 250
    assert table.columnWidth(0) == 40
    assert table.columnWidth(11) == 150
    assert "removed column" not in settings["main_table_column_widths"]
    assert not controller.save_timer.isActive()
    table.deleteLater()


def test_column_widths_survive_settings_save_and_new_window(window):
    window.register_table.setColumnWidth(2, 250)
    window.register_table.setColumnWidth(11, 165)
    window._save_settings(sync_main_fields=False)
    with open(window.settings_path, encoding="utf-8") as file:
        saved = json.load(file)
    assert saved["main_table_column_widths"]["Name"] == 250
    assert saved["main_table_column_widths"]["Cloud Wert"] == 165
    reopened = gui.MainWindow()
    try:
        assert reopened.register_table.columnWidth(2) == 250
        assert reopened.register_table.columnWidth(11) == 165
    finally:
        reopened.close()
        reopened.deleteLater()


def test_column_settings_writes_are_debounced(window, application, monkeypatch):
    writes = []
    monkeypatch.setattr(window, "_write_settings_file", lambda: writes.append(True))
    for width in range(151, 181):
        window.register_table.setColumnWidth(11, width)
    assert window.settings["main_table_column_widths"]["Cloud Wert"] == 180
    assert writes == []
    wait_for(lambda: len(writes) == 1)
    assert not window.main_table_columns.save_timer.isActive()


def test_live_rows_preserve_manual_name_width_and_long_cloud_values(window):
    table = window.register_table
    table.setColumnWidth(2, 250)
    table.setColumnWidth(11, 160)
    table.setColumnWidth(12, 135)
    reg = DecodedRegister(0x63, 1012, 0, 3, 1, 1, "1", "Very long name " * 40, "DIGI1", time.time())
    window._upsert_register_row(reg, changed=False)
    old, new = "old state " * 100, "new state " * 120
    window.apply_cloud_rows_to_main([cloud_row(old, "Mode")])
    window.apply_cloud_rows_to_main([cloud_row(new, "Mode")])
    row = window.table_rows[1012]
    assert table.columnWidth(2) == 250
    assert table.columnWidth(11) == 160 and table.columnWidth(12) == 135
    assert table.rowHeight(row) == 24
    assert table.item(row, 11).text() == new
    assert new in table.item(row, 11).toolTip()
    assert table.item(row, 12).text() == old
    assert old in table.item(row, 12).toolTip()
    window._upsert_register_row(reg, changed=False)
    assert table.columnWidth(2) == 250
    assert new in table.item(row, 11).toolTip()
    assert old in table.item(row, 12).toolTip()
    window.clear_cloud_overlay()
    assert table.item(row, 11).toolTip() == table.item(row, 12).toolTip() == ""


@pytest.mark.parametrize("stopped_state", ["CONNECTED", "DISCONNECTED", "ERROR", "CONNECTING"])
def test_cloud_border_animation_follows_state_and_preserves_layout(window, stopped_state, monkeypatch):
    monkeypatch.setattr(window, "request_cloud_snapshot", lambda *a, **kw: pytest.fail("UI must not request Cloud data"))
    button = window.cloud_btn
    timing = window.cloud_timing_state
    window.set_cloud_ui_state("CONNECTED", device_name="GL9", last_success_at=100000)
    size, icon, text = button.sizeHint(), button.icon().cacheKey(), button.text()
    assert not button.animation_timer.isActive()
    assert "Verbunden · Polling gestoppt" in button.toolTip()
    window.set_cloud_ui_state("POLLING")
    assert button.animation_timer.isActive()
    assert button.property("pollingActive") is True
    assert "Verbunden · Polling aktiv" in button.toolTip()
    assert "Letzter erfolgreicher Abruf:" in button.toolTip()
    assert "Gerät: GL9" in button.toolTip()
    assert button.sizeHint() == size
    assert button.icon().cacheKey() == icon and button.text() == text
    button.animation_timer.timeout.emit()
    window.set_cloud_ui_state(stopped_state)
    assert not button.animation_timer.isActive()
    assert button.property("pollingActive") is False
    assert button._dash_offset == 0
    assert button.sizeHint() == size
    assert window.cloud_timing_state is timing


def test_close_stops_animation_and_pending_column_save(window):
    window.set_cloud_ui_state("POLLING")
    window.register_table.setColumnWidth(11, 175)
    assert window.cloud_btn.animation_timer.isActive()
    assert window.main_table_columns.save_timer.isActive()
    window.close()
    assert not window.cloud_btn.animation_timer.isActive()
    assert not window.main_table_columns.save_timer.isActive()
    with open(window.settings_path, encoding="utf-8") as file:
        assert json.load(file)["main_table_column_widths"]["Cloud Wert"] == 175
