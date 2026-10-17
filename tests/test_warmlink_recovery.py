"""Lost FC03 recovery using real ReaderWorkers/QThreads and simulated TCP streams."""
import queue
import socket
import threading
import time

import pytest
from PySide6.QtTest import QSignalSpy
from PySide6.QtGui import QCloseEvent
from types import SimpleNamespace

import foxair_phnix_control as gui
from core import warmlink_request_scheduler as scheduling
from core.foxair_phnix_core import crc_bytes_le
from test_warmlink_request_scheduler import application, window, request, response, wait
from test_csv_logger_transport import wait_for


def reply(value, quantity=1):
    data = bytes([0x63, 3, quantity * 2]) + value.to_bytes(2, "big") * quantity
    return data + crc_bytes_le(data)


class SimulatedTCP:
    def __init__(self, *, fail=False, late_on_close=False):
        self.incoming = queue.Queue()
        self.sent = []
        self.closed = False
        self.fail = fail
        self.late_on_close = late_on_close
        self.connected = False

    def connect(self):
        if self.fail:
            raise OSError("simulated LTE connection failure")
        self.connected = True

    def is_connected(self):
        return self.connected and not self.closed

    def close(self):
        if not self.closed:
            self.closed = True
            self.incoming.put(reply(999) if self.late_on_close else b"")

    def recv(self, size):
        try:
            return self.incoming.get(timeout=0.01)
        except queue.Empty:
            raise socket.timeout()

    def send(self, data):
        if self.closed:
            raise OSError("closed simulated stream")
        self.sent.append(data)


@pytest.fixture
def connection(window, monkeypatch):
    old = window.worker
    old.running = False
    window.worker = None
    window.connected = False
    window.host_edit.setText("simulated.invalid")
    window.write_bus_edit.setText("0x63")
    window.settings.setdefault("backend_settings", {}).setdefault("warmlink_raw", {})["transport"] = "tcp"
    window.settings["auto_read_init_on_startup"] = False
    window.settings["auto_poll_live_values"] = True
    clients = []
    failures = set()
    def client(*args, **kwargs):
        value = SimulatedTCP(fail=len(clients) in failures, late_on_close=not clients)
        clients.append(value)
        return value
    monkeypatch.setattr(gui, "WarmlinkSocketClient", client)
    monkeypatch.setattr(gui, "WARMLINK_RECONNECT_DELAYS_MS", (10, 15, 20))
    monkeypatch.setattr(scheduling, "WARMLINK_LOST_RESPONSE_GRACE_MS", 30)
    monkeypatch.setattr(scheduling, "WARMLINK_TIMEOUT_DRAIN_MS", 20)
    window.connect_to_device()
    wait_for(lambda: window.connected)
    yield window, clients, failures
    window.disconnect_from_device()
    wait_for(lambda: window.thread is None)
    assert not window._warmlink_reconnect_timer.isActive()


def send_and_lose(window, address=1158, **kwargs):
    window.send_read_request(address, label="Auto-Poll lost", **kwargs)
    wait_for(lambda: window.warmlink_read_scheduler.active is not None
             and window.warmlink_read_scheduler.active["sent_monotonic"] is not None)
    lost = window.warmlink_read_scheduler.active
    window.warmlink_read_scheduler._timeout()
    assert window.warmlink_read_scheduler.unresolved is lost
    assert not window.pending_read_requests
    return lost


@pytest.mark.parametrize("priority", ["background", "readback"])
def test_lost_reply_reconnects_and_queued_read_succeeds(connection, priority):
    window, clients, _ = connection
    old_worker = window.worker
    old_guard = window._reader_signal_guard
    finished = QSignalSpy(window.thread.finished)
    send_and_lose(window, priority=priority)
    queued = window.send_read_request(1205, label="Auto-Poll following")
    wait_for(lambda: len(clients) == 2 and window.connected)
    assert clients[0].closed and finished.count() == 1
    assert window.worker is not old_worker
    assert window.worker.buf == b""
    assert window.live_poll_timer.isActive()
    assert window.warmlink_read_scheduler.unresolved is None
    wait_for(lambda: queued.get("sent_monotonic") is not None)
    assert window.warmlink_read_scheduler.active is queued
    assert len(window.pending_read_requests) == 1
    assert 1158 not in window.latest_regs  # Last recv on the old socket was discarded.
    # A delivery queued by the retired worker must not match the new qty=1 read.
    old_guard.frame(response(window, 777))
    old_guard.sent(1205, 1, 0x63)
    old_guard.failed(1205, 1, 0x63, "stale failure")
    old_guard.disconnected()
    assert window.connected and window.warmlink_read_scheduler.active is queued
    assert 1205 not in window.latest_regs
    clients[1].incoming.put(reply(321))
    wait_for(lambda: 1205 in window.latest_regs)
    assert window.latest_regs[1205].raw_value == 321
    assert window.warmlink_read_scheduler.active is None
    assert not window.pending_read_requests and window._warmlink_recovery_attempts == 0
    # A new ordinary background poll also uses and completes on the fresh stream.
    window._live_poll_tick()
    wait_for(lambda: window.warmlink_read_scheduler.active is not None
             and window.warmlink_read_scheduler.active["sent_monotonic"] is not None)
    active = window.warmlink_read_scheduler.active
    clients[1].incoming.put(reply(123, active["quantity"]))
    try:
        wait_for(lambda: window.warmlink_read_scheduler.active is None)
    except AssertionError:
        pytest.fail(window.log_text.toPlainText()[-6000:])
    assert window.latest_regs[active["addr"]].raw_value == 123


def test_late_reply_before_recovery_cancels_reconnect(connection):
    window, clients, _ = connection
    window.warmlink_read_scheduler.recovery_timer.setInterval(1000)
    send_and_lose(window)
    window.warmlink_read_scheduler.recovery_timer.start(1000)
    clients[0].incoming.put(reply(455))
    wait_for(lambda: window.warmlink_read_scheduler.unresolved is None)
    assert not window.warmlink_read_scheduler.recovery_timer.isActive()
    following = window.send_read_request(1205)
    wait_for(lambda: following.get("sent_monotonic") is not None)
    assert len(clients) == 1
    clients[0].incoming.put(reply(322))
    wait_for(lambda: 1205 in window.latest_regs)
    assert 1158 not in window.latest_regs and window.latest_regs[1205].raw_value == 322


def test_old_unsent_writes_are_discarded_and_never_replayed(connection):
    window, clients, _ = connection
    send_and_lose(window)
    old_worker = window.worker
    old_worker.next_write_monotonic = time.monotonic() + 100
    window.send_register_write(1336, 45, label="SG Ready")
    assert window.pending_write_requests and not old_worker.write_queue.empty()
    following = window.send_read_request(1205)
    wait_for(lambda: len(clients) == 2 and window.connected)
    wait_for(lambda: following.get("sent_monotonic") is not None)
    assert not window.pending_write_requests
    assert old_worker.write_queue.empty()
    assert all(frame[1] == 3 for stream in clients for frame in stream.sent)
    clients[1].incoming.put(reply(123))
    wait_for(lambda: not window.pending_read_requests)


def test_failed_connection_attempts_stop_at_limit(connection):
    window, clients, failures = connection
    failures.update({1, 2, 3, 4})
    send_and_lose(window)
    window.send_read_request(1205, label="Auto-Poll queued")
    wait_for(lambda: len(clients) == 4 and window.thread is None
             and window._warmlink_recovery is None)
    wait(80)
    assert len(clients) == 4  # Original connection + exactly three attempts.
    assert not window.connected and not window.live_poll_timer.isActive()
    window._update_init_read_progress()
    assert "fehlgeschlagen" in window.status_label.text()
    assert not window.pending_read_requests and not window.warmlink_read_scheduler.queue
    assert not window.warmlink_read_scheduler.recovery_timer.isActive()
    failures.clear()
    window.connect_to_device()  # Explicit user reconnect starts a fresh budget.
    wait_for(lambda: window.connected)
    req = window.send_read_request(1205)
    wait_for(lambda: req.get("sent_monotonic") is not None)
    clients[-1].incoming.put(reply(456))
    wait_for(lambda: 1205 in window.latest_regs)
    assert window.latest_regs[1205].raw_value == 456


def test_successful_reconnect_does_not_reset_budget_without_successful_read(connection):
    window, clients, _ = connection
    for _ in range(3):
        count = len(clients)
        send_and_lose(window)
        wait_for(lambda: len(clients) == count + 1 and window.connected)
    send_and_lose(window)
    wait_for(lambda: window.thread is None and window._warmlink_recovery is None)
    assert len(clients) == 4 and "fehlgeschlagen" in window.status_label.text()


@pytest.mark.parametrize("action", ["disconnect", "backend", "settings", "capture", "close"])
def test_recovery_backoff_is_cancelled_by_user_or_context_change(connection, action):
    window, clients, _ = connection
    window._warmlink_reconnect_timer.setInterval(1000)
    send_and_lose(window)
    wait_for(lambda: window.thread is None and window._warmlink_reconnect_timer.isActive())
    window._warmlink_reconnect_timer.stop()
    if action == "disconnect":
        assert window.disconnect_btn.isEnabled()
        window.disconnect_btn.click()
    elif action == "backend":
        window.backend_combo.setCurrentIndex(window.backend_combo.findData("standard_modbus"))
        window._backend_changed()
    elif action == "settings":
        window.host_edit.setText("changed.invalid")
    elif action == "capture":
        window.settings["warmlink_raw_capture"] = {"enabled": True, "mode": "firmware"}
        window._set_firmware_capture_guard(True)
    else: window.close()
    window._attempt_warmlink_reconnect()  # Also reject an already queued timer callback.
    wait(50)
    assert len(clients) == 1 and window._warmlink_recovery is None
    assert not window.warmlink_read_scheduler.queue


def test_recovery_waits_for_old_thread_finished_before_connecting(connection, monkeypatch):
    window, clients, _ = connection
    gate = threading.Event()
    old_recv = clients[0].recv
    entered = threading.Event()
    def delayed_recv(size):
        data = old_recv(size)
        entered.set()
        gate.wait(timeout=1)
        return data
    clients[0].recv = delayed_recv
    send_and_lose(window)
    try:
        wait_for(entered.is_set)
        wait(70)
        assert len(clients) == 1 and window.thread is not None
        assert window.warmlink_read_scheduler.recovering
    finally:
        gate.set()
    wait_for(lambda: len(clients) == 2 and window.connected)


def test_scheduler_reserves_queue_until_new_transport_and_keeps_priority(application):
    owner = gui.QObject()
    sent, recoveries = [], []
    scheduler = scheduling.WarmlinkRequestScheduler(owner, sent.append, lambda _: None,
                                                   lambda _: None, recoveries.append)
    lost, background, readback = request(1158), request(2001), request(1205)
    scheduler.submit(lost); scheduler.sent(1158, 1, 0x63)
    scheduler.submit(background, "background"); scheduler.submit(readback, "readback")
    scheduler._timeout(); scheduler.recovery_timer.stop(); scheduler._recover_lost_response()
    assert recoveries == [lost] and sent == [lost]
    scheduler.unmatched_response(0x63, 2)
    scheduler._dispatch()
    assert scheduler.unresolved is lost and sent == [lost]
    scheduler.transport_reconnected(); scheduler.resume_at = 0; scheduler._dispatch()
    assert sent == [lost, readback] and not scheduler.recovering
    scheduler.cancel()


def test_corrupt_or_foreign_late_frames_cannot_cancel_recovery(connection):
    window, clients, _ = connection
    lost = send_and_lose(window)
    corrupt = response(window, 888); corrupt.crc_ok = False
    window.on_frame_decoded(corrupt)
    window.on_frame_decoded(response(window, 888, slave=0x64))
    assert window.warmlink_read_scheduler.unresolved is lost
    assert window.warmlink_read_scheduler.recovery_timer.isActive()
    queued = window.send_read_request(1205)
    wait_for(lambda: len(clients) == 2 and window.connected)
    wait_for(lambda: queued.get("sent_monotonic") is not None)
    clients[1].incoming.put(reply(123))
    wait_for(lambda: 1205 in window.latest_regs)
    assert 1158 not in window.latest_regs


def test_declined_recovery_still_allows_late_response_to_drain(application):
    owner = gui.QObject()
    scheduler = scheduling.WarmlinkRequestScheduler(owner, lambda _: None, lambda _: None,
                                                   lambda _: None, lambda _: False)
    lost = request(1158)
    scheduler.submit(lost); scheduler.sent(1158, 1, 0x63)
    scheduler._timeout(); scheduler.recovery_timer.stop(); scheduler._recover_lost_response()
    assert scheduler.unresolved is lost and not scheduler.recovering
    scheduler.unmatched_response(0x63, 2)
    assert scheduler.unresolved is None
    scheduler.cancel()


def test_no_response_trigger_send_failure_does_not_leave_orphan(window):
    window.worker.client.send = lambda _: (_ for _ in ()).throw(OSError("connection lost"))
    window.send_read_request(4, expect_response=False)
    window.worker._flush_write_queue()
    assert window.warmlink_read_scheduler.active is None
    assert not window.pending_read_requests


def test_thread_references_and_recovery_are_kept_until_native_cleanup_finishes(window, monkeypatch):
    calls, ticks = [], []
    joined = [False]
    thread = SimpleNamespace(wait=lambda timeout: calls.append(("wait", timeout)) or joined[0],
                             deleteLater=lambda: calls.append(("delete",)))
    worker = window.worker
    with monkeypatch.context() as patch:
        patch.setattr(window, "thread", thread)
        patch.setattr(window, "_warmlink_recovery", {"settings": window._current_reader_settings()})
        patch.setattr(window, "_schedule_warmlink_reconnect", lambda: calls.append(("reconnect",)))
        patch.setattr(gui.QTimer, "singleShot", lambda delay, callback: ticks.append((delay, callback)))
        window._clear_thread_refs()
        assert calls == [("wait", 0)]  # Nonblocking probe, no delete or reconnect yet.
        assert window.thread is thread and window.worker is worker
        assert len(ticks) == 1
        joined[0] = True
        ticks[0][1]()
        assert window.thread is None and window.worker is None
        assert calls == [("wait", 0), ("wait", 0), ("delete",), ("reconnect",)]


def test_close_during_worker_shutdown_is_nonblocking_and_prevents_reconnect(connection):
    window, clients, _ = connection
    gate, entered = threading.Event(), threading.Event()
    old_recv = clients[0].recv
    def delayed_recv(size):
        result = old_recv(size)
        entered.set(); gate.wait(timeout=1)
        return result
    clients[0].recv = delayed_recv
    send_and_lose(window)
    try:
        wait_for(entered.is_set)
        event = QCloseEvent()
        window.closeEvent(event)
        assert not event.isAccepted() and window._close_after_reader
        assert window.thread is not None and window._warmlink_recovery is None
    finally:
        gate.set()
    wait_for(lambda: window.thread is None)
    wait(50)
    assert len(clients) == 1 and not window._warmlink_reconnect_timer.isActive()



def test_stop_before_worker_start_cannot_be_overwritten_by_run(window, monkeypatch):
    monkeypatch.setattr(gui, "WarmlinkSocketClient", lambda *a, **kw: pytest.fail("Cancelled worker must not connect"))
    worker = gui.ReaderWorker("simulated.invalid", 1234, window.regmap)
    connected, disconnected = QSignalSpy(worker.connected), QSignalSpy(worker.disconnected)
    worker.stop(); worker.run()
    assert connected.count() == 0 and disconnected.count() == 1
    assert not worker.running


def test_cancel_during_connection_attempt_cannot_reactivate_worker(connection, monkeypatch):
    window, clients, _ = connection
    gate, entered = threading.Event(), threading.Event()
    old_connect = SimulatedTCP.connect
    def delayed_connect(self):
        entered.set(); gate.wait(timeout=1)
        old_connect(self)
    monkeypatch.setattr(SimulatedTCP, "connect", delayed_connect)
    send_and_lose(window)
    try:
        wait_for(entered.is_set)
        window.disconnect_from_device()
        assert not window.connected and window._warmlink_recovery is None
    finally:
        gate.set()
    wait_for(lambda: window.thread is None)
    wait(60)
    assert len(clients) == 2 and clients[-1].closed
    assert not window.connected and not window.live_poll_timer.isActive()
    assert not window.pending_read_requests and window.warmlink_read_scheduler.active is None
