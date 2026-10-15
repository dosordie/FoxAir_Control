"""Display/Unit-1 source separation and the existing resync handshake in simulation."""
import json
import time
from pathlib import Path

import pytest

from core.display_protocol import REQUIRED_PARAMETER_PACKETS, validate_parameter_packet
from core.foxair_phnix_core import (
    RegisterMap, build_read_frame, build_write_registers_frame, crc_bytes_le,
    decode_frame, decode_read_response_registers, find_frames, format_value_by_type,
)
from dialogs.backup_restore_dialog import BackupRestoreDialog
from dialogs.offline_register_browser_dialog import OfflineRegisterBrowserDialog
from ui.context_menu_helpers import build_register_context_menu
from test_warmlink_request_scheduler import application, window as base_window

ROOT = Path(__file__).parents[1]
DISPLAY = RegisterMap(str(ROOT / "data/foxair_phnix_display_registers.json"))
MAIN = RegisterMap(str(ROOT / "data/foxair_phnix_registers.json"))


@pytest.fixture
def window(base_window):
    yield base_window
    base_window.display_fake_reboot_state = {}


def decoded(raw, regmap=MAIN):
    return decode_frame(find_frames(bytearray(raw))[0], regmap)


def response_words(words, slave=1):
    payload = bytes([slave, 3, len(words) * 2]) + b"".join(int(n).to_bytes(2, "big") for n in words)
    return decoded(payload + crc_bytes_le(payload))


def packet(start, slave=3, count=90):
    words = [0] * count
    identity = b"WF0123456789"  # Synthetic identifier matching the observed shape.
    words[:6] = [int.from_bytes(identity[n:n+2], "big") for n in range(0, 12, 2)]
    words[8:10] = [0x0210, start]
    return decoded(build_write_registers_frame(start, words, slave_addr=slave))


def set_display(window):
    window.backend_combo.setCurrentIndex(window.backend_combo.findData("display_modbus"))
    window.write_bus_edit.setText("0x03")


def test_shared_header_validator_preserves_partial_diagnostic_range():
    words = [reg.raw_value for reg in packet(1001, count=10).registers]
    assert validate_parameter_packet(1001, words) is None
    assert validate_parameter_packet(1001, words, complete=False)["end"] == 1010


def start_wait(window, *, age=1):
    set_display(window)
    window.display_fake_reboot_state = {
        "active": True, "phase": "wait_upload", "started": time.monotonic() - age,
        "packets_since": time.monotonic() - age, "upload_wait_started": time.monotonic() - age,
        "attempt": 3, "max_attempts": 3, "flag_retries": 5,
    }


@pytest.mark.parametrize("virtual,raw,text", [
    (91102, 0xAB25, "37 Hz"), (91103, 90, "90 Hz"),
    (91104, 100, "45 °C"), (91105, 230, "230 V"),
    (91106, 37, "3.7 A"), (91107, 56, "5.6 A"), (91108, 325, "325 V"),
    (91110, 95, "40 °C"), (91110, 100, "45 °C"), (91110, 107, "52 °C"),
    (91110, 0xAB64, "45 °C"), (91118, 0xFFFF, "-1"),
    (91118, 0x8000, "-32768"), (91130, 605, "605 rpm"), (91142, 555, "555 rpm"),
])
def test_unit1_telemetry_runs_through_real_table_with_own_encoding(window, virtual, raw, text):
    set_display(window)
    words = [0] * 51
    words[virtual - 91099] = raw
    # Preserve unrelated MAIN words even when their alias is present in telemetry.
    window.last_values.update({2080: 0x40, 2081: 0x8000, 2082: 3})
    window.on_frame_decoded(decoded(build_read_frame(2099, 51, slave_addr=1)))
    window.on_frame_decoded(response_words(words))
    assert set(range(91099, 91150)) <= set(window.latest_regs)
    assert window.latest_regs[virtual].raw_value == raw
    row = window.table_rows[virtual]
    assert window.register_table.item(row, 7).text() == text
    tooltip = window.register_table.item(row, 7).toolTip()
    assert f"INV1:{virtual - 89000}" in tooltip and str(virtual) in tooltip
    assert [window.last_values[n] for n in (2080, 2081, 2082)] == [0x40, 0x8000, 3]


def test_virtual_word_kinds_and_fault_namespace_are_not_main_copies():
    info = DISPLAY.get(91113)
    assert format_value_by_type(0xAB12, info.dtype) == "0xAB12: High=171, Low=18"
    assert 15 not in DISPLAY.get(91100).bit_map  # MAIN-local communication bit.
    assert 15 in MAIN.get(2081).bit_map
    assert DISPLAY.get(91101).dtype == "UINT16"  # Unknown source stays unsigned raw.
    assert DISPLAY.get(91109).dtype == "FAULT_BITS"
    assert all(DISPLAY.get(n).metadata["virtual"] for n in range(91099, 91150))


def test_matched_active_unit1_read_also_projects_before_main_acceptance(window):
    set_display(window)
    window.pending_read_requests.append({"addr": 2099, "wire_addr": 2099,
        "slave_addr": 1, "quantity": 51, "time": time.time(), "label": "manuelles Popup"})
    frame = response_words([0] * 51)
    window.on_frame_decoded(frame)
    assert frame.typ == 91099 and 91110 in window.latest_regs
    assert 2109 not in window.latest_regs and 2139 not in window.latest_regs


@pytest.mark.parametrize("slave,count,crc", [(1, 50, True), (1, 51, False), (4, 51, True)])
def test_partial_corrupt_or_foreign_unit1_data_cannot_be_promoted(window, slave, count, crc):
    set_display(window)
    frame = response_words([0] * count, slave)
    frame.typ = 2099
    frame.registers = decode_read_response_registers(frame, 2099, MAIN)
    frame.crc_ok = crc
    assert not window._display_hmi_promote_0x01_2099_virtual(frame)
    assert not window._display_hmi_should_apply_registers(frame, 3, False, False)


def test_virtual_ids_never_create_wire_requests_and_have_own_browser_group(window):
    set_display(window)
    for register in (91099, 91110, 91149):
        window.send_read_request(register, slave_addr=3)
        window.send_register_write(register, 1, slave_addr=3)
        window.open_register_quick_write(register, 3)
    assert window.worker.write_queue.empty() and not window.pending_read_requests
    menu, actions = build_register_context_menu(window, 91110, slave_addr=1)
    assert not actions and all(not action.isEnabled() for action in menu.actions())
    menu.close()
    browser = OfflineRegisterBrowserDialog(window)
    browser.search_edit.clear()
    browser.source_combo.setCurrentIndex(browser.source_combo.findData("unit1"))
    assert len(browser.items) == 51
    browser.table.selectRow(0)
    browser._show_selected_description()
    assert not browser.read_btn.isEnabled() and not browser.write_btn.isEnabled()
    assert "Unit 0x01" in browser.description_box.text()
    browser.read_selected(); browser.write_selected()
    assert window.worker.write_queue.empty()
    browser.close()


def test_dwin_catalog_enums_masks_rtc_and_object_words():
    assert set(MAIN.items).isdisjoint(DISPLAY.items)
    sync = DISPLAY.get(3011)
    assert sync.dtype == "BITFIELD" and not sync.value_map
    text = format_value_by_type(0x8006, sync.dtype, bit_map=sync.bit_map)
    assert all(part in text for part in ("1001", "1091", "Initialisierung", "0x8006"))
    assert DISPLAY.get(3012).metadata["firmware_examples"] == {"V1.7": 463}
    assert format_value_by_type(17, DISPLAY.get(3013).dtype) == "V1.7"
    assert format_value_by_type(18, DISPLAY.get(3013).dtype) == "V1.8"
    assert DISPLAY.get(3016).metadata["raw_range"] == [1, 7]
    assert not DISPLAY.get(3016).value_map
    assert format_value_by_type(26, DISPLAY.get(3017).dtype) == "2026"
    for reg in (4726, 4727, *range(4736, 4744)):
        info = DISPLAY.get(reg)
        assert "ausblenden" in info.name
        assert "sichtbar" in info.value_map[0] or info.value_map[0] == "anzeigen"
        assert "ausgeblendet" in info.value_map[1] or info.value_map[1] == "ausblenden"
    assert set(DISPLAY.get(4730).value_map) == set(DISPLAY.get(4731).value_map) == {0, 1, 2}
    for reg in (5920, 5936, 6144, 6272, 6656):
        assert DISPLAY.get(reg).dtype == "UINT16"
        assert "°C" not in format_value_by_type(100, DISPLAY.get(reg).dtype)


def test_dwin_display_value_uses_display_catalog_and_sensor_zero_caveat(window):
    set_display(window)
    words = [0] * 21
    words[10:13] = [0x8006, 463, 17]
    words[15:21] = [7, 26, 10, 15, 12, 30]
    window.pending_read_requests.append({"addr": 3001, "wire_addr": 3001,
        "slave_addr": 3, "quantity": 21, "time": time.time(), "label": "DWIN"})
    window.on_frame_decoded(response_words(words, 3))
    assert window.register_table.item(window.table_rows[3013], 7).text() == "V1.7"
    assert "Parameterpaket ab 1001" in window.register_table.item(window.table_rows[3011], 7).text()
    assert "Sensorfehler" in DISPLAY.get(4722).metadata["description"]


@pytest.mark.parametrize("count,optional,complete", [(4, False, False), (4, True, False), (5, True, False), (6, False, True), (6, True, True)])
def test_resync_requires_every_fresh_valid_required_packet(window, monkeypatch, count, optional, complete):
    start_wait(window)
    monkeypatch.setattr(window, "_display_0bc3_value_from_3001", lambda: 0x8000)
    for start in REQUIRED_PARAMETER_PACKETS[:count]:
        window._display_hmi_log_block_diff(packet(start))
    if optional:
        window._display_hmi_log_block_diff(packet(1541))
    window._display_fake_reboot_check_upload()
    assert (not window.display_fake_reboot_state.get("active")) is complete
    if complete:
        assert window.display_last_sync_result["complete"]
        assert not window.display_last_sync_result["missing"]
        assert "vollständig synchronisiert" in window.display_init_progress_text
        assert bool(window.display_last_sync_result["optional_received"]) is optional
    else:
        assert window.init_progress_bar.value() == count
        assert "fehlen" in window.display_init_progress_text
        assert "vollständig synchronisiert" not in window.display_init_progress_text


@pytest.mark.parametrize("kind", ["stale", "short", "unit", "crc", "header"])
def test_invalid_or_cached_packets_do_not_complete_sync(window, kind):
    start_wait(window)
    now = time.monotonic()
    if kind == "stale":
        window.display_valid_param_packet_times = {start: now - 60 for start in REQUIRED_PARAMETER_PACKETS}
        window.display_hmi_block_snapshot_times = {(3, start, "word-frame"): now for start in REQUIRED_PARAMETER_PACKETS}
    else:
        frame = packet(1001, slave=4 if kind == "unit" else 3, count=10 if kind == "short" else 90)
        if kind == "crc": frame.crc_ok = False
        if kind == "header": frame.registers[9].raw_value = 1091
        assert not window._record_display_parameter_packet(frame)
    assert not window._display_reboot_fresh_param_blocks(now - 1)


def test_partial_timeout_keeps_real_progress_and_lists_missing_packets(window):
    start_wait(window, age=30)
    for start in REQUIRED_PARAMETER_PACKETS[:4]:
        window._display_hmi_log_block_diff(packet(start))
    window._display_fake_reboot_check_upload()
    result = window.display_last_sync_result
    assert not result["complete"] and result["missing"] == [1361, 1451]
    assert "teilweise synchronisiert (4/6)" in window.display_init_progress_text
    assert window.init_progress_bar.value() == 4 and window.init_progress_bar.maximum() == 6
    assert not window.display_fake_reboot_state


def test_complete_sync_through_the_full_frame_pipeline(window, monkeypatch):
    start_wait(window)
    monkeypatch.setattr(window, "_display_0bc3_value_from_3001", lambda: 0x8000)
    for start in REQUIRED_PARAMETER_PACKETS:
        window.on_frame_decoded(packet(start))
    assert len(window.display_valid_param_packet_times) == 6
    window._display_fake_reboot_check_upload()
    assert window.display_last_sync_result["complete"]


def test_passive_source_decoder_has_unit1_metadata_before_projection(window):
    set_display(window)
    window.on_frame_decoded(decoded(build_read_frame(2099, 51, slave_addr=1)))
    words = [0] * 51
    words[11] = 100
    frame = response_words(words)
    assert window._apply_observed_display_read_response(frame)
    assert frame.registers[11].name == DISPLAY.get(91110).name
    assert frame.registers[11].display_value == "45 °C"


@pytest.mark.parametrize("busy", ["capture", "parameter", "queue", "restore"])
def test_resync_does_not_interleave_with_writes_or_capture(window, monkeypatch, busy):
    set_display(window)
    if busy == "capture": monkeypatch.setattr(window, "_is_firmware_capture_mode", lambda: True)
    elif busy == "parameter": window.display_user_value_state = {"active": True}
    elif busy == "queue": window.worker.enqueue_write(1018, 1)
    else: window.pending_write_requests.append({"time": time.time(), "label": "Restore"})
    before = window.worker.write_queue.qsize()
    assert not window._start_display_reboot_snapshot(force=True)
    assert window.worker.write_queue.qsize() == before


def test_restore_1017_from_old_backup_is_blocked_and_unknown_slots_survive(window):
    dialog = BackupRestoreDialog(window)
    dialog.loaded_backup = {"registers": [{"reg": 1017, "raw_value": 99}, {"reg": 1089, "raw_value": 65535}]}
    assert 1017 not in dialog.backup_registers() and 1017 not in dialog.restore_registers()
    assert [reg for reg, _value, _name in dialog._restore_items("changed")] == [1089]
    assert "Unbekannter Parameter" == MAIN.get(1017).name
    assert "Logo" in MAIN.get(1026).name
    dialog.close()


def test_no_parameter_write_can_start_during_resync(window):
    start_wait(window)
    window.send_register_write(1018, 1, slave_addr=3, label="Restore")
    assert window.worker.write_queue.empty()


def test_backend_change_cancels_old_display_sync_callbacks(window):
    start_wait(window)
    window.backend_combo.setCurrentIndex(window.backend_combo.findData("warmlink_raw"))
    window._backend_changed()
    window._display_fake_reboot_send_flag()
    window._display_fake_reboot_check_upload()
    assert not window.display_fake_reboot_state and window.worker.write_queue.empty()
