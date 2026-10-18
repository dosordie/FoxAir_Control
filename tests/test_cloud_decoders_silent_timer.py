"""Decoder/Silent Cloud regressions using synthetic accounts and in-memory APIs."""
import time

import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMessageBox

import foxair_phnix_control as gui
from cloud.cloud_write_helpers import (SILENT_TIMER_CODES, cloud_code_for_register,
    cloud_command_batches, validate_cloud_commands, cloud_readback_matches)
from cloud.warmlink_codes import cloud_hint
from cloud.warmlink_value_translator import parse_cloud_word
from dialogs.decoder_dialogs import ContactDecoderDialog, LoadOutputDecoderDialog
from dialogs.cloud_dialog import WarmLinkCloudDialog
from test_cloud_at_curve_and_csv_cleanup import cloud_only
from test_cloud_single_read_and_values import application, cloud_row
from test_control_transport import command_api, CommandApi
from test_configuration_cloud_writes import run_commands
from test_csv_logger_transport import wait_for
from test_warmlink_request_scheduler import window

CODES = tuple(SILENT_TIMER_CODES.values())
INITIAL = (0, 8, 15, 1, 22, 30)


def capture(window, monkeypatch):
    cloud_only(window)
    requests = []
    monkeypatch.setattr(window, "request_cloud_snapshot", lambda r: requests.append(r))
    return requests


def silent(window, monkeypatch):
    requests = capture(window, monkeypatch)
    window.open_silent_timer_editor()
    dialog = window.silent_timer_dialog
    dialog.initial_read_timer.stop()
    dialog.read_from_wp()
    request = requests[-1]
    dialog.cloud_read_finished(request.cycle_id, [cloud_row(v, c) for c, v in zip(CODES, INITIAL)], "")
    return dialog, requests


@pytest.mark.parametrize("kind,register,code", [
    ("contact", 2034, "S01~S10"), ("load_output", 2019, "O01~023")])
def test_decoder_autoload_binary_manual_poll_and_close(window, monkeypatch, kind, register, code):
    requests = capture(window, monkeypatch)
    window.last_values[register] = 65535
    getattr(window, f"open_{kind}_decoder")()
    dialog = window.contact_dialog if kind == "contact" else window.load_output_dialog
    assert dialog.table.item(0, 1).text() == "--"
    QTest.qWait(300)
    assert len(requests) == 1 and requests[0].codes == (code,)
    # Exercise actual dispatch, not only the dialog callback.
    dispatcher = WarmLinkCloudDialog(window)
    dispatcher._on_targeted_snapshot(requests[0].purpose, requests[0].cycle_id,
        [cloud_row("1000000000000001", code, dataType="BINARY")], "")
    assert dialog.table.item(0, 1).text() == dialog.table.item(15, 1).text() == "1"
    dialog.read_now_btn.click()
    dialog.cloud_read_finished(requests[-1].cycle_id, [cloud_row("512", code)], "")
    assert dialog.table.item(9, 1).text() == "1"
    if kind == "contact":
        assert 15 in dialog._flash_tokens
    dialog.poll_cb.setChecked(True)
    assert dialog.poll_timer.isActive()
    dialog.poll_once(); pending = requests[-1]
    dialog.accept()
    assert pending.cancelled.is_set() and not dialog.poll_timer.isActive()
    dialog.cloud_read_finished(pending.cycle_id, [cloud_row(0, code)], "")
    assert dialog.table.item(9, 1).text() == "1"
    dispatcher.close()


@pytest.mark.parametrize("dialog_class,register", [(ContactDecoderDialog, 2034), (LoadOutputDecoderDialog, 2019)])
@pytest.mark.parametrize("failure", ["missing", "invalid", "stale", "cached", "currentEmpty", "timeout", "error"])
def test_decoder_missing_never_becomes_zero(window, monkeypatch, dialog_class, register, failure):
    requests = capture(window, monkeypatch)
    dialog = dialog_class(window, 77); dialog.show(); dialog.poll_once()
    code = dialog.CLOUD_REGISTERS[register]
    row = cloud_row("bad" if failure == "invalid" else 1, code)
    if failure in ("stale", "cached", "currentEmpty"):
        row[failure] = True
    if failure == "timeout":
        dialog.cloud_request.deadline = time.monotonic() - 1
    dialog.cloud_read_finished(requests[-1].cycle_id, [] if failure == "missing" else [row],
                               "synthetic error" if failure == "error" else "")
    assert dialog.table.item(0, 1).text() == "--"
    assert "unvollständig" in dialog.status_label.text() or "error" in dialog.status_label.text()
    dialog.close()


@pytest.mark.parametrize("dialog_class,register", [(ContactDecoderDialog, 2034), (LoadOutputDecoderDialog, 2019)])
@pytest.mark.parametrize("backend", ["warmlink_raw", "standard_modbus", "display_modbus"])
def test_decoder_local_priority_and_read_path(window, monkeypatch, dialog_class, register, backend):
    window.backend_combo.blockSignals(True)
    window.backend_combo.setCurrentIndex(window.backend_combo.findData(backend))
    window.backend_combo.blockSignals(False)
    window.settings["warmlink_cloud"]["username"] = "user"
    window.set_cloud_connection_state(True, "device")
    window.last_values[register] = 2
    window.cloud_overlay_by_reg[register] = {"raw": 1}
    calls = []
    monkeypatch.setattr(window, "send_read_request", lambda *a, **kw: calls.append((a, kw)))
    monkeypatch.setattr(window, "request_cloud_snapshot", lambda *_: pytest.fail("Local priority"))
    opener = window.open_contact_decoder if register == 2034 else window.open_load_output_decoder
    opener(); dialog = window.contact_dialog if register == 2034 else window.load_output_dialog
    assert dialog.table.item(1, 1).text() == "1"
    dialog.poll_once()
    assert calls[0][0] == (register, 1)
    QTest.qWait(260)
    dialog.close()


@pytest.mark.parametrize("raw,expected", [("1000000000000001", 32769), ("512", 512), ("10", 10),
    (10, 10), (-1, 65535), (65535, 65535), (None, None), ("", None), ("bad", None),
    (65536, None), (-32769, None), (1.5, None), ("nan", None), (True, None)])
def test_word_parser(raw, expected):
    assert parse_cloud_word(raw, {"dataType": "BINARY"}) == expected


def test_silent_autoload_all_six_bypasses_display_prerequisites(window, monkeypatch):
    requests = capture(window, monkeypatch)
    monkeypatch.setattr(window, "_display_wait_for_param_blocks_before_popup",
                        lambda *_: pytest.fail("Cloud must bypass display prerequisites"))
    window.open_onoff_timer_editor()
    dialog = window.silent_timer_dialog
    assert window.onoff_timer_dialog is None
    assert not dialog.send_btn.isEnabled()
    QTest.qWait(300)
    assert len(requests) == 1 and requests[0].codes == CODES
    dispatcher = WarmLinkCloudDialog(window)
    dispatcher._on_targeted_snapshot("silent_timer", requests[0].cycle_id,
        [cloud_row(v, c) for c, v in zip(CODES, INITIAL)], "")
    assert dialog.start_hour.value() == 8 and dialog.stop_enable_cb.isChecked()
    assert not dialog._dirty
    assert not hasattr(dialog, "cloud_test_cb")
    dialog.close(); dispatcher.close()


def test_silent_one_batch_engineering_payload_dirty_and_newer_edit(window, monkeypatch, command_api):
    dialog, _ = silent(window, monkeypatch)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: pytest.fail("No Cloud confirmation"))
    dialog.start_hour.setValue(9); dialog.start_min.setValue(20)
    dialog.send_values()
    assert not dialog.send_btn.isEnabled()
    dialog.start_hour.setValue(10)
    wait_for(lambda: window.cloud_write_thread is None)
    expected = ((CODES[1], "9"), (CODES[2], "20"))
    assert CommandApi.created[0].calls == [("write", "device", expected),
        ("readback", "device", [CODES[1], CODES[2]])]
    assert dialog._dirty == {1245} and dialog.start_hour.value() == 10
    dialog.send_values(); wait_for(lambda: window.cloud_write_thread is None)
    assert not dialog._dirty and not dialog.send_btn.isEnabled()
    dialog.close()


@pytest.mark.parametrize("failure", ["missing", "mismatch", "cached", "stale", "currentEmpty", "timeout"])
def test_silent_partial_readback_keeps_unconfirmed_dirty(window, monkeypatch, command_api, failure):
    dialog, _ = silent(window, monkeypatch)
    original = CommandApi.get_data_by_code
    def read(self, device, codes):
        result = original(self, device, codes)
        if failure == "timeout":
            raise TimeoutError("synthetic read timeout")
        if failure == "missing":
            result["objectResult"].pop()
        elif failure == "mismatch":
            result["objectResult"][-1]["value"] = "1"
        else:
            result["objectResult"][-1][failure] = True
        return result
    monkeypatch.setattr(CommandApi, "get_data_by_code", read)
    dialog.start_hour.setValue(9); dialog.start_min.setValue(20)
    dialog.send_values(); wait_for(lambda: window.cloud_write_thread is None)
    assert 1246 in dialog._dirty
    assert (1245 in dialog._dirty) == (failure == "timeout")
    assert sum(c[0] == "write" for c in CommandApi.created[0].calls) == 1
    assert "fehlt" in dialog.status_label.text()
    dialog.close()


@pytest.mark.parametrize("start,stop", [(0, 0), (0, 1), (1, 0), (1, 1)])
def test_timer_barriers_shared_parameter_batch(command_api, start, stop):
    commands = tuple(zip(CODES, map(str, (start, 9, 20, stop, 23, 45))))
    results, errors = run_commands(commands)
    assert not errors and results[-1]["sequence_complete"]
    groups = cloud_command_batches(commands)
    assert len(groups) == (2 if start == stop else 3)
    calls = CommandApi.created[0].calls
    assert calls == [call for group in groups for call in (
        ("write", "device", group), ("readback", "device", [c for c, _ in group]))]
    assert len(next(g for g in groups if g[0][0] == CODES[1])) == 4
    for code, value in commands:
        if code in (CODES[0], CODES[3]):
            assert (groups[0] if value == "0" else groups[-1]) == tuple(
                x for x in commands if x[0] in (CODES[0], CODES[3]) and x[1] == value)


@pytest.mark.parametrize("failure", ["missing", "mismatch", "cached", "stale", "timeout"])
@pytest.mark.parametrize("activate", [False, True])
def test_timer_failed_barrier_prevents_followup(command_api, monkeypatch, failure, activate):
    original = CommandApi.get_data_by_code
    def read(self, device, codes):
        result = original(self, device, codes)
        if failure == "timeout":
            raise TimeoutError("synthetic")
        if failure == "missing":
            result["objectResult"].clear()
        elif failure == "mismatch":
            result["objectResult"][0]["value"] = "2"
        else:
            result["objectResult"][0][failure] = True
        return result
    monkeypatch.setattr(CommandApi, "get_data_by_code", read)
    commands = ((CODES[0], str(int(activate))), (CODES[1], "9"))
    results, errors = run_commands(commands)
    assert not errors and not results[-1]["sequence_complete"]
    writes = [c for c in CommandApi.created[0].calls if c[0] == "write"]
    assert len(writes) == 1
    expected = ((CODES[1], "9"),) if activate else ((CODES[0], "0"),)
    assert writes[0][2] == expected


@pytest.mark.parametrize("kind", ["contact", "load_output", "silent"])
@pytest.mark.parametrize("action", ["device", "account", "transport", "close", "timeout"])
def test_pending_snapshot_lifecycle(window, monkeypatch, kind, action):
    requests = capture(window, monkeypatch)
    if kind == "silent":
        window.open_silent_timer_editor(); dialog = window.silent_timer_dialog
        read = dialog.read_from_wp
    else:
        getattr(window, f"open_{kind}_decoder")()
        dialog = window.contact_dialog if kind == "contact" else window.load_output_dialog
        read = dialog.poll_once
    dialog.initial_read_timer.stop(); read(); pending = requests[-1]
    if action == "close":
        dialog.close()
    elif action == "device":
        window.set_cloud_connection_state(True, "other")
    elif action == "account":
        window.settings["warmlink_cloud"]["username"] = "other"
        window._notify_control_connection_changed()
    elif action == "transport":
        window.connected = True
        window._notify_control_connection_changed()
    else:
        dialog._cloud_timeout()
    dialog.cloud_read_finished(pending.cycle_id, [cloud_row(1, c) for c in pending.codes], "")
    assert pending.cancelled.is_set()
    if kind == "silent":
        assert not dialog._baseline
    else:
        assert dialog.table.item(0, 1).text() == "--"
    dialog.close()


@pytest.mark.parametrize("action", ["device", "close"])
def test_silent_write_late_reply_cannot_clear_draft(window, monkeypatch, command_api, action):
    dialog, _ = silent(window, monkeypatch)
    dialog.start_hour.setValue(9); dialog.send_values()
    if action == "close":
        dialog.close()
        window.open_silent_timer_editor(); replacement = window.silent_timer_dialog
        replacement.initial_read_timer.stop(); replacement.start_hour.setValue(11)
    else:
        window.set_cloud_connection_state(True, "other")
        replacement = dialog
        replacement.initial_read_timer.stop(); replacement.start_hour.setValue(11)
    wait_for(lambda: window.cloud_write_thread is None)
    assert replacement.start_hour.value() == 11 and 1245 in replacement._dirty
    replacement.close()


def test_silent_partial_autoload_preserves_edits_and_blocks_default_writes(window, monkeypatch):
    requests = capture(window, monkeypatch)
    window.open_silent_timer_editor(); dialog = window.silent_timer_dialog
    dialog.initial_read_timer.stop(); dialog.start_hour.setValue(9); dialog.read_from_wp()
    dialog.cloud_read_finished(requests[-1].cycle_id, [cloud_row(8, CODES[1])], "")
    assert dialog.start_hour.value() == 9 and dialog._dirty == {1245}
    assert not dialog.send_btn.isEnabled()
    monkeypatch.setattr(window, "send_cloud_write", lambda *a, **kw: pytest.fail("Incomplete baseline"))
    dialog.send_values()
    assert "unvollständig" in dialog.status_label.text()
    dialog.close()


@pytest.mark.parametrize("backend", ["warmlink_raw", "standard_modbus", "display_modbus"])
def test_silent_local_write_path_and_delay_unchanged(window, monkeypatch, backend):
    window.backend_combo.blockSignals(True)
    window.backend_combo.setCurrentIndex(window.backend_combo.findData(backend))
    window.backend_combo.blockSignals(False)
    monkeypatch.setattr(window, "_display_wait_for_param_blocks_before_popup", lambda *a: True)
    calls = []
    monkeypatch.setattr(window, "send_timer_values", lambda *a, **kw: calls.append((a, kw)))
    window.open_silent_timer_editor(); dialog = window.silent_timer_dialog
    dialog.timer_delay_ms.setValue(1700); dialog.send_values()
    assert calls[0][0] == (gui.DEFAULT_BUS_ADDR, dialog.timer_values(), 1700)
    dialog.close()


@pytest.mark.parametrize("register,code", list(SILENT_TIMER_CODES.items()))
def test_exact_six_write_grants_and_integer_values(register, code):
    assert cloud_code_for_register(register, require_write_allowed=True) == code
    assert cloud_hint(code)["write_allowed"]
    assert validate_cloud_commands(((code, "1"),)) == ((code, "1"),)
    for value in ("-1", "60", "1.5", "nan"):
        with pytest.raises(ValueError):
            validate_cloud_commands(((code, value),))
    assert not cloud_readback_matches(code, "1", cloud_row(0.6, code))


def test_no_other_timer_or_decoder_write_grants(window):
    cloud_only(window)
    for register in (2019, 2034, *range(1256, 1326)):
        assert cloud_code_for_register(register, require_write_allowed=True) is None
        assert not window.control_can_write(register)


def test_exact_six_member_payload_uses_central_api(monkeypatch):
    from cloud.warmlink_api import WarmLinkCloudApi, ENDPOINT_DEVICE_CONTROL_LANG
    api = WarmLinkCloudApi("user", "unused", initial_token="synthetic-token")
    calls = []
    monkeypatch.setattr(api, "_request_json", lambda endpoint, payload, **kw:
        calls.append((endpoint, payload)) or {"isReusltSuc": True})
    commands = tuple(zip(CODES, map(str, INITIAL)))
    api.write_control_batch("device", commands)
    assert calls == [(ENDPOINT_DEVICE_CONTROL_LANG, {"appId": "16", "param": [
        {"deviceCode": "device", "protocolCode": c, "value": v} for c, v in commands]})]


def test_silent_ui_mixed_disable_and_activation_use_verified_barriers(window, monkeypatch, command_api):
    dialog, _ = silent(window, monkeypatch)
    dialog.start_enable_cb.setChecked(True); dialog.start_hour.setValue(9)
    dialog.stop_enable_cb.setChecked(False); dialog.stop_min.setValue(45)
    dialog.send_values(); wait_for(lambda: window.cloud_write_thread is None)
    groups = (((CODES[3], "0"),), ((CODES[1], "9"), (CODES[5], "45")), ((CODES[0], "1"),))
    assert CommandApi.created[0].calls == [call for group in groups for call in (
        ("write", "device", group), ("readback", "device", [c for c, _ in group]))]
    assert not dialog._dirty
    dialog.close()


@pytest.mark.parametrize("code,value", [(CODES[0], "1"), (CODES[3], "0")])
def test_only_enable_changed_has_one_batch(command_api, code, value):
    results, errors = run_commands(((code, value),))
    assert not errors and results[-1]["sequence_complete"]
    assert CommandApi.created[0].calls == [("write", "device", ((code, value),)),
                                          ("readback", "device", [code])]


def test_autoload_waits_for_write_in_all_three_dialogs(window, monkeypatch):
    requests = capture(window, monkeypatch)
    window.open_contact_decoder(); window.open_load_output_decoder(); window.open_silent_timer_editor()
    dialogs = (window.contact_dialog, window.load_output_dialog, window.silent_timer_dialog)
    window.cloud_write_thread = object()
    try:
        for dialog in dialogs:
            dialog.status_label.setText("Schreiben …")
            dialog.initial_read_timer.start(1)
        QTest.qWait(20)
        assert not requests
        assert all(d.status_label.text() == "Schreiben …" for d in dialogs)
    finally:
        window.cloud_write_thread = None
    QTest.qWait(300)
    assert {r.purpose for r in requests} == {"contact_decoder", "load_output_decoder", "silent_timer"}
    for dialog in dialogs:
        dialog.close()


@pytest.mark.parametrize("code,value", [(CODES[0], 2), (CODES[1], 24), (CODES[2], 60)])
def test_silent_invalid_snapshot_range_blocks_write(window, monkeypatch, code, value):
    requests = capture(window, monkeypatch)
    window.open_silent_timer_editor(); dialog = window.silent_timer_dialog
    dialog.initial_read_timer.stop(); dialog.read_from_wp()
    rows = [cloud_row(value if c == code else v, c) for c, v in zip(CODES, INITIAL)]
    dialog.cloud_read_finished(requests[-1].cycle_id, rows, "")
    assert len(dialog._baseline) == 5 and "unvollständig" in dialog.status_label.text()
    assert not dialog.send_btn.isEnabled()
    dialog.close()


def test_existing_combined_dialog_routes_cloud_silent_and_never_writes_other_timers(window, monkeypatch):
    monkeypatch.setattr(window, "_display_wait_for_param_blocks_before_popup", lambda *a: True)
    window.open_onoff_timer_editor(); combined = window.onoff_timer_dialog
    requests = capture(window, monkeypatch)
    monkeypatch.setattr(window, "send_timer_values", lambda *a, **kw: pytest.fail("No unconfirmed Cloud timers"))
    monkeypatch.setattr(window, "send_read_request", lambda *a, **kw: pytest.fail("No local Cloud-only reads"))
    combined.tabs.setCurrentIndex(6); combined.send_values()
    dialog = window.silent_timer_dialog
    assert dialog.isVisible()
    combined.read_from_wp(); combined.send_all_values()
    assert "lokalen Modbus" in combined.status_label.text()
    combined._start_onoff_timer_read("late local response")
    assert not combined._timer_read_sequence_active
    dialog.close(); combined.close()


def test_decoder_cloud_snapshot_wins_over_old_local_updates_then_restores_local(window, monkeypatch):
    requests = capture(window, monkeypatch)
    window.last_values[2034] = 2
    window.open_contact_decoder(); dialog = window.contact_dialog
    dialog.initial_read_timer.stop(); dialog.poll_once()
    dialog.cloud_read_finished(requests[-1].cycle_id, [cloud_row(1, "S01~S10")], "")
    window._update_contact_table(2)
    assert dialog.table.item(0, 1).text() == "1"
    window.connected = True
    window._notify_control_connection_changed()
    assert dialog.table.item(0, 1).text() == "0" and dialog.table.item(1, 1).text() == "1"
    dialog.close()
