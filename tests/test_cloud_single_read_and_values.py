import os
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication, QMainWindow, QTableWidget

import foxair_phnix_control as gui
from cloud import warmlink_api
from cloud.cloud_write_helpers import cloud_write_value_from_user_input
from cloud.register_resolver import current_register_definitions
from cloud.warmlink_codes import cloud_modbus_register
from core.foxair_phnix_core import DecodedRegister, RegisterMap
from workers import warmlink_cloud_worker as workers


@pytest.fixture(scope="module")
def application():
    return QApplication.instance() or QApplication([])


class CloudWindow(gui.MainWindow):
    """Exercise real table, overlay, scaling and dialog methods without startup I/O."""

    def __init__(self):
        QMainWindow.__init__(self)
        self.register_defs = current_register_definitions()
        self.regmap = RegisterMap(str(Path(__file__).parents[1] / "data/foxair_phnix_registers.json"))
        self.latest_regs = {}
        self.last_values = {}
        self.previous_value_texts = {}
        self.table_rows = {}
        self.cloud_overlay_by_reg = {}
        self.cloud_last_rows = []
        self.register_table = QTableWidget(0, 14, self)
        self.register_write_dialogs = {}
        self.contact_dialog = self.load_output_dialog = None
        self.warmlink_cloud_dialog = None
        self.cloud_read_thread = self.cloud_read_worker = None
        self.cloud_read_reg_no = None
        self.cloud_session_authenticated = True
        self.cloud_session_device_code = "selected-device"
        self.settings = {"warmlink_cloud": {"save_token": False}}
        self.logs = []

    def _cloud_write_credentials(self):
        return "user", "password", "session-token", "different-saved-device"

    def _log(self, text, **kwargs): self.logs.append(text)
    def _display_parts_for_register(self, reg_no, name):
        from cloud.mapping_validation import register_code_from_definition
        return "", register_code_from_definition(self.register_defs.get(str(reg_no), {})), name
    def _apply_register_row_visual_state(self, *args, **kwargs): pass
    def _apply_cloud_only_visibility_for_reg(self, *args): pass
    def _apply_cloud_only_visibility(self): pass
    def _resize_name_column(self): pass
    def _update_fault_decoder(self): pass
    def current_device_model(self): return ""


def cloud_row(value, code="R02", **metadata):
    return {"code": code, "value": value, "supported": True,
            "lastFetch": str(value), **metadata}


def open_dialog(window, register):
    dialog = gui.RegisterQuickWriteDialog(window, register)
    window.register_write_dialogs[(0x63, register)] = dialog
    return dialog


def test_r02_prefill_and_both_write_representations(application):
    register = cloud_modbus_register("R02")
    local = CloudWindow()
    local.latest_regs[register] = DecodedRegister(0x63, register, 0, 0x03, 550, 550, "55 °C", "R02", "TEMP1", time.time())
    assert open_dialog(local, register).write_value_edit.text() == "55"
    cloud = CloudWindow()
    cloud.apply_cloud_rows_to_main([cloud_row(55)])
    dialog = open_dialog(cloud, register)
    assert dialog.write_value_edit.text() == "55"
    assert dialog.cloud_value_label.text() == "55 °C"
    assert dialog.current_raw_label.text() == "--"
    assert cloud.latest_regs[register].cloud_value == 55
    assert cloud.latest_regs[register].local_raw_value is None
    assert local.latest_regs[register].local_raw_value == 550
    assert register not in cloud.last_values
    assert local.parse_register_write_value(register, "52") == 520
    assert cloud_write_value_from_user_input("R02", "52", cloud.regmap.get(register),
        lambda text: cloud.parse_register_write_value(register, text)) == "52"


@pytest.mark.parametrize("dtype,value", [
    ("TEMP1", 55), ("TEMP05", 12.5), ("BAR_X10", 2.3),
    ("FLOW_M3H_X10", 3.7), ("FLOW_M3H_X100", 0.36),
    ("POWER_KW_X10", 7.8), ("AMP_X10", 3.4), ("AMP_X2", 4.5),
    ("DIGI5", 6.7), ("DIGI6", 6.7),
])
def test_cloud_prefill_never_uses_local_scaling(application, dtype, value):
    window = CloudWindow()
    register = cloud_modbus_register("R02")
    window.regmap.get(register).dtype = dtype
    window.apply_cloud_rows_to_main([cloud_row(value)])
    assert float(open_dialog(window, register).write_value_edit.text()) == value


def test_existing_cloud_row_updates_without_duplicate_and_preserves_edits(application):
    window = CloudWindow()
    register = cloud_modbus_register("R02")
    window.apply_cloud_rows_to_main([cloud_row(55), cloud_row(70, "F23")])
    dialog = open_dialog(window, register)
    row = window.table_rows[register]
    old_timestamp = window.latest_regs[register].timestamp
    window.apply_cloud_rows_to_main([cloud_row(52)])
    assert window.table_rows[register] == row
    assert window.register_table.rowCount() == 2
    assert window.register_table.item(row, 7).text() == "52 °C"
    assert window.register_table.item(row, 11).text() == "52 °C"
    assert window.register_table.item(row, 13).text() == "52"
    assert window.latest_regs[register].timestamp >= old_timestamp
    assert window.latest_regs[register].cloud_value == 52
    assert window.latest_regs[register].raw_value == 52
    assert dialog.write_value_edit.text() == "52"
    assert len(window.cloud_last_rows) == 2  # single reads preserve other cached rows
    dialog.write_value_edit.setText("49")
    dialog.write_value_edit.setModified(True)
    window.apply_cloud_rows_to_main([cloud_row(50)])
    assert dialog.write_value_edit.text() == "49"


def test_local_raw_is_preserved_when_cloud_overlay_arrives(application):
    window = CloudWindow()
    register = cloud_modbus_register("R02")
    local = DecodedRegister(0x63, register, 0, 0x03, 550, 550, "55 °C", "R02", "TEMP1", time.time())
    window._upsert_register_row(local, changed=False)
    window.last_values[register] = 550
    dialog = open_dialog(window, register)
    window.apply_cloud_rows_to_main([cloud_row(52)])
    assert window.latest_regs[register] is local
    assert window.last_values[register] == 550
    assert dialog.write_value_edit.text() == "55"
    assert dialog.cloud_value_label.text() == "52 °C"
    assert window.register_table.item(window.table_rows[register], 11).text() == "52 °C"


def forbid_discovery(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Single read must not discover devices or fetch status/faults")
    for name in ("get_devices", "get_houses", "get_house_devices", "get_device_status", "get_fault_data_by_device_code"):
        monkeypatch.setattr(warmlink_api.WarmLinkCloudApi, name, forbidden)
    monkeypatch.setattr(workers, "discover_cloud_devices", forbidden)


@pytest.mark.parametrize("mode", ["success", "expired", "error", "empty"])
def test_main_single_read_session_result_and_cleanup(application, monkeypatch, mode):
    forbid_discovery(monkeypatch)
    requests = []
    logins = []

    def login(api, *args):
        logins.append(True)
        api.token = "renewed-token"
        api.last_login_method = "md5"
        return True

    def request(api, endpoint, payload=None, **kwargs):
        requests.append((endpoint, payload, kwargs.get("token")))
        assert endpoint == warmlink_api.ENDPOINT_GET_DATA_BY_CODE
        assert payload == {"deviceCode": "selected-device", "protocalCodes": ["R02"]}
        if mode == "expired" and len(requests) == 1:
            return {"error_code": "-100", "error_msg": "Please login again"}
        if mode == "error":
            raise RuntimeError("transport failed")
        return {"isResultSuc": True, "objectResult": [] if mode == "empty" else [cloud_row(55)]}

    monkeypatch.setattr(warmlink_api.WarmLinkCloudApi, "_request_json", request)
    monkeypatch.setattr(warmlink_api.WarmLinkCloudApi, "login", login)
    window = CloudWindow()
    register = cloud_modbus_register("R02")
    dialog = open_dialog(window, register)
    gui_thread = application.thread()
    callback_threads = []
    completion_errors = []
    completed = dialog.cloud_read_completed
    def record_completion(**kwargs):
        from PySide6.QtCore import QThread
        callback_threads.append(QThread.currentThread())
        completion_errors.append(kwargs.get("error", ""))
        completed(**kwargs)
    dialog.cloud_read_completed = record_completion
    dialog.read_cloud_register()
    thread = window.cloud_read_thread
    assert thread is not None
    assert not dialog.cloud_read_btn.isEnabled()
    assert window.read_cloud_register(register)  # a second request is rejected
    loop = QEventLoop()
    thread.finished.connect(loop.quit)
    QTimer.singleShot(3000, loop.quit)
    loop.exec()
    application.processEvents()
    assert window.cloud_read_thread is None and window.cloud_read_worker is None
    assert not dialog._cloud_read_pending
    assert dialog.cloud_read_btn.isEnabled()
    assert callback_threads and all(t == gui_thread for t in callback_threads)
    assert bool(completion_errors[0]) == (mode in ("error", "empty"))
    assert len(requests) == (2 if mode == "expired" else 1)
    assert len(logins) == (1 if mode == "expired" else 0)
    assert requests[0][2] == "session-token"
    if mode in ("success", "expired"):
        assert dialog.write_value_edit.text() == "55"
        assert window.cloud_overlay_by_reg[register]["engineering_value"] == 55
        assert dialog.cloud_value_label.text() in dialog.status_label.text()
    else:
        assert register not in window.cloud_overlay_by_reg
        assert dialog.status_label.text()  # error result, independent of exact wording


def test_missing_selected_device_finishes_without_api_call(application, monkeypatch):
    forbid_discovery(monkeypatch)
    monkeypatch.setattr(warmlink_api.WarmLinkCloudApi, "get_data_by_code",
                        lambda *args: pytest.fail("No API call without a selected device"))
    worker = workers.WarmLinkCloudReadWorker("user", "password", "", ["R02"], "token")
    errors, finished = [], []
    worker.error.connect(errors.append)
    worker.finished.connect(lambda: finished.append(True))
    worker.run()
    assert errors and len(finished) == 1
    window = CloudWindow()
    window.cloud_session_device_code = ""
    dialog = open_dialog(window, cloud_modbus_register("R02"))
    dialog.read_cloud_register()
    assert not dialog._cloud_read_pending
    assert window.cloud_read_thread is None


def test_cloud_confirmation_uses_engineering_unit(application, monkeypatch):
    window = CloudWindow()
    register = cloud_modbus_register("R02")
    window.apply_cloud_rows_to_main([cloud_row(55)])
    confirmations, sent = [], []
    monkeypatch.setattr(gui, "ask_yes_no", lambda _parent, _title, text, **kwargs: confirmations.append(text) or True)
    window.send_cloud_write = lambda code, value, **kwargs: sent.append((code, value))
    window.open_cloud_write_for_register(register, "52")
    assert "52 °C" in confirmations[0]
    assert sent == [("R02", "52")]


def test_active_session_token_is_used_without_persistent_token_storage(application, monkeypatch):
    from types import SimpleNamespace

    window = CloudWindow()
    window.settings["warmlink_cloud"].update(username="user")
    window.warmlink_cloud_dialog = SimpleNamespace(
        username_edit=SimpleNamespace(text=lambda: "user"),
        save_token_cb=SimpleNamespace(isChecked=lambda: False),
        _cloud_token_username="user", _cloud_token="live-token",
        _selected_device_code=lambda: "selected-device",
        _password=lambda: "password",
    )
    monkeypatch.setattr(gui, "get_token", lambda *args: pytest.fail("No saved token needed"))
    credentials = gui.MainWindow._cloud_write_credentials(window)
    assert credentials == ("user", "password", "live-token", "selected-device")


@pytest.mark.parametrize("code,unit", [("F23", "rpm"), ("P10", "%"), ("P08", "W"), ("P16", "bar"), ("D22", "m³/h")])
def test_cloud_write_confirmation_uses_shared_unit(application, monkeypatch, code, unit):
    window = CloudWindow()
    confirmations = []
    monkeypatch.setattr(gui, "ask_yes_no", lambda _parent, _title, text, **kwargs: confirmations.append(text) or False)
    window.open_cloud_write_for_register(cloud_modbus_register(code), "52")
    assert f"52 {unit}" in confirmations[0]


def test_read_overlay_and_compare_use_live_unit(application):
    from dialogs.cloud_table_helpers import compare_table_values, local_display_value

    window = CloudWindow()
    row = cloud_row(58, "P10", unit="rpm", dataType="TEMP")
    window.apply_cloud_rows_to_main([row])
    register = cloud_modbus_register("P10")
    assert window.cloud_overlay_by_reg[register]["value"] == "58 rpm"
    assert local_display_value(window.latest_regs, register) == ("", None)
    values, _status = compare_table_values(row, register,
        latest_regs=window.latest_regs, regmap=window.regmap,
        display_parts_for_register=window._display_parts_for_register,
        cloud_display_text=window._cloud_display_text)
    assert values[5] == "58 rpm" and values[7] == "rpm"


def test_cloud_fault_word_remains_an_unscaled_bit_word(application):
    window = CloudWindow()
    window.apply_cloud_rows_to_main([cloud_row("0000001000000000", "Fault8", dataType="BINARY", dataTypeAi="binary")])
    register = 2082
    assert window.latest_regs[register].raw_value == 0x0200
    assert window.cloud_overlay_by_reg[register]["raw"] == 0x0200
    assert "512" in window.register_table.item(window.table_rows[register], 4).text()
