import threading
import time

import pytest
from PySide6.QtCore import QEventLoop, QThread, QTimer

from cloud.logger_snapshot import CloudLoggerSnapshotRequest
from cloud.warmlink_api import WarmLinkCloudApi, WarmLinkCloudError, ENDPOINT_DEVICE_CONTROL
from core.csv_register_logger import logger_cloud_mappings
from core.foxair_phnix_core import crc_bytes_le, decode_frame, find_frames
from core.warmlink_request_scheduler import WarmlinkRequestScheduler
from workers import warmlink_cloud_worker as workers
from dialogs.cloud_dialog import WarmLinkCloudDialog
from test_csv_register_logger import read_csv
from test_cloud_single_read_and_values import application
from test_cloud_polling import fake_api, poll_worker, success
from test_cloud_app_heartbeat import scanned_session, REAL_SETTLE
from test_warmlink_request_scheduler import window


def request(cycle=1, codes=None):
    return CloudLoggerSnapshotRequest(cycle, tuple(codes or logger_cloud_mappings()),
                                      time.monotonic() + 60, "user", "device")


def block_frame(window, words=None, corrupt=False):
    words = [0] * 90 if words is None else words
    payload = b"".join(word.to_bytes(2, "big") for word in words)
    raw = bytes([window._wire_slave_addr(0x63), 3, len(payload)]) + payload
    raw += crc_bytes_le(raw)
    frame = decode_frame(find_frames(bytearray(raw))[0], window.regmap)
    if corrupt:
        frame.crc_ok = False
    return frame


@pytest.mark.parametrize("backend", ["standard_modbus", "warmlink_raw"])
def test_logger_uses_real_central_request_mapping_and_decoder_on_existing_io(window, tmp_path, backend):
    window.backend_combo.blockSignals(True)
    window.backend_combo.setCurrentIndex(window.backend_combo.findData(backend))
    window.backend_combo.blockSignals(False)
    window.unit_spin.setValue(1 if backend == "standard_modbus" else 0x63)
    if window.warmlink_read_scheduler is None:
        window.warmlink_read_scheduler = WarmlinkRequestScheduler(window, window._send_warmlink_read,
            window._warmlink_read_timeout, window._warmlink_queue_log)
    path = tmp_path / f"{backend}.csv"
    controller = window.csv_logger_controller
    io_worker = window.worker
    controller.start(path, 30)
    assert controller.local_request in window.pending_read_requests
    assert controller.local_request["quantity"] == 90
    window.worker._flush_write_queue()
    assert len(window._test_transmitted) == 1
    words = [0] * 90
    words[2048 - 2001] = 453
    words[2034 - 2001] = 65535
    window.on_frame_decoded(block_frame(window, words))
    rows = read_csv(path)
    assert len(rows) == 2 and rows[1][1] == backend
    assert rows[1][rows[0].index("R2048")] == "45.3"
    assert rows[1][rows[0].index("R2034")] == "65535"
    assert window.worker is io_worker and window.connected
    assert "DEBUG Pending-Read" not in window.log_text.toPlainText()
    assert "Datensatz 1 geschrieben" not in window.log_text.toPlainText()
    controller.stop()
    assert window.worker is io_worker and window.connected


def test_bad_crc_response_is_never_a_csv_measurement(window, tmp_path):
    path = tmp_path / "crc.csv"
    controller = window.csv_logger_controller
    controller.start(path, 30)
    window.worker._flush_write_queue()
    window.on_frame_decoded(block_frame(window, [453] * 90, corrupt=True))
    assert len(read_csv(path)) == 1
    controller.cycle_timeout()
    assert read_csv(path)[1][3:] == [""] * 90
    controller.stop()


def test_cloud_one_shot_reuses_worker_api_heartbeat_settle_and_known_subset_without_discovery(fake_api, monkeypatch):
    req = request()
    worker = poll_worker(poll_once=True, session=scanned_session(), logger_request=req)
    snapshots = []
    worker.logger_snapshot.connect(lambda ident, rows, error: snapshots.append((ident, rows, error)))
    monkeypatch.setattr(worker, "_settle_after_heartbeat", lambda: fake_api.created[-1].calls.append("settle") or False)
    worker.run()
    calls = fake_api.created[-1].calls
    assert calls == ["heartbeat", "settle", ("read", list(req.codes))]
    assert len(fake_api.created) == 1 and snapshots[0][0] == req.cycle_id and snapshots[0][2] == ""
    assert snapshots[0][1] and all(row["code"] in req.codes for row in snapshots[0][1])
    assert worker.session.static_codes == ["F23"] and worker.session.live_codes == ["T04"]


def test_real_heartbeat_payload_used_for_logger_has_no_appid(monkeypatch):
    calls = []
    monkeypatch.setattr(WarmLinkCloudApi, "post", lambda api, endpoint, payload: calls.append((endpoint, payload)) or success({}))
    monkeypatch.setattr(WarmLinkCloudApi, "get_data_by_code_batched", lambda api, device, codes, **kw:
                        calls.append(("read", codes)) or success([{"code": "T04", "value": 45.3}]))
    monkeypatch.setattr(workers.WarmLinkCloudWorker, "_settle_after_heartbeat", lambda worker: False)
    worker = poll_worker(poll_once=True, session=scanned_session(), logger_request=request(codes=["T04"]))
    worker.run()
    assert calls == [(ENDPOINT_DEVICE_CONTROL, {"param": [{"deviceCode": "device", "protocolCode": "app_heartbeat", "value": "23205"}]}),
                     ("read", ["T04"])]


def test_logger_response_never_contains_retained_cached_values(fake_api, monkeypatch):
    session = scanned_session()
    session.rows = {"T04": {"code": "T04", "value": 99, "supported": True}}
    monkeypatch.setattr(fake_api, "get_data_by_code_batched", lambda *a, **kw: success([]))
    worker = poll_worker(poll_once=True, session=session, logger_request=request(codes=["T04"]))
    snapshots = []
    worker.logger_snapshot.connect(lambda _id, rows, _error: snapshots.append(rows))
    worker.run()
    assert snapshots[0][0]["supported"] is False
    assert snapshots[0][0]["value"] in (None, "")
    assert worker.session.rows["T04"]["value"] == 99 and worker.session.rows["T04"]["stale"]


def test_logger_wake_preserves_normal_poll_deadline_and_uses_same_api_serially(fake_api, monkeypatch):
    now = [100.0]
    monkeypatch.setattr(workers.time, "monotonic", lambda: now[0])
    # cloud.logger_snapshot.time is the same time module; give the request ample time.
    req = request(codes=["T04"])
    original = fake_api.get_data_by_code_batched
    def read(api, *args, **kwargs):
        now[0] += 4
        return original(api, *args, **kwargs)
    monkeypatch.setattr(fake_api, "get_data_by_code_batched", read)
    worker = poll_worker(session=scanned_session())
    waits, timings, snapshots = [], [], []
    worker.timing_updated.connect(timings.append)
    worker.logger_snapshot.connect(lambda ident, rows, error: snapshots.append((ident, rows, error)))
    def wait(seconds):
        waits.append(seconds)
        if len(waits) == 1:
            now[0] += 2
            worker.request_logger_snapshot(req)
            return False
        return True
    worker._sleep_interruptible = wait
    worker.run()
    assert len(fake_api.created) == 1
    assert fake_api.created[0].calls == ["heartbeat", ("read", ["T04"]), "status", "heartbeat", ("read", ["T04"])]
    deadlines = [state.deadline for state in timings if state.phase == "POLL_WAIT"]
    assert deadlines == [134, 134] and waits == [30, 24]
    assert len(snapshots) == 1 and snapshots[0][0] == req.cycle_id


def test_logger_stop_does_not_stop_polling_and_cancelled_snapshot_does_not_read(fake_api):
    worker = poll_worker(session=scanned_session())
    req = request(codes=["T04"])
    req.cancelled.set()
    worker.request_logger_snapshot(req)
    waits = []
    worker._sleep_interruptible = lambda seconds: waits.append(seconds) or True
    worker.run()
    assert not worker._stop_event.is_set()
    assert fake_api.created[0].calls == ["heartbeat", ("read", ["T04"]), "status"]
    assert waits  # normal polling survived the cancelled logger request


def test_normal_poll_stop_completes_pending_logger_request_without_hanging(fake_api):
    worker = poll_worker(session=scanned_session())
    req = request(codes=["T04"])
    snapshots = []
    worker.logger_snapshot.connect(lambda ident, rows, error: snapshots.append((ident, rows, error)))
    worker.request_logger_snapshot(req)
    worker.stop()
    worker.run()
    assert snapshots and snapshots[0][0] == req.cycle_id and snapshots[0][2]
    assert not fake_api.created


def test_full_scan_request_is_preserved_during_logger_one_shot(fake_api):
    worker = poll_worker(poll_once=True, session=scanned_session(), logger_request=request(codes=["T04"]))
    worker.request_full_scan()
    worker.run()
    reads = [call[1] for call in fake_api.created[-1].calls if isinstance(call, tuple) and call[0] == "read"]
    assert reads == [["T04"], worker.codes]
    assert worker.session.scanned


def test_cloud_error_finishes_cycle_with_no_old_values_and_no_extra_thread(fake_api):
    fake_api.failures = [WarmLinkCloudError("timeout")]
    worker = poll_worker(poll_once=True, session=scanned_session(), logger_request=request(codes=["T04"]))
    snapshots = []
    worker.logger_snapshot.connect(lambda ident, rows, error: snapshots.append((ident, rows, error)))
    worker.run()
    assert len(snapshots) == 1 and snapshots[0][1] == [] and snapshots[0][2]
    assert len(fake_api.created) == 1


def test_real_worker_settle_keeps_gui_responsive_and_does_not_run_in_gui_thread(fake_api, application, monkeypatch):
    thread_ids, sequence = [], []
    read = fake_api.get_data_by_code_batched
    def record(api, *args, **kwargs):
        thread_ids.append(threading.get_ident())
        sequence.append("read")
        return read(api, *args, **kwargs)
    monkeypatch.setattr(fake_api, "get_data_by_code_batched", record)
    monkeypatch.setattr(workers, "WARMLINK_APP_HEARTBEAT_SETTLE_S", 0.06)
    monkeypatch.setattr(workers.WarmLinkCloudWorker, "_settle_after_heartbeat", REAL_SETTLE)
    worker = poll_worker(poll_once=True, session=scanned_session(), logger_request=request(codes=["T04"]))
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)
    loop, timer = QEventLoop(), QTimer()
    beats = []
    timer.timeout.connect(lambda: beats.append(True))
    timer.start(5)
    thread.finished.connect(loop.quit)
    watchdog = QTimer()
    watchdog.setSingleShot(True)
    watchdog.timeout.connect(lambda: (worker.stop(), loop.quit()))
    watchdog.start(2000)
    thread.start()
    loop.exec()
    timer.stop()
    watchdog.stop()
    assert thread.wait(1000)
    assert beats and thread_ids[0] != threading.get_ident()
    assert sequence == ["read"] and fake_api.created[0].calls[0] == "heartbeat"


def wait_for(predicate, timeout_ms=2000):
    loop, poll, watchdog = QEventLoop(), QTimer(), QTimer()
    poll.timeout.connect(lambda: loop.quit() if predicate() else None)
    poll.start(5)
    watchdog.setSingleShot(True)
    watchdog.timeout.connect(loop.quit)
    watchdog.start(timeout_ms)
    if not predicate():
        loop.exec()
    poll.stop()
    watchdog.stop()
    assert predicate()


@pytest.mark.parametrize("polling", [False, True])
def test_main_window_cloud_dialog_routes_logger_on_existing_worker_and_keeps_polling(window, fake_api, monkeypatch, tmp_path, polling):
    window.connected, window.worker = False, None
    window.settings["warmlink_cloud"].update(username="user", selected_device_code="device", save_token=False)
    window.cloud_credentials_cache = {"token": "token", "token_user": "user", "password": "password",
                                     "password_user": "user", "session_password": "password"}
    window.cloud_session = scanned_session()
    window.set_cloud_connection_state(True, "device")
    monkeypatch.setattr(workers, "load_cloud_credentials", lambda user, password, token, **kw: (password, token))
    dialog = window.warmlink_cloud_dialog = WarmLinkCloudDialog(window)
    dialog.codes_edit.setPlainText("\n".join(window.cloud_session.candidates))
    controller = window.csv_logger_controller
    try:
        existing_worker = None
        if polling:
            dialog._start_worker(False)
            wait_for(lambda: fake_api.created and "status" in fake_api.created[0].calls)
            existing_worker = dialog.cloud_worker
        path = tmp_path / "cloud-integration.csv"
        controller.start(path, 30)
        if polling:
            assert dialog.cloud_worker is existing_worker
        wait_for(lambda: controller.writer.rows_written == 1)
        rows = read_csv(path)
        assert rows[1][1] == "cloud" and rows[1][rows[0].index("R2048")] != ""
        assert rows[1][rows[0].index("R2078")] == ""
        controller.stop()
        assert window.is_cloud_connected()
        if polling:
            assert dialog.cloud_worker is existing_worker and dialog.cloud_thread.isRunning()
            assert not existing_worker._stop_event.is_set()
        else:
            wait_for(lambda: dialog.cloud_thread is None)
        assert len(fake_api.created) == 1
    finally:
        controller.stop()
        dialog.stop_worker()
        wait_for(lambda: dialog.cloud_thread is None)
