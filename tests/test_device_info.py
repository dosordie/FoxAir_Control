import time

from core.device_info import (DEVICE_INFO_BLOCK_STARTS, DeviceInfoCycleState,
    DeviceInfoTracker, decode_c37b, decode_c544, decode_product_key,
    decode_wifi_id, decode_wifi_id_date, fc16_data_words, readable_firmware_version)
from core.foxair_phnix_core import build_write_registers_frame


def words(text, count=None):
    raw = text.encode("ascii")
    if count is not None:
        raw = raw.ljust(count * 2, b"\0")
    return [int.from_bytes(raw[i:i + 2], "big") for i in range(0, len(raw), 2)]


def test_wifi_id_big_endian_known_format_and_date():
    value = decode_wifi_id(words("WF2403150123"))
    assert value == "WF2403150123"
    assert decode_wifi_id_date(value) == ("240315", "15.03.2024")


def test_wifi_id_impossible_date_is_not_invented():
    assert decode_wifi_id_date("WF2413320123") == ("241332", None)


def test_product_key_nul_padding_and_invalid_ascii():
    result = decode_product_key(words("testProduct1", 16))
    assert result.value == "testProduct1"
    assert "\0" not in result.value
    invalid = [0x7465, 0xFF00] + [0] * 14
    assert decode_product_key(invalid).value is None
    assert "Nicht-ASCII" in decode_product_key(invalid).error


def test_c544_and_version_display():
    values = [0x0063] + words("823099990001824099990042")
    decoded = decode_c544(values)
    assert decoded == {"service_ssid": 0x0063, "hardware_code": "82309999",
        "hardware_version": "0001", "software_code": "82409999",
        "internal_version": "0042", "firmware_version": "V4.2"}
    assert readable_firmware_version("0033") == "V3.3"
    assert readable_firmware_version("beta") == "beta"


def test_c37b_status_7_and_ack_distinction():
    assert decode_c37b([0x0063, 7])["meaning"].startswith("C544-")
    frame = build_write_registers_frame(50043, [0x0063, 7], slave_addr=0x63)
    assert fc16_data_words(frame) == (50043, [0x0063, 7])
    ack = bytes.fromhex("63 10 C3 7B 00 02 00 00")
    assert fc16_data_words(ack) is None


def test_progress_counts_only_eight_unique_confirmed_blocks():
    tracker = DeviceInfoTracker()
    tracker.start(now=100)
    for start in DEVICE_INFO_BLOCK_STARTS:
        frame = build_write_registers_frame(start, [0] * 90, slave_addr=0x63)
        tracker.feed_fc16(frame)
        tracker.feed_fc16(frame)
    assert tracker.snapshot.block_count == 8
    assert tracker.snapshot.state == DeviceInfoCycleState.WAITING_FOR_C544
    assert 1541 not in DEVICE_INFO_BLOCK_STARTS
    assert 2181 not in DEVICE_INFO_BLOCK_STARTS


def test_timeout_preserves_partial_results_after_90_seconds():
    tracker = DeviceInfoTracker()
    tracker.start(now=10)
    tracker.snapshot.product_key = "testProduct1"
    assert tracker.check_timeout(now=99) is False
    assert tracker.check_timeout(now=100) is True
    assert tracker.snapshot.state == DeviceInfoCycleState.PARTIAL_TIMEOUT
    assert tracker.snapshot.product_key == "testProduct1"


def test_register_four_trigger_is_not_a_pending_read_source():
    source = open("foxair_phnix_control.py", encoding="utf-8").read()
    body = source.split("def start_device_info_cycle", 1)[1].split("\n    def ", 1)[0]
    assert "pending_read_requests.append" not in body
    assert "enqueue_read(4, 1" in body


def test_about_has_no_wifi_identity_and_button_is_adjacent():
    source = open("foxair_phnix_control.py", encoding="utf-8").read()
    about = source.split("class AboutDialog", 1)[1].split("class WPControlDialog", 1)[0]
    assert "WiFi Barcode" not in about
    assert "top.addWidget(self.device_info_btn)\n        top.addWidget(self.about_btn)" in source
