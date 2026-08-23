import pytest

from core.foxair_phnix_core import find_frames


OTA_OFFER = bytes.fromhex("63 10 C3 50 00 07 0E 00 63 38 32 34 30 30 36 34 34 30 30 33 33 59 4D")
OTA_OFFER_ACK = bytes.fromhex("63 10 C3 50 00 07 B5 DC")
OTA_BOARD_STATUS = bytes.fromhex("63 10 C3 6E 00 02 04 00 63 00 00 35 59")
OTA_FRAMES = (OTA_OFFER, OTA_OFFER_ACK, OTA_BOARD_STATUS)


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
