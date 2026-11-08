"""Small UI controls reuse the real session/worker and timer encoders with fake I/O."""
import copy
import threading
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QThread
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QCheckBox, QLabel, QMessageBox, QSpinBox

import foxair_phnix_control as gui
from cloud.polling import CloudTimingState
from cloud.token_store import get_password, get_token, set_password, set_token
from dialogs.cloud_dialog import WarmLinkCloudDialog
from test_cloud_decoders_silent_timer import _onoff_cloud
from test_cloud_single_read_and_values import application, cloud_row
from test_cloud_polling import DialogWindow, fake_api
from test_control_transport import command_api, CommandApi
from test_csv_logger_transport import wait_for
from test_warmlink_request_scheduler import window


def configured(window, memory=True):
    window.settings["warmlink_cloud"].update(username="user", selected_device_code="device",
        cached_devices_username="user", cached_devices=[{"deviceCode": "device"}], save_token=True)
    if memory:
        window.cloud_credentials_cache = {"token_user": "user", "token": "synthetic-token",
            "password_user": "user", "password": "unused"}
    return window._ensure_warmlink_cloud_dialog()


def open_local(window, monkeypatch, backend="warmlink_raw"):
    window.backend_combo.blockSignals(True)
    window.backend_combo.setCurrentIndex(window.backend_combo.findData(backend))
    window.backend_combo.blockSignals(False)
    monkeypatch.setattr(window, "_display_wait_for_param_blocks_before_popup", lambda *a: True)
    window.open_onoff_timer_editor()
    dialog = window.onoff_timer_dialog
    dialog.initial_read_timer.stop()
    return dialog


def update(dialog, register, raw):
    dialog.update_from_live_register(SimpleNamespace(reg=register, raw_value=raw))


def test_shortcut_is_compact_and_immediately_after_existing_status_button(window, monkeypatch):
    layout = window.cloud_btn.parentWidget().layout().itemAt(0).layout()
    assert layout.itemAt(layout.indexOf(window.cloud_btn) + 1).widget() is window.cloud_quick_btn
    assert window.cloud_quick_btn.maximumWidth() <= 40
    assert not window.cloud_quick_btn.icon().isNull()
    assert window.cloud_quick_btn.text() == ""
    assert window.cloud_quick_btn.accessibleName() == "Cloud: Verbinden" and window.cloud_quick_btn.isEnabled()
    window.cloud_btn.click()
    assert window.warmlink_cloud_dialog.isVisible()
    for state in ("CONNECTING", "CONNECTED", "POLLING", "ERROR", "DISCONNECTED"):
        if state in ("CONNECTED", "POLLING"):
            window.set_cloud_connection_state(True, "device")
        else:
            window.set_cloud_connection_state(False)
        window.set_cloud_ui_state(state)
        if state == "CONNECTING":
            assert not window.cloud_quick_btn.isEnabled() and "Verbinde" in window.cloud_quick_btn.accessibleName()
        elif state in ("CONNECTED", "POLLING"):
            assert window.cloud_quick_btn.accessibleName() == "Cloud: Trennen" and window.cloud_quick_btn.isEnabled()
        else:
            assert window.cloud_quick_btn.accessibleName() == "Cloud: Verbinden"
        assert window.cloud_quick_btn.animation_timer.isActive() == (state == "POLLING")
        assert window.cloud_quick_btn.text() == ""
        assert not window.cloud_quick_btn.icon().isNull()
        assert window.cloud_quick_btn.toolTip() == window.cloud_quick_btn.accessibleDescription()


@pytest.mark.parametrize("memory", [True, False])
def test_quick_connect_uses_existing_poll_worker_and_saved_device(window, monkeypatch, memory):
    dialog = configured(window, memory)
    if not memory:
        set_password("user", "synthetic-password")
        set_token("user", "synthetic-token")
    starts = []
    monkeypatch.setattr(dialog, "_start_worker", lambda **kw: starts.append((kw, dialog._password(), dialog._initial_token_for_user("user"), dialog._selected_device_code())))
    window.cloud_quick_btn.click()
    wait_for(lambda: bool(starts))
    assert len(starts) == 1 and starts[0][0] == {"poll_once": False} and starts[0][3] == "device"
    assert starts[0][2] == "synthetic-token"
    assert not dialog.isVisible()


@pytest.mark.parametrize("missing", ["username", "device", "foreign_cache", "credentials"])
def test_missing_saved_configuration_opens_original_cloud_dialog(window, monkeypatch, missing):
    dialog = configured(window, memory=missing != "credentials")
    if missing == "username":
        window.settings["warmlink_cloud"]["username"] = ""
    elif missing == "device":
        window.settings["warmlink_cloud"]["selected_device_code"] = "unknown"
    elif missing == "foreign_cache":
        dialog._devices_username = "different-account"
    monkeypatch.setattr(dialog, "_start_worker", lambda *a, **kw: pytest.fail("Missing preflight must not start HTTP"))
    window.cloud_quick_btn.click()
    wait_for(dialog.isVisible)
    assert not dialog._quick_connect_pending
    assert window.cloud_quick_btn.accessibleName() == "Cloud: Verbinden"


def test_slow_keyring_keeps_gui_responsive_and_disconnect_discards_callback(window, monkeypatch):
    dialog = configured(window, memory=False)
    entered, release = threading.Event(), threading.Event()
    from dialogs import cloud_dialog
    def load(*a, **kw):
        entered.set()
        assert release.wait(3)
        return "password", "token"
    monkeypatch.setattr(cloud_dialog, "load_cloud_credentials", load)
    monkeypatch.setattr(dialog, "_start_worker", lambda *a, **kw: pytest.fail("Cancelled preflight"))
    window.cloud_quick_btn.click()
    try:
        wait_for(entered.is_set)
        assert not window.cloud_quick_btn.isEnabled()
        assert dialog._quick_connect_pending
        dialog.disconnect_session()
    finally:
        release.set()
    wait_for(lambda: not dialog._quick_connect_pending)
    QTest.qWait(30)
    assert not window.is_cloud_connected() and window.cloud_quick_btn.accessibleName() == "Cloud: Verbinden"


def test_disconnect_preserves_credentials_tokens_settings_and_cannot_be_revived(window, monkeypatch):
    dialog = configured(window)
    set_password("user", "synthetic-password"); set_token("user", "synthetic-token")
    window.settings["warmlink_cloud"]["auto_start_polling"] = True
    dialog.auto_start_cb.setChecked(True)
    window.set_cloud_connection_state(True, "device"); window.set_cloud_ui_state("POLLING")
    saved_cfg = copy.deepcopy(window.settings["warmlink_cloud"])
    saved_cache = copy.deepcopy(window.cloud_credentials_cache)
    window.cloud_quick_btn.click()
    assert not window.is_cloud_connected() and window.cloud_quick_btn.accessibleName() == "Cloud: Verbinden"
    assert not window._cloud_disconnect_pending and window._cloud_manually_disconnected
    assert window.settings["warmlink_cloud"] == saved_cfg
    assert window.cloud_credentials_cache == saved_cache
    assert get_password("user") == "synthetic-password" and get_token("user") == "synthetic-token"
    dialog._on_connection_state("POLLING")
    dialog._on_devices([{"deviceCode": "late-device"}])
    dialog._on_token_updated("late-token")
    dialog._on_worker_error("401 login")
    window.set_cloud_connection_state(True, "device")
    window._on_cloud_read_data("T01", [cloud_row(99, "T01")])
    window._on_cloud_read_token("late-single-read-token")
    assert not window.is_cloud_connected() and not window.cloud_overlay_by_reg
    assert window.cloud_credentials_cache == saved_cache
    monkeypatch.setattr(dialog, "_start_worker", lambda *a, **kw: pytest.fail("Manual disconnect must suppress delayed autostart"))
    window._autostart_warmlink_cloud_if_enabled()
    dialog._on_worker_status("late worker state")
    assert dialog.status_label.text() == "Cloud-Sitzung getrennt."


@pytest.mark.parametrize("job_name", ["cloud_thread", "debug_thread", "sim_thread", "cloud_read_thread", "cloud_write_thread"])
def test_disconnect_waits_for_normal_thread_cleanup_including_closed_dialog(window, monkeypatch, job_name):
    dialog = configured(window)
    window.set_cloud_connection_state(True, "device")
    entered, release = threading.Event(), threading.Event()
    class WaitingThread(QThread):
        def run(self):
            entered.set()
            release.wait(3)
    owner = window if job_name in ("cloud_read_thread", "cloud_write_thread") else dialog
    thread = WaitingThread(owner)
    setattr(owner, job_name, thread)
    stopped = []
    if job_name == "cloud_thread":
        dialog.cloud_worker = SimpleNamespace(stop=lambda: stopped.append(True))
        thread.finished.connect(dialog._worker_finished)
    else:
        thread.finished.connect(lambda: setattr(owner, job_name, None))
    thread.start()
    try:
        wait_for(entered.is_set)
        if job_name == "debug_thread":
            dialog.close()  # Still a QObject child, though no longer the active slot.
        coordinator = window._ensure_warmlink_cloud_dialog()
        coordinator.disconnect_session()
        assert window._cloud_disconnect_pending and not window.is_cloud_connected()
        assert not window.cloud_quick_btn.isEnabled() and "Trenne" in window.cloud_quick_btn.accessibleName()
        assert window.cloud_ui_state == "DISCONNECTING"
        coordinator.close()
        assert window.warmlink_cloud_dialog is coordinator
        window.set_cloud_ui_state("POLLING")
        assert window.cloud_ui_state == "DISCONNECTING"
    finally:
        release.set()
        wait_for(lambda: getattr(owner, job_name) is None)
        wait_for(lambda: not window._cloud_disconnect_pending)
    assert window.cloud_quick_btn.isEnabled() and window.cloud_quick_btn.accessibleName() == "Cloud: Verbinden"
    assert bool(stopped) == (job_name == "cloud_thread")


def test_disconnect_cancels_snapshot_and_write_guards(window, monkeypatch):
    dialog, requests = _onoff_cloud(window, monkeypatch)
    dialog.read_from_wp(); request = requests[-1]
    window._control_cloud_write_cancelled = threading.Event()
    coordinator = window._ensure_warmlink_cloud_dialog()
    coordinator.disconnect_session()
    assert request.cancelled.is_set() and window._control_cloud_write_cancelled.is_set()
    assert not window.control_can_write(1256) and not window.control_can_read(1256)
    assert "Cloud-Verbindung" in gui.MainWindow.request_cloud_snapshot(window, request)
    assert "Cloud-Steuerverbindung" in window.send_cloud_write("KG1", "256")
    dialog.close()


@pytest.mark.parametrize("backend", ["standard_modbus", "warmlink_raw", "display_modbus"])
def test_quick_disconnect_keeps_local_transport_and_timing_display(window, monkeypatch, backend):
    dialog = configured(window)
    window.backend_combo.blockSignals(True)
    window.backend_combo.setCurrentIndex(window.backend_combo.findData(backend))
    window.backend_combo.blockSignals(False)
    original = (window.connect_btn.isEnabled(), window.disconnect_btn.isEnabled())
    window.set_cloud_connection_state(True, "device")
    window.set_cloud_ui_state("POLLING")
    window.set_cloud_timing_state(CloudTimingState("POLL_WAIT", 60, 60))
    assert window.cloud_progress_bar.property("cloudPhase") == "POLL_WAIT"
    window.cloud_quick_btn.click()
    assert window.control_transport() == backend
    assert original == (window.connect_btn.isEnabled(), window.disconnect_btn.isEnabled())
    assert window.cloud_timing_state.phase == "IDLE"


def test_combined_timer_has_seven_tabs_and_no_removed_inputs(window, monkeypatch):
    dialog = open_local(window, monkeypatch)
    assert dialog.tabs.count() == 7
    assert not hasattr(dialog, "timer_delay_ms") and not hasattr(dialog, "auto_update_cb")
    assert all("day_raw" not in field for field in dialog.fields.values())
    assert not hasattr(dialog, "_day_raw_changed") and not hasattr(dialog, "_day_controls_changed")
    assert not any("Pause zwischen" in w.text() or "Raw:" in w.text() for w in dialog.findChildren(QLabel))
    assert not any(w.text() == "live aktualisieren" for w in dialog.findChildren(QCheckBox))
    assert len(dialog.findChildren(QSpinBox)) == 28  # 6 * 4 times + Silent's 4.
    dialog.close()


@pytest.mark.parametrize("timer_no", range(1, 7))
@pytest.mark.parametrize("backend", ["standard_modbus", "warmlink_raw", "display_modbus"])
def test_single_timer_local_write_keeps_partner_byte_and_fixed_delay(window, monkeypatch, timer_no, backend):
    dialog = open_local(window, monkeypatch, backend)
    register = dialog._mask_reg(timer_no)
    update(dialog, register, 0xA5C3)
    fld = dialog.fields[timer_no]
    fld["active_cb"].setChecked(not fld["active_cb"].isChecked())
    fld["day_checks"][1].setChecked(not fld["day_checks"][1].isChecked())
    values = dialog.timer_values(timer_no)
    raw = values[-1][1]
    assert (raw & 0x00FF if timer_no % 2 == 0 else raw & 0xFF00) == (0xC3 if timer_no % 2 == 0 else 0xA500)
    assert dialog._byte_from_pair_raw(timer_no, raw) == dialog._timer_day_byte_from_controls(timer_no)
    calls = []
    monkeypatch.setattr(window, "send_timer_values", lambda *a, **kw: calls.append((a, kw)))
    dialog.tabs.setCurrentIndex(timer_no - 1); dialog.send_values()
    assert calls == [((gui.DEFAULT_BUS_ADDR, values, 1200), {"title": f"WP Ein/Aus Timer {timer_no}"})]
    dialog.close()


@pytest.mark.parametrize("timer_no", range(1, 7))
def test_automatic_local_mask_update_preserves_draft_and_refreshes_partner(window, monkeypatch, timer_no):
    dialog = open_local(window, monkeypatch)
    register = dialog._mask_reg(timer_no)
    update(dialog, register, 0x8181)
    fld = dialog.fields[timer_no]
    fld["day_checks"][1].setChecked(True)
    desired = dialog._timer_day_byte_from_controls(timer_no)
    fresh = 0xA581 if timer_no % 2 else 0x81A5
    update(dialog, register, fresh)
    assert dialog._timer_day_byte_from_controls(timer_no) == desired
    raw = dialog.timer_values(timer_no)[-1][1]
    assert dialog._byte_from_pair_raw(timer_no + (1 if timer_no % 2 else -1), raw) == 0xA5
    assert timer_no in dialog._local_dirty_days
    update(dialog, register, raw)  # A matching readback clears this timer's draft.
    assert timer_no not in dialog._local_dirty_days
    dialog.close()


@pytest.mark.parametrize("register", [1256, 1257, 1258, 1267, 1244, 1245, 1246, 1247, 1248, 1249])
def test_automatic_local_time_and_silent_updates_preserve_edits_without_focus(window, monkeypatch, register):
    dialog = open_local(window, monkeypatch)
    update(dialog, register, 0)
    if register < 1250:
        widget = dict(zip(range(1244, 1250), (dialog.silent_start_enable_cb, dialog.silent_start_hour,
            dialog.silent_start_min, dialog.silent_stop_enable_cb, dialog.silent_stop_hour, dialog.silent_stop_min)))[register]
    else:
        fld = dialog.fields[(register - 1256) // 2 + 1]
        widget = fld["start_hour" if register % 2 == 0 else "stop_hour"]
    if isinstance(widget, QCheckBox):
        widget.setChecked(True)
    else:
        widget.setValue(9)
    dialog.close_btn.setFocus()
    desired = dialog._cloud_value(register)
    update(dialog, register, 0)
    assert dialog._cloud_value(register) == desired and register in dialog._local_dirty
    update(dialog, register, desired)
    assert register not in dialog._local_dirty
    dialog.close()


def test_local_initial_read_and_manual_reload_use_existing_sequence(window, monkeypatch):
    calls = []
    monkeypatch.setattr(window, "send_read_request", lambda *a, **kw: calls.append((a, kw)))
    dialog = open_local(window, monkeypatch)
    dialog.initial_read_timer.start(1)
    QTest.qWait(20)
    assert [a for a, _ in calls] == [(1244, 6)]
    dialog.on_timer_read_response(dialog.TIMER_READ_LABEL_SILENT, 1244, 6)
    wait_for(lambda: len(calls) == 2)
    assert [a for a, _ in calls] == [(1244, 6), (1256, 15)]
    dialog.read_btn.click()
    assert len(calls) == 3
    dialog.close()


def test_manual_local_cached_reload_resets_draft_explicitly(window, monkeypatch):
    dialog = open_local(window, monkeypatch)
    update(dialog, 1256, gui.encode_hhmm(7, 30))
    dialog.fields[1]["start_hour"].setValue(9)
    window.latest_regs[1256] = SimpleNamespace(reg=1256, raw_value=gui.encode_hhmm(8, 0), value_source="local")
    dialog.load_btn.click()
    assert dialog.fields[1]["start_hour"].value() == 8 and 1256 not in dialog._local_dirty
    dialog.close()


def test_unknown_local_partner_is_not_fabricated_as_zero(window, monkeypatch):
    dialog = open_local(window, monkeypatch)
    with pytest.raises(ValueError, match="Partner-Byte"):
        dialog.timer_values(1)
    dialog.close()


def test_all_local_timers_and_combined_silent_use_fixed_delay(window, monkeypatch):
    dialog = open_local(window, monkeypatch)
    for register in (1268, 1269, 1270):
        update(dialog, register, 0x8181)
    calls = []
    monkeypatch.setattr(window, "send_timer_values", lambda *a, **kw: calls.append((a, kw)))
    dialog.send_all_values()
    dialog.tabs.setCurrentIndex(6); dialog.send_values()
    assert len(calls) == 2 and all(a[2] == 1200 for a, _ in calls)
    assert dict((r, v) for r, v, _ in calls[0][0][1])[1268] == 0x8181
    dialog.close()


def test_cloud_pair_dirty_and_readback_preserve_newer_edits_after_ui_removal(window, monkeypatch, command_api):
    dialog, _ = _onoff_cloud(window, monkeypatch)
    dialog.fields[1]["day_checks"][1].setChecked(True)
    dialog.send_values()
    dialog.fields[2]["day_checks"][2].setChecked(True)
    wait_for(lambda: window.cloud_write_thread is None)
    assert 1268 in dialog._cloud_dirty
    assert dialog._pair_raw_from_controls(1) == 0x8583
    assert CommandApi.created[0].calls[0][2] == (("KG13~KG28", f"{0x8183:016b}"),)
    dialog.close()


def test_real_poll_worker_can_quick_connect_disconnect_and_reconnect(window, monkeypatch, fake_api):
    dialog = configured(window)
    dialog.codes_edit.setPlainText("T04")
    window.cloud_quick_btn.click()
    wait_for(lambda: window.is_cloud_connected() and window.cloud_ui_state == "POLLING")
    assert dialog.cloud_thread is not None and not dialog.isVisible()
    assert window.cloud_quick_btn.animation_timer.isActive()
    window.cloud_quick_btn.click()
    assert not window.is_cloud_connected() and window._cloud_disconnect_pending
    wait_for(lambda: not window._cloud_disconnect_pending)
    assert dialog.cloud_thread is None and not window.cloud_quick_btn.animation_timer.isActive()
    window.cloud_quick_btn.click()
    wait_for(lambda: window.is_cloud_connected() and window.cloud_ui_state == "POLLING")
    assert not window._cloud_manually_disconnected
    window.cloud_quick_btn.click()
    wait_for(lambda: not window._cloud_disconnect_pending)
    assert len(fake_api.created) == 2


def test_stopping_polling_keeps_session_and_shortcut_disconnects_it(window, fake_api):
    dialog = configured(window)
    dialog.codes_edit.setPlainText("T04")
    window.cloud_quick_btn.click()
    wait_for(lambda: window.cloud_ui_state == "POLLING")
    dialog.stop_worker()
    wait_for(lambda: dialog.cloud_thread is None)
    assert window.is_cloud_connected() and window.cloud_quick_btn.accessibleName() == "Cloud: Trennen"
    assert not window.cloud_quick_btn.animation_timer.isActive()
    window.cloud_quick_btn.click()
    assert not window.is_cloud_connected() and window.cloud_quick_btn.accessibleName() == "Cloud: Verbinden"


def test_cancelled_keyring_reply_cannot_satisfy_a_new_connect_attempt(window, monkeypatch):
    dialog = configured(window, memory=False)
    pending, starts = [], []
    monkeypatch.setattr(dialog._keyring, "submit", lambda operation, callback: pending.append(callback))
    monkeypatch.setattr(dialog, "_start_worker", lambda **kw: starts.append(kw))
    window.cloud_quick_btn.click()
    dialog.disconnect_session()
    window.cloud_quick_btn.click()
    assert len(pending) == 2
    pending[0](("obsolete-password", "obsolete-token"), None)
    assert not starts and dialog._quick_connect_pending
    pending[1](("current-password", "current-token"), None)
    assert starts == [{"poll_once": False}] and not dialog._quick_connect_pending
    assert dialog._initial_token_for_user("user") == "current-token"


def test_delayed_autostart_does_not_duplicate_quick_connection(window, monkeypatch):
    dialog = configured(window, memory=False)
    window.settings["warmlink_cloud"]["auto_start_polling"] = True
    pending = []
    monkeypatch.setattr(dialog._keyring, "submit", lambda operation, callback: pending.append(callback))
    monkeypatch.setattr(dialog, "_start_worker", lambda **kw: pytest.fail("Already connecting"))
    window.cloud_quick_btn.click()
    window._autostart_warmlink_cloud_if_enabled()
    assert len(pending) == 1
    dialog.disconnect_session()


def test_disconnect_during_possibly_executed_timer_write_prevents_remaining_batch(window, monkeypatch, command_api):
    dialog, _ = _onoff_cloud(window, monkeypatch)
    dialog.fields[1]["start_hour"].setValue(9)
    dialog.fields[1]["day_checks"][1].setChecked(True)
    entered, release = threading.Event(), threading.Event()
    original = CommandApi.write_control_batch
    def write(self, *args):
        result = original(self, *args)
        entered.set()
        assert release.wait(3)
        return result
    monkeypatch.setattr(CommandApi, "write_control_batch", write)
    previous_values = {reg: info["engineering_value"] for reg, info in window.cloud_overlay_by_reg.items()}
    dialog.send_values()
    try:
        wait_for(entered.is_set)
        coordinator = window._ensure_warmlink_cloud_dialog()
        coordinator.disconnect_session()
        assert window._cloud_disconnect_pending and not window.is_cloud_connected()
    finally:
        release.set()
        wait_for(lambda: window.cloud_write_thread is None)
        wait_for(lambda: not window._cloud_disconnect_pending)
    assert [call[0] for call in CommandApi.created[0].calls] == ["write"]
    assert [code for code, _ in CommandApi.created[0].calls[0][2]] == ["KG1"]
    assert {reg: info["engineering_value"] for reg, info in window.cloud_overlay_by_reg.items()} == previous_values
    assert all(info["stale"] for info in window.cloud_overlay_by_reg.values())
    dialog.close()


def retained_cloud_window():
    owner = DialogWindow()
    dialog = WarmLinkCloudDialog(owner)
    owner.warmlink_cloud_dialog = dialog
    owner.set_cloud_connection_state(True, "device")
    rows = [cloud_row(4.58, "2060", lastFetch="2026-11-08 10:00:00"),
            cloud_row(1234, "T60", lastFetch="2026-11-08 10:00:00")]
    dialog._on_data(rows)
    return owner, dialog


def test_manual_disconnect_retains_display_and_marks_all_caches_stale(application, monkeypatch):
    owner, dialog = retained_cloud_window()
    previous = {reg: (owner.latest_regs[reg], owner.cloud_overlay_by_reg[reg]["value"])
                for reg in (2032, 2060)}
    last_success = owner.cloud_last_success_at
    dialog.session.validated = dialog.session.scanned = True
    dialog.disconnect_session()
    assert not owner.is_cloud_connected() and owner.cloud_ui_state == "DISCONNECTED"
    assert owner.cloud_last_success_at == last_success
    assert not dialog.session.validated and not dialog.session.scanned
    assert all(row["stale"] and row["cached"] for row in dialog.session.rows.values())
    assert all(row["stale"] and row["cached"] for row in dialog.data_rows + owner.cloud_last_rows)
    for reg, (register, value) in previous.items():
        assert owner.latest_regs[reg] is register
        assert owner.cloud_overlay_by_reg[reg]["stale"]
        row = owner.table_rows[reg]
        assert owner.register_table.item(row, 7).text() == value
        assert owner.register_table.item(row, 11).text() == value
        assert "Zuletzt bekannter Cloudwert" in owner.register_table.item(row, 7).toolTip()
        assert "zuletzt bekannt" in owner.register_table.item(row, 14).text()
    # No queued poll/read/write/snapshot path may replace the retained values.
    late = [cloud_row(99, "2060")]
    owner.apply_cloud_rows_to_main(late)
    owner._on_cloud_read_data("2060", late)
    dialog._on_data(late)
    dialog._pending_overlay["2060"] = late[0]
    dialog._flush_overlay_chunk()
    monkeypatch.setattr(owner, "_on_cloud_write_result", lambda *args: pytest.fail("Late write confirmation"))
    owner._on_cloud_write_result_current({"readback_verified": True, "readback": late[0]})
    gui.MainWindow._on_cloud_write_result(owner, "2060", {"readback_verified": True, "readback": late[0]})
    owner.parameter_dialog = SimpleNamespace(cloud_read_finished=lambda *args: pytest.fail("Late snapshot"))
    dialog._on_targeted_snapshot("parameters", 1, late, "")
    owner.parameter_dialog = None
    assert owner.cloud_overlay_by_reg[2060]["engineering_value"] == 4.58
    assert not dialog._pending_overlay
    assert not owner.cloud_change_highlights
    assert not owner.is_cloud_connected()
    dialog.close()


def test_reconnect_replaces_only_observed_cached_values_without_double_scaling(application):
    owner, dialog = retained_cloud_window()
    dialog.disconnect_session()
    owner._cloud_manually_disconnected = False
    owner.set_cloud_connection_state(True, "device")
    dialog._on_data([cloud_row(5.12, "2060", dataType="TEMP", unit="COP", lastFetch="2026-11-08 10:01:00")])
    assert owner.cloud_overlay_by_reg[2060]["engineering_value"] == 5.12
    assert not owner.cloud_overlay_by_reg[2060]["stale"]
    assert owner.cloud_overlay_by_reg[2032]["stale"]
    for row in (dialog.session.rows["2060"], next(r for r in dialog.data_rows if r["code"] == "2060")):
        assert not any(row.get(flag) for flag in ("stale", "cached", "currentEmpty"))
    assert "Zuletzt bekannter" not in owner.register_table.item(owner.table_rows[2060], 7).toolTip()
    assert owner.register_value_sources(2060).local_raw is None
    dialog.close()


@pytest.mark.parametrize("change", ["device", "account"])
def test_retained_cloud_snapshot_does_not_cross_device_or_account(application, change):
    from core.foxair_phnix_core import DecodedRegister
    owner, dialog = retained_cloud_window()
    local = DecodedRegister(0x63, 2060, 0, 3, 321, 321, "3.21 COP", "COP", "COP_X100", 0)
    owner._upsert_register_row(local, False)
    owner.last_values[2060] = 321
    dialog.disconnect_session()
    assert owner.register_value_sources(2060).local_raw == 321
    owner._cloud_manually_disconnected = False
    if change == "account":
        owner.settings["warmlink_cloud"]["username"] = "other-user"
    owner.set_cloud_connection_state(True, "other-device" if change == "device" else "device")
    assert not owner.cloud_overlay_by_reg and not owner.cloud_last_rows and not owner.cloud_session.rows
    assert not dialog.data_rows
    dialog._apply_overlay_to_main()
    assert not owner.cloud_overlay_by_reg
    assert owner.latest_regs[2060] is local and owner.last_values[2060] == 321
    assert 2032 not in owner.latest_regs
    dialog.close()


@pytest.mark.parametrize("error", ["401 login expired", "-100 Please login again"])
def test_authentication_failure_retains_existing_reset_behavior(application, error):
    owner, dialog = retained_cloud_window()
    dialog._on_worker_error(error)
    assert not owner.is_cloud_connected() and owner.cloud_ui_state == "ERROR"
    assert not owner.cloud_overlay_by_reg and not owner.latest_regs
    dialog.close()


def test_explicit_full_reset_still_clears_manually_retained_values(window):
    dialog = configured(window)
    window.set_cloud_connection_state(True, "device")
    window.apply_cloud_rows_to_main([cloud_row(4.58, "2060")])
    dialog.disconnect_session()
    assert 2060 in window.latest_regs
    window.clear_main_window_values()
    assert not window.latest_regs and not window.cloud_overlay_by_reg
    assert window.register_table.rowCount() == 0


def test_main_register_loader_keeps_query_codes_separate_from_t_display(window, tmp_path):
    import json
    expected = {2065: ("T49", "T49"), 2066: ("T50", "T50"), 2067: ("T51", "T51"),
                2023: ("T57", "T57"), 2032: ("T60", "T60"), 2033: ("T65", "T65"),
                2060: ("T200", "2060"), 2054: ("T201", "2054"), 2059: ("T202", "2059"),
                2029: ("T203", "2029"), 2030: ("T204", "2030"), 2031: ("T205", "2031")}
    for register, (display, code) in expected.items():
        assert window.register_defs[str(register)]["code"] == code
        assert window._display_parts_for_register(register)[1] == display
        assert window._validated_cloud_modbus_register(code)[0] == register
    window.apply_cloud_rows_to_main([cloud_row(4.58, "2060"), cloud_row(1.2, "2054"),
                                     cloud_row(5.5, "2059"), cloud_row(1234, "T60")])
    assert {reg: info["engineering_value"] for reg, info in window.cloud_overlay_by_reg.items()} == {
        2060: 4.58, 2054: 1.2, 2059: 5.5, 2032: 1234}
    path = tmp_path / "display-only-and-legacy.json"
    path.write_text(json.dumps({"2060": {"name": "COP", "block": "T", "display_code": "T200"},
                                "1001": {"name": "H01 / Legacy parameter"}}))
    definitions = gui.MainWindow._load_register_defs(SimpleNamespace(regmap_path=str(path)))
    assert "code" not in definitions["2060"]
    assert definitions["1001"]["code"] == "H01"


@pytest.mark.parametrize("change", ["device", "account"])
def test_single_read_response_cannot_cross_cloud_identity(application, change):
    owner, dialog = retained_cloud_window()
    owner._cloud_read_identity = ("user", "device")
    if change == "account":
        owner.settings["warmlink_cloud"]["username"] = "other-user"
    else:
        owner.set_cloud_connection_state(True, "other-device")
    previous = copy.deepcopy(owner.cloud_overlay_by_reg)
    owner._on_cloud_read_data("2060", [cloud_row(99, "2060")])
    owner._on_cloud_read_error("401 login expired")
    owner._on_cloud_read_token("old-token")
    owner._on_cloud_read_login_method("obsolete")
    assert owner.cloud_overlay_by_reg == previous
    assert owner.is_cloud_connected()
    assert owner.settings["warmlink_cloud"].get("login_method") != "obsolete"
    dialog.close()


@pytest.mark.parametrize("flag", ["stale", "cached", "currentEmpty"])
def test_cached_response_is_not_a_successful_single_read_or_recent_fetch(application, flag):
    from test_cloud_single_read_and_values import open_dialog
    owner, dialog = retained_cloud_window()
    quick = open_dialog(owner, 2060)
    owner.cloud_read_reg_no = 2060
    previous_success = owner.cloud_last_success_at
    owner._on_cloud_read_data("2060", [cloud_row(4.58, "2060", **{flag: True})])
    assert "fehlgeschlagen" in quick.status_label.text()
    assert owner.cloud_last_success_at == previous_success
    assert owner.cloud_overlay_by_reg[2060]["stale"]
    quick.close()
    dialog.close()


def test_single_timer_does_not_send_unsaved_local_partner_draft(window, monkeypatch):
    dialog = open_local(window, monkeypatch)
    update(dialog, 1268, 0x8181)
    dialog.fields[1]["day_checks"][1].setChecked(True)
    dialog.fields[2]["day_checks"][2].setChecked(True)
    assert dialog.timer_values(1)[-1][1] == 0x8183
    assert dialog.timer_values(2)[-1][1] == 0x8581
    assert dialog.all_timer_values()[-3][1] == 0x8583
    dialog.close()


def test_raising_existing_timer_dialog_does_not_reload_over_draft(window, monkeypatch):
    dialog = open_local(window, monkeypatch)
    update(dialog, 1256, gui.encode_hhmm(7, 0))
    dialog.fields[1]["start_hour"].setValue(9)
    window.latest_regs[1256] = SimpleNamespace(reg=1256, raw_value=gui.encode_hhmm(8, 0), value_source="local")
    window.open_onoff_timer_editor()
    assert window.onoff_timer_dialog is dialog
    assert dialog.fields[1]["start_hour"].value() == 9 and 1256 in dialog._local_dirty
    dialog.load_btn.click()
    assert dialog.fields[1]["start_hour"].value() == 8 and 1256 not in dialog._local_dirty
    dialog.close()
