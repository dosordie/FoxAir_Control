"""Functional CSV controls and normal close behavior, without pixel assertions."""

import pytest
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import QGroupBox, QHBoxLayout

from core.csv_logger_controller import CsvLoggerController
from dialogs.csv_logger_dialog import CsvLoggerDialog
from test_cloud_polling import DialogWindow
from test_cloud_single_read_and_values import application, cloud_row
from test_csv_register_logger import read_csv
from test_warmlink_request_scheduler import window


class RecordingCloseDialog(CsvLoggerDialog):
    close_calls = 0

    def closeEvent(self, event):
        self.close_calls += 1
        super().closeEvent(event)


def cloud_dialog():
    owner = DialogWindow()
    owner.connected = False
    owner.cloud_session_device_code = "device"
    owner.cloud_write_thread = None
    owner.csv_logger_controller = CsvLoggerController(owner)
    requests = []
    owner.request_csv_cloud_snapshot = lambda request: requests.append(request)
    return owner, RecordingCloseDialog(owner), requests


def test_groups_button_order_and_main_icon(application):
    owner = DialogWindow()
    owner.connected = False
    owner.csv_logger_controller = CsvLoggerController(owner)
    pixmap = QPixmap(16, 16)
    pixmap.fill(QColor("green"))
    owner.setWindowIcon(QIcon(pixmap))
    dialog = CsvLoggerDialog(owner)
    groups = {group.title(): group for group in dialog.findChildren(QGroupBox)}
    assert set(groups) == {"Aufzeichnung", "Status"}
    for widget in (dialog.path_edit, dialog.choose_button, dialog.interval_spin):
        assert groups["Aufzeichnung"].isAncestorOf(widget)
    for widget in (dialog.source_label, dialog.status_label, dialog.last_label, dialog.rows_label):
        assert groups["Status"].isAncestorOf(widget)
    buttons = dialog.layout().itemAt(dialog.layout().count() - 1).layout()
    assert isinstance(buttons, QHBoxLayout)
    assert buttons.itemAt(0).widget() is dialog.start_button
    assert buttons.itemAt(1).widget() is dialog.stop_button
    assert buttons.itemAt(2).spacerItem() is not None
    assert buttons.itemAt(3).widget() is dialog.close_button
    assert not dialog.windowIcon().isNull()
    assert dialog.windowIcon().cacheKey() == owner.windowIcon().cacheKey()
    dialog.close()
    owner.deleteLater()


@pytest.mark.parametrize("close_method", ["button", "window-close"])
def test_cloud_close_stops_flushes_and_cancels_only_recording(application, tmp_path, close_method):
    owner, dialog, requests = cloud_dialog()
    controller = owner.csv_logger_controller
    path = tmp_path / "cloud.csv"
    dialog.path_edit.setText(str(path))
    assert dialog.start_button.isEnabled() and not dialog.stop_button.isEnabled()
    dialog.start_button.click()
    assert controller.running and not dialog.start_button.isEnabled() and dialog.stop_button.isEnabled()
    assert all(not widget.isEnabled() for widget in (dialog.path_edit, dialog.choose_button, dialog.interval_spin))
    controller.cloud_response(requests[-1].cycle_id, [cloud_row("512", "Fault8")])
    assert controller.writer.rows_written == 1
    dialog.stop_button.click()
    assert not controller.running and dialog.start_button.isEnabled() and not dialog.stop_button.isEnabled()
    assert all(widget.isEnabled() for widget in (dialog.path_edit, dialog.choose_button, dialog.interval_spin))
    dialog.start_button.click()
    pending = requests[-1]
    file = controller.writer.file
    if close_method == "button":
        dialog.close_button.click()
    else:
        dialog.close()
    assert dialog.close_calls == 1
    assert not controller.running and controller.writer.file is None and file.closed
    assert not controller.interval_timer.isActive() and not controller.timeout_timer.isActive()
    assert pending.cancelled.is_set()
    assert owner.is_cloud_connected() and owner.cloud_session_device_code == "device"
    controller.cloud_response(pending.cycle_id, [cloud_row("1024", "Fault8")])
    rows = read_csv(path)
    assert len(rows) == 2
    assert rows[1][3 + 2088 - 2001] == "512"
    owner.deleteLater()


def test_close_keeps_local_transport_and_background_read(window, application, tmp_path):
    # Real MAIN methods, scheduler and ReaderWorker, with an in-memory client.
    window.send_read_request(1158, label="normal read")
    window.worker._flush_write_queue()
    worker = window.worker
    scheduler = window.warmlink_read_scheduler
    active = scheduler.active
    dialog = RecordingCloseDialog(window)
    dialog.path_edit.setText(str(tmp_path / "local.csv"))
    dialog.start_button.click()
    controller = window.csv_logger_controller
    assert controller.running and controller.local_request is not None
    dialog.close_button.click()
    assert dialog.close_calls == 1
    assert not controller.running and controller.writer.file is None
    assert window.connected and window.worker is worker and worker.running
    assert scheduler.active is active and active["label"] == "normal read"
    assert not any("CSV" in entry[2]["label"] for entry in scheduler.queue)
