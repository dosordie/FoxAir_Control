"""Register audit through real table, cloud projection and scheduled FC03 reads."""
import json
import time
from pathlib import Path

import pytest

from cloud.mapping_audit import audit_cloud_mappings
from cloud.warmlink_api import normalize_data_values
from cloud.warmlink_codes import cloud_hint, cloud_modbus_register, WARMLINK_SERVICE_REGISTERS
from core.foxair_phnix_core import (
    DecodedRegister, RegisterMap, format_bitfield_details, format_value_by_type,
    crc_bytes_le, decode_frame, find_frames,
)
from test_cloud_single_read_and_values import CloudWindow, cloud_row
from test_warmlink_request_scheduler import application, window, response, pump

ROOT = Path(__file__).parents[1]
DEFINITIONS = json.loads((ROOT / "data/foxair_phnix_registers.json").read_text(encoding="utf-8"))
KNOWLEDGE = json.loads((ROOT / "data/foxair_phnix_knowledge.json").read_text(encoding="utf-8"))
REGMAP = RegisterMap(str(ROOT / "data/foxair_phnix_registers.json"))


def local_word(reg, raw, slave=0x63, source="modbus"):
    info = REGMAP.get(reg)
    return DecodedRegister(slave, reg, 0, 3, raw, raw, "", info.name, info.dtype, time.time(), value_source=source)


@pytest.mark.parametrize("reg,raw,expected", [
    (2026, 0, "0"), (2026, 128, "128"), (2026, 255, "255"),
    (2027, 255, "255"), (2028, 0xFFFF, "-1"), (2028, 0x8000, "-32768"),
    (2028, 0x7FFF, "32767"), (2056, 0xFFFF, "65535"),
])
def test_diagnostic_numeric_types_in_real_read_responses(window, reg, raw, expected):
    window.send_read_request(reg, 1, label="audit")
    window.worker._flush_write_queue()
    window.on_frame_decoded(response(window, raw))
    row = window.table_rows[reg]
    assert window.register_table.item(row, 7).text() == expected
    assert window.latest_regs[reg].raw_value == raw


def test_parameter_mask_and_unknown_bits_in_main_table(application):
    main = CloudWindow()
    main._upsert_register_row(local_word(2109, 0x8021), False)
    row = main.table_rows[2109]
    value = main.register_table.item(row, 7)
    assert all(text in value.text() for text in ("Parameterblock 1", "Parameterblock 6", "B15 (unbekannt)"))
    assert "Parameterblock 2" not in value.text()
    assert "0x8021" in main.register_table.item(row, 4).text()
    assert "1000000000100001" in value.toolTip()
    assert "1001–1090" in value.toolTip() and "1451–1540" in value.toolTip()
    for raw, expected in [(0, "Keine aktiven Bits"), (None, "–")]:
        assert format_value_by_type(raw, "BITFIELD", bit_map=REGMAP.get(2109).bit_map, compact=True) == expected
    assert set(REGMAP.get(2109).bit_map) == set(range(6))
    assert "1016" in KNOWLEDGE["2109"]["description"]
    main.deleteLater()


@pytest.mark.parametrize("reg,mask,bits", [(2139, 0x0205, [0, 2, 9]), (2152, 0x00F8, [3, 4, 5, 6, 7]), (2080, 0x4080, [7, 14])])
def test_new_status_bits_have_neutral_details_and_compact_labels(reg, mask, bits):
    info = REGMAP.get(reg)
    compact = format_value_by_type(mask, info.dtype, bit_map=info.bit_map, compact=True)
    details = format_bitfield_details(mask, info)
    for bit in bits:
        assert info.bit_map[bit] in compact and f"B{bit}:" in details
    assert f"RAW={mask}" in details and f"0x{mask:04X}" in details and f"{mask:016b}" in details
    assert DEFINITIONS[str(reg)]["mode"] == "read"
    assert not DEFINITIONS[str(reg)].get("write_allowed")
    assert KNOWLEDGE[str(reg)]["description"] == DEFINITIONS[str(reg)]["description"]
    if reg == 2139:
        assert "State 1" in details and "2071" in details and "State-2" in details
        assert "2152 Bit 6" in details
        assert "A38" in info.bit_descriptions[4] and "2115" in info.bit_descriptions[4]
    elif reg == 2152:
        assert "0x200144D1" in details and "stehen bleiben" in details
        assert "3600" in details and "500 ms" in details and "2085 Bit 0" in details
        assert "0x20016E2C+4 Bit 1" in details and "1422" in details
        assert "Aktoren offen" in info.bit_descriptions[3]


@pytest.mark.parametrize("code,register,local_code,unit", [
    ("T49", 2065, "T-Diag1", "°C"), ("T50", 2066, "T-Diag2", "K"), ("T51", 2067, "T-Diag3", "K"),
])
@pytest.mark.parametrize("value", ["-3.5", "0", "19.8"])
def test_live_cloud_aliases_keep_units_sign_and_engineering_scale(application, code, register, local_code, unit, value):
    main = CloudWindow()
    hint = cloud_hint(code)
    assert cloud_modbus_register(code) == register
    assert hint["confidence"] == "confirmed" and hint["write_allowed"] is False
    assert DEFINITIONS[str(register)]["code"] == local_code
    assert code in DEFINITIONS[str(register)]["cloud_aliases"]
    report = audit_cloud_mappings([cloud_row(value, code)])
    assert not report["errors"]
    assert next(e for e in report["codes"] if e["code"] == code)["main_register"] == register
    main.apply_cloud_rows_to_main([cloud_row(value, code, dataType="TEMP")])
    item = main.register_table.item(main.table_rows[register], 7)
    assert float(item.text().split()[0]) == float(value)
    assert item.text().endswith(unit)
    assert main.latest_regs[register].local_raw_value is None
    # A real local sample keeps its own raw scale and unit beside the cloud value.
    main._upsert_register_row(local_word(register, 98), False)
    assert main.register_table.item(main.table_rows[register], 7).text() == f"9.8 {unit}"
    assert main.cloud_overlay_by_reg[register]["engineering_value"] == float(value)
    main.deleteLater()


@pytest.mark.parametrize("code", ["T57", "T58", "T52", "T06_1", "T_PWM_Out2", "T100", "T120"])
@pytest.mark.parametrize("value", ["0", 0, "", None])
def test_cloud_zero_empty_and_unmapped_codes_remain_distinct(code, value):
    rows = normalize_data_values({"objectResult": [{"code": code, "value": value}]}, [code])
    assert rows[0]["value"] == value
    assert rows[0]["supported"] == (value not in (None, ""))
    if code != "T57":
        assert cloud_modbus_register(code) is None
    else:
        assert cloud_modbus_register(code) == 2023 and "T57" in DEFINITIONS["2023"]["cloud_aliases"]


def test_status_tabs_use_scheduler_response_timeout_and_polling(window, application):
    window.write_bus_edit.setText("0x63")
    window.open_system_io_decoder()
    dialog = window.system_io_dialog
    assert dialog.tabs.count() == 5 and not dialog.poll_timer.isActive()
    assert not window._test_transmitted  # Opening/tabs do not start background reads.
    dialog.tabs.setCurrentIndex(1)
    dialog.poll_once()
    window.worker._flush_write_queue()
    assert window.warmlink_read_scheduler.active["addr"] == 2139
    frame = response(window, 0x0211)
    window.on_frame_decoded(frame)
    assert dialog._diagnostic_values[2139] == 0x0211
    assert "Erfolgreich" in dialog.status_label.text()
    assert "Niederdruck" in dialog.diagnostic_summaries[2139].text()
    assert "0x0211" in dialog.value_label.text()
    pump(application)
    dialog.poll_once()
    window.worker._flush_write_queue()
    req = window.warmlink_read_scheduler.active
    req["time"] = time.time() - 100
    window._check_pending_read_timeouts()
    assert window.warmlink_read_scheduler.active is req  # Wallclock is not the deadline owner.
    window.warmlink_read_scheduler._timeout()  # Simulate its transport-started timer.
    assert "Timeout" in dialog.status_label.text()
    assert dialog._diagnostic_values[2139] == 0x0211
    dialog.poll_cb.setChecked(True)
    assert dialog.poll_timer.isActive()
    dialog.close()
    assert not dialog.poll_timer.isActive()
    assert all(frame[1] == 0x03 for frame in window._test_transmitted)


def test_status_dialog_preserves_io_and_rejects_cloud_or_other_bus(window):
    window.write_bus_edit.setText("0x63")
    window._upsert_register_row(local_word(2146, 0x036C), False)
    window._upsert_register_row(local_word(2147, 0xFFFE), False)
    window.open_system_io_decoder()
    dialog = window.system_io_dialog
    assert dialog._value_2146 == 0x036C and dialog._value_2147 == -2
    assert "gesperrt" in dialog.table.item(1, 2).text()
    assert dialog.table.item(4, 2).text() == "-2"
    assert not dialog.update_from_live_register(local_word(2139, 4, slave=0xC1, source="cloud"))
    assert not dialog.update_from_live_register(local_word(2139, 4, slave=0x01))
    assert 2139 not in dialog._diagnostic_values
    dialog.tabs.setCurrentIndex(3)
    assert dialog.update_from_live_register(local_word(2109, 0x8001))
    assert dialog.diagnostic_tables[2109].item(15, 1).text() == "gesetzt"
    assert "unbekannt" in dialog.diagnostic_tables[2109].item(15, 2).text()
    dialog.clear_values()
    assert dialog._value_2146 is None and dialog._value_2147 is None
    assert not dialog._diagnostic_values and dialog.diagnostic_summaries[2109].text() == "–"
    dialog.close()


@pytest.mark.parametrize("tab,register,words", [(0, 2146, [0x036C, 0xFFFE]),
    (1, 2139, [0x8000]), (2, 2152, [0x80]), (3, 2109, [0x21]), (4, 2080, [0x4080])])
def test_each_status_group_reads_only_its_words(window, tab, register, words):
    window.write_bus_edit.setText("0x63")
    window.open_system_io_decoder()
    dialog = window.system_io_dialog
    dialog.tabs.setCurrentIndex(tab)
    dialog.poll_once()
    window.worker._flush_write_queue()
    req = window.warmlink_read_scheduler.active
    assert (req["addr"], req["quantity"]) == (register, len(words))
    assert len(window._test_transmitted) == 1 and not window.warmlink_read_scheduler.queue
    payload = bytes([0x63, 3, len(words) * 2]) + b"".join(n.to_bytes(2, "big") for n in words)
    frame = decode_frame(find_frames(bytearray(payload + crc_bytes_le(payload)))[0], window.regmap)
    window.on_frame_decoded(frame)
    assert "Erfolgreich" in dialog.status_label.text()
    if tab == 0:
        assert dialog._value_2146 == words[0] and dialog._value_2147 == -2
    else:
        assert dialog._diagnostic_values[register] == words[0]
    dialog.close()


def test_diagnostic_main_words_do_not_use_dwin_map_for_display_unit(window):
    window.backend_combo.setCurrentIndex(window.backend_combo.findData("display_modbus"))
    window.write_bus_edit.setText("0x03")
    window.open_system_io_decoder()
    dialog = window.system_io_dialog
    label = "System-/I/O-Status 2109"
    window.pending_read_requests.append({"addr": 2109, "wire_addr": 2109,
        "slave_addr": 3, "quantity": 1, "time": time.time(), "label": label})
    frame = response(window, 0x21, slave=3)
    assert window._apply_pending_read_response(frame)
    assert frame.registers[0].name == REGMAP.get(2109).name
    assert frame.registers[0].dtype == "BITFIELD"
    assert dialog._diagnostic_values[2109] == 0x21
    dialog.close()


def test_no_ems_service_write_grants():
    assert all(not WARMLINK_SERVICE_REGISTERS[reg]["write_allowed"] for reg in range(8001, 8011))
