"""Configuration transport regressions; no requests reach a real heat pump."""
import time

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMessageBox, QTableWidget

import foxair_phnix_control as gui
from cloud.cloud_write_helpers import cloud_code_for_register, cloud_readback_matches
from cloud.warmlink_api import WarmLinkCloudApi
from core.at_compensation import AT_SEVEN_POINT_REGISTERS
from core.warmlink_request_scheduler import WARMLINK_READBACK_TIMEOUT_S
from dialogs.cloud_dialog import WarmLinkCloudDialog
from dialogs.sg_ready_editor_dialog import SGReadyEditorDialog
from workers import warmlink_cloud_worker as workers
from test_cloud_at_curve_and_csv_cleanup import cloud_only, open_at
from test_cloud_single_read_and_values import application, cloud_row
from test_cloud_polling import fake_api
from test_control_transport import command_api, CommandApi
from test_csv_logger_transport import wait_for
from test_warmlink_request_scheduler import window, response


CURVE_CODES = ("CP1-1", "CP1-2", "CP1-3", "compensate_offset", "CP1-5", "CP1-6", "CP1-7")


def open_sg(window):
    window.open_sg_editor()
    window.sg_dialog.initial_read_timer.stop()
    return window.sg_dialog


@pytest.mark.parametrize("pair,code", list(zip(AT_SEVEN_POINT_REGISTERS, CURVE_CODES)))
def test_curve_grants_are_per_code_and_mapping_is_exact(pair, code):
    _, reg = pair
    assert cloud_code_for_register(reg) == code
    assert cloud_code_for_register(reg, True) == code
    assert code != "CP1-4"


def test_app_control_payload_includes_app_id_and_engineering_value():
    api = WarmLinkCloudApi("user", "unused")
    assert api._write_control_primary_payload("device", "CP1-1", "45.5") == {
        "appId": "16", "param": [{"deviceCode": "device", "protocolCode": "CP1-1", "value": "45.5"}]}


@pytest.mark.parametrize("value,expected", [(45.5, True), (45.500000001, True), (45.6, False), (450, False), (float("nan"), False)])
def test_readback_resolution(value, expected):
    assert cloud_readback_matches("CP1-1", "45.5", cloud_row(value, "CP1-1")) is expected


@pytest.mark.parametrize("flag", ["stale", "cached", "currentEmpty"])
def test_stale_readback_is_not_confirmation(flag):
    assert not cloud_readback_matches("SG03", "4.5", cloud_row(4.5, "SG03", **{flag: True}))


def run_commands(commands, guard=None):
    worker = workers.WarmLinkCloudCommandWorker("user", "unused", "device", *commands[0],
        dry_run=False, commands=commands, write_guard=guard)
    results, errors = [], []
    worker.result.connect(results.append); worker.error.connect(errors.append)
    worker.run()
    return results, errors


def test_complete_curve_is_one_batch_and_every_value_verified(command_api):
    commands = tuple((code, str(45.5 - i)) for i, code in enumerate(CURVE_CODES))
    results, errors = run_commands(commands)
    assert not errors and results[-1]["sequence_complete"]
    assert results[-1]["confirmed_codes"] == list(CURVE_CODES)
    assert [c[0] for c in CommandApi.created[0].calls] == ["write", "readback"]
    assert all(r["readback_verified"] for r in results)
    assert all(r["sequence_complete"] for r in results)


@pytest.mark.parametrize("failure", ["missing", "mismatch", "exception", "api"])
def test_readback_failure_stops_before_following_parameter(command_api, monkeypatch, failure):
    def read(self, device, codes):
        self.calls.append(("readback", device, codes))
        if failure == "exception":
            raise TimeoutError("no answer")
        return {"isReusltSuc": failure != "api", "objectResult": [] if failure == "missing"
                else [{"code": codes[0], "value": 12}]}
    monkeypatch.setattr(CommandApi, "get_data_by_code", read)
    results, errors = run_commands((("CP1-1", "45.5"), ("CP1-2", "44.5")))
    assert not errors and len(results) == 2
    assert results[0]["api_success"] and not results[0]["readback_verified"]
    assert not results[0]["sequence_complete"] and results[0]["confirmed_codes"] == []
    assert "Readback bestätigt" in results[0]["validation_error"]
    assert len([c for c in CommandApi.created[0].calls if c[0] == "write"]) == 1
    assert len(CommandApi.created[0].calls) == 4  # one write, three bounded reads


def test_eventually_fresh_readback_retries_only_reads(command_api, monkeypatch):
    original = CommandApi.get_data_by_code
    count = []
    def read(self, device, codes):
        result = original(self, device, codes)
        count.append(1)
        if len(count) == 1:
            result["objectResult"][0]["value"] = 40
        return result
    monkeypatch.setattr(CommandApi, "get_data_by_code", read)
    results, errors = run_commands((("CP1-1", "45.5"),))
    assert not errors and results[0]["sequence_complete"]
    assert [c[0] for c in CommandApi.created[0].calls] == ["write", "readback", "readback"]


def test_partial_success_reports_confirmed_subset(command_api, monkeypatch):
    original = CommandApi.get_data_by_code
    def read(self, device, codes):
        response = original(self, device, codes)
        response["objectResult"] = response["objectResult"][:1]
        return response
    monkeypatch.setattr(CommandApi, "get_data_by_code", read)
    results, _ = run_commands(tuple((c, "45.5") for c in CURVE_CODES[:3]))
    assert len(results) == 3 and results[-1]["confirmed_codes"] == ["CP1-1"]
    assert not results[-1]["sequence_complete"]
    assert len([c for c in CommandApi.created[0].calls if c[0] == "write"]) == 1


@pytest.mark.parametrize("stage", ["write", "readback"])
def test_account_or_device_change_aborts_sequence_after_network_call(command_api, monkeypatch, stage):
    allowed = [True]
    original = CommandApi.write_control_batch if stage == "write" else CommandApi.get_data_by_code
    def changed(self, *args, **kw):
        result = original(self, *args, **kw)
        allowed[0] = False
        return result
    monkeypatch.setattr(CommandApi, "write_control_batch" if stage == "write" else "get_data_by_code", changed)
    results, errors = run_commands((("CP1-1", "45.5"), ("CP1-2", "44.5")), guard=lambda: allowed[0])
    assert errors and not results
    assert len([c for c in CommandApi.created[0].calls if c[0] == "write"]) == 1


def test_at_curve_uses_existing_worker_batch_and_engineering_values(window, monkeypatch, command_api):
    cloud_only(window)
    monkeypatch.setattr(gui, "ask_yes_no", lambda *a, **kw: True)
    at = open_at(window)
    at.mode_combo.setCurrentIndex(at.mode_combo.findData(2))
    assert at.write_curve_btn.isEnabled()
    for i, spin in enumerate(at._seven_spins()):
        spin.setValue(45.5 - i)
    at.write_seven_points()
    wait_for(lambda: window.cloud_write_thread is None)
    calls = CommandApi.created[0].calls
    assert [c[2] for c in calls if c[0] == "write"] == [tuple((c, str(45.5 - i)) for i, c in enumerate(CURVE_CODES))]
    assert "abgeschlossen" in at.status_label.text()
    assert not at.findChildren(QTableWidget)
    window.apply_cloud_rows_to_main([cloud_row(49, "CP1-1")])
    assert at._seven_spins()[0].value() == 49  # Saved fields follow subsequent live changes.
    at.close()


def test_at_live_refresh_preserves_draft_and_explicit_adoption_replaces_it(window):
    cloud_only(window)
    window.apply_cloud_rows_to_main([cloud_row(2, "H36"), cloud_row(40, "CP1-1")])
    at = open_at(window)
    at._seven_spins()[0].setValue(45.5)
    window.apply_cloud_rows_to_main([cloud_row(42, "CP1-1"), cloud_row(43, "CP1-2"), cloud_row(1, "H36")])
    assert at._seven_spins()[0].value() == 45.5
    assert at._seven_spins()[1].value() == 43
    at.apply_live_btn.click()
    assert at._seven_spins()[0].value() == 42 and at.mode_combo.currentData() == 1
    at.close()


def test_at_canvas_drag_emits_and_changes_spin_with_limits(window, application):
    at = open_at(window)
    at.mode_combo.setCurrentIndex(at.mode_combo.findData(2))
    for spin in at._seven_spins():
        spin.setValue(40)
    application.processEvents()
    canvas = at.curve_canvas
    x, y = canvas._screen_points()[1]
    rect, _, _, minimum, maximum = canvas._plot_data()
    dest = QPoint(round(x), round(rect.bottom() - (44.5 - minimum) / (maximum - minimum) * rect.height()))
    QTest.mousePress(canvas, Qt.LeftButton, pos=QPoint(round(x), round(y)))
    QTest.mouseMove(canvas, dest)
    QTest.mouseRelease(canvas, Qt.LeftButton, pos=dest)
    assert abs(at._seven_spins()[1].value() - 44.5) < 0.3
    assert 1251 in at._dirty_registers
    at._curve_point_dragged(1, 999)
    assert at._seven_spins()[1].value() == at._limits()[1]
    at.close()


@pytest.mark.parametrize("backend", ["standard_modbus", "warmlink_raw", "display_modbus"])
def test_sg_cloud_only_snapshot_and_live_values_never_send_local(window, monkeypatch, backend):
    cloud_only(window)
    window.backend_combo.blockSignals(True)
    window.backend_combo.setCurrentIndex(window.backend_combo.findData(backend))
    window.backend_combo.blockSignals(False)
    requests = []
    monkeypatch.setattr(window, "send_read_request", lambda *a, **k: pytest.fail("No local read"))
    monkeypatch.setattr(window, "send_register_write", lambda *a, **k: pytest.fail("No local write"))
    monkeypatch.setattr(window, "_display_wait_for_param_blocks_before_popup", lambda *a: pytest.fail("No display startup"))
    monkeypatch.setattr(window, "request_cloud_snapshot", requests.append)
    sg = open_sg(window)
    sg.read_from_wp(); sg.read_from_wp()
    assert len(requests) == 1 and requests[0].codes == SGReadyEditorDialog.CLOUD_CODES
    rows = [cloud_row(7, "SG01"), cloud_row(4.5, "SG03"), cloud_row(-2.5, "SG07"), cloud_row(0, "SG Status")]
    sg.cloud_read_finished(requests[0].cycle_id, rows, "")
    assert sg.sg_mode_combo.currentData() == 7
    assert sg.power_spins[1336].value() == 4.5 and sg.temp_spins[1340].value() == -2.5
    assert "Wärmepumpe aus oder SG Ready deaktiviert" in sg.sg_status_label.text()
    assert not sg.virtual_sg_combo.isEnabled() and not hasattr(sg, "delay_ms")
    window.apply_cloud_rows_to_main([cloud_row(3, "SG Status")])
    assert "High PV" in sg.sg_status_label.text()
    window.apply_cloud_rows_to_main([cloud_row(0, "SG Status")])
    assert "deaktiviert" in sg.sg_status_label.text()
    assert not window.control_can_write(2133)
    assert not window.control_can_write(8801)
    sg.close()


def test_sg_writes_only_changed_values_with_correct_scaling_and_mode_last(window, monkeypatch, command_api):
    cloud_only(window)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **kw: QMessageBox.Yes)
    sg = open_sg(window)
    window.apply_cloud_rows_to_main([cloud_row(0, "SG01"), cloud_row(4, "SG03"), cloud_row(1, "SG05")])
    sg.sg_mode_combo.setCurrentIndex(sg.sg_mode_combo.findData(7))
    sg.power_spins[1336].setValue(4.5); sg.temp_spins[1338].setValue(2.5)
    sg.send_values()
    wait_for(lambda: window.cloud_write_thread is None)
    assert [c[2] for c in CommandApi.created[0].calls if c[0] == "write"] == [
        (("SG03", "4.5"), ("SG05", "2.5")), (("SG01", "7"),)]
    assert "abgeschlossen" in sg.status_label.text()
    sg.send_values()
    assert len(CommandApi.created) == 1
    window.apply_cloud_rows_to_main([cloud_row(5, "SG03")])
    assert sg.power_spins[1336].value() == 5
    sg.close()


@pytest.mark.parametrize("loss", ["device", "account", "local", "close", "timeout"])
def test_sg_snapshot_cancellation_rejects_old_values(window, monkeypatch, loss):
    cloud_only(window)
    monkeypatch.setattr(window, "request_cloud_snapshot", lambda _: None)
    sg = open_sg(window); sg.read_from_wp(); pending = sg.cloud_request
    if loss == "device": window.set_cloud_connection_state(True, "other-device")
    elif loss == "account":
        window.settings["warmlink_cloud"]["username"] = "other-user"; sg.connection_changed()
    elif loss == "local":
        window.connected = True; sg.connection_changed()
    elif loss == "close": sg.close()
    else: sg._cloud_timeout()
    assert pending.cancelled.is_set()
    sg.cloud_read_finished(pending.cycle_id, [cloud_row(7, "SG01")], "")
    assert 1334 not in window.cloud_overlay_by_reg
    sg.close()


def test_sg_local_queue_retains_transport_spacing_and_skips_unchanged(window, monkeypatch):
    window.backend_combo.setCurrentIndex(window.backend_combo.findData("standard_modbus"))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **kw: QMessageBox.Yes)
    sg = open_sg(window)
    writes = []
    monkeypatch.setattr(window, "send_register_write", lambda *a, **kw: writes.append((a, kw)))
    sg.raw_spins[1335].setValue(5); sg.power_spins[1336].setValue(4.5)
    sg.send_values()
    assert [a[:2] for a, kw in writes] == [(1335, 5), (1336, 45)]
    assert [kw["delay_ms"] for _, kw in writes] == [500, 500]
    assert not hasattr(sg, "cloud_test_cb")
    sg.close()


def test_sg_display_uses_existing_packet_batch_and_sync(window, monkeypatch):
    window.backend_combo.blockSignals(True)
    window.backend_combo.setCurrentIndex(window.backend_combo.findData("display_modbus"))
    window.backend_combo.blockSignals(False)
    monkeypatch.setattr(window, "_display_wait_for_param_blocks_before_popup", lambda *a: True)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **kw: QMessageBox.Yes)
    plans, batches = [], []
    monkeypatch.setattr(window, "_display_timer_batch_plan", lambda values, slave: plans.append(values) or ["packet-plan"])
    monkeypatch.setattr(window, "_send_display_timer_batch", lambda *a: batches.append(a))
    monkeypatch.setattr(window, "send_register_write", lambda *a, **kw: pytest.fail("Use packet batch"))
    sg = open_sg(window); sg.power_spins[1336].setValue(4.5); sg.send_values()
    assert plans == [[(1336, 45, "SG Ready")]]
    assert batches == [(["packet-plan"], 500, "SG Ready")]
    sg.close()


def test_lte_automatic_timeout_is_longer_and_has_single_owner(window):
    window.send_read_request(1158, label="Popup Register 1158", priority="readback")
    scheduler = window.warmlink_read_scheduler
    active = scheduler.active
    assert active["time"] is None and not scheduler.timer.isActive()
    window.worker._flush_write_queue()
    assert window._pending_read_timeout_s(active) == WARMLINK_READBACK_TIMEOUT_S
    assert scheduler.timer.interval() == int(WARMLINK_READBACK_TIMEOUT_S * 1000)
    active["time"] = time.time() - 8  # Old competing wall-time check must not win.
    active["sent_monotonic"] = time.monotonic() - 8
    window._check_pending_read_timeouts()
    assert scheduler.active is active and active in window.pending_read_requests
    window.on_frame_decoded(response(window, 455))
    assert scheduler.active is None and not window.pending_read_requests
    assert window.latest_regs[1158].raw_value == 455


def test_lte_timeout_never_assigns_unresolved_reply_to_next_request(window, application):
    window.send_read_request(1158, priority="readback")
    window.send_read_request(1205)
    window.worker._flush_write_queue()
    old = window.warmlink_read_scheduler.active
    window._warmlink_read_timeout(old)
    assert not window.pending_read_requests and window.warmlink_read_scheduler.unresolved is old
    window.warmlink_read_scheduler.resume_at = 0
    window.warmlink_read_scheduler._dispatch()
    assert window.warmlink_read_scheduler.active is None
    assert not window._apply_pending_read_response(response(window, 455))
    assert window.warmlink_read_scheduler.unresolved is None
    assert 1205 not in window.latest_regs
    window.warmlink_read_scheduler.resume_at = 0
    window.warmlink_read_scheduler._dispatch()
    window.worker._flush_write_queue()
    assert window.warmlink_read_scheduler.active["addr"] == 1205
    assert len(window.pending_read_requests) == 1
    window.on_frame_decoded(response(window, 321))
    assert window.latest_regs[1205].raw_value == 321 and not window.pending_read_requests


def test_at_narrowing_live_limits_preserves_draft_and_prevents_invalid_write(window, monkeypatch):
    cloud_only(window)
    window.apply_cloud_rows_to_main([cloud_row(2, "H36"), cloud_row(5, "R10"), cloud_row(70, "R11")])
    at = open_at(window)
    at._seven_spins()[0].setValue(65)
    window.apply_cloud_rows_to_main([cloud_row(60, "R11"), cloud_row(55, "CP1-1")])
    assert at._seven_spins()[0].value() == 65
    monkeypatch.setattr(gui, "ask_yes_no", lambda *a, **kw: pytest.fail("Invalid curve must not reach confirmation"))
    at.write_seven_points()
    assert "außerhalb R10/R11" in at.status_label.text()
    at.close()


@pytest.mark.parametrize("backend", ["standard_modbus", "warmlink_raw", "display_modbus"])
@pytest.mark.parametrize("mode", [2, 3, 7])
def test_sg_virtual_register_depends_on_selected_transport_and_source(window, monkeypatch, backend, mode):
    window.backend_combo.blockSignals(True)
    window.backend_combo.setCurrentIndex(window.backend_combo.findData(backend))
    window.backend_combo.blockSignals(False)
    monkeypatch.setattr(window, "_display_wait_for_param_blocks_before_popup", lambda *a: True)
    sg = open_sg(window)
    sg.sg_mode_combo.setCurrentIndex(sg.sg_mode_combo.findData(mode))
    available = backend == "standard_modbus" and mode in (3, 7)
    assert sg.virtual_sg_combo.isEnabled() is available
    assert (8801 in [r for r, _, _ in sg.sg_values()]) is available
    assert bool(window.control_can_write(8801)) is (backend == "standard_modbus")
    sg.close()


def test_sg_draft_and_status_update_independently(window):
    cloud_only(window)
    window.apply_cloud_rows_to_main([cloud_row(7, "SG01"), cloud_row(4, "SG03"), cloud_row(1, "SG Status")])
    sg = open_sg(window)
    sg.power_spins[1336].setValue(4.5)
    window.apply_cloud_rows_to_main([cloud_row(5, "SG03"), cloud_row(0, "SG Status")])
    assert sg.power_spins[1336].value() == 4.5
    assert "deaktiviert" in sg.sg_status_label.text()
    sg.load_from_live_values()
    assert sg.power_spins[1336].value() == 5
    sg.close()


def test_sg_disable_is_written_before_dependent_configuration(window, monkeypatch, command_api):
    cloud_only(window)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **kw: QMessageBox.Yes)
    window.apply_cloud_rows_to_main([cloud_row(7, "SG01"), cloud_row(5, "SG02")])
    sg = open_sg(window)
    sg.sg_mode_combo.setCurrentIndex(sg.sg_mode_combo.findData(0))
    sg.raw_spins[1335].setValue(6)
    sg.send_values(); wait_for(lambda: window.cloud_write_thread is None)
    assert [c[2] for c in CommandApi.created[0].calls if c[0] == "write"] == [(("SG01", "0"),), (("SG02", "6"),)]
    sg.close()


def test_lte_corrupt_late_reply_cannot_release_unresolved_request(window):
    window.send_read_request(1158)
    window.worker._flush_write_queue()
    old = window.warmlink_read_scheduler.active
    window._warmlink_read_timeout(old)
    frame = response(window, 455); frame.crc_ok = False
    assert not window._apply_pending_read_response(frame)
    assert window.warmlink_read_scheduler.unresolved is old
    window.warmlink_read_scheduler.cancel()
    assert window.warmlink_read_scheduler.unresolved is None


def test_cp1_1_regular_control_needs_no_experimental_grant(window, monkeypatch):
    cloud_only(window)
    writes = []
    monkeypatch.setattr(window, "send_cloud_write", lambda c, v, **kw: writes.append((c, v)))
    assert window.control_write_register(1250, 455, 45.5) is None
    assert writes == [("CP1-1", "45.5")]
    assert window.control_can_write(1251)


def test_sg_snapshot_runs_through_existing_cloud_worker_and_routes_to_dialog(window, fake_api, monkeypatch):
    cloud_only(window)
    monkeypatch.setattr(workers, "load_cloud_credentials", lambda user, pw, token, **kw: (pw, token))
    cloud = window.warmlink_cloud_dialog = WarmLinkCloudDialog(window)
    sg = open_sg(window)
    try:
        sg.read_from_wp()
        wait_for(lambda: sg.cloud_request is None)
        calls = fake_api.created[0].calls
        reads = [c[1] for c in calls if isinstance(c, tuple) and c[0] == "read"]
        assert reads == [list(SGReadyEditorDialog.CLOUD_CODES)]
        assert len(fake_api.created) == 1
        assert "9/9" in sg.status_label.text()
        assert set(range(1334, 1342)) | {2133} <= set(window.cloud_overlay_by_reg)
        assert 8801 not in window.cloud_overlay_by_reg
    finally:
        sg.close(); cloud.stop_worker()
        wait_for(lambda: cloud.cloud_thread is None)


@pytest.mark.parametrize("kind", ["at", "sg"])
def test_confirmed_write_does_not_clear_newer_draft(window, kind):
    cloud_only(window)
    dialog = open_at(window) if kind == "at" else open_sg(window)
    register = 1250 if kind == "at" else 1336
    spin = dialog._seven_spins()[0] if kind == "at" else dialog.power_spins[1336]
    spin.setValue(40)
    dialog._pending_write_versions = {register: dialog._edit_versions[register]}
    spin.setValue(41)
    dialog.write_readback_confirmed(register)
    dirty = dialog._dirty_registers if kind == "at" else dialog._dirty
    assert register in dirty and spin.value() == 41
    dialog.close()
