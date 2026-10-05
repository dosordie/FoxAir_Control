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


def test_worker_lifecycle_locks_device_controls_and_restores_manual_remove(monkeypatch):
    dialog = make_dialog()
    dialog.devices = [
        {"deviceCode": "A", "discoverySource": "deviceList"},
        {"deviceCode": "B", "discoverySource": "manual"},
    ]
    dialog.refresh_devices()
    dialog.device_combo.setCurrentIndex(dialog.device_combo.findData("B"))
    monkeypatch.setattr(cloud_dialog_module, "QThread", FakeThread)
    monkeypatch.setattr(cloud_dialog_module, "WarmLinkCloudWorker", FakeWorker)

    dialog._start_worker(poll_once=False)

    assert not dialog.device_combo.isEnabled()
    assert not dialog.add_device_btn.isEnabled()
    assert not dialog.remove_device_btn.isEnabled()
    assert FakeWorker.created[-1].kwargs["device_code"] == "B"

    dialog._worker_finished()

    assert dialog.device_combo.isEnabled()
    assert dialog.add_device_btn.isEnabled()
    assert dialog.remove_device_btn.isEnabled()


def test_automatic_device_remove_stays_disabled_after_worker_end():
    dialog = make_dialog()
    dialog.devices = [
        {"deviceCode": "A", "discoverySource": "deviceList"},
        {"deviceCode": "B", "discoverySource": "manual"},
    ]
    dialog.refresh_devices()
    dialog.device_combo.setCurrentIndex(dialog.device_combo.findData("A"))
    dialog.cloud_thread = FakeThread()

    dialog._worker_finished()

    assert dialog.device_combo.isEnabled()
    assert dialog.add_device_btn.isEnabled()
    assert not dialog.remove_device_btn.isEnabled()


def test_add_and_remove_guards_do_nothing_while_worker_runs(monkeypatch):
    dialog = make_dialog()
    dialog.devices = [{"deviceCode": "B", "discoverySource": "manual"}]
    dialog.refresh_devices()
    before_settings = dict(dialog._cloud_settings())
    before_devices = list(dialog.devices)
    dialog.cloud_thread = FakeThread()
    monkeypatch.setattr(
        cloud_dialog_module.QInputDialog, "getText",
        lambda *args: (_ for _ in ()).throw(AssertionError("input dialog must not open")),
    )

    dialog.add_known_device()
    dialog.remove_selected_known_device()

    assert dialog._cloud_settings() == before_settings
    assert dialog.devices == before_devices


def test_device_can_change_after_stop_and_next_worker_uses_new_code(monkeypatch):
    dialog = make_dialog()
    dialog.devices = [
        {"deviceCode": "A", "discoverySource": "deviceList"},
        {"deviceCode": "B", "discoverySource": "manual"},
    ]
    dialog.refresh_devices()
    dialog.cloud_thread = FakeThread()
    dialog._worker_finished()
    dialog.device_combo.setCurrentIndex(dialog.device_combo.findData("B"))
    monkeypatch.setattr(cloud_dialog_module, "QThread", FakeThread)
    monkeypatch.setattr(cloud_dialog_module, "WarmLinkCloudWorker", FakeWorker)

    dialog._start_worker(poll_once=True)

    assert FakeWorker.created[-1].kwargs["device_code"] == "B"


def test_validating_second_manual_device_preserves_first_and_updates_list():
    dialog = make_dialog()
    dialog._known_device_validated("C", [{"supported": True, "value": 1}])
    assert dialog._cloud_settings()["known_device_codes"] == ["B", "C"]
    assert [dialog.known_device_table.item(row, 0).text() for row in range(2)] == ["B", "C"]

    dialog._known_device_validated("D", [{"supported": True, "value": 1}])
    assert dialog._cloud_settings()["known_device_codes"] == ["B", "C", "D"]
    assert [dialog.known_device_table.item(row, 0).text() for row in range(3)] == ["B", "C", "D"]
