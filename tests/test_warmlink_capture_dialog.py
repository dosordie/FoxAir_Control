import os
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

qt_widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
QApplication = qt_widgets.QApplication
QMainWindow = qt_widgets.QMainWindow
QPushButton = qt_widgets.QPushButton

import foxair_phnix_control as app
from warmlink_raw_capture import CaptureStatus


class FakeCapture:
    def __init__(self, active=True, tx_size=0):
        self.status = CaptureStatus(active=active, segment="segment-1", rx_size=2048, tx_size=tx_size)
        self.rotations = 0

    def get_status(self):
        return self.status

    def force_new_segment(self):
        self.rotations += 1


class FakeMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = {"warmlink_raw_capture": {"enabled": False, "mode": "firmware"}}
        self.warmlink_capture = None
        self.connected = True
        self.base_dir = self.user_data_dir = os.getcwd()
        self.started = self.stopped = self.saved = 0

    def _capture_settings(self):
        cfg = dict(app.DEFAULT_CAPTURE_SETTINGS)
        cfg.update(self.settings["warmlink_raw_capture"])
        return cfg

    def _is_firmware_capture_mode(self):
        cfg = self._capture_settings()
        return bool(cfg["enabled"] and cfg["mode"] == "firmware")

    def _set_firmware_capture_guard(self, active):
        self.guard = active

    def _save_settings(self, sync_main_fields=False):
        self.saved += 1

    def _start_warmlink_capture_if_enabled(self):
        self.started += 1
        self.warmlink_capture = FakeCapture()

    def _stop_warmlink_capture(self, reason=""):
        self.stopped += 1
        self.warmlink_capture = None

    def connect_to_device(self):
        raise AssertionError("already connected")


def qt_app():
    return QApplication.instance() or QApplication([])


def test_capture_start_keeps_dialog_open_and_uses_existing_settings_key():
    qt_app()
    main = FakeMainWindow()
    dialog = app.WarmlinkCaptureDialog(main)
    dialog.show()
    dialog.start_capture()

    assert dialog.isVisible()
    assert main.started == 1
    assert main.settings["warmlink_raw_capture"]["enabled"] is True
    assert main.guard is True


def test_closing_dialog_does_not_stop_capture():
    qt_app()
    main = FakeMainWindow()
    main.warmlink_capture = FakeCapture()
    dialog = app.WarmlinkCaptureDialog(main)

    dialog.close()

    assert main.stopped == 0
    assert main.warmlink_capture.get_status().active is True


def test_live_status_and_main_button_follow_actual_capture_status():
    qt_app()
    main = FakeMainWindow()
    main.warmlink_capture = FakeCapture(active=True, tx_size=0)
    dialog = app.WarmlinkCaptureDialog(main)
    dialog.refresh_status()

    assert "FIRMWARE-CAPTURE AKTIV" in dialog.status_labels["capture"].text()
    assert "TX-SPERRE AKTIV" in dialog.status_labels["tx_guard"].text()
    assert dialog.status_labels["tx"].text().endswith("✓")

    main.warmlink_capture_btn = QPushButton()
    app.MainWindow._update_warmlink_capture_button(main)
    assert main.warmlink_capture_btn.text() == "● Firmware-Capture AKTIV"
    main.warmlink_capture.status.active = False
    app.MainWindow._update_warmlink_capture_button(main)
    assert main.warmlink_capture_btn.text() == "Langzeit-Capture ..."
