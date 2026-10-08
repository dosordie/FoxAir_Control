import os
import threading
import time
from copy import deepcopy

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PySide6.QtCore import QEventLoop, QThread, QTimer
from PySide6.QtWidgets import QApplication

from cloud.polling import CloudSession, classify_cloud_codes
from cloud.warmlink_api import WarmLinkCloudApi, WarmLinkCloudError, WarmLinkAuthError
from cloud.token_store import AsyncKeyringStore
from dialogs.cloud_dialog import WarmLinkCloudDialog
from ui.status_button import CloudStatusButton
from workers import warmlink_cloud_worker as workers
from test_cloud_single_read_and_values import CloudWindow, cloud_row


@pytest.fixture(scope="module")
def application():
    return QApplication.instance() or QApplication([])


def success(items):
    return {"error_code": "0", "isReusltSuc": True, "objectResult": items}


class PollApi:
    created = []
    failures = []

    def __init__(self, user, password, **kwargs):
        self.token = kwargs.get("initial_token") or "new-token"
        self.last_login_method = ""
        self.calls = []
        self.username = user
        self.password = password
        self.__class__.created.append(self)

    success = staticmethod(WarmLinkCloudApi.success)
    message = staticmethod(WarmLinkCloudApi.message)
    _token_expired = staticmethod(WarmLinkCloudApi._token_expired)

    def get_devices(self):
        self.calls.append("devices")
        return success([])

    def get_houses(self):
        self.calls.append("houses")
        return success([{"id": "house-a"}, {"id": "house-b"}])

    def get_house_devices(self, house):
        self.calls.append(("house", house))
        return success({"data": [{"houseRelDeviceList": [{"deviceCode": "device", "deviceNickName": "FoxAir GL9"}]}]})

    def get_data_by_code_batched(self, device, codes, **kwargs):
        self.calls.append(("read", list(codes)))
        if self.failures:
            failure = self.failures.pop(0)
            if failure:
                raise failure
        if kwargs.get("progress"):
            kwargs["progress"](len(codes), len(codes))
        return success([{"code": code, "value": len(self.calls), "unit": "rpm" if code == "F23" else "°C"}
                        for code in codes if code != "unsupported"])

    def get_device_status(self, device):
        self.calls.append("status")
        return success({"isFault": True})

    def send_app_heartbeat(self, device):
        self.calls.append("heartbeat")
        return success({})

    def get_fault_data_by_device_code(self, device):
        pytest.fail("Polling must not fetch fault history")


@pytest.fixture
def fake_api(monkeypatch):
    PollApi.created, PollApi.failures = [], []
    monkeypatch.setattr(workers, "WarmLinkCloudApi", PollApi)
    monkeypatch.setattr(workers.WarmLinkCloudWorker, "_settle_after_heartbeat",
                        lambda worker: worker._stop_event.is_set())
    return PollApi


def poll_worker(**kwargs):
    return workers.WarmLinkCloudWorker("user", "password", ["F23", "T04", "unmapped", "unsupported"],
                                     device_code="device", initial_token="token", **kwargs)


def run_cycles(worker, count=2):
    sleeps = []
    def wait(seconds):
        sleeps.append(seconds)
        return len(sleeps) >= count
    worker._sleep_interruptible = wait
    worker.run()


def test_classification_uses_current_confirmed_mapping():
    groups = classify_cloud_codes(["F23", "T04", "T_unknown", "F_live_name_only"])
    assert groups == {"static": ["F23"], "live": ["T04"], "other": ["T_unknown", "F_live_name_only"]}
    # Mapping takes precedence over the cloud code spelling.
    groups = classify_cloud_codes(["F23"], {"2048": {"code": "F23"}})
    assert groups["live"] == ["F23"]


def test_initial_scan_then_only_live_with_partial_updates(fake_api):
    worker = poll_worker()
    updates, states, progress = [], [], []
    worker.data.connect(updates.append)
    worker.connection_state.connect(states.append)
    worker.progress.connect(lambda phase, done, total: progress.append((phase, done, total)))
    run_cycles(worker)
    reads = [call[1] for call in fake_api.created[-1].calls if isinstance(call, tuple) and call[0] == "read"]
    assert reads == [["F23", "T04", "unmapped", "unsupported"], ["T04"]]
    assert len(updates[0]) == 4 and [row["code"] for row in updates[1]] == ["T04"]
    assert worker.session.static_codes == ["F23"]
    assert worker.session.live_codes == ["T04"]
    assert worker.session.other_codes == ["unmapped"]
    assert worker.session.rows["F23"]["lastFetch"] == updates[0][0]["lastFetch"]
    assert worker.session.rows["F23"]["unit"] == "rpm"
    assert states[0] == "CONNECTING" and states[-1] == "POLLING"
    assert ("READING_INITIAL", 4, 4) in progress and ("READING_LIVE", 1, 1) in progress
    assert ("DISCOVERING", 2, 2) in progress


def test_restart_reuses_validated_device_and_supported_groups(fake_api):
    first = poll_worker(poll_once=True)
    first.run()
    second = poll_worker(poll_once=True, session=first.session)
    second.run()
    calls = fake_api.created[-1].calls
    assert "houses" not in calls and "devices" not in calls
    assert ("read", ["T04"]) in calls
    assert second.session.rows["F23"] == first.session.rows["F23"]
    assert second.session.rows is not first.session.rows


@pytest.mark.parametrize("change", ["account", "device", "manual"])
def test_rediscovery_when_session_is_not_reusable(fake_api, change, monkeypatch):
    first = poll_worker(poll_once=True)
    first.run()
    session = deepcopy(first.session)
    extra = {}
    if change == "account": session.username = "other"
    if change == "device": session.device_code = "other"
    if change == "manual": extra["force_discovery"] = True
    second = poll_worker(poll_once=True, session=session, **extra)
    second.run()
    assert "houses" in fake_api.created[-1].calls
    assert ("read", second.codes) in fake_api.created[-1].calls


def test_manual_configuration_reload_reuses_session(fake_api):
    first = poll_worker(poll_once=True)
    first.run()
    second = poll_worker(poll_once=True, session=first.session, reload_static=True)
    second.run()
    calls = fake_api.created[-1].calls
    assert calls == [("read", ["F23"])]
    assert second.session.rows["T04"] == first.session.rows["T04"]


def test_static_reload_can_wake_running_poll(fake_api):
    worker = poll_worker()
    iterations = []
    def wait(_seconds):
        iterations.append(1)
        if len(iterations) == 1:
            worker.request_static_reload()
            return False
        return True
    worker._sleep_interruptible = wait
    worker.run()
    assert ("read", ["F23"]) in fake_api.created[-1].calls
    assert len(worker.session.rows) == 4


def test_timeout_keeps_static_cache_and_does_not_permanently_red(fake_api):
    first = poll_worker(poll_once=True)
    first.run()
    fake_api.failures = [WarmLinkCloudError("timeout"), None]
    second = poll_worker(session=first.session)
    states, updates = [], []
    second.connection_state.connect(states.append)
    second.data.connect(updates.append)
    run_cycles(second)
    assert "ERROR" not in states and states[-1] == "POLLING"
    assert updates[0][0]["stale"] is True
    assert second.session.rows["F23"] == first.session.rows["F23"]
    assert "houses" not in fake_api.created[-1].calls


@pytest.mark.parametrize("error", [WarmLinkAuthError("401"), WarmLinkCloudError("invalid device")])
def test_access_failure_invalidates_snapshot_and_refreshes_devices_only_for_device_errors(fake_api, error):
    first = poll_worker(poll_once=True)
    first.run()
    fake_api.failures = [error, None]
    second = poll_worker(session=first.session)
    run_cycles(second)
    assert ("houses" in fake_api.created[-1].calls) == (not isinstance(error, WarmLinkAuthError))
    assert ("read", second.codes) in fake_api.created[-1].calls
    assert second.session.validated


def test_batches_report_actual_progress_and_cancel_without_next_call(monkeypatch):
    api = WarmLinkCloudApi("u", "p", initial_token="t")
    calls, progress = [], []
    monkeypatch.setattr(api, "get_data_by_code", lambda device, codes: calls.append(codes) or success([{"code": c, "value": 1} for c in codes]))
    api.get_data_by_code_batched("d", ["a", "b", "c"], batch_size=2, progress=lambda done, total: progress.append((done, total)))
    assert calls == [["a", "b"], ["c"]] and progress == [(2, 3), (3, 3)]
    calls.clear()
    with pytest.raises(WarmLinkCloudError):
        api.get_data_by_code_batched("d", ["a", "b", "c"], batch_size=2, cancelled=lambda: bool(calls))
    assert calls == [["a", "b"]]


class DialogWindow(CloudWindow):
    def __init__(self):
        super().__init__()
        self.settings = {"warmlink_cloud": {"username": "user", "save_token": False, "selected_device_code": "device"}}
        self.cloud_btn = CloudStatusButton(self)
        self.user_data_dir = "."
    def _save_settings(self, **kwargs): pass


def test_ui_merges_partials_and_updates_existing_items_lazily(application, monkeypatch):
    window = DialogWindow()
    dialog = WarmLinkCloudDialog(window)
    dialog.tabs.setCurrentIndex(1)
    dialog.show()
    dialog._on_data([cloud_row(55), cloud_row(20, "T04")])
    first = dialog.data_table.item(0, 2)
    static_row = deepcopy(dialog.data_rows[0])
    calls = []
    monkeypatch.setattr(dialog, "refresh_compare", lambda: calls.append("compare"))
    monkeypatch.setattr(dialog, "refresh_finder_codes", lambda: calls.append("finder"))
    monkeypatch.setattr(dialog.data_table, "resizeColumnsToContents", lambda: pytest.fail("No resize for a partial poll"))
    dialog._on_data([cloud_row(22, "T04")])
    assert len(dialog.data_rows) == 2 and dialog.data_rows[0] == static_row
    assert dialog.data_table.item(0, 2) is first
    assert dialog.data_table.item(1, 2).text() == "22"
    assert calls == []
    dialog.tabs.setCurrentIndex(2)
    assert calls == ["compare"]
    dialog.hide()
    dialog._on_data([cloud_row(23, "T04")])
    assert calls == ["compare"]
    assert window.cloud_overlay_by_reg[2048]["engineering_value"] == 23
    dialog.show()
    assert calls == ["compare", "compare"]
    dialog.close()


@pytest.mark.parametrize("state", ["DISCONNECTED", "CONNECTING", "CONNECTED", "POLLING", "ERROR"])
def test_cloud_button_distinct_states_and_safe_tooltip(application, state):
    window = DialogWindow()
    window.set_cloud_ui_state(state, device_name="FoxAir GL9", last_success_at=100000)
    assert window.cloud_btn.property("cloudState") == state
    assert window.cloud_btn.property("pollingActive") == (state == "POLLING")
    assert window.cloud_btn.animation_timer.isActive() == (state == "POLLING")
    assert "FoxAir GL9" in window.cloud_btn.toolTip()
    assert "device" not in window.cloud_btn.toolTip()
    assert window.cloud_btn.styleSheet()


def test_credential_work_does_not_block_qt_heartbeat(application):
    owner = DialogWindow()
    store = AsyncKeyringStore(owner)
    gate = threading.Event()
    thread_ids, beats, results = [], [], []
    loop = QEventLoop()
    timer = QTimer()
    timer.setInterval(5)
    timer.timeout.connect(lambda: beats.append(1))
    timer.start()
    def os_provider():
        thread_ids.append(threading.get_ident())
        gate.wait(1)
        return "loaded"
    def done(value, error):
        results.append((value, error, threading.get_ident()))
        loop.quit()
    store.submit(os_provider, done)
    QTimer.singleShot(60, gate.set)
    QTimer.singleShot(2000, loop.quit)
    loop.exec()
    timer.stop()
    assert len(beats) >= 3
    assert thread_ids != [threading.get_ident()]
    assert results == [("loaded", None, threading.get_ident())]


def test_cloud_start_has_heartbeat_and_stop_during_slow_keyring(application, monkeypatch, fake_api):
    gate = threading.Event()
    def load(*args, **kwargs):
        gate.wait(1)
        return "password", "token"
    monkeypatch.setattr(workers, "load_cloud_credentials", load)
    window = DialogWindow()
    dialog = WarmLinkCloudDialog(window)
    dialog.password_edit.clear()
    loop, beats = QEventLoop(), []
    timer = QTimer()
    timer.setInterval(5)
    timer.timeout.connect(lambda: beats.append(1))
    dialog._start_worker(False)
    assert dialog.cloud_thread is not None and dialog.stop_poll_btn.isEnabled()
    dialog.cloud_thread.finished.connect(loop.quit)
    timer.start()
    QTimer.singleShot(30, dialog.stop_worker)
    QTimer.singleShot(80, gate.set)
    QTimer.singleShot(2000, loop.quit)
    loop.exec()
    timer.stop()
    assert len(beats) >= 3 and fake_api.created == []
    assert dialog.cloud_thread is None
    assert dialog.start_poll_btn.isEnabled()
    dialog.close()


def test_confirmed_raw_fault_words_remain_in_the_live_group():
    from cloud.warmlink_codes import cloud_hint
    from cloud.register_resolver import resolve_cloud_register
    codes = [f"Fault{i}" for i in range(1, 11)]
    assert classify_cloud_codes(codes)["live"] == codes
    assert [resolve_cloud_register(code, cloud_hint(code)) for code in codes] == list(range(2081, 2091))
    assert all(cloud_hint(code)["confidence"] == "confirmed" and not cloud_hint(code)["write_allowed"] for code in codes)
    assert classify_cloud_codes(["Fault11", "T_unknown"])["other"] == ["Fault11", "T_unknown"]


def test_initial_table_and_overlay_render_yield_between_batches(application):
    from cloud.warmlink_codes import WARMLINK_644_DISCOVERY_CODES
    window = DialogWindow()
    dialog = WarmLinkCloudDialog(window)
    dialog.tabs.setCurrentIndex(1)
    dialog.show()
    rows = [cloud_row(1, code) for code in WARMLINK_644_DISCOVERY_CODES[:120]]
    dialog._on_data(rows)
    assert dialog._pending_data_rows and dialog._pending_overlay
    assert dialog.data_table.rowCount() == 120
    loop = QEventLoop()
    turns = []
    def tick():
        turns.append(1)
        if dialog._pending_data_rows or dialog._pending_overlay:
            QTimer.singleShot(0, tick)
        else:
            loop.quit()
    QTimer.singleShot(0, tick)
    QTimer.singleShot(2000, loop.quit)
    loop.exec()
    assert len(turns) >= 2 and not dialog._pending_data_rows and not dialog._pending_overlay
    assert dialog.data_table.item(119, 2) is not None
    dialog.close()


def test_single_read_updates_static_cache_and_survives_live_snapshot(application):
    window = DialogWindow()
    dialog = WarmLinkCloudDialog(window)
    window.warmlink_cloud_dialog = dialog
    dialog.session = CloudSession(username="user", device_code="device", scanned=True,
                                  static_codes=["R02"], live_codes=["T04"])
    dialog._on_data([cloud_row(55, lastFetch="2026-10-05 12:00:00"), cloud_row(20, "T04")])
    old_snapshot = deepcopy(dialog.session)
    window.cloud_read_reg_no, window.cloud_read_code = 1158, "R02"
    window._on_cloud_read_data("R02", [cloud_row(54, lastFetch="2026-10-05 12:00:01")])
    dialog._on_session_updated(old_snapshot)
    dialog._on_data([cloud_row(21, "T04")])
    assert dialog.session.rows["R02"]["value"] == 54
    assert dialog.data_rows[0]["value"] == 54
    dialog.close()


def test_polling_progress_has_nonmodal_determinate_batch_state(application):
    window = DialogWindow()
    dialog = WarmLinkCloudDialog(window)
    dialog._on_progress("CONNECTING", 0, 0)
    assert dialog.progress_bar.maximum() == 0
    dialog._on_progress("READING_INITIAL", 50, 420)
    assert dialog.progress_bar.value() == 50 and dialog.progress_bar.maximum() == 420
    assert not dialog.isModal()
    dialog.close()


def test_session_token_is_reusable_without_keyring_persistence(application):
    window = DialogWindow()
    dialog = WarmLinkCloudDialog(window)
    dialog._cloud_token_username, dialog._cloud_token = "user", "memory-token"
    assert not dialog.save_token_cb.isChecked()
    assert dialog._initial_token_for_user("user") == "memory-token"
    assert dialog._initial_token_for_user("other") is None
    dialog.close()


def test_token_renewal_invalidates_static_snapshot_then_reads_full_catalog(fake_api, monkeypatch):
    first = poll_worker(poll_once=True)
    first.run()
    original = fake_api.get_data_by_code_batched
    def renewing(api, device, codes, **kwargs):
        result = original(api, device, codes, **kwargs)
        api.token = "renewed-token"
        return result
    monkeypatch.setattr(fake_api, "get_data_by_code_batched", renewing)
    second = poll_worker(session=first.session)
    run_cycles(second, count=1)
    reads = [call[1] for call in fake_api.created[-1].calls if isinstance(call, tuple) and call[0] == "read"]
    assert reads == [["T04"], second.codes]
    assert "houses" not in fake_api.created[-1].calls
    assert second.session.scanned


def test_device_change_removes_cloud_only_values_but_keeps_local(application):
    from core.foxair_phnix_core import DecodedRegister
    window = DialogWindow()
    window.apply_cloud_rows_to_main([cloud_row(55), cloud_row(20, "T04")])
    local = DecodedRegister(0x63, 1158, 0, 3, 550, 550, "55 °C", "R02", "TEMP1", time.time())
    window._upsert_register_row(local, False)
    window.clear_cloud_device_values()
    assert window.latest_regs == {1158: local}
    assert window.register_table.rowCount() == 1
    assert not window.cloud_overlay_by_reg and not window.cloud_last_rows


def test_invalid_saved_device_does_not_win_rediscovery(fake_api, monkeypatch):
    first = poll_worker(poll_once=True)
    first.run()
    original = fake_api.get_data_by_code_batched
    read_devices = []
    def reading(api, device, codes, **kwargs):
        read_devices.append(device)
        if device == "device":
            raise WarmLinkCloudError("invalid device")
        return original(api, device, codes, **kwargs)
    monkeypatch.setattr(fake_api, "get_data_by_code_batched", reading)
    monkeypatch.setattr(fake_api, "get_house_devices", lambda api, house: success({"data": [{"houseRelDeviceList": [{"deviceCode": "replacement"}]}]}))
    second = poll_worker(session=first.session)
    run_cycles(second)
    assert read_devices == ["device", "replacement"]
    assert second.session.device_code == "replacement" and second.session.validated


def test_gui_selection_tracks_worker_selected_device(application):
    window = DialogWindow()
    dialog = WarmLinkCloudDialog(window)
    dialog.session = CloudSession(username="user", device_code="replacement")
    dialog._on_devices([{"deviceCode": "device"}, {"deviceCode": "replacement"}])
    assert dialog._selected_device_code() == "replacement"
    assert window.cloud_session_device_code == "replacement"
    dialog.close()


def test_initial_no_supported_codes_stops_without_repeated_full_scans(fake_api, monkeypatch):
    monkeypatch.setattr(fake_api, "get_data_by_code_batched", lambda *args, **kwargs: success([]))
    worker = poll_worker()
    errors, states = [], []
    worker.error.connect(errors.append)
    worker.connection_state.connect(states.append)
    worker.run()
    assert len(errors) == 1 and states[-1] == "ERROR"
    assert not worker.session.validated and not worker.session.scanned


def test_status_relogin_also_refreshes_configuration_snapshot(fake_api, monkeypatch):
    first = poll_worker(poll_once=True)
    first.run()
    original = fake_api.get_device_status
    def renewing(api, device):
        api.token = "renewed-status-token"
        return original(api, device)
    monkeypatch.setattr(fake_api, "get_device_status", renewing)
    second = poll_worker(session=first.session)
    run_cycles(second, count=1)
    reads = [call[1] for call in fake_api.created[-1].calls if isinstance(call, tuple) and call[0] == "read"]
    assert reads == [["T04"], second.codes]
    assert second.session.scanned
