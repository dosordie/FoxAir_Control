import pytest

from core.foxair_phnix_core import find_frames
from warmlink_raw_capture import format_ota_frame_for_visible_log


OTA_OFFER = bytes.fromhex("63 10 C3 50 00 07 0E 00 63 38 32 34 30 30 36 34 34 30 30 33 33 59 4D")
OTA_OFFER_ACK = bytes.fromhex("63 10 C3 50 00 07 B5 DC")
OTA_BOARD_STATUS = bytes.fromhex("63 10 C3 6E 00 02 04 00 63 00 00 35 59")
OTA_FRAMES = (OTA_OFFER, OTA_OFFER_ACK, OTA_BOARD_STATUS)


def _with_crc(body: bytes) -> bytes:
    from core.foxair_phnix_core import crc16_modbus
    return body + crc16_modbus(body).to_bytes(2, "little")


def _feed(chunks):
    buffer = bytearray()
    frames = []
    rests = []
    for chunk in chunks:
        buffer.extend(chunk)
        frames.extend(find_frames(buffer, max_len=512))
        rests.append(bytes(buffer))
    return [frame[6] for frame in frames], rests


@pytest.mark.parametrize("frame", OTA_FRAMES)
def test_real_ota_frames_are_parsed_individually(frame):
    parsed, rests = _feed([frame])
    assert parsed == [frame]
    assert rests == [b""]


def test_real_ota_frames_are_parsed_when_concatenated():
    parsed, rests = _feed([b"".join(OTA_FRAMES)])
    assert parsed == list(OTA_FRAMES)
    assert rests == [b""]


def test_complete_offer_keeps_five_ack_bytes_then_completes_ack():
    parsed, rests = _feed([OTA_OFFER + OTA_OFFER_ACK[:5], OTA_OFFER_ACK[5:]])
    assert parsed == [OTA_OFFER, OTA_OFFER_ACK]
    assert rests == [OTA_OFFER_ACK[:5], b""]


def test_c36e_four_then_nine_bytes():
    parsed, rests = _feed([OTA_BOARD_STATUS[:4], OTA_BOARD_STATUS[4:]])
    assert parsed == [OTA_BOARD_STATUS]
    assert rests == [OTA_BOARD_STATUS[:4], b""]


@pytest.mark.parametrize("frame", OTA_FRAMES)
def test_every_fragmentation_position_preserves_real_ota_frame(frame):
    for split in range(1, len(frame)):
        parsed, rests = _feed([frame[:split], frame[split:]])
        assert rests[0] == frame[:split]
        assert parsed == [frame]
        assert rests[-1] == b""


def test_multiple_complete_frames_keep_incomplete_following_frame():
    tail = OTA_BOARD_STATUS[:4]
    parsed, rests = _feed([OTA_OFFER + OTA_OFFER_ACK + tail])
    assert parsed == [OTA_OFFER, OTA_OFFER_ACK]
    assert rests == [tail]


def test_invalid_crc_is_not_returned_and_valid_successor_is_found():
    invalid = bytearray(OTA_OFFER)
    invalid[-1] ^= 1
    parsed, _rests = _feed([bytes(invalid) + OTA_OFFER_ACK])
    assert parsed == [OTA_OFFER_ACK]


def test_reader_debug_log_reports_actual_five_byte_tail():
    app = pytest.importorskip("foxair_phnix_control", exc_type=ImportError)
    worker = app.ReaderWorker("host", 2001, None)
    messages = []
    worker.log.connect(messages.append)

    frames = worker._parse_rx_chunk(OTA_OFFER + OTA_OFFER_ACK[:5])

    assert [frame[6] for frame in frames] == [OTA_OFFER]
    assert bytes(worker.buf) == OTA_OFFER_ACK[:5]
    assert any("Buffer 28->5 Byte" in message for message in messages)
    assert not any("Buffer 28->0 Byte" in message for message in messages)


def test_ota_frames_are_forwarded_as_readable_worker_log_after_reassembly():
    app = pytest.importorskip("foxair_phnix_control", exc_type=ImportError)
    worker = app.ReaderWorker("host", 2001, None)
    messages = []
    worker.log.connect(messages.append)

    worker._parse_rx_chunk(OTA_OFFER + OTA_OFFER_ACK[:6])
    worker._parse_rx_chunk(OTA_OFFER_ACK[6:] + OTA_BOARD_STATUS)

    ota_messages = [message for message in messages if message.startswith("OTA ")]
    assert ota_messages == [
        "OTA C350: Updateangebot, Softwarecode=82400644, Version=0033, Ziel-SSID=0063",
        "OTA C350 ACK empfangen",
        "OTA C36E: Status=0 – gleiche Firmware, keine Übertragung",
    ]
    assert bytes(worker.buf) == b""


def test_visible_ota_formatter_ignores_normal_modbus_frame():
    normal = bytes.fromhex("63 10 00 04 00 01 02 00 01 6D C8")
    assert format_ota_frame_for_visible_log(normal) is None


def test_visible_ota_formatter_describes_later_transfer_phases():
    c357 = bytes.fromhex("63 10 C3 57 00 05 0A 00 00 01 00 00 04 AA BB CC DD 00 00")
    c5a8 = bytes.fromhex("63 10 C5 A8 00 02 00 03 AA BB 00 00")

    assert format_ota_frame_for_visible_log(c357) == (
        "OTA C357: Firmware-Datenblock, Offset=256, Länge=4 Byte"
    )
    assert format_ota_frame_for_visible_log(c5a8) == (
        "OTA C5A8: Flash-/Schreibphase, Phase=3, Länge=4 Byte"
    )


def test_fragmented_c544_is_emitted_only_when_complete_and_described_as_board_info():
    payload = b"\x00\x63" + b"82345678" + b"H123" + b"87654321" + b"F456"
    frame = _with_crc(bytes.fromhex("63 10 C5 44 00 0D 1A") + payload)

    for split in range(1, len(frame)):
        parsed, rests = _feed([frame[:split], frame[split:]])
        assert rests[0] == frame[:split]
        assert parsed == [frame]

    assert format_ota_frame_for_visible_log(frame) == (
        "BOARD C544: Versions-/Geräteinformation, SSID=0063, Hardwarecode=82345678, "
        "Hardwareversion=H123, Softwarecode=87654321, Firmwareversion=F456"
    )


def test_c544_bad_crc_is_not_logged_and_c37b_status_7_is_normal_confirmation():
    payload = b"\x00\x63" + b"82345678" + b"H123" + b"87654321" + b"F456"
    damaged = bytearray(_with_crc(bytes.fromhex("63 10 C5 44 00 0D 1A") + payload))
    damaged[-1] ^= 1
    parsed, _rests = _feed([bytes(damaged)])
    assert parsed == []

    ack = _with_crc(bytes.fromhex("63 10 C3 7B 00 02 04 00 63 00 07"))
    assert format_ota_frame_for_visible_log(ack) == "BOARD C37B: Status 7 – Geräteinformation bestätigt"
