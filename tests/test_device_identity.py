"""Synthetic-only tests for the irreversible identity service (issue #115)."""
from types import SimpleNamespace
import json

import pytest
from PySide6.QtWidgets import QApplication, QWidget

import foxair_phnix_control as gui
from core.device_info import DeviceInfoTracker
from core.device_identity import (
    WARNING, encode_wifi_identity, decode_wifi_identity, validate_wifi_identity,
    build_identity_write_payload, mask_wifi_identity, validate_identity_write_ack,
    verify_identity_readback, create_identity_backup, load_identity_backup,
)
from core.device_identity_service import DeviceIdentityService
from core.foxair_phnix_core import crc_bytes_le, find_frames
from dialogs.device_identity_dialog import DeviceIdentityDialog
from dialogs.device_info_dialog import DeviceInfoDialog

OLD = "WF2403150123"
NEW = "WF2403150456"
WORDS = encode_wifi_identity(OLD) + [0x1234, 0xABCD]


def packet(body):
    return body + crc_bytes_le(body)


def read_reply(words=WORDS, slave=0x63):
    return packet(bytes([slave, 3, len(words) * 2]) + b"".join(w.to_bytes(2, "big") for w in words))


def ack(slave=0x63, function=0x10, start=7001, quantity=10):
    return packet(bytes([slave, function]) + start.to_bytes(2, "big") + quantity.to_bytes(2, "big"))


def pump():
    for _ in range(4):
        QApplication.instance().processEvents()


class Client:
    def __init__(self):
        self.frames = []
        self.connected = True
    def is_connected(self):
        return self.connected
    def send(self, frame):
        self.frames.append(frame)
    def close(self):
        self.connected = False


class Owner(QWidget):
    def __init__(self, tmp_path):
        super().__init__()
        self.settings = {"show_engineering_parameters": True}
        self.backend = "warmlink_raw"
        self.slave = 0x63
        self.connected = True
        self.user_data_dir = str(tmp_path)
        self.pending_read_requests = []
        self.warmlink_read_scheduler = None
        self.device_info_tracker = DeviceInfoTracker()
        self.latest_regs = {}
        self.logs = []
        self.make_worker()
    def make_worker(self):
        self.worker = gui.ReaderWorker("synthetic", 2000, None)
        self.worker.running = True
        self.worker.client = Client()
        self.worker.log.connect(self.logs.append)
    def current_backend_key(self):
        return self.backend
    def current_backend_label(self):
        return self.backend
    def _active_io_worker(self):
        return self.worker if self.connected else None
    def _wire_slave_addr(self, requested):
        return self.slave
    def _log(self, text):
        self.logs.append(text)
    def start_device_info_cycle(self):
        pass
    def read_device_info_registers(self):
        pass


@pytest.fixture
def owner(tmp_path):
    owner = Owner(tmp_path)
    yield owner
    owner.worker.stop()
    owner.close()
    owner.deleteLater()
    pump()


@pytest.fixture
def service(owner):
    clock = [100.0]
    service = DeviceIdentityService(owner, clock=lambda: clock[0])
    service.test_clock = clock
    yield service
    service.close()


def respond(service, raw):
    worker = service.worker
    worker._flush_write_queue()
    frames = worker._parse_rx_chunk(raw)
    for frame in frames:
        assert worker._identity_route_frame(frame[6]) is True
    pump()


def prepared(service):
    assert service.prepare(NEW)
    respond(service, read_reply())
    assert service.state == "prepared"


def writing(service, words=WORDS):
    prepared(service)
    assert service.write(NEW)
    respond(service, read_reply(words))
    assert service.state == "writing"
    service.worker._flush_write_queue()
    pump()


def confirmed(service):
    writing(service)
    respond(service, ack())
    respond(service, read_reply(encode_wifi_identity(NEW) + WORDS[6:]))
    assert service.state == "ram_confirmed"


def test_codec_payload_and_sensitive_backup(tmp_path):
    assert encode_wifi_identity(OLD) == [0x5746, 0x3234, 0x3033, 0x3135, 0x3031, 0x3233]
    assert decode_wifi_identity(WORDS) == OLD
    payload = build_identity_write_payload(OLD, 0x1234, 0xABCD)
    assert payload == [0xAA, 0x5A, *WORDS]
    assert len(payload) == 10
    assert mask_wifi_identity(OLD) == "WF24******23"
    assert OLD not in mask_wifi_identity(OLD)
    path, record = create_identity_backup(tmp_path, WORDS, NEW)
    assert record["raw_2001_2008"] == WORDS
    assert record["old_id"] == OLD and record["expected_id"] == NEW
    assert record["reserved"] == WORDS[6:]
    assert record["sensitive"] is True and record["timestamp"]
    assert load_identity_backup(path) == record
    if __import__("os").name != "nt":
        assert path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("value", ["", "WF240315012", "WF24031501234", "XX2403150123", "WF24031501é3", "WF２４０３１５０１２３", "WF240315012\n", None])
def test_invalid_identity_never_encodes(value):
    assert not validate_wifi_identity(value)
    with pytest.raises(ValueError):
        encode_wifi_identity(value)


@pytest.mark.parametrize("words", [WORDS[:-1], WORDS + [0], WORDS[:7] + [-1], WORDS[:7] + [65536]])
def test_incomplete_or_invalid_read_words_fail(words):
    with pytest.raises(ValueError):
        decode_wifi_identity(words)


@pytest.mark.parametrize("kwargs", [{"slave": 1}, {"function": 6}, {"start": 7002}, {"quantity": 1}])
def test_wrong_ack_is_not_accepted(kwargs):
    assert validate_identity_write_ack(ack())
    assert not validate_identity_write_ack(ack(**kwargs))
    assert not validate_identity_write_ack(ack()[:-1] + b"\xff")


@pytest.mark.parametrize("index", [0, 6, 7])
def test_readback_detects_identity_and_each_reserved_word(index):
    expected = encode_wifi_identity(NEW) + WORDS[6:]
    assert verify_identity_readback(expected, NEW, WORDS[6:])
    expected[index] ^= 1
    assert not verify_identity_readback(expected, NEW, WORDS[6:])


def test_device_info_engineering_gate_refreshes_without_changing_normal_info(owner):
    owner.settings["show_engineering_parameters"] = False
    dialog = DeviceInfoDialog(owner)
    dialog.show()
    dialog.refresh()
    assert not dialog.identity_btn.isVisible()
    dialog.open_identity_dialog()
    assert dialog.identity_dialog is None
    owner.settings["show_engineering_parameters"] = True
    dialog.refresh()
    assert dialog.identity_btn.isVisible()
    owner.settings["show_engineering_parameters"] = False
    dialog.refresh()
    assert not dialog.identity_btn.isVisible()
    assert dialog.direct_read_btn.isVisible() and dialog.read_btn.isVisible()
    dialog.close()


@pytest.mark.parametrize("backend", ["standard_modbus", "display_modbus", "cloud"])
def test_wrong_transport_never_reads_or_writes(service, owner, backend):
    owner.backend = backend
    assert service.prepare(NEW) is False
    assert service.write(NEW) is False
    owner.worker._flush_write_queue()
    assert owner.worker.client.frames == []


@pytest.mark.parametrize("condition", ["engineering", "worker", "remapped_slave", "capture", "queued", "pending", "scheduler"])
def test_access_and_busy_guards(service, owner, condition):
    if condition == "engineering": owner.settings["show_engineering_parameters"] = False
    elif condition == "worker": owner.connected = False
    elif condition == "remapped_slave": owner.slave = 1
    elif condition == "capture": owner.worker.set_tx_blocked(True)
    elif condition == "queued": owner.worker.enqueue_read(1205, 1)
    elif condition == "pending": owner.pending_read_requests.append({"quantity": 8})
    elif condition == "scheduler": owner.warmlink_read_scheduler = SimpleNamespace(active={"quantity": 8}, queue=[])
    assert service.prepare(NEW) is False
    assert service.token is None


def test_direct_dialog_call_and_write_blocked_without_engineering(owner):
    owner.settings["show_engineering_parameters"] = False
    dialog = DeviceIdentityDialog(owner)
    dialog.target_edit.setText(NEW)
    dialog.service.target = NEW
    dialog.service.state = "prepared"
    dialog.confirmation_edit.setText(NEW)
    assert not dialog.write_btn.isEnabled()
    assert dialog.write_identity() is False
    assert owner.worker.write_queue.empty()
    dialog.close()


def test_typing_exact_confirmation_and_fresh_prewrite_read(service, owner):
    prepared(service)
    assert service.write(NEW + " ") is False
    assert service.write(OLD) is False
    assert owner.worker.write_queue.empty()
    assert service.write(NEW)
    # Only FC03 is queued, and no backup/write exists before the fresh reply.
    assert service.backup is None
    respond(service, read_reply())
    assert service.backup["raw_2001_2008"] == WORDS
    assert service.backup_path.exists()
    owner.worker._flush_write_queue()
    sent = owner.worker.client.frames
    assert [frame[1] for frame in sent] == [3, 3, 16]
    assert sent[-1][:7] == bytes.fromhex("63 10 1b 59 00 0a 14")
    assert len(sent[-1]) == 29
    assert sent[-1][7:-2] == b"".join(v.to_bytes(2, "big") for v in service.payload)


def test_changed_fresh_words_require_another_preview_confirmation(service, owner):
    prepared(service)
    assert service.write(NEW)
    fresh = WORDS[:6] + [0x1111, 0x2222]
    respond(service, read_reply(fresh))
    assert service.state == "prepared"
    assert service.payload[-2:] == fresh[-2:]
    assert service.backup is None
    assert all(frame[1] == 3 for frame in owner.worker.client.frames)
    assert service.write(NEW)
    respond(service, read_reply(fresh))
    assert service.state == "writing"
    assert service.backup["reserved"] == fresh[-2:]


def test_engineering_gate_revocation_before_actual_send(service, owner):
    prepared(service)
    # Revoke the gate after fresh read/backup, before the queued FC10 is sent.
    service.write(NEW)
    respond(service, read_reply())
    owner.settings["show_engineering_parameters"] = False
    owner.worker._flush_write_queue()
    pump()
    assert all(frame[1] == 3 for frame in owner.worker.client.frames)
    assert service.state == "failed"


@pytest.mark.parametrize("kwargs", [{"slave": 1}, {"function": 6}, {"start": 7002}, {"quantity": 11}])
def test_bad_ack_never_succeeds_or_retries(service, owner, kwargs):
    writing(service)
    respond(service, ack(**kwargs))
    # A wrong slave/function is not this transaction's ACK, so it times out.
    service.test_clock[0] += 9
    service.tick()
    assert service.state == "failed"
    assert service.ack_ok is False
    assert sum(frame[1] == 16 for frame in owner.worker.client.frames) == 1
    assert not owner.worker.running
    assert owner.worker._identity_route_frame(read_reply()) is True  # Late reply remains private.


@pytest.mark.parametrize("index", [0, 6, 7])
def test_failed_readback_stops_without_retry(service, owner, index):
    writing(service)
    respond(service, ack())
    readback = encode_wifi_identity(NEW) + WORDS[6:]
    readback[index] ^= 1
    respond(service, read_reply(readback))
    assert service.state == "failed" and service.immediate_ok is False
    assert service.wait_seconds == 60
    assert sum(frame[1] == 16 for frame in owner.worker.client.frames) == 1
    assert json.loads(service.backup_path.read_text())["immediate_readback"]["ok"] is False


def test_ack_alone_is_not_ram_or_persistence_success(service):
    writing(service)
    respond(service, ack())
    assert service.ack_ok is True
    assert service.immediate_ok is None and service.persistence_ok is None
    assert service.state == "readback"


def test_no_cache_or_reply_before_send_can_prepare(service, owner):
    owner.latest_regs = {2001+i: SimpleNamespace(raw_value=w) for i, w in enumerate(WORDS)}
    assert service.prepare(NEW)
    assert owner.worker._identity_route_frame(read_reply()) is True
    pump()
    assert service.words is None and service.state == "preparing"
    respond(service, read_reply())
    assert service.state == "prepared"


def test_incomplete_fresh_read_aborts(service):
    service.prepare(NEW)
    respond(service, read_reply(WORDS[:-1]))
    assert service.state == "failed" and service.backup is None


def test_ram_confirmation_wait_reconnect_and_actual_restart_confirmation(service, owner):
    confirmed(service)
    assert service.wait_seconds == 60 and service.persistence_ok is None
    assert service.verify_after_restart(True) is False
    service.test_clock[0] += 60
    assert service.wait_seconds == 0
    assert service.verify_after_restart(True) is False
    owner.connected = False
    service.tick()
    owner.make_worker()
    owner.connected = True
    service.tick()
    assert service.reconnected is True
    assert service.verify_after_restart(False) is False
    assert service.verify_after_restart(True) is True
    respond(service, read_reply(encode_wifi_identity(NEW) + WORDS[6:]))
    assert service.state == "persisted" and service.persistence_ok is True
    assert json.loads(service.backup_path.read_text())["persistence_readback"]["ok"] is True


def test_restore_uses_new_reserve_words_and_full_safety_path(service, owner, tmp_path):
    path, _ = create_identity_backup(tmp_path, WORDS, NEW)
    assert service.restore_backup(path)
    current = encode_wifi_identity(NEW) + [0x5555, 0x6666]
    respond(service, read_reply(current))
    assert service.target == OLD
    assert service.payload[-2:] == [0x5555, 0x6666]
    assert service.write(NEW) is False
    assert service.write(OLD)
    respond(service, read_reply(current))
    assert service.backup["raw_2001_2008"] == current
    assert service.payload[-2:] != WORDS[-2:]


def test_backup_failure_prevents_write(service, owner, monkeypatch):
    prepared(service)
    def fail(*args):
        raise OSError("synthetic error")
    monkeypatch.setattr("core.device_identity_service.create_identity_backup", fail)
    service.write(NEW)
    respond(service, read_reply())
    assert service.state == "failed"
    assert all(frame[1] == 3 for frame in owner.worker.client.frames)


def test_lease_excludes_competing_requests_and_full_id_from_logs_capture(service, owner):
    transmitted_raw = []
    owner.worker.tx_chunk.connect(transmitted_raw.append)
    prepared(service)
    assert owner.worker.enqueue_read(1205, 1) is False
    assert owner.worker.enqueue_write(1205, 1) is False
    assert owner.worker.enqueue_write_block(7001, service.payload) is False
    service.write(NEW)
    respond(service, read_reply())
    respond(service, ack())
    respond(service, read_reply(encode_wifi_identity(NEW) + WORDS[6:]))
    assert transmitted_raw == []
    log = "\n".join(owner.logs)
    assert OLD not in log and NEW not in log
    assert "WF24******56" in log
    assert "57 46 32 34" not in log
    assert "5746" not in log
    assert service.backup["old_id"] == OLD and service.backup["expected_id"] == NEW


def test_main_scheduler_is_not_polluted_during_identity_lease(service, owner):
    prepared(service)
    assert gui.MainWindow.send_read_request(owner, 2001, 8) is None
    assert owner.pending_read_requests == []
    assert owner.worker.write_queue.empty()


def test_popup_has_required_warning_preview_and_clears_confirmation_on_changed_reserve(owner):
    dialog = DeviceIdentityDialog(owner)
    assert any(WARNING in label.text() for label in dialog.findChildren(gui.QLabel))
    dialog.target_edit.setText(NEW)
    assert dialog.service.prepare(NEW)
    respond(dialog.service, read_reply())
    dialog.confirmation_edit.setText(NEW)
    assert dialog.write_btn.isEnabled()
    assert dialog.write_identity()
    respond(dialog.service, read_reply(WORDS[:6] + [1, 2]))
    assert dialog.confirmation_edit.text() == ""
    assert not dialog.write_btn.isEnabled()
    assert "7009 = 0x0001" in dialog.payload_preview.toPlainText()
    dialog.close()


@pytest.mark.parametrize("content", ["[]", "null", "{}", "not-json"])
def test_malformed_backup_cannot_restore_or_expose_restore_button(service, owner, tmp_path, content):
    directory = tmp_path / "device_identity_backups"
    directory.mkdir()
    path = directory / "invalid.json"
    path.write_text(content)
    assert service.restore_backup(path) is False
    dialog = DeviceIdentityDialog(owner)
    dialog.refresh()
    assert dialog.restore_btn.isHidden()
    dialog.close()


def test_timeout_never_retries_or_accepts_late_ack(service, owner):
    writing(service)
    service.test_clock[0] += 9
    service.tick()
    assert service.state == "failed"
    token = owner.worker._identity_token
    service._event(token, "ack", ack())
    assert service.state == "failed" and not service.ack_ok
    assert service.wait_seconds == 60
    assert sum(frame[1] == 16 for frame in owner.worker.client.frames) == 1


def test_worker_enforces_narrow_lease_shape(service, owner):
    prepared(service)
    token = service.token
    worker = owner.worker
    assert worker.enqueue_read(2001, 7, slave_addr=0x63, identity_token=token) is False
    assert worker.enqueue_read(2001, 8, slave_addr=1, identity_token=token) is False
    assert worker.enqueue_write_block(7002, service.payload, slave_addr=0x63, identity_token=token) is False
    invalid = service.payload[:]
    invalid[0] = 0
    assert worker.enqueue_write_block(7001, invalid, slave_addr=0x63, identity_token=token) is False
    invalid = service.payload[:]
    invalid[2] = 0
    assert worker.enqueue_write_block(7001, invalid, slave_addr=0x63, identity_token=token) is False
    assert worker.write_queue.empty()


def test_reprepare_clears_previous_confirmation_even_for_same_id(owner):
    dialog = DeviceIdentityDialog(owner)
    dialog.target_edit.setText(NEW)
    dialog.service.prepare(NEW)
    respond(dialog.service, read_reply())
    dialog.confirmation_edit.setText(NEW)
    assert dialog.write_btn.isEnabled()
    dialog.service.prepare(NEW)
    respond(dialog.service, read_reply())
    assert dialog.confirmation_edit.text() == "" and not dialog.write_btn.isEnabled()
    dialog.close()


def test_real_reader_loop_runs_service_off_gui_thread_and_hides_raw_data(service, owner, monkeypatch):
    import queue
    import socket
    import threading
    import time
    from PySide6.QtCore import QTimer

    class Stream(Client):
        def __init__(self):
            super().__init__()
            self.rx = queue.Queue()
            self.started = threading.Event()
            self.current = WORDS[:]
        def connect(self):
            self.started.set()
        def send(self, frame):
            super().send(frame)
            if frame[1] == 3:
                self.rx.put(read_reply(self.current))
            else:
                assert frame[1] == 16
                # A local backup exists before the real FC10 send.
                assert service.backup_path.exists()
                self.current = [int.from_bytes(frame[i:i+2], "big") for i in range(11, 27, 2)]
                self.rx.put(ack())
        def recv(self, count):
            try:
                return self.rx.get(timeout=0.05)
            except queue.Empty:
                raise socket.timeout()
        def close(self):
            super().close()
            self.rx.put(b"")

    stream = Stream()
    monkeypatch.setattr(gui, "WarmlinkSocketClient", lambda *args, **kwargs: stream)
    raw, tx, normal_frames, ticks = [], [], [], []
    worker = owner.worker
    worker.raw_chunk.connect(raw.append)
    worker.tx_chunk.connect(tx.append)
    worker.frame_decoded.connect(normal_frames.append)
    timer = QTimer()
    timer.setInterval(1)
    timer.timeout.connect(lambda: ticks.append(1))
    timer.start()
    thread = threading.Thread(target=worker.run)
    thread.start()
    def until(predicate):
        deadline = time.monotonic() + 3
        while not predicate() and time.monotonic() < deadline:
            pump()
            time.sleep(0.002)  # Only test harness; no GUI implementation sleep.
        assert predicate()
    try:
        until(lambda: stream.started.is_set())
        assert service.prepare(NEW)
        until(lambda: service.state == "prepared")
        assert service.write(NEW)
        until(lambda: service.state == "ram_confirmed")
        assert service.immediate_ok and ticks
        assert raw == [] and tx == [] and normal_frames == []
        assert [frame[1] for frame in stream.frames] == [3, 3, 16, 3]
    finally:
        timer.stop()
        worker.stop()
        thread.join(timeout=3)
    assert not thread.is_alive()
