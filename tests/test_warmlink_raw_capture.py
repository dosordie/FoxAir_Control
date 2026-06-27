from core.warmlink_raw_capture import WarmlinkChunkEventParser, parse_modbus


def test_payload_chunks_are_not_unknown_function_anomalies():
    parser = WarmlinkChunkEventParser(unit_id=0x63)
    chunks = [
        bytes.fromhex("00 18"),
        bytes.fromhex("63 10 04 43 00 5a b4 57"),
        bytes.fromhex("46 32 32 31 30 32 35 30 34 37 35"),
        bytes.fromhex("1a 00 2d 02 01 2c 96"),
        bytes.fromhex("63 10 04 43 00 5a b8 94"),
    ]

    events = [parser.parse_modbus(chunk) for chunk in chunks]

    assert events[0]["parser"] == "chunk"
    assert all(event.get("anomaly") != "unknown_function" for event in events)
    assert events[1]["parser"] == "frame_start"
    assert events[1]["function"] == 0x10
    assert events[1]["start_addr"] == 0x0443
    assert events[1]["qty"] == 90
    assert events[1]["known_warmlink_block"] is True
    assert events[2]["parser"] == "continuation"
    assert "function" not in events[2]
    assert events[3]["parser"] == "continuation"
    assert "function" not in events[3]
    assert events[4]["parser"] == "frame_start"


def test_unknown_function_requires_expected_bus_address_and_minimum_length():
    assert parse_modbus(bytes.fromhex("46 32 32 31")).get("anomaly") is None
    assert parse_modbus(bytes.fromhex("02 01 2c 00")).get("anomaly") is None
    assert parse_modbus(bytes.fromhex("63 32 00")).get("anomaly") is None
    event = parse_modbus(bytes.fromhex("63 32 00 00"))
    assert event["parser"] == "frame_start"
    assert event["anomaly"] == "unknown_function"


def test_normal_status_blocks_are_not_firmware_candidates():
    parser = WarmlinkChunkEventParser(unit_id=0x63)
    for start in (0x0443, 0x07D1, 0x082B):
        event = parser.parse_modbus(bytes([0x63, 0x10]) + start.to_bytes(2, "big") + bytes.fromhex("00 5a b4 57"))
        assert event["known_warmlink_block"] is True
        assert "firmware_like_fc16_sequence_candidate" not in event
