import pytest
from PySide6.QtWidgets import QMessageBox

from cloud.polling import CloudSession
from dialogs.cloud_dialog import WarmLinkCloudDialog
from test_cloud_polling import DialogWindow
from test_cloud_single_read_and_values import application


def device_dialog():
    owner = DialogWindow()
    dialog = WarmLinkCloudDialog(owner)
    dialog.devices = [{"deviceCode": "A", "deviceNickName": "First"},
                      {"deviceCode": "B", "deviceNickName": "Second"}]
    dialog._devices_username = "user"
    dialog.session = CloudSession(username="user", device_code="A", devices=list(dialog.devices), devices_cached=True)
    dialog.refresh_devices()
    dialog._device_selection_changed()
    owner.set_cloud_connection_state(True, "A")
    return owner, dialog


@pytest.mark.parametrize("answer", [QMessageBox.Yes, QMessageBox.No])
def test_device_double_click_selects_first_and_reuses_polling_start(application, monkeypatch, answer):
    owner, dialog = device_dialog()
    starts, prompts = [], []
    def question(*args):
        prompts.append(args)
        assert dialog._selected_device_code() == "B"
        assert dialog.session.device_code == "B"
        assert owner.cloud_session_device_code == "B"
        assert owner.settings["warmlink_cloud"]["selected_device_code"] == "B"
        return answer
    monkeypatch.setattr(QMessageBox, "question", question)
    monkeypatch.setattr(dialog, "_start_worker", lambda **kwargs: starts.append(kwargs))
    dialog.device_table.cellDoubleClicked.emit(1, 0)
    assert len(prompts) == 1
    assert starts == ([{"poll_once": False, "just_login": False}] if answer == QMessageBox.Yes else [])
    assert dialog._selected_device_code() == "B"
    dialog.close()
    owner.deleteLater()


def test_device_table_and_combo_cannot_change_polling_session(application, monkeypatch):
    owner, dialog = device_dialog()
    dialog.cloud_thread = object()
    monkeypatch.setattr(QMessageBox, "question", lambda *a: pytest.fail("No duplicate polling prompt"))
    monkeypatch.setattr(dialog, "_start_worker", lambda **kw: pytest.fail("No second worker"))
    dialog.device_table.selectRow(1)
    assert dialog._selected_device_code() == "A" and dialog.device_table.currentRow() == 0
    dialog.device_table.cellDoubleClicked.emit(1, 0)
    dialog.device_table.cellDoubleClicked.emit(0, 0)
    dialog.device_combo.setCurrentIndex(dialog.device_combo.findData("B"))
    assert dialog._selected_device_code() == "A"
    assert dialog.session.device_code == owner.cloud_session_device_code == "A"
    assert owner.settings["warmlink_cloud"]["selected_device_code"] == "A"
    dialog.cloud_thread = None
    dialog.close()
    owner.deleteLater()


def test_double_click_rechecks_selection_after_confirmation(application, monkeypatch):
    owner, dialog = device_dialog()
    monkeypatch.setattr(dialog, "_start_worker", lambda **kw: pytest.fail("Selection changed during prompt"))
    def question(*args):
        dialog.device_combo.setCurrentIndex(dialog.device_combo.findData("A"))
        return QMessageBox.Yes
    monkeypatch.setattr(QMessageBox, "question", question)
    dialog.device_table.cellDoubleClicked.emit(1, 0)
    assert dialog._selected_device_code() == "A"
    dialog.close()
    owner.deleteLater()
