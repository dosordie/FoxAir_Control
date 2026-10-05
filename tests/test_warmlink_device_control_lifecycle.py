import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

qt_widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
QApplication = qt_widgets.QApplication
QMainWindow = qt_widgets.QMainWindow

from dialogs import cloud_dialog as cloud_dialog_module
from dialogs.cloud_dialog import WarmLinkCloudDialog


class MainWindowStub(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = {
            "warmlink_cloud": {
                "username": "user@example.test",
                "save_token": False,
                "known_device_codes": ["B"],
                "selected_device_code": "A",
            },
        }
        self.cloud_session_authenticated = False
        self.latest_regs = {}
        self.regmap = {}
        self.user_data_dir = "."

    def _save_settings(self, **kwargs):
        pass

    def _log(self, text):
        pass

    def set_cloud_connection_state(self, *args):
        pass


class FakeSignal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)


class FakeThread:
    def __init__(self, parent=None):
        self.started = FakeSignal()
        self.finished = FakeSignal()
        self.started_called = False

    def start(self):
        self.started_called = True

    def quit(self):
        pass

    def deleteLater(self):
        pass


class FakeWorker:
    created = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.log = FakeSignal()
        self.status = FakeSignal()
        self.devices = FakeSignal()
        self.data = FakeSignal()
        self.error = FakeSignal()
        self.login_method = FakeSignal()
        self.token_updated = FakeSignal()
        self.finished = FakeSignal()
        self.progress = FakeSignal()
        self.session_updated = FakeSignal()
        self.credentials_loaded = FakeSignal()
        self.connection_state = FakeSignal()
        self.timing_updated = FakeSignal()
        self.__class__.created.append(self)

    def moveToThread(self, thread):
        pass

    def run(self):
        pass

    def stop(self):
        pass

    def deleteLater(self):
        pass


def make_dialog():
    application = QApplication.instance() or QApplication([])
    main = MainWindowStub()
    dialog = WarmLinkCloudDialog(main)
    dialog._test_application = application
    dialog._test_main_window = main
    dialog._password = lambda: "password"
    return dialog


def test_worker_lifecycle_locks_selection_and_discovery_and_restores_them(monkeypatch):
    dialog = make_dialog()
    dialog._on_devices([{"deviceCode": "A"}, {"deviceCode": "B"}])
    dialog.device_combo.setCurrentIndex(dialog.device_combo.findData("B"))
    monkeypatch.setattr(cloud_dialog_module, "QThread", FakeThread)
    monkeypatch.setattr(cloud_dialog_module, "WarmLinkCloudWorker", FakeWorker)
    dialog._start_worker(poll_once=False)
    assert not dialog.device_combo.isEnabled() and not dialog.rediscover_btn.isEnabled()
    assert not dialog.username_edit.isEnabled()
    assert FakeWorker.created[-1].kwargs["device_code"] == "B"
    assert "known_device_codes" not in FakeWorker.created[-1].kwargs
    dialog._worker_finished()
    assert dialog.device_combo.isEnabled() and dialog.rediscover_btn.isEnabled()
    assert dialog.username_edit.isEnabled()


def test_legacy_manual_settings_are_tolerated_but_not_used_as_devices():
    dialog = make_dialog()
    assert dialog.devices == [] and dialog.device_combo.count() == 0
    assert dialog._cloud_settings()["known_device_codes"] == ["B"]
    for attribute in ("add_device_btn", "remove_device_btn", "known_device_table", "add_known_device"):
        assert not hasattr(dialog, attribute)


def test_device_can_change_after_stop_and_next_worker_uses_cached_new_code(monkeypatch):
    dialog = make_dialog()
    dialog._on_devices([{"deviceCode": "A"}, {"deviceCode": "B"}])
    dialog.cloud_thread = FakeThread()
    dialog._worker_finished()
    dialog.device_combo.setCurrentIndex(dialog.device_combo.findData("B"))
    monkeypatch.setattr(cloud_dialog_module, "QThread", FakeThread)
    monkeypatch.setattr(cloud_dialog_module, "WarmLinkCloudWorker", FakeWorker)
    dialog._start_worker(poll_once=True)
    kwargs = FakeWorker.created[-1].kwargs
    assert kwargs["device_code"] == "B"
    assert kwargs["session"].reusable("user@example.test", "B", None)


def test_discovery_replaces_persistent_cache_and_removes_missing_devices():
    dialog = make_dialog()
    dialog._on_devices([{"deviceCode": "A", "extra": 1}, {"deviceCode": "B"}])
    dialog.device_combo.setCurrentIndex(dialog.device_combo.findData("B"))
    dialog._on_devices([{"deviceCode": "C", "extra": 2}])
    cfg = dialog._cloud_settings()
    assert cfg["cached_devices_username"] == "user@example.test"
    assert cfg["cached_devices"] == [{"deviceCode": "C", "extra": 2, "discoverySource": "deviceList"}]
    assert cfg["selected_device_code"] == "C"
    assert dialog.device_combo.count() == 1
