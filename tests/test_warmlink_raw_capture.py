import datetime
import io
import json
from pathlib import Path

import pytest

from warmlink_raw_capture import DEFAULT_CAPTURE_SETTINGS, WarmlinkRawCapture, parse_modbus
from core.settings_manager import ensure_defaults


def test_legacy_capture_settings_default_to_normal_mode():
    settings = ensure_defaults({"warmlink_raw_capture": {"enabled": True}})
    assert settings["warmlink_raw_capture"]["mode"] == "normal"
    assert DEFAULT_CAPTURE_SETTINGS["mode"] == "normal"


def test_passive_block_event_does_not_write_tx_bytes(tmp_path):
    cap = WarmlinkRawCapture({"directory": str(tmp_path), "mode": "firmware"}, str(tmp_path))
    cap.start()
    cap.note_event("passive_tx_blocked", command="read", byte_count=8, address=2001)
    cap.stop(join=True)
    assert next(tmp_path.glob("*.tx.bin")).read_bytes() == b""
    events = [json.loads(line) for line in next(tmp_path.glob("*.events.jsonl")).read_text(encoding="utf-8").splitlines()]
    assert any(event.get("event") == "passive_tx_blocked" for event in events)


@pytest.mark.parametrize("command", ["read", "write", "write_block"])
def test_reader_worker_tx_barrier_blocks_send_and_tx_signal(command, tmp_path):
    app = pytest.importorskip("foxair_phnix_control", exc_type=ImportError)

    class FakeClient:
        def __init__(self):
            self.sent = []
        def is_connected(self):
            return True
        def send(self, frame):
            self.sent.append(bytes(frame))

    worker = app.ReaderWorker("host", 2001, None)
    worker.client = FakeClient()
    worker.running = True
    tx_chunks = []
    worker.tx_chunk.connect(tx_chunks.append)
    cap = WarmlinkRawCapture({"directory": str(tmp_path), "mode": "firmware"}, str(tmp_path))
    cap.start()
    worker.tx_blocked_attempt.connect(
        lambda kind, bus, addr, size: cap.note_event(
            "passive_tx_blocked", command=kind, bus=bus, address=addr, byte_count=size
        )
    )
    worker.set_tx_blocked(True)
    if command == "read":
        worker.enqueue_read(2001, 1)
    elif command == "write":
        worker.enqueue_write(1001, 7)
    else:
        worker.enqueue_write_block(1001, [7, 8])
    worker._flush_write_queue()
    cap.stop(join=True)

    assert worker.client.sent == []
    assert tx_chunks == []
    events = [json.loads(line) for line in next(tmp_path.glob("*.events.jsonl")).read_text(encoding="utf-8").splitlines()]
    assert any(event.get("event") == "passive_tx_blocked" and event.get("command") == command for event in events)


def test_reader_worker_can_send_again_after_tx_barrier_is_removed():
    app = pytest.importorskip("foxair_phnix_control", exc_type=ImportError)

    class FakeClient:
        def __init__(self): self.sent = []
        def is_connected(self): return True
        def send(self, frame): self.sent.append(bytes(frame))

    worker = app.ReaderWorker("host", 2001, None)
    worker.client = FakeClient(); worker.running = True
    tx_chunks = []
    worker.tx_chunk.connect(tx_chunks.append)
    worker.set_tx_blocked(True)
    worker.enqueue_read(2001, 1)
    worker._flush_write_queue()
    worker.set_tx_blocked(False)
    worker.enqueue_read(2001, 1)
    worker._flush_write_queue()
    assert len(worker.client.sent) == 1
    assert len(tx_chunks) == 1


def test_dual_logger_start_is_blocked_in_firmware_mode(monkeypatch):
    app = pytest.importorskip("foxair_phnix_control", exc_type=ImportError)
    warnings = []
    monkeypatch.setattr(app.QMessageBox, "warning", lambda *args: warnings.append(args))

    class Main:
        @staticmethod
        def _is_firmware_capture_mode(): return True
    class FakeDialog:
        main_window = Main()
        messages = []
        def _log(self, text): self.messages.append(text)

    fake = FakeDialog()
    app.DualBusLoggerDialog.start(fake)
    assert warnings
    assert fake.messages == ["Firmware-Capture aktiv – aktive Warmlink-Diagnose gesperrt."]


def test_possible_firmware_protocol_uses_realistic_rate_and_complete_crc_frames(monkeypatch, tmp_path):
    import warmlink_raw_capture as capture_module

    cap = WarmlinkRawCapture({"directory": str(tmp_path)}, str(tmp_path))
    cap.events = io.StringIO()
    # 7.2 KiB over eight seconds is attainable at 9600 baud and contains no
    # complete, CRC-valid known frame.
    for second in range(9):
        cap._anomaly("rx", b"x" * 800, {"parser": "chunk"}, 100.0 + second)
    events = [json.loads(line) for line in cap.events.getvalue().splitlines()]
    assert any(event.get("event") == "possible_firmware_protocol" for event in events)

    cap2 = WarmlinkRawCapture({"directory": str(tmp_path)}, str(tmp_path))
    cap2.events = io.StringIO()
    valid_frame = _with_crc("63 03 04 00 01 00 02")
    monkeypatch.setattr(capture_module.time, "monotonic", lambda: 104.0)
    cap2._write_frame_complete_event("rx", 0, valid_frame, {
        "bus": 0x63, "function": "0x03", "crc_ok": True,
        "crc": int.from_bytes(valid_frame[-2:], "little"),
    })
    monkeypatch.setattr(capture_module.time, "monotonic", lambda: 105.0)
    cap2._write_frame_complete_event("rx", len(valid_frame), valid_frame, {
        "bus": 0x63, "function": "0x03", "crc_ok": True,
        "crc": int.from_bytes(valid_frame[-2:], "little"),
    })
    for second in range(9):
        cap2._anomaly("rx", b"x" * 800, {"parser": "chunk"}, 100.0 + second)
    events2 = [json.loads(line) for line in cap2.events.getvalue().splitlines()]
    assert not any(event.get("event") == "possible_firmware_protocol" for event in events2)


def test_parse_modbus_does_not_treat_payload_chunks_as_unknown_frames():
    assert parse_modbus(bytes.fromhex("00 18"))["parser"] == "partial"
    payload = parse_modbus(bytes.fromhex("46 32 32 31 30 32 35 30"))
    assert payload["parser"] == "chunk"
    assert "function" not in payload
    payload2 = parse_modbus(bytes.fromhex("02 01 2c 00"))
    assert payload2["parser"] == "chunk"
    assert "function" not in payload2


def test_capture_marks_large_fc16_payload_chunks_as_continuation_without_unknown_function(tmp_path):
    cap = WarmlinkRawCapture({"directory": str(tmp_path), "write_events": True}, str(tmp_path))
    cap.start()
    chunks = [
        bytes.fromhex("00 18"),
        bytes.fromhex("63 10 04 43 00 5a b4 57"),
        bytes.fromhex("46 32 32 31 30 32 35 30 34 37 35"),
        bytes.fromhex("1a 00 2d 00 01 96 02 01 2c"),
        bytes.fromhex("63 10 04 43 00 5a b8 94"),
    ]
    for chunk in chunks:
        cap.capture_rx(chunk)
    cap.stop(join=True)

    rx_file = next(Path(tmp_path).glob("*.rx.bin"))
    assert rx_file.read_bytes() == b"".join(chunks)
    events = [json.loads(line) for line in next(Path(tmp_path).glob("*.events.jsonl")).read_text().splitlines()]
    anomaly_kinds = [ev.get("kind") for ev in events if ev.get("event") == "anomaly"]
    assert "unknown_function" not in anomaly_kinds
    parsers = [ev.get("parser") for ev in events if ev.get("dir") == "rx"]
    assert parsers[0] == "partial"
    assert parsers[1] == "frame_start"
    assert "continuation" in parsers


def _with_crc(hex_without_crc: str) -> bytes:
    data = bytes.fromhex(hex_without_crc)
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return data + crc.to_bytes(2, "little")


def test_capture_writes_frame_complete_for_split_fc16_request(tmp_path):
    payload = bytes(range(180))
    frame = _with_crc("63 10 08 2b 00 5a b4")[:-2] + payload
    frame = _with_crc(frame.hex())
    cap = WarmlinkRawCapture({"directory": str(tmp_path), "write_events": True}, str(tmp_path))
    cap.start()
    cap.capture_rx(frame[:11])
    cap.capture_rx(frame[11:])
    cap.stop(join=True)

    events = [json.loads(line) for line in next(Path(tmp_path).glob("*.events.jsonl")).read_text().splitlines()]
    frames = [ev for ev in events if ev.get("event") == "frame_complete"]
    assert len(frames) == 1
    ev = frames[0]
    assert ev["dir"] == "rx"
    assert ev["offset_start"] == 0
    assert ev["offset_end"] == len(frame)
    assert ev["len"] == len(frame)
    assert ev["bus"] == 0x63
    assert ev["function"] == "0x10"
    assert ev["addr"] == 2091
    assert ev["qty"] == 90
    assert ev["byte_count"] == 180
    assert ev["payload_offset"] == 7
    assert ev["payload_len"] == 180
    assert ev["crc_ok"] is True
    assert ev["crc"].startswith("0x")


def test_capture_does_not_write_frame_complete_for_plain_chunk(tmp_path):
    cap = WarmlinkRawCapture({"directory": str(tmp_path), "write_events": True}, str(tmp_path))
    cap.start()
    cap.capture_rx(bytes.fromhex("46 32 32 31 30 32 35 30"))
    cap.stop(join=True)

    events = [json.loads(line) for line in next(Path(tmp_path).glob("*.events.jsonl")).read_text().splitlines()]
    assert [ev for ev in events if ev.get("event") == "frame_complete"] == []


def _fc16_frame(addr: int = 0x082B, qty: int = 90, payload: bytes | None = None) -> bytes:
    if payload is None:
        payload = bytes(range(qty * 2))
    header = bytes([0x63, 0x10]) + addr.to_bytes(2, "big") + qty.to_bytes(2, "big") + bytes([len(payload)])
    return _with_crc((header + payload).hex())


def _events(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_capture_skips_existing_segment_prefix_and_starts_offsets_at_zero(tmp_path):
    today = datetime.date.today().isoformat()
    old_rx = tmp_path / f"warmlink_capture_{today}_001.rx.bin"
    old_events = tmp_path / f"warmlink_capture_{today}_001.events.jsonl"
    old_rx.write_bytes(b"old")
    old_events.write_text('{"event":"old"}\n', encoding="utf-8")
    frame = _fc16_frame()

    cap = WarmlinkRawCapture({"directory": str(tmp_path), "write_events": True}, str(tmp_path))
    cap.start()
    cap.capture_rx(frame)
    cap.stop(join=True)

    new_rx = tmp_path / f"warmlink_capture_{today}_002.rx.bin"
    new_events = tmp_path / f"warmlink_capture_{today}_002.events.jsonl"
    assert new_rx.read_bytes() == frame
    assert old_rx.read_bytes() == b"old"
    assert {ev.get("event") for ev in _events(new_events)}.isdisjoint({"old"})
    frames = [ev for ev in _events(new_events) if ev.get("event") == "frame_complete"]
    assert len(frames) == 1
    assert frames[0]["offset_start"] == 0
    assert frames[0]["offset_end"] == len(frame)


def test_multiple_capture_starts_same_day_do_not_append_to_first_segment(tmp_path):
    today = datetime.date.today().isoformat()
    first = b"first"
    second = b"second"

    cap1 = WarmlinkRawCapture({"directory": str(tmp_path), "write_events": True}, str(tmp_path))
    cap1.start()
    cap1.capture_rx(first)
    cap1.stop(join=True)

    cap2 = WarmlinkRawCapture({"directory": str(tmp_path), "write_events": True}, str(tmp_path))
    cap2.start()
    cap2.capture_rx(second)
    cap2.stop(join=True)

    assert (tmp_path / f"warmlink_capture_{today}_001.rx.bin").read_bytes() == first
    assert (tmp_path / f"warmlink_capture_{today}_002.rx.bin").read_bytes() == second
    assert cap1.get_status().segment.endswith("_001")
    assert cap2.get_status().segment.endswith("_002")


def test_rotation_uses_new_segment_and_resets_offsets_and_frame_buffer(tmp_path):
    today = datetime.date.today().isoformat()
    frame = _fc16_frame()

    cap = WarmlinkRawCapture({"directory": str(tmp_path), "write_events": True}, str(tmp_path))
    cap.start()
    cap.capture_rx(frame[:11])
    cap.force_new_segment()
    cap.capture_rx(frame)
    cap.stop(join=True)

    first_rx = tmp_path / f"warmlink_capture_{today}_001.rx.bin"
    second_rx = tmp_path / f"warmlink_capture_{today}_002.rx.bin"
    assert first_rx.read_bytes() == frame[:11]
    assert second_rx.read_bytes() == frame

    first_events = _events(tmp_path / f"warmlink_capture_{today}_001.events.jsonl")
    second_events = _events(tmp_path / f"warmlink_capture_{today}_002.events.jsonl")
    assert [ev for ev in first_events if ev.get("event") == "frame_complete"] == []
    frames = [ev for ev in second_events if ev.get("event") == "frame_complete"]
    assert len(frames) == 1
    assert frames[0]["offset_start"] == 0
    assert frames[0]["offset_end"] == len(frame)


def test_main_window_does_not_start_capture_for_non_warmlink_backend(monkeypatch, tmp_path):
    app = pytest.importorskip("foxair_phnix_control", exc_type=ImportError)

    starts = []

    class FakeCapture:
        def __init__(self, *args, **kwargs):
            starts.append((args, kwargs))
        def start(self, baseline=None):
            starts.append(("start", baseline))

    class FakeMain:
        settings = {"warmlink_raw_capture": {"enabled": True, "directory": str(tmp_path)}}
        latest_regs = {}
        warmlink_capture = "old"
        user_data_dir = str(tmp_path)
        base_dir = str(tmp_path)
        def current_backend_key(self):
            return "standard_modbus"
        def _log(self, text):
            self.logged = text
        def _capture_thread_log(self, text):
            pass

    monkeypatch.setattr(app, "WarmlinkRawCapture", FakeCapture)
    fake = FakeMain()

    app.MainWindow._start_warmlink_capture_if_enabled(fake)

    assert starts == []
    assert fake.warmlink_capture is None
    assert "nicht Modbus Warmlink LTE" in fake.logged


def test_main_window_starts_capture_for_warmlink_backend(monkeypatch, tmp_path):
    app = pytest.importorskip("foxair_phnix_control", exc_type=ImportError)

    starts = []

    class FakeCapture:
        def __init__(self, *args, **kwargs):
            starts.append(("init", args, kwargs))
        def start(self, baseline=None):
            starts.append(("start", baseline))

    class FakeMain:
        settings = {"warmlink_raw_capture": {"enabled": True, "directory": str(tmp_path)}}
        latest_regs = {}
        warmlink_capture = None
        user_data_dir = str(tmp_path)
        base_dir = str(tmp_path)
        def current_backend_key(self):
            return "warmlink_raw"
        def _log(self, text):
            pass
        def _capture_thread_log(self, text):
            pass

    monkeypatch.setattr(app, "WarmlinkRawCapture", FakeCapture)
    fake = FakeMain()

    app.MainWindow._start_warmlink_capture_if_enabled(fake)

    assert [entry[0] for entry in starts] == ["init", "start"]
