"""Regression coverage for shared value updates, persistent metadata and full scans."""
import time
import threading
from copy import deepcopy
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QEventLoop, Qt, QTimer
from PySide6.QtWidgets import QPushButton

import foxair_phnix_control as gui
from cloud.polling import CloudSession
from cloud.warmlink_codes import WARMLINK_644_DISCOVERY_CODES, cloud_modbus_register
from core.foxair_phnix_core import DecodedRegister
from core.settings_manager import load_settings, save_settings
from dialogs.cloud_dialog import WarmLinkCloudDialog
from dialogs.parameter_settings_dialog import ParameterSettingsDialog
from test_cloud_single_read_and_values import application, cloud_row
from test_cloud_polling import DialogWindow, fake_api, poll_worker, run_cycles, success
from test_warmlink_device_control_lifecycle import FakeThread, FakeWorker
from workers import warmlink_cloud_worker as workers


def parameter_window(code):
    window = DialogWindow()
    window.connected = False
    dialog = window.parameter_dialog = ParameterSettingsDialog(window)
    dialog.auto_read_block_cb.setChecked(False)
    dialog._select_block(code[0])
    dialog.show()
    return window, dialog


def parameter_cells(dialog, register):
    for row in range(dialog.table.rowCount()):
        if dialog.table.item(row, 0).data(Qt.UserRole) == register:
            return [dialog.table.item(row, col).text() for col in (3, 4, 7)]
    pytest.fail(f"Missing parameter row {register}")


@pytest.mark.parametrize("source", ["initial", "live", "static", "single", "write-readback"])
def test_open_parameter_table_receives_every_cloud_update_without_reopening(application, source):
    window, dialog = parameter_window("H01")
    reg = cloud_modbus_register("H01")
    window.apply_cloud_rows_to_main([cloud_row(0, "H01")])
    assert parameter_cells(dialog, reg) == ["0 = Nein", "--", "0 = Nein"]
    if source == "single":
        window.cloud_read_reg_no = reg
        window._on_cloud_read_data("H01", [cloud_row(1, "H01")])
    elif source == "write-readback":
        window._on_cloud_write_result("H01", {"success": True, "readback": cloud_row(1, "H01")})
    else:
        cloud_dialog = window.warmlink_cloud_dialog = WarmLinkCloudDialog(window)
        cloud_dialog._on_data([cloud_row(1, "H01")])
        loop = QEventLoop()
        QTimer.singleShot(80, loop.quit)
        loop.exec()
        assert not cloud_dialog._pending_overlay
    assert window.parameter_dialog is dialog
    assert parameter_cells(dialog, reg) == ["1 = Ja", "--", "1 = Ja"]
    assert reg not in window.last_values
    assert window.latest_regs[reg].value_source == "cloud"
    assert window.latest_regs[reg].local_raw_value is None
    dialog.close()


def test_parameter_cloud_engineering_value_and_local_raw_remain_separate(application):
    window, dialog = parameter_window("R02")
    reg = cloud_modbus_register("R02")
    window.apply_cloud_rows_to_main([cloud_row(55.5)])
    assert parameter_cells(dialog, reg) == ["55.5 °C", "--", "55.5 °C"]
    local = DecodedRegister(0x63, reg, 0, 3, 520, 520, "52 °C", "R02", "TEMP1", time.time())
    window.latest_regs[reg] = local
    window.last_values[reg] = 520
    window.previous_value_texts[reg] = "51 °C"
    window.apply_cloud_rows_to_main([cloud_row(57.5)])
    assert parameter_cells(dialog, reg) == ["52 °C", "520", "57.5 °C"]
    assert window.latest_regs[reg] is local
    assert window.last_values[reg] == 520 and window.previous_value_texts[reg] == "51 °C"
    window.clear_cloud_device_values()
    assert parameter_cells(dialog, reg) == ["52 °C", "520", "--"]
    dialog.close()


def test_parameter_cloud_only_values_clear_on_device_switch_and_no_local_reads(application, monkeypatch):
    window, dialog = parameter_window("R02")
    reg = cloud_modbus_register("R02")
    monkeypatch.setattr(window, "send_read_request", lambda *a, **kw: pytest.fail("No local transport"))
    window.apply_cloud_rows_to_main([cloud_row(55)])
    dialog.read_visible_registers(auto=True)
    window.clear_cloud_device_values()
    assert parameter_cells(dialog, reg) == ["--", "--", "--"]
    assert not dialog._read_expected_regs
    dialog.close()


def test_restart_loads_safe_full_cache_and_selection_before_discovery(application, tmp_path, monkeypatch):
    first = DialogWindow()
    dialog = WarmLinkCloudDialog(first)
    dialog._on_devices([{"deviceCode": "A", "newBackendField": {"version": 9, "accessToken": "secret"},
                         "deviceSecret": "secret", "sn": "sn-a", "productKey": "pk"},
                        {"deviceCode": "B", "dtuIccid": "iccid-b", "password": "secret"}])
    dialog.device_combo.setCurrentIndex(dialog.device_combo.findData("B"))
    path = tmp_path / "settings.json"
    save_settings(str(path), first.settings)
    assert "secret" not in path.read_text()
    restarted = DialogWindow()
    restarted.settings = load_settings(str(path))
    assert not restarted.cloud_session.devices
    restored = WarmLinkCloudDialog(restarted)
    assert restored._selected_device_code() == "B"
    assert restored.devices[0]["newBackendField"] == {"version": 9}
    assert restored.devices[0]["sn"] == "sn-a" and restored.devices[1]["dtuIccid"] == "iccid-b"
    assert restored.session.devices_cached and not restored.session.validated and not restored.session.scanned
    cfg = restarted.settings["warmlink_cloud"]
    assert not {"rows", "live_codes", "static_codes", "scanned", "validated"}.intersection(cfg)
    monkeypatch.setattr(workers, "discover_cloud_devices", lambda *a, **kw: pytest.fail("Cache must skip discovery"))
    # With no token, the first value request performs normal API authentication.
    monkeypatch.setattr(workers, "WarmLinkCloudApi", MinimalCacheApi)
    worker = workers.WarmLinkCloudWorker("user", "password", ["T04"], device_code="B", session=restored.session, poll_once=True)
    worker.run()
    assert worker.session.validated and worker.session.scanned
    assert worker.session.device_code == "B"
    restored.close()
    dialog.close()


class MinimalCacheApi:
    def __init__(self, *args, **kwargs):
        self.token = None
        self.last_login_method = ""

    def get_data_by_code_batched(self, device, codes, **kwargs):
        self.token = "authenticated-token"
        return success([{"code": code, "value": 10} for code in codes])

    def get_device_status(self, device):
        return success({})


@pytest.mark.parametrize("cache_user", ["other", ""])
def test_cache_from_other_or_unknown_account_is_never_loaded(application, cache_user):
    window = DialogWindow()
    window.settings["warmlink_cloud"].update(cached_devices_username=cache_user,
        cached_devices=[{"deviceCode": "private-other-device"}], selected_device_code="private-other-device",
        known_device_codes=["legacy-device"])
    dialog = WarmLinkCloudDialog(window)
    assert dialog.devices == [] and dialog.device_combo.count() == 0
    assert not dialog.session.reusable("user", "private-other-device", "token")
    dialog.close()


def test_account_edit_invalidates_device_cache_and_old_values(application):
    window = DialogWindow()
    dialog = WarmLinkCloudDialog(window)
    dialog._on_devices([{"deviceCode": "device"}])
    window.apply_cloud_rows_to_main([cloud_row(55)])
    dialog.username_edit.setText("other-user")
    dialog._save_settings()
    assert dialog.devices == [] and window.cloud_overlay_by_reg == {}
    assert dialog._cloud_settings()["cached_devices"] == []
    assert not dialog._selected_device_code() and not window.is_cloud_connected()
    assert not dialog.session.reusable("other-user", "device", "token")
    dialog.close()


def test_pending_full_scan_wakes_existing_worker_and_rechecks_all_groups(fake_api, monkeypatch):
    worker = poll_worker()
    rounds, timings = [], []
    worker.timing_updated.connect(timings.append)
    def wait(_seconds):
        rounds.append(True)
        if len(rounds) == 1:
            worker.request_full_scan(["F23", "T04", "unmapped", "unsupported", "Fault1", "new-other"])
            assert worker._wake_event.is_set()
            return False
        return True
    worker._sleep_interruptible = wait
    worker.run()
    calls = fake_api.created[-1].calls
    reads = [call[1] for call in calls if isinstance(call, tuple) and call[0] == "read"]
    assert reads == [["F23", "T04", "unmapped", "unsupported"],
                     ["F23", "T04", "unmapped", "unsupported", "Fault1", "new-other"]]
    assert calls.count("devices") == 1 and calls.count("houses") == 1
    assert worker.session.live_codes == ["T04", "Fault1"]
    assert worker.session.static_codes == ["F23"]
    assert worker.session.other_codes == ["unmapped", "new-other"]
    assert worker.session.rows["unsupported"]["supported"] is False
    assert any(state.phase == "INITIAL_SCAN" and state.done == state.total == 6 for state in timings)


def test_stopped_full_scan_uses_existing_session_and_fresh_support_evidence(fake_api, monkeypatch):
    first = poll_worker(poll_once=True)
    first.run()
    def read(api, device, codes, **kwargs):
        api.calls.append(("read", list(codes)))
        return success([{"code": code, "value": 5} for code in codes if code != "F23"])
    monkeypatch.setattr(fake_api, "get_data_by_code_batched", read)
    second = poll_worker(poll_once=True, session=first.session, full_scan=True)
    second.run()
    assert "devices" not in fake_api.created[-1].calls and "houses" not in fake_api.created[-1].calls
    assert ("read", second.codes) in fake_api.created[-1].calls
    assert "F23" not in second.session.supported_codes and second.session.static_codes == []
    assert second.session.rows["F23"]["stale"]  # last useful value is retained independently of support


@pytest.mark.parametrize("invalid", ["no_token", "unvalidated"])
def test_cached_devices_survive_session_reauthentication_without_discovery(fake_api, invalid, monkeypatch):
    first = poll_worker(poll_once=True)
    first.run()
    session = deepcopy(first.session)
    if invalid == "unvalidated":
        session.validated = False
    else:
        original_init = fake_api.__init__
        def init(api, *args, **kwargs):
            original_init(api, *args, **kwargs)
            api.token = None
        monkeypatch.setattr(fake_api, "__init__", init)
    second = poll_worker(poll_once=True, session=session)
    second.run()
    assert "devices" not in fake_api.created[-1].calls and "houses" not in fake_api.created[-1].calls
    assert ("read", second.codes) in fake_api.created[-1].calls


@pytest.mark.parametrize("backend", ["standard_modbus", "warmlink", "display_modbus"])
@pytest.mark.parametrize("cloud_connected", [True, False])
def test_all_registers_button_preserves_all_three_local_paths(backend, cloud_connected):
    calls = []
    window = SimpleNamespace(connected=True, _is_firmware_capture_mode=lambda: False,
        is_cloud_connected=lambda: cloud_connected,
        current_backend_key=lambda: backend, current_backend_label=lambda: backend,
        write_bus_edit=SimpleNamespace(text=lambda: "0x63"), _parse_int_text=lambda text: int(text, 0),
        init_pause_spin=SimpleNamespace(value=lambda: 900), _log=lambda text: None,
        warmlink_cloud_dialog=SimpleNamespace(reload_all_values=lambda: pytest.fail("Local takes precedence")),
        standard_modbus_init_controller=SimpleNamespace(start=lambda **kw: calls.append(("standard_modbus", kw))),
        warmlink_init_controller=SimpleNamespace(start=lambda **kw: calls.append(("warmlink", kw))),
        _start_display_reboot_snapshot=lambda **kw: calls.append(("display_modbus", kw)))
    gui.MainWindow.send_init_reads(window)
    assert calls[0][0] == backend and len(calls) == 1
    if backend == "display_modbus":
        assert calls[0][1] == {"source_label": "Alle bekannten Register lesen", "force": True}
    else:
        assert calls[0][1] == {"slave_addr": 0x63, "pause_ms": 900}


def test_cloud_only_full_scan_button_is_nonmodal_and_uses_existing_worker(application, monkeypatch):
    window = DialogWindow()
    window.connected = False
    dialog = window.warmlink_cloud_dialog = WarmLinkCloudDialog(window)
    full_requests = []
    worker = SimpleNamespace(request_full_scan=lambda codes: full_requests.append(list(codes)))
    dialog.cloud_worker = worker
    dialog.cloud_thread = FakeThread()
    monkeypatch.setattr(dialog, "_start_worker", lambda *a, **kw: pytest.fail("No second worker"))
    window.send_init_reads()
    assert full_requests == [list(WARMLINK_644_DISCOVERY_CODES)]
    assert not dialog.isVisible()
    dialog.cloud_worker = dialog.cloud_thread = None
    dialog.close()


def test_stopped_dialog_full_scan_ignores_subset_and_starts_async_worker(application, monkeypatch):
    from dialogs import cloud_dialog as module
    window = DialogWindow()
    window.connected = False
    dialog = window.warmlink_cloud_dialog = WarmLinkCloudDialog(window)
    dialog._on_devices([{"deviceCode": "device"}])
    dialog.codes_edit.setPlainText("F23")
    monkeypatch.setattr(module, "QThread", FakeThread)
    monkeypatch.setattr(module, "WarmLinkCloudWorker", FakeWorker)
    window.send_init_reads()
    kwargs = FakeWorker.created[-1].kwargs
    assert kwargs["full_scan"] and kwargs["poll_once"]
    assert kwargs["codes"] == list(WARMLINK_644_DISCOVERY_CODES)
    assert kwargs["session"].devices_cached and not kwargs["force_discovery"]
    assert dialog.cloud_thread.started_called
    dialog._worker_finished()
    dialog.close()


def test_full_scan_no_connections_and_capture_never_send(application, monkeypatch):
    window = DialogWindow()
    window.connected = False
    window.cloud_session_authenticated = False
    monkeypatch.setattr(gui, "WarmLinkCloudDialog", lambda *a: pytest.fail("No valid connection"))
    window.send_init_reads()
    assert "keine lokale oder gültige Cloud-Verbindung" in window.logs[-1]
    window.cloud_session_authenticated = True
    monkeypatch.setattr(window, "_is_firmware_capture_mode", lambda: True)
    window.send_init_reads()
    assert "Senden gesperrt" in window.logs[-1]


def test_direct_write_retains_capture_and_concurrent_write_guards(application, monkeypatch):
    window = DialogWindow()
    messages = []
    monkeypatch.setattr(gui.QMessageBox, "warning", lambda *args: messages.append(args[-1]))
    monkeypatch.setattr(gui.QMessageBox, "information", lambda *args: messages.append(args[-1]))
    monkeypatch.setattr(gui, "WarmLinkCloudCommandWorker", lambda **kw: pytest.fail("Guard must prevent worker"))
    window.cloud_write_thread = object()
    window.send_cloud_write("R02", "52")
    assert "bereits" in messages[-1]
    monkeypatch.setattr(window, "_is_firmware_capture_mode", lambda: True)
    window.cloud_write_thread = None
    window.send_cloud_write("R02", "52")
    assert "Firmware-Capture" in messages[-1]


def test_unknown_account_cannot_display_unowned_cache(application):
    window = DialogWindow()
    window.settings["warmlink_cloud"].update(username="", cached_devices_username="",
        cached_devices=[{"deviceCode": "unowned"}])
    dialog = WarmLinkCloudDialog(window)
    assert dialog.devices == [] and not dialog.session.devices_cached
    dialog.close()


def test_real_full_scan_worker_keeps_gui_event_loop_responsive(application, monkeypatch):
    gate = threading.Event()
    class SlowApi(MinimalCacheApi):
        def get_data_by_code_batched(self, device, codes, **kwargs):
            assert gate.wait(2), "GUI must keep delivering timer events"
            kwargs["progress"](len(codes), len(codes))
            return super().get_data_by_code_batched(device, codes, **kwargs)
    monkeypatch.setattr(workers, "WarmLinkCloudApi", SlowApi)
    monkeypatch.setattr(workers, "load_cloud_credentials", lambda *args, **kwargs: ("password", None))
    monkeypatch.setattr(workers, "discover_cloud_devices", lambda *a, **kw: pytest.fail("Use existing devices"))
    window = DialogWindow()
    window.connected = False
    dialog = window.warmlink_cloud_dialog = WarmLinkCloudDialog(window)
    dialog._on_devices([{"deviceCode": "device"}])
    loop = QEventLoop()
    timer, timeout = QTimer(), QTimer()
    beats = []
    def beat():
        beats.append(True)
        if len(beats) >= 3:
            gate.set()
    timer.timeout.connect(beat)
    timer.start(5)
    timeout.setSingleShot(True)
    timeout.timeout.connect(lambda: (gate.set(), loop.quit()))
    timeout.start(3000)
    window.send_init_reads()
    thread = dialog.cloud_thread
    thread.finished.connect(loop.quit)
    loop.exec()
    timer.stop()
    timeout.stop()
    assert len(beats) >= 3 and dialog.cloud_thread is None
    assert dialog.session.scanned and len(dialog.session.candidates) == len(WARMLINK_644_DISCOVERY_CODES)
    assert window.cloud_overlay_by_reg
    dialog.close()


def test_direct_write_still_rejects_invalid_values_and_read_only_mapping(application, monkeypatch):
    window = DialogWindow()
    messages = []
    monkeypatch.setattr(gui.QMessageBox, "warning", lambda *args: messages.append(args[-1]))
    monkeypatch.setattr(gui.QMessageBox, "information", lambda *args: messages.append(args[-1]))
    monkeypatch.setattr(window, "send_cloud_write", lambda *a, **kw: pytest.fail("Invalid write must be blocked"))
    window.open_cloud_write_for_register(cloud_modbus_register("R02"), "not-a-number")
    assert messages
    window.open_cloud_write_for_register(cloud_modbus_register("T04"), "55")
    assert "freigegebener" in messages[-1]
