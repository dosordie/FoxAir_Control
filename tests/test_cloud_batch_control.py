"""Batch control and dialog regressions with synthetic accounts/devices only."""
import time

import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMessageBox

import foxair_phnix_control as gui
from cloud.cloud_write_helpers import validate_cloud_commands
from cloud.warmlink_api import WarmLinkCloudApi, ENDPOINT_DEVICE_CONTROL_LANG
from dialogs.decoder_dialogs import FaultDecoderDialog
from dialogs.parameter_settings_dialog import ParameterSettingsDialog
from dialogs.cloud_dialog import WarmLinkCloudDialog
from test_cloud_single_read_and_values import application, cloud_row
from test_cloud_at_curve_and_csv_cleanup import cloud_only, open_at
from test_configuration_cloud_writes import CURVE_CODES, run_commands, open_sg
from test_control_transport import command_api, CommandApi, open_wp
from test_csv_logger_transport import wait_for
from test_warmlink_request_scheduler import window


@pytest.mark.parametrize("count", [1, 7])
def test_exact_batch_payload_endpoint_and_no_token_replay(monkeypatch, count):
    api = WarmLinkCloudApi("user", "unused", initial_token="synthetic-token")
    calls = []
    monkeypatch.setattr(api, "_request_json", lambda endpoint, payload, **kwargs:
        calls.append((endpoint, payload, kwargs)) or {"isReusltSuc": False, "error_code": "-100"})
    monkeypatch.setattr(api, "login", lambda *a: pytest.fail("No write token replay"))
    commands = tuple((code, "45.5") for code in CURVE_CODES[:count])
    api.write_control_batch("device", commands)
    assert len(calls) == 1 and calls[0][0] == ENDPOINT_DEVICE_CONTROL_LANG == "app/device/control?lang=en"
    assert calls[0][1] == {"appId": "16", "param": [
        {"deviceCode": "device", "protocolCode": code, "value": "45.5"} for code, _ in commands]}


def test_single_write_api_delegates_to_batch(monkeypatch):
    api = WarmLinkCloudApi("user", "unused")
    calls = []
    monkeypatch.setattr(api, "write_control_batch", lambda *a: calls.append(a) or {})
    api.write_test_code("device", "CP1-1", "45.5")
    assert calls == [("device", (("CP1-1", "45.5"),))]


@pytest.mark.parametrize("commands", [(("CP1-1", "45.5"), ("CP1-4", "45.5")),
    (("SG Status", "1"),), (("SG08", "2"),), (("CP1-1", "NaN"),),
    (("CP1-1", "45"), ("CP1-1", "46")), (), (("unknown", "1"),)])
def test_entire_invalid_batch_is_rejected_before_network(command_api, commands):
    with pytest.raises(ValueError):
        validate_cloud_commands(commands)
    if commands:
        results, errors = run_commands(commands)
        assert errors and not results and not CommandApi.created


@pytest.mark.parametrize("failure", ["mismatch", "missing", "stale", "cached", "currentEmpty"])
def test_partial_batch_classifies_each_code_and_never_replays(command_api, monkeypatch, failure):
    original = CommandApi.get_data_by_code
    def read(self, device, codes):
        result = original(self, device, codes)
        if failure == "missing":
            result["objectResult"].pop()
        elif failure == "mismatch":
            result["objectResult"][-1]["value"] = "30"
        else:
            result["objectResult"][-1][failure] = True
        return result
    monkeypatch.setattr(CommandApi, "get_data_by_code", read)
    commands = tuple((code, "45.5") for code in CURVE_CODES)
    results, errors = run_commands(commands)
    assert not errors and len(results) == 7
    assert results[-1]["confirmed_codes"] == list(CURVE_CODES[:-1])
    field = "missing_codes" if failure == "missing" else "mismatched_codes" if failure == "mismatch" else "stale_codes"
    assert results[-1][field] == [CURVE_CODES[-1]]
    assert not results[-1]["sequence_complete"]
    assert [c[0] for c in CommandApi.created[0].calls] == ["write", "readback", "readback", "readback"]
    assert all(c[2] == list(CURVE_CODES) for c in CommandApi.created[0].calls[1:])


@pytest.mark.parametrize("reply", ["timeout", "api_error", "http_error"])
def test_ambiguous_write_reads_existing_state_without_resending(command_api, monkeypatch, reply):
    original = CommandApi.write_control_batch
    def write(self, device, commands):
        original(self, device, commands)
        if reply == "timeout":
            raise TimeoutError("synthetic write timeout")
        return {"isReusltSuc": True, "error_code": "9" if reply == "api_error" else "0",
                "http_status": 500 if reply == "http_error" else 200}
    monkeypatch.setattr(CommandApi, "write_control_batch", write)
    results, errors = run_commands((("CP1-1", "45.5"),))
    assert not errors and results[0]["readback_verified"] and not results[0]["api_success"]
    assert [c[0] for c in CommandApi.created[0].calls] == ["write", "readback"]


def test_read_timeout_does_not_repeat_write_or_rollback(command_api, monkeypatch):
    def read(self, device, codes):
        self.calls.append(("readback", device, codes))
        raise TimeoutError("synthetic read timeout")
    monkeypatch.setattr(CommandApi, "get_data_by_code", read)
    results, errors = run_commands((("CP1-1", "45.5"),))
    assert not errors and not results[0]["readback_verified"]
    assert results[0]["missing_codes"] == ["CP1-1"]
    assert [c[0] for c in CommandApi.created[0].calls] == ["write", "readback", "readback", "readback"]


def test_failed_parameter_batch_prevents_sg_activation(command_api, monkeypatch):
    original = CommandApi.get_data_by_code
    def read(self, device, codes):
        result = original(self, device, codes)
        result["objectResult"][0]["value"] = "1"
        return result
    monkeypatch.setattr(CommandApi, "get_data_by_code", read)
    results, _ = run_commands((("SG03", "4.5"), ("SG08", "1"), ("SG01", "7")))
    assert results[-1]["confirmed_codes"] == ["SG08"]
    assert [c[2] for c in CommandApi.created[0].calls if c[0] == "write"] == [(("SG03", "4.5"), ("SG08", "1"))]


def test_at_only_dirty_fields_and_linear_batch_without_confirmation(window, command_api, monkeypatch):
    cloud_only(window)
    monkeypatch.setattr(gui, "ask_yes_no", lambda *a, **k: pytest.fail("Cloud must write directly"))
    window.apply_cloud_rows_to_main([cloud_row(1, "H36"), cloud_row(1, "compensate_slope"), cloud_row(40, "compensate_offset")])
    at = open_at(window)
    at.write_linear_params()
    assert not CommandApi.created
    at.slope_spin.setValue(1.2); at.offset_spin.setValue(41)
    at.write_linear_params()
    assert not at.write_curve_btn.isEnabled()
    wait_for(lambda: window.cloud_write_thread is None)
    assert CommandApi.created[0].calls[0][2] == (("compensate_slope", "1.2"), ("compensate_offset", "41.0"))
    assert not at._dirty_registers
    at.mode_combo.setCurrentIndex(at.mode_combo.findData(2))
    at._seven_spins()[0].setValue(45)
    at.write_seven_points()
    wait_for(lambda: window.cloud_write_thread is None)
    assert CommandApi.created[1].calls[0][2] == (("CP1-1", "45.0"),)
    at.close()


def test_at_partial_readback_preserves_dirty_and_newer_edits(window, command_api, monkeypatch):
    cloud_only(window)
    original = CommandApi.get_data_by_code
    def read(self, device, codes):
        result = original(self, device, codes)
        result["objectResult"] = result["objectResult"][:1]
        return result
    monkeypatch.setattr(CommandApi, "get_data_by_code", read)
    at = open_at(window)
    at.mode_combo.setCurrentIndex(at.mode_combo.findData(2))
    at._seven_spins()[0].setValue(45); at._seven_spins()[1].setValue(46)
    at.write_seven_points()
    # A new editor version must survive even a matching old readback.
    at._seven_spins()[0].setValue(47)
    wait_for(lambda: window.cloud_write_thread is None)
    assert {1250, 1251} <= at._dirty_registers
    assert at._seven_spins()[0].value() == 47 and at._seven_spins()[1].value() == 46
    assert "fehlt" in at.status_label.text()
    at.close()


def test_sg_order_boolean_widget_and_immediate_cloud_write(window, command_api, monkeypatch):
    cloud_only(window)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: pytest.fail("Cloud must write directly"))
    sg = open_sg(window)
    assert not hasattr(sg, "cloud_test_cb") and 1341 not in sg.raw_spins
    assert [sg.sg08_combo.itemData(i) for i in range(2)] == [0, 1]
    form = sg.sg08_combo.parentWidget().layout().itemAt(1).layout()
    positions = [form.getWidgetPosition(sg._widget_for_reg(reg))[0] for reg in range(1334, 1342)]
    assert positions == sorted(positions)
    sg.raw_spins[1335].setValue(5); sg.power_spins[1336].setValue(4.5)
    sg.sg08_combo.setCurrentIndex(1)
    sg.send_values()
    assert not sg.send_btn.isEnabled()
    wait_for(lambda: window.cloud_write_thread is None)
    assert CommandApi.created[0].calls[0][2] == (("SG02", "5"), ("SG03", "4.5"), ("SG08", "1"))
    assert not sg._dirty
    sg.close()


def capture_reads(window, monkeypatch):
    cloud_only(window)
    requests = []
    monkeypatch.setattr(window, "request_cloud_snapshot", lambda request: requests.append(request))
    return requests


def test_at_sg_parameter_autoload_use_targeted_requests_and_preserve_edits(window, monkeypatch):
    requests = capture_reads(window, monkeypatch)
    at = open_at(window); at.initial_read_timer.start(250); sg = open_sg(window)
    sg.initial_read_timer.start(250)
    parameter = window.parameter_dialog = ParameterSettingsDialog(window)
    parameter.show()
    at._seven_spins()[0].setValue(45); sg.power_spins[1336].setValue(4.5)
    QTest.qWait(350)
    assert {r.purpose for r in requests} == {"at_compensation", "sg_ready", "parameters"}
    assert len(requests) == 3
    sg_request = next(r for r in requests if r.purpose == "sg_ready")
    assert sg_request.codes == sg.CLOUD_CODES
    sg.cloud_read_finished(sg_request.cycle_id, [cloud_row(5, "SG03"), cloud_row(1, "SG08")], "")
    assert sg.power_spins[1336].value() == 4.5 and sg.sg08_combo.currentData() == 1
    at.cloud_read_finished(at.cloud_request.cycle_id, [cloud_row(42, "CP1-1")], "")
    assert at._seven_spins()[0].value() == 45
    parameter_request = parameter.cloud_request
    assert 0 < len(parameter_request.codes) < 100
    parameter.cloud_read_finished(parameter_request.cycle_id, [cloud_row(1, code) for code in parameter_request.codes], "")
    parameter.read_visible_registers(auto=True)
    assert len(requests) == 3
    parameter._select_block("SG")
    assert len(requests) == 4 and set(parameter.cloud_request.codes) <= set(sg.CLOUD_CODES)
    pending = parameter.cloud_request
    parameter.close(); parameter.cloud_read_finished(pending.cycle_id, [cloud_row(7, "SG01")], "")
    assert pending.cancelled.is_set()
    at.close(); sg.close()


@pytest.mark.parametrize("raw,expected", [("0000010000000000", 1024), ("512", 512), ("10", 10), (-1, 65535), ("0", 0),
    (0, 0), ("", None), (None, None), ("bad", None), (1.5, None), (65536, None)])
def test_fault_word_decoding(raw, expected):
    assert FaultDecoderDialog._parse_word(raw, {"dataType": "BINARY"}) == expected


def test_fault_autoload_complete_missing_poll_manual_and_close(window, monkeypatch):
    requests = capture_reads(window, monkeypatch)
    # An old local alarm must not leak into Cloud-only.
    window.last_values[2019] = 1024
    window.open_fault_decoder(); fault = window.fault_dialog
    assert "unbekannt" in fault.status_label.text()
    assert "unvollständig" in fault.table.item(0, 4).text()
    QTest.qWait(350)
    assert len(requests) == 1 and requests[0].codes == fault.CLOUD_CODES
    rows = [cloud_row("0000010000000000", "O01~023", dataType="BINARY")]
    rows += [cloud_row(0, code) for code in fault.CLOUD_CODES[1:]]
    rows[1]["value"] = "0000000000000001"; rows[1]["dataType"] = "BINARY"
    fault.cloud_read_finished(requests[0].cycle_id, rows, "")
    assert "AKTIV" in fault.status_label.text()
    assert fault.table.item(0, 0).text() == "2081" and fault.table.item(0, 1).text() == "Fehler 1"
    fault.read_now_btn.click()
    assert len(requests) == 2
    fault.cloud_read_finished(requests[-1].cycle_id, [cloud_row(0, c) for c in fault.CLOUD_CODES], "")
    assert "Keine aktiven" in fault.table.item(0, 4).text() and "aus" in fault.status_label.text()
    fault.poll_once(); request = requests[-1]
    fault.cloud_read_finished(request.cycle_id, [cloud_row(0, c) for c in fault.CLOUD_CODES[:-1]], "")
    assert "unvollständig" in fault.table.item(0, 4).text()
    fault.poll_cb.setChecked(True); assert fault.poll_timer.isActive()
    fault.poll_once(); pending = requests[-1]
    fault.close()
    assert pending.cancelled.is_set() and not fault.poll_timer.isActive()
    fault.cloud_read_finished(pending.cycle_id, rows, "")
    assert "unvollständig" in fault.table.item(0, 4).text()


def test_fault_local_reads_and_priority_are_preserved(window, monkeypatch):
    window.last_values[2019] = 0
    # The local source accessor is authoritative when both transports exist.
    original = window.register_value_sources
    from types import SimpleNamespace
    monkeypatch.setattr(window, "register_value_sources", lambda r: SimpleNamespace(local_raw=0))
    window.cloud_overlay_by_reg[2019] = {"raw_value": 1024}
    fault = FaultDecoderDialog(window); fault.show()
    assert "aus" in fault.status_label.text()
    calls = []
    monkeypatch.setattr(window, "send_read_request", lambda *a, **k: calls.append((a, k)))
    fault.poll_once()
    assert [a for a, _ in calls] == [(2019, 1), (2081, 10)]
    fault.close()


def test_cloud_tabs_cleanup_and_exports_keep_debugger(window, monkeypatch, tmp_path):
    dialog = WarmLinkCloudDialog(window)
    labels = [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())]
    assert "Schreibtest" not in labels and "Wertefinder" not in labels
    assert "Cloud ↔ Lokal" in labels and any("API" in label for label in labels)
    assert not hasattr(dialog, "command_thread") and not hasattr(dialog, "finder_table")
    assert not hasattr(dialog, "_unknown_mapping_candidates")
    dialog._on_data([cloud_row(5, "SG03"), cloud_row(5, "unknown-code")])
    from PySide6.QtWidgets import QFileDialog
    for method, extension in ((dialog.export_csv, "csv"), (dialog.export_mapping_candidates_csv, "csv"),
                              (dialog.export_mapping_check_csv, "csv"), (dialog.export_json, "json")):
        path = tmp_path / (method.__name__ + "." + extension)
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, p=path: (str(p), ""))
        method()
        text = path.read_text(encoding="utf-8-sig")
        assert "SG03" in text and "Wertefinder" not in text and "numeric==cloud" not in text
    dialog.close()


def test_shared_at_offset_draft_stays_in_sync_between_curve_modes(window):
    cloud_only(window)
    at = open_at(window)
    at.offset_spin.setValue(42.5)
    assert at._seven_spins()[3].value() == 42.5
    at._seven_spins()[3].setValue(43.5)
    assert at.offset_spin.value() == 43.5 and 1235 in at._dirty_registers
    at.close()


def test_direct_cloud_register_write_still_works_with_local_connection(window, command_api, monkeypatch):
    window.settings["warmlink_cloud"]["username"] = "user"
    window.settings["warmlink_cloud"]["selected_device_code"] = "device"
    window.cloud_credentials_cache = {"token": "synthetic-token", "token_user": "user",
                                      "password": "unused", "password_user": "user"}
    window.set_cloud_connection_state(True, "device")
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: pytest.fail(str(a[-1])))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: pytest.fail("No cloud confirmation"))
    assert window.control_transport() == "warmlink_raw"
    window.open_cloud_write_for_register(1158, "42.0")
    wait_for(lambda: window.cloud_write_thread is None)
    assert CommandApi.created[0].calls[0][2] == (("R02", "42.0"),)
    assert window.control_transport() == "warmlink_raw"


def test_closed_dialog_does_not_receive_old_write_confirmation(window, command_api):
    cloud_only(window)
    at = open_at(window)
    at.mode_combo.setCurrentIndex(at.mode_combo.findData(2))
    at._seven_spins()[0].setValue(45)
    at.write_seven_points()
    at.close()
    replacement = open_at(window)
    replacement._seven_spins()[0].setValue(47)
    wait_for(lambda: window.cloud_write_thread is None)
    assert replacement._seven_spins()[0].value() == 47
    assert 1250 in replacement._dirty_registers
    replacement.close()


@pytest.mark.parametrize("kind", ["parameters", "fault"])
def test_context_switch_rejects_pending_dialog_snapshot(window, monkeypatch, kind):
    requests = capture_reads(window, monkeypatch)
    if kind == "parameters":
        dialog = window.parameter_dialog = ParameterSettingsDialog(window)
        dialog.show(); dialog.read_visible_registers()
        register, code = 1334, "SG01"
    else:
        window.open_fault_decoder(); dialog = window.fault_dialog
        dialog.poll_once(); register, code = 2081, "Fault1"
    pending = requests[0]
    window.set_cloud_connection_state(True, "other-device")
    dialog.cloud_read_finished(pending.cycle_id, [cloud_row(1, code)], "")
    assert pending.cancelled.is_set() and register not in window.cloud_overlay_by_reg
    dialog.close()


def test_command_transaction_serializes_poll_http_through_final_readback(application, monkeypatch):
    import threading
    from workers import warmlink_cloud_worker as workers
    from cloud.warmlink_api import ENDPOINT_GET_DATA_BY_CODE
    entered, release = threading.Event(), threading.Event()
    calls, values = [], {}
    def request(self, endpoint, payload, **kwargs):
        calls.append((threading.current_thread().name, endpoint))
        if endpoint == ENDPOINT_DEVICE_CONTROL_LANG:
            values.update({p["protocolCode"]: p["value"] for p in payload["param"]})
            entered.set()
            assert release.wait(2)
            return {"isReusltSuc": True}
        assert endpoint == ENDPOINT_GET_DATA_BY_CODE
        return {"isReusltSuc": True, "objectResult": [
            {"code": c, "value": values.get(c, "0")} for c in payload["protocalCodes"]]}
    monkeypatch.setattr(WarmLinkCloudApi, "_request_json", request)
    monkeypatch.setattr(workers.time, "sleep", lambda *_: None)
    worker = workers.WarmLinkCloudCommandWorker("user", "unused", "device", "CP1-1", "45.5",
                                               initial_token="synthetic-token", dry_run=False)
    command = threading.Thread(target=worker.run, name="command-test")
    poll_api = WarmLinkCloudApi("user", "unused", initial_token="synthetic-token")
    poll = threading.Thread(target=lambda: poll_api.get_data_by_code("device", ["CP1-1"]), name="poll-test")
    command.start()
    try:
        assert entered.wait(2)
        poll.start()
    finally:
        release.set()
        command.join(3)
        if poll.ident is not None:
            poll.join(3)
    assert not command.is_alive() and not poll.is_alive()
    assert calls == [("command-test", ENDPOINT_DEVICE_CONTROL_LANG),
                     ("command-test", ENDPOINT_GET_DATA_BY_CODE), ("poll-test", ENDPOINT_GET_DATA_BY_CODE)]


@pytest.mark.parametrize("failure", ["unsupported", "http_error", "contradictory"])
def test_untrusted_or_contradictory_readbacks_never_form_complete_success(command_api, monkeypatch, failure):
    original = CommandApi.get_data_by_code
    attempts = []
    def read(self, device, codes):
        result = original(self, device, codes)
        attempts.append(1)
        if failure == "unsupported":
            result["objectResult"][-1]["supported"] = False
        elif failure == "http_error":
            result["http_status"] = 500
        else:
            result["objectResult"][1 if len(attempts) == 1 else 0]["value"] = "30"
        return result
    monkeypatch.setattr(CommandApi, "get_data_by_code", read)
    results, _ = run_commands((("CP1-1", "45.5"), ("CP1-2", "45.5")))
    assert len(attempts) == 3 and not results[-1]["sequence_complete"]
    assert len(results[-1]["confirmed_codes"]) < 2


def test_missing_device_and_dry_run_do_not_login_or_touch_network(command_api):
    from workers import warmlink_cloud_worker as workers
    missing = workers.WarmLinkCloudCommandWorker("user", "unused", "", "CP1-1", "45.5", dry_run=False)
    errors = []
    missing.error.connect(errors.append); missing.run()
    assert errors and not CommandApi.created
    dry = workers.WarmLinkCloudCommandWorker("user", "unused", "device", "CP1-1", "45.5", dry_run=True)
    results = []
    dry.result.connect(results.append); dry.run()
    assert results[0]["sent"] is False and not CommandApi.created


def test_parameter_block_switch_reuses_fresh_poll_values_after_initial_load(window, monkeypatch):
    requests = capture_reads(window, monkeypatch)
    dialog = window.parameter_dialog = ParameterSettingsDialog(window)
    dialog.show(); dialog.read_visible_registers()
    initial = requests[0]
    dialog.cloud_read_finished(initial.cycle_id, [cloud_row(1, c) for c in initial.codes], "")
    window.apply_cloud_rows_to_main([cloud_row(1, c, lastFetch=time.strftime("%Y-%m-%d %H:%M:%S"))
                                     for c in ("SG01", "SG02", "SG03", "SG04", "SG05", "SG06", "SG07", "SG08", "SG Status")])
    dialog._select_block("SG")
    assert len(requests) == 1 and dialog.cloud_request is None
    assert "Polling" in dialog.read_status_label.text()
    dialog.close()


def test_local_wp_at_sg_keep_confirmation_cancellation(window, monkeypatch):
    calls = []
    monkeypatch.setattr(gui, "ask_yes_no", lambda *a, **k: calls.append(a[1]) or False)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: calls.append(a[1]) or QMessageBox.No)
    monkeypatch.setattr(window, "send_register_write", lambda *a, **k: pytest.fail("Cancelled local write"))
    wp = open_wp(window); wp.write_power()
    at = open_at(window); at.write_mode()
    sg = open_sg(window); sg.raw_spins[1335].setValue(5); sg.send_values()
    assert len(calls) == 3
    wp.close(); at.close(); sg.close()


def test_initial_cloud_reads_wait_for_running_write_without_overwriting_status(window, monkeypatch):
    requests = capture_reads(window, monkeypatch)
    at = open_at(window); sg = open_sg(window)
    at.set_write_status("Schreiben …"); sg.set_write_status("Schreiben …")
    window.cloud_write_thread = object()
    try:
        at.initial_read_timer.start(1); sg.initial_read_timer.start(1)
        QTest.qWait(20)
        assert requests == []
        assert at.status_label.text() == sg.status_label.text() == "Schreiben …"
    finally:
        window.cloud_write_thread = None
    QTest.qWait(350)
    assert {r.purpose for r in requests} == {"at_compensation", "sg_ready"}
    at.read_from_wp(); sg.read_from_wp()
    assert len(requests) == 2
    at.close(); sg.close()


def test_application_shutdown_rejects_new_snapshot_before_starting_worker(window, monkeypatch):
    from cloud.snapshot_request import CloudSnapshotRequest
    cloud_only(window)
    window._warmlink_closing = True
    monkeypatch.setattr(gui, "WarmLinkCloudDialog", lambda *_: pytest.fail("No worker during shutdown"))
    request = CloudSnapshotRequest(1, ("Fault1",), time.monotonic() + 60, "user", "device")
    assert "beendet" in window.request_cloud_snapshot(request)


def test_all_seven_sg_parameters_share_one_engineering_batch(window, command_api):
    cloud_only(window)
    window.apply_cloud_rows_to_main([cloud_row(7, "SG01"), cloud_row(5, "SG02"),
        cloud_row(4, "SG03"), cloud_row(4, "SG04"), cloud_row(1, "SG05"),
        cloud_row(1, "SG06"), cloud_row(1, "SG07"), cloud_row(0, "SG08")])
    sg = open_sg(window)
    sg.raw_spins[1335].setValue(6)
    sg.power_spins[1336].setValue(4.5); sg.power_spins[1337].setValue(5.5)
    sg.temp_spins[1338].setValue(2.5); sg.temp_spins[1339].setValue(3.5)
    sg.temp_spins[1340].setValue(-2.5); sg.sg08_combo.setCurrentIndex(1)
    sg.send_values(); wait_for(lambda: window.cloud_write_thread is None)
    expected = (("SG02", "6"), ("SG03", "4.5"), ("SG04", "5.5"),
                ("SG05", "2.5"), ("SG06", "3.5"), ("SG07", "-2.5"), ("SG08", "1"))
    assert CommandApi.created[0].calls == [("write", "device", expected),
        ("readback", "device", [code for code, _ in expected])]
    assert not sg._dirty
    sg.close()


def test_only_sg01_changed_uses_single_member_batch(command_api):
    results, errors = run_commands((("SG01", "7"),))
    assert not errors and results[0]["sequence_complete"]
    assert CommandApi.created[0].calls == [("write", "device", (("SG01", "7"),)),
                                          ("readback", "device", ["SG01"])]


@pytest.mark.parametrize("job_name", ["debug_thread", "sim_thread"])
def test_main_close_waits_for_cloud_auxiliary_thread_even_after_dialog_closed(window, job_name):
    import threading
    from PySide6.QtCore import QThread
    gate = threading.Event()
    class WaitingThread(QThread):
        def run(self):
            gate.wait(3)
    dialog = WarmLinkCloudDialog(window)
    job = WaitingThread(dialog)
    setattr(dialog, job_name, job)
    job.finished.connect(lambda: setattr(dialog, job_name, None))
    job.start()
    window.show()
    dialog.close()  # The active dialog slot is deliberately empty.
    try:
        window.close()
        assert window.isVisible() and job.isRunning()
    finally:
        gate.set()
        wait_for(lambda: not job.isRunning())
    wait_for(lambda: not window.isVisible())
    assert getattr(dialog, job_name) is None
