import datetime
import json
from pathlib import Path

from warmlink_raw_capture import WarmlinkRawCapture, parse_modbus


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
