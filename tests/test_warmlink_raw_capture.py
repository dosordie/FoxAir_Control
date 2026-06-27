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
