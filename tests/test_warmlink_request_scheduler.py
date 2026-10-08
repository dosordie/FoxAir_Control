import os
import time
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

import foxair_phnix_control as gui
from core.foxair_phnix_core import crc_bytes_le, decode_frame, find_frames
from core.warmlink_request_scheduler import WarmlinkRequestScheduler, WARMLINK_READBACK_DELAY_MS, WARMLINK_TIMEOUT_DRAIN_MS


@pytest.fixture(scope="module")
def application():
    return QApplication.instance() or QApplication([])


def request(addr, qty=1, label=""):
    return {"slave_addr": 0x63, "addr": addr, "wire_addr": addr, "quantity": qty, "label": label}


def pump(application):
    # Deliberately outside application implementation: process queued test callbacks.
    application.processEvents()


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def test_two_reads_wait_and_match_only_active_request(application):
    owner = gui.QObject()
    sent, timeouts = [], []
    scheduler = WarmlinkRequestScheduler(owner, sent.append, timeouts.append, lambda _: None)
    a, b = request(1158), request(1205)
    scheduler.submit(a)
    scheduler.submit(b)
    assert sent == [a] and len(scheduler.queue) == 1
    assert scheduler.matching(0x63, 2) is None  # not physically sent yet
    scheduler.sent(1158, 1, 0x63)
    assert scheduler.matching(0x63, 2) is a
    assert scheduler.matching(0x64, 2) is None
    assert scheduler.matching(0x63, 4) is None
    scheduler.complete(a)
    pump(application)
    assert sent == [a, b]
    scheduler.sent(1205, 1, 0x63)
    assert scheduler.matching(0x63, 2) is b
    scheduler.cancel()


def test_readback_before_background_and_init(application):
    owner = gui.QObject()
    sent = []
    scheduler = WarmlinkRequestScheduler(owner, sent.append, lambda _: None, lambda _: None)
    a, b, initial, readback = request(2001, label="Auto-Poll A"), request(2091, label="Auto-Poll B"), request(1001, label="Init"), request(1158, label="Popup Register 1158")
    scheduler.submit(a)
    scheduler.submit(b)
    scheduler.submit(initial)
    scheduler.submit(readback, priority="readback")
    scheduler.sent(a["addr"], 1, 0x63)
    scheduler.complete(a)
    pump(application)
    assert sent == [a, readback]
    scheduler.complete(readback)
    pump(application)
    assert sent[-1] is b
    scheduler.cancel()


def test_queued_identical_read_promoted_but_active_not_cancelled(application):
    owner = gui.QObject()
    sent = []
    scheduler = WarmlinkRequestScheduler(owner, sent.append, lambda _: None, lambda _: None)
    a, old = request(2001), request(1158)
    scheduler.submit(a)
    scheduler.submit(old, "background")
    new = request(1158)
    scheduler.submit(new, "readback")
    assert len(scheduler.queue) == 1 and scheduler.queue[0][2] is new
    scheduler.sent(2001, 1, 0x63)
    scheduler.complete(a)
    pump(application)
    scheduler.sent(1158, 1, 0x63)
    newer = request(1158)
    scheduler.submit(newer, "readback")
    assert scheduler.active is new and sent[-1] is new
    scheduler.complete(new)
    pump(application)
    assert sent[-1] is newer
    scheduler.cancel()


def test_timeout_starts_at_transport_send_then_releases_queue(application):
    owner = gui.QObject()
    sent, timeouts = [], []
    scheduler = WarmlinkRequestScheduler(owner, sent.append, timeouts.append, lambda _: None)
    a, b = request(1158), request(1205)
    scheduler.submit(a)
    scheduler.submit(b)
    assert a["time"] is None and not scheduler.timer.isActive()
    scheduler.sent(1158, 1, 0x63)
    assert a["time"] and scheduler.timer.isActive()
    scheduler._timeout()
    pump(application)
    assert timeouts == [a] and sent == [a]
    assert scheduler.matching(0x63, 2) is None
    wait(WARMLINK_TIMEOUT_DRAIN_MS + 30)
    assert sent == [a, b]
    scheduler.cancel()


def test_readback_delay_reserves_next_slot(application):
    owner = gui.QObject()
    sent = []
    scheduler = WarmlinkRequestScheduler(owner, sent.append, lambda _: None, lambda _: None)
    readback, background = request(1158), request(2001)
    started = time.monotonic()
    scheduler.submit(readback, "readback", delay_ms=WARMLINK_READBACK_DELAY_MS)
    scheduler.submit(background, "background")
    assert sent == []
    wait(WARMLINK_READBACK_DELAY_MS + 30)
    assert sent == [readback] and time.monotonic() - started >= WARMLINK_READBACK_DELAY_MS / 1000
    scheduler.cancel()


@pytest.fixture
def window(application, monkeypatch, tmp_path):
    monkeypatch.setattr(gui, "app_user_data_dir", lambda: str(tmp_path))
    monkeypatch.setattr(gui.MainWindow, "_autoconnect_if_enabled", lambda self: None)
    monkeypatch.setattr(gui.MainWindow, "_autostart_warmlink_cloud_if_enabled", lambda self: None)
    monkeypatch.setattr(gui.MainWindow, "check_for_updates_on_startup", lambda self: None)
    window = gui.MainWindow()
    window.backend_combo.setCurrentIndex(window.backend_combo.findData("warmlink_raw"))
    worker = gui.ReaderWorker("unused", 2000, window.regmap)
    transmitted = []
    worker.running = True
    worker.client = SimpleNamespace(is_connected=lambda: True, send=transmitted.append, close=lambda: None)
    worker.read_sent.connect(window._on_warmlink_read_sent)
    worker.read_failed.connect(window._on_warmlink_read_failed)
    window.worker, window.connected = worker, True
    window._test_transmitted = transmitted
    yield window
    worker.running = False
    window.warmlink_read_scheduler.cancel()
    window.worker = None
    for dialog in list(window.register_write_dialogs.values()): dialog.close()
    window.close()
    window.deleteLater()
    application.processEvents()


def response(window, value, slave=0x63):
    raw = bytes([slave, 3, 2]) + value.to_bytes(2, "big")
    raw += crc_bytes_le(raw)
    return decode_frame(find_frames(bytearray(raw))[0], window.regmap)


def test_real_pending_decoding_updates_correct_register_and_quickwrite(window, application):
    window.send_read_request(1158, 1, label="Popup Register 1158")
    window.send_read_request(1205, 1, label="manuell")
    window.worker._flush_write_queue()
    assert len(window._test_transmitted) == 1
    window.open_register_quick_write(1158)
    dialog = window.register_write_dialogs[(0x63, 1158)]
    frame = response(window, 550)
    window.on_frame_decoded(frame)
    assert frame.typ == 1158
    assert window.latest_regs[1158].raw_value == 550
    assert dialog.write_value_edit.text() == "55"
    assert 1205 not in window.latest_regs
    pump(application)
    window.worker._flush_write_queue()
    assert len(window._test_transmitted) == 2
    frame = response(window, 123)
    window.on_frame_decoded(frame)
    assert frame.typ == 1205 and window.latest_regs[1205].raw_value == 123
    assert window.latest_regs[1158].raw_value == 550


def test_quickwrite_ack_readback_overtakes_background_and_ignores_stale_pending(window, application):
    window.open_register_quick_write(1158)
    dialog = window.register_write_dialogs[(0x63, 1158)]
    window.send_read_request(2048, label="Auto-Poll A")
    window.send_read_request(2050, label="Auto-Poll B")
    window.worker._flush_write_queue()
    window.pending_read_requests.append({"slave_addr": 0x63, "addr": 1158, "wire_addr": 1158,
                                        "quantity": 1, "time": time.time(), "label": "stale"})
    dialog.write_value_edit.setText("54")
    dialog.write_register()
    window.worker._flush_write_queue()
    assert window._test_transmitted[-1][1] == 0x10
    ack = bytes([0x63, 0x10]) + (1158).to_bytes(2, "big") + b'\x00\x01'
    ack += crc_bytes_le(ack)
    frame = decode_frame(find_frames(bytearray(ack))[0], window.regmap)
    window.on_frame_decoded(frame)
    assert window.warmlink_read_scheduler.queue[0][2]["priority"] in ("background", "readback")
    window.on_frame_decoded(response(window, 200))
    pump(application)
    wait(WARMLINK_READBACK_DELAY_MS + 40)
    window.worker._flush_write_queue()
    active = window.warmlink_read_scheduler.active
    assert active["addr"] == 1158 and active["priority"] == "readback"
    assert [req["addr"] for req in window.pending_read_requests] == [1158]
    window.on_frame_decoded(response(window, 540))
    assert window.latest_regs[1158].raw_value == 540
    assert dialog.write_value_edit.text() == "54"
    assert "ohne Antwort" not in dialog.status_label.text()
    pump(application)
    window.worker._flush_write_queue()
    assert window.warmlink_read_scheduler.active["addr"] == 2050


def test_quickwrite_manual_read_sends_single_fc03(window):
    window.open_register_quick_write(1158)
    dialog = window.register_write_dialogs[(0x63, 1158)]
    dialog.read_register()
    window.worker._flush_write_queue()
    assert window._test_transmitted[-1][1] == 3
    assert window.warmlink_read_scheduler.active["addr"] == 1158
    window.on_frame_decoded(response(window, 550))
    assert dialog.write_value_edit.text() == "55"


def test_write_ack_different_address_does_not_create_readback(window):
    window.open_register_quick_write(1158)
    window.send_register_write(1158, 540, label="Popup Register 1158")
    frame = SimpleNamespace(mode="write-response", slave_addr=0x63, typ=1205, length_field=1)
    assert not window._apply_pending_write_ack(frame)
    assert window.warmlink_read_scheduler.active is None


def test_standard_backend_keeps_existing_queue_path(window):
    window.backend_combo.setCurrentIndex(window.backend_combo.findData("standard_modbus"))
    window.send_read_request(1158, label="manuell")
    window.send_read_request(1205, label="manuell")
    assert window.warmlink_read_scheduler.active is None
    assert len(window.pending_read_requests) == 2
    window.worker._flush_write_queue()
    assert len(window._test_transmitted) == 2


def test_late_response_during_timeout_drain_does_not_steal_next_request(window, application):
    window.send_read_request(1158)
    window.send_read_request(1205)
    window.worker._flush_write_queue()
    active = window.warmlink_read_scheduler.active
    window._warmlink_read_timeout(active)
    pump(application)
    frame = response(window, 550)
    assert not window._apply_pending_read_response(frame)
    assert window.warmlink_read_scheduler.active is None
    assert len(window._test_transmitted) == 1
    wait(WARMLINK_TIMEOUT_DRAIN_MS + 40)
    window.worker._flush_write_queue()
    assert window.warmlink_read_scheduler.active["addr"] == 1205


def test_failed_transport_does_not_leave_undeadlined_active_read(window):
    window.worker.client.send = lambda frame: (_ for _ in ()).throw(OSError("connection lost"))
    window.send_read_request(1158)
    window.worker._flush_write_queue()
    assert window.warmlink_read_scheduler.active is None
    assert not window.pending_read_requests
