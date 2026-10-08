"""Control routing, value semantics and identity guards through existing I/O."""

import time
import threading
from types import SimpleNamespace

import pytest

import foxair_phnix_control as gui
from cloud.warmlink_api import WarmLinkCloudApi
from cloud.warmlink_codes import cloud_hint
from core.control_transport import ControlContext, register_control_capability, select_control_transport
from core.foxair_phnix_core import DecodedRegister
from workers import warmlink_cloud_worker as workers
from test_cloud_at_curve_and_csv_cleanup import cloud_only, open_at
from test_cloud_single_read_and_values import application, cloud_row
from test_csv_logger_transport import wait_for
from test_warmlink_request_scheduler import window


@pytest.mark.parametrize("backend", ["standard_modbus", "warmlink_raw", "display_modbus"])
@pytest.mark.parametrize("local,cloud", [(False, False), (True, False), (False, True), (True, True)])
def test_transport_priority(backend, local, cloud):
    assert select_control_transport(local, backend, cloud) == (backend if local else "cloud" if cloud else "none")


def test_unknown_or_unavailable_local_path_never_falls_back_to_cloud():
    assert select_control_transport(True, "unsupported", True) == "none"
    capability = register_control_capability(ControlContext("display_modbus"), (1158,),
                                             lambda *a, **kw: pytest.fail("No Cloud lookup for local path"), write=True)
    assert not capability


def open_wp(window):
    window.open_wp_control()
    window.wp_control_dialog.initial_read_timer.stop()
    return window.wp_control_dialog


@pytest.mark.parametrize("backend", ["standard_modbus", "warmlink_raw", "display_modbus"])
def test_connected_local_path_wins_for_reads_and_writes(window, monkeypatch, backend):
    window.backend_combo.blockSignals(True)
    window.backend_combo.setCurrentIndex(window.backend_combo.findData(backend))
    window.backend_combo.blockSignals(False)
    window.settings["warmlink_cloud"]["username"] = "user"
    window.set_cloud_connection_state(True, "device")
    reads, writes = [], []
    monkeypatch.setattr(window, "send_read_request", lambda *a, **kw: reads.append(a))
    monkeypatch.setattr(window, "send_register_write", lambda *a, **kw: writes.append(a))
    monkeypatch.setattr(window, "request_cloud_snapshot", lambda *a: pytest.fail("No Cloud read while local"))
    monkeypatch.setattr(window, "send_cloud_write", lambda *a, **kw: pytest.fail("No Cloud write while local"))
    monkeypatch.setattr(window, "_display_wait_for_param_blocks_before_popup", lambda *a, **kw: True)
    monkeypatch.setattr(gui, "ask_yes_no", lambda *a, **kw: True)
    wp, at = open_wp(window), open_at(window)
    wp.read_from_wp(); at.read_from_wp()
    assert len(reads) == len(wp.READ_BLOCKS) + len(gui.AT_READ_BLOCKS)
    wp.target_spin.setValue(42)
    wp.write_target(); at.write_mode()
    assert writes[0][0:2] == (1157, 420)  # Default mode is WW.
    assert writes[1][0] == 1236
    wp.close(); at.close()


def test_missing_local_worker_does_not_fall_back_to_valid_cloud(window, monkeypatch):
    window.settings["warmlink_cloud"]["username"] = "user"
    window.set_cloud_connection_state(True, "device")
    monkeypatch.setattr(window, "_active_io_worker", lambda: None)
    monkeypatch.setattr(window, "send_cloud_write", lambda *a, **kw: pytest.fail("No fallback"))
    assert window.control_transport() == "warmlink_raw"
    assert window.control_write_register(1158, 420, 42)
    assert window.control_read_blocks(((1158, 1),), "read")


def test_unsupported_local_action_reports_error_without_cloud_fallback(window, monkeypatch):
    window.set_cloud_connection_state(True, "device")
    monkeypatch.setattr(window, "send_cloud_write", lambda *a, **kw: pytest.fail("No Cloud fallback"))
    def unsupported(*args, **kwargs):
        raise ValueError("Local action unavailable")
    monkeypatch.setattr(window, "send_register_write", unsupported)
    assert window.control_write_register(1158, 420, 42) == "Local action unavailable"


def test_wp_targeted_read_has_no_backlog_and_routes_live_values(window, monkeypatch):
    cloud_only(window)
    requests = []
    monkeypatch.setattr(window, "request_cloud_snapshot", lambda request: requests.append(request))
    wp = open_wp(window)
    wp.read_from_wp(); wp.read_from_wp(); wp._toggle_auto_refresh(True)
    assert len(requests) == 1
    request = requests[0]
    assert request.purpose == "wp_control"
    assert set(request.codes) == {"Power", "Mode", "ModeState", "R01", "R02", "R03", "H36", "2014", "T01", "T02", "T08", "T04", "T39"}
    wp.cloud_read_finished(request.cycle_id, [cloud_row(1, "Power"), cloud_row(1, "Mode"),
        cloud_row(42, "R02"), cloud_row(50, "R01"), cloud_row(40, "2014"), cloud_row(10, "T04")], "")
    assert wp.target_spin.value() == 42 and wp.ww_target_spin.value() == 50
    assert wp._value(2014) == 40
    assert wp._value(2011) is None and wp._value(2013) is None
    assert "Cloud Power" in wp.power_state_caption.text()
    assert wp.temp_labels[2013].text() == "--"
    assert 2011 not in window.table_rows and 2013 not in window.table_rows
    window.apply_cloud_rows_to_main([cloud_row(48, "R01"), cloud_row(41, "2014")])
    assert wp.ww_target_spin.value() == 48 and wp._value(2014) == 41
    local = DecodedRegister(0x63, 2014, 0, 3, 430, 430, "43 °C", "target", "TEMP1", time.time())
    window.latest_regs[2014] = local
    window.apply_cloud_rows_to_main([cloud_row(39, "2014")])
    assert wp._value(2014) == 39
    assert window.latest_regs[2014] is local
    local_target = DecodedRegister(0x63, 1158, 0, 3, 430, 430, "43 °C", "R02", "TEMP1", time.time())
    window.latest_regs[1158] = local_target
    window.apply_cloud_rows_to_main([cloud_row(39, "R02")])
    assert wp.target_spin.value() == 39
    assert window.latest_regs[1158] is local_target
    wp.close()


@pytest.mark.parametrize("backend", ["standard_modbus", "warmlink_raw", "display_modbus"])
@pytest.mark.parametrize("cache", ["latest_regs", "last_values"])
@pytest.mark.parametrize("dialog_kind", ["wp", "at"])
def test_dialog_values_follow_disconnect_and_reconnect_with_local_cache_retained(window, backend, cache, dialog_kind):
    worker = window.worker
    cloud_only(window)
    window.worker = worker
    window.backend_combo.blockSignals(True)
    window.backend_combo.setCurrentIndex(window.backend_combo.findData(backend))
    window.backend_combo.blockSignals(False)
    register, code = (1158, "R02") if dialog_kind == "wp" else (1250, "CP1-1")
    window.apply_cloud_rows_to_main([cloud_row(1, "Mode"), cloud_row(2, "H36"), cloud_row(40, code)])
    local = DecodedRegister(0x63, register, 0, 3, 350, 350, "35 °C", code, "TEMP1", time.time())
    if cache == "latest_regs":
        window.latest_regs[register] = local
    else:
        # Exercise the raw-cache fallback without a decoded register carrier.
        window.latest_regs.pop(register)
    window.last_values[register] = 350
    window.on_connected()
    dialog = open_wp(window) if dialog_kind == "wp" else open_at(window)
    spin = dialog.target_spin if dialog_kind == "wp" else dialog._seven_spins()[0]

    def assert_display(expected, cloud=False):
        assert spin.value() == expected
        value = dialog._value(register) if dialog_kind == "wp" else dialog._temp(register)
        assert value == expected
        if dialog_kind == "wp":
            display = (window.cloud_overlay_by_reg[register]["value"] if cloud else
                       gui.format_value_by_type(int(expected * 10), "TEMP1"))
            assert dialog._fmt(register) == display

    assert window.control_transport() == backend
    assert_display(35)

    window.on_disconnected()
    assert window.control_transport() == "cloud"
    assert window.register_value_sources(register).local_raw == 350
    assert window.last_values[register] == 350
    if cache == "latest_regs":
        assert window.latest_regs[register] is local
    assert_display(40, cloud=True)

    window.last_values[register] = 360
    if cache == "latest_regs":
        local.raw_value = local.signed_value = 360
        local.display_value = "36 °C"
    window.on_connected()
    assert window.control_transport() == backend
    assert_display(36)
    dialog.close()


@pytest.mark.parametrize("register,code,value", [(1011, "Power", 1), (1012, "Mode", 2),
    (1157, "R01", 42.0), (1158, "R02", 42.0), (1159, "R03", 42.0)])
def test_cloud_control_values_are_engineering_not_scaled_words(window, monkeypatch, register, code, value):
    cloud_only(window)
    writes = []
    monkeypatch.setattr(window, "send_cloud_write", lambda c, v, **kw: writes.append((c, v, kw)))
    raw = int(value * 10) if register in (1157, 1158, 1159) else value
    assert window.control_write_register(register, raw, value) is None
    assert writes[0][:2] == (code, str(value))
    assert writes[0][2]["device_code"] == "device"
    assert writes[0][2]["control_context"] == window.control_context()
    assert str(raw) != writes[0][1] if raw != value else True


def test_wp_buttons_use_dispatcher_and_one_confirmation(window, monkeypatch):
    cloud_only(window)
    writes, confirms = [], []
    monkeypatch.setattr(window, "send_cloud_write", lambda code, value, **kw: writes.append((code, value)))
    monkeypatch.setattr(gui, "ask_yes_no", lambda *a, **kw: confirms.append(a[2]) or True)
    wp = open_wp(window)
    wp.power_combo.setCurrentIndex(1); wp.write_power()
    wp.mode_combo.setCurrentIndex(wp.mode_combo.findData(1)); wp.write_mode()
    wp.target_spin.setValue(42); wp.write_target()
    wp.ww_target_spin.setValue(43); wp.write_ww_target()
    assert writes == [("Power", "1"), ("Mode", "1"), ("R02", "42.0"), ("R01", "43.0")]
    assert len(confirms) == 4 and all("WarmLink Cloud" in text for text in confirms)
    assert not wp.silent_write_btn.isEnabled()
    wp.write_silent()
    assert len(writes) == 4 and len(confirms) == 4
    wp.close()


def test_confirmation_is_bound_to_transport_and_selected_device(window, monkeypatch):
    cloud_only(window)
    wp = open_wp(window)
    monkeypatch.setattr(window, "send_cloud_write", lambda *a, **kw: pytest.fail("No write to changed device"))
    def confirm(*args, **kwargs):
        window.set_cloud_connection_state(True, "different-device")
        return True
    monkeypatch.setattr(gui, "ask_yes_no", confirm)
    wp.write_power()
    assert not wp.cloud_request
    wp.close()


@pytest.mark.parametrize("loss", ["device", "account", "local", "disconnect", "close"])
def test_wp_pending_read_is_cancelled_and_old_values_are_not_accepted(window, monkeypatch, loss):
    cloud_only(window)
    requests = []
    monkeypatch.setattr(window, "request_cloud_snapshot", lambda request: requests.append(request))
    wp = open_wp(window)
    wp.read_from_wp()
    request = requests[0]
    if loss == "device":
        window.set_cloud_connection_state(True, "other-device")
    elif loss == "account":
        window.settings["warmlink_cloud"]["username"] = "other-user"
        wp.connection_changed()
    elif loss == "local":
        window.connected = True
        wp.connection_changed()
    elif loss == "disconnect":
        window.set_cloud_connection_state(False)
    else:
        wp.close()
    assert request.cancelled.is_set()
    wp.cloud_read_finished(request.cycle_id, [cloud_row(50, "R02")], "")
    assert 1158 not in window.cloud_overlay_by_reg
    wp.close()


def test_at_cloud_writes_h36_but_rejects_partial_curve_actions(window, monkeypatch):
    cloud_only(window)
    writes = []
    monkeypatch.setattr(window, "send_cloud_write", lambda c, v, **kw: writes.append((c, v)))
    monkeypatch.setattr(gui, "ask_yes_no", lambda *a, **kw: True)
    at = open_at(window)
    at.mode_combo.setCurrentIndex(at.mode_combo.findData(2))
    assert at.write_mode_btn.isEnabled()
    at.write_mode()
    assert writes == [("H36", "2")]
    for code in ("CP1-1", "CP1-2", "CP1-3", "compensate_offset"):
        monkeypatch.setitem(cloud_hint(code), "write_allowed", True)
    at._update_write_actions()
    assert not at.write_seven_btn.isEnabled()
    at.write_seven_points()
    assert writes == [("H36", "2")]
    at.mode_combo.setCurrentIndex(at.mode_combo.findData(1))
    assert not at.write_linear_btn.isEnabled()
    at.write_linear_params()
    assert len(writes) == 1
    monkeypatch.setitem(cloud_hint("compensate_slope"), "write_allowed", True)
    at._update_write_actions()
    assert at.write_linear_btn.isEnabled()  # Both mappings required, no blanket Cloud ban.
    at.close()


def test_capture_and_busy_guards_block_normal_controls(window, monkeypatch):
    cloud_only(window)
    monkeypatch.setattr(window, "send_cloud_write", lambda *a, **kw: pytest.fail("No guarded I/O"))
    window.cloud_write_thread = object()
    assert window.control_write_register(1158, 420, 42)
    window.cloud_write_thread = None
    monkeypatch.setattr(window, "_is_firmware_capture_mode", lambda: True)
    assert not window.control_can_write(1158)
    assert not window.control_can_read(1158)
    assert window.control_write_register(1158, 420, 42)


class CommandApi:
    created = []
    on_login = staticmethod(lambda: None)
    success = staticmethod(WarmLinkCloudApi.success)

    def __init__(self, *args, **kwargs):
        self.calls = []
        self.values = {}
        self.created.append(self)

    def login(self):
        self.on_login()

    def write_test_code(self, **kwargs):
        self.calls.append(("write", kwargs["device_code"], kwargs["code"], kwargs["value"]))
        self.values[kwargs["code"]] = kwargs["value"]
        return {"isReusltSuc": True, "payload": kwargs}

    def get_data_by_code(self, device, codes):
        self.calls.append(("readback", device, codes))
        return {"isReusltSuc": True, "objectResult": [{"code": code, "value": self.values[code]} for code in codes]}


@pytest.fixture
def command_api(monkeypatch):
    CommandApi.created = []
    monkeypatch.setattr(workers, "WarmLinkCloudApi", CommandApi)
    monkeypatch.setattr(workers.time, "sleep", lambda *_: None)
    return CommandApi


def test_existing_command_worker_checks_identity_again_after_login(command_api, monkeypatch):
    allowed = [True]
    monkeypatch.setattr(CommandApi, "on_login", staticmethod(lambda: allowed.__setitem__(0, False)))
    errors = []
    worker = workers.WarmLinkCloudCommandWorker("user", "password", "device", "R02", "42.0",
                                              dry_run=False, write_guard=lambda: allowed[0])
    worker.error.connect(errors.append)
    worker.run()
    assert errors and command_api.created[0].calls == []


def test_normal_write_reuses_worker_and_readback_updates_open_wp(window, monkeypatch, command_api):
    cloud_only(window)
    monkeypatch.setattr(gui, "ask_yes_no", lambda *a, **kw: True)
    wp = open_wp(window)
    window.apply_cloud_rows_to_main([cloud_row(1, "Mode"), cloud_row(35, "R02")])
    wp.target_spin.setValue(42)
    wp.write_target()
    assert window.cloud_write_thread is not None
    wait_for(lambda: window.cloud_write_thread is None)
    assert command_api.created[0].calls == [("write", "device", "R02", "42.0"), ("readback", "device", ["R02"])]
    assert window.cloud_overlay_by_reg[1158]["engineering_value"] == 42
    assert wp.target_spin.value() == 42
    wp.close()


def test_all_confirmed_writable_curve_registers_use_one_serial_command_worker(window, monkeypatch, command_api):
    cloud_only(window)
    # A future reviewed grant can enable a whole action; no production grant is changed.
    for code in ("compensate_slope", "compensate_offset"):
        monkeypatch.setitem(cloud_hint(code), "write_allowed", True)
    monkeypatch.setattr(gui, "ask_yes_no", lambda *a, **kw: True)
    at = open_at(window)
    at.mode_combo.setCurrentIndex(at.mode_combo.findData(1))
    at.slope_spin.setValue(1.5); at.offset_spin.setValue(42)
    at.write_linear_params()
    wait_for(lambda: window.cloud_write_thread is None)
    assert len(command_api.created) == 1
    assert command_api.created[0].calls == [
        ("write", "device", "compensate_slope", "1.5"), ("readback", "device", ["compensate_slope"]),
        ("write", "device", "compensate_offset", "42.0"), ("readback", "device", ["compensate_offset"]),
    ]
    assert window.cloud_overlay_by_reg[1234]["engineering_value"] == 1.5
    assert window.cloud_overlay_by_reg[1235]["engineering_value"] == 42
    at.close()


def test_device_change_clears_dialog_values_and_cached_cloud_carriers(window):
    cloud_only(window)
    wp, at = open_wp(window), open_at(window)
    window.apply_cloud_rows_to_main([cloud_row(1, "Mode"), cloud_row(2, "H36"), cloud_row(45, "R02"),
                                    cloud_row(50, "CP1-1"), cloud_row(10, "T04")])
    window.set_cloud_connection_state(True, "other-device")
    assert wp.target_spin.value() == 0 and wp.temp_labels[2048].text() == "--"
    assert at.current_at_label.text() == "--"
    assert at.mode_combo.currentData() == 0
    assert not window.cloud_overlay_by_reg
    assert not any(getattr(reg, "value_source", "local") == "cloud" for reg in window.latest_regs.values())
    wp.close(); at.close()


def test_stale_write_readback_and_error_cannot_change_new_device(window, monkeypatch):
    cloud_only(window)
    window._control_cloud_write_context = window.control_context()
    window._control_cloud_write_cancelled = threading.Event()
    window.set_cloud_connection_state(True, "new-device")
    monkeypatch.setattr(gui.QMessageBox, "warning", lambda *a: pytest.fail("No stale error popup"))
    window._on_cloud_write_error("401 login expired")
    window._on_cloud_write_result_current({"isReusltSuc": True, "readback": cloud_row(42, "R02")})
    assert window.is_cloud_connected() and window.cloud_session_device_code == "new-device"
    assert 1158 not in window.cloud_overlay_by_reg
    window._control_cloud_write_context = None


def test_running_snapshot_still_blocks_write_after_dialog_timeout(window, monkeypatch):
    cloud_only(window)
    worker = workers.WarmLinkCloudWorker("user", "password", ["R02"], device_code="device")
    worker._snapshot_active.set()
    window.warmlink_cloud_dialog = SimpleNamespace(cloud_worker=worker)
    monkeypatch.setattr(window, "send_cloud_write", lambda *a, **kw: pytest.fail("Snapshot HTTP still active"))
    assert not window.control_can_write(1158)
    assert window.control_write_register(1158, 420, 42)
    worker._snapshot_active.clear()
    assert window.control_can_write(1158)
    window.warmlink_cloud_dialog = None


def test_main_close_waits_for_cloud_command_thread_without_blocking_gui(window, monkeypatch):
    from PySide6.QtGui import QCloseEvent

    calls = []
    window.cloud_write_thread = SimpleNamespace(deleteLater=lambda: calls.append("thread-deleted"))
    window._control_cloud_write_cancelled = threading.Event()
    event = QCloseEvent()
    window.closeEvent(event)
    assert not event.isAccepted() and window._close_after_cloud_write
    assert window._control_cloud_write_cancelled.is_set()
    monkeypatch.setattr(window, "close", lambda: calls.append("close"))
    window._cloud_write_finished()
    assert calls == ["thread-deleted", "close"]
    assert window.cloud_write_thread is None
