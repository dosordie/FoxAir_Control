import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MAIN_MAP_PATH = ROOT / "data/foxair_phnix_registers.json"
DISPLAY_MAP_PATH = ROOT / "data/foxair_phnix_display_registers.json"
DISPLAY_ONLY_REGISTERS = set(range(3001, 3022)) | {91105, 91108}


def _numeric_keys(data: dict) -> set[int]:
    return {int(key) for key in data if str(key).isdigit()}


def _load_static_maps() -> tuple[dict, dict]:
    main = json.loads(MAIN_MAP_PATH.read_text(encoding="utf-8"))
    display = json.loads(DISPLAY_MAP_PATH.read_text(encoding="utf-8"))
    return main, display


def test_main_and_display_register_maps_do_not_overlap():
    main, display = _load_static_maps()

    duplicate_registers = sorted(_numeric_keys(main) & _numeric_keys(display))

    assert duplicate_registers == []


def test_register_map_ignores_known_json_comment_metadata(tmp_path):
    from core.foxair_phnix_core import RegisterMap

    mapping_path = tmp_path / "registers.json"
    mapping_path.write_text(
        json.dumps({"_comment": "metadata only", "1001": {"name": "Known", "type": "RAW"}}),
        encoding="utf-8",
    )

    regmap = RegisterMap(str(mapping_path))

    assert 1001 in regmap.items
    assert len(regmap.items) == 1


def test_register_map_rejects_unexpected_non_numeric_keys(tmp_path):
    from core.foxair_phnix_core import RegisterMap

    mapping_path = tmp_path / "registers.json"
    mapping_path.write_text(
        json.dumps({"213X": {"name": "Typo", "type": "RAW"}}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Invalid register map key '213X'"):
        RegisterMap(str(mapping_path))


def test_backend_register_map_separation_uses_actual_loaded_maps():
    from core.foxair_phnix_core import RegisterMap

    main = RegisterMap(str(MAIN_MAP_PATH))
    display = RegisterMap(str(DISPLAY_MAP_PATH))

    # Warmlink and Standard-Modbus pass only MainWindow.regmap into ReaderWorker.
    warmlink_regs = set(main.items)
    standard_modbus_regs = set(main.items)

    assert DISPLAY_ONLY_REGISTERS.isdisjoint(warmlink_regs)
    assert DISPLAY_ONLY_REGISTERS.isdisjoint(standard_modbus_regs)

    # Modbus Display keeps normal WP registers in the main map and display-only
    # / virtual registers in the separate display map.
    assert set(range(3012, 3022)).issubset(display.items)
    assert {91105, 91108}.issubset(display.items)
    assert {2122, 2133}.issubset(main.items)
    assert set(range(3012, 3022)).isdisjoint(main.items)
    assert {2122, 2124}.isdisjoint(display.items)


def test_fw33_confirmed_register_metadata_and_interface_boundary():
    main, _display = _load_static_maps()

    sg01_values = main["1334"]["value_map"]
    assert set(sg01_values) == {str(value) for value in range(8)}
    assert sg01_values["3"] == "Klassisch: Modbus 8801 / 4 Zustände"
    assert sg01_values["4"] == "AI Saving / Remote Energy Control"
    assert all(str(value) in sg01_values for value in (5, 6, 7))
    assert "tatsächlich laufend" in main["2019"]["bit_map"]["0"]
    assert "Lüfter tatsächlich aktiv" in main["2019"]["bit_map"]["2"]
    assert main["2057"]["name"] == "T35 / AC Input Current"
    assert main["2071"]["name"] == "Kompressor-Sollfrequenz"
    assert main["2109"]["name"] == "Internes Ereignis-/Statusbitfeld"
    assert main["2109"]["type"] == "BITFIELD"
    assert main["2136"]["type"] == "TEMP1"
    assert main["2137"]["type"] == main["2138"]["type"] == "POWER_KW_X10"
    assert main["2125"]["name"].endswith("High Word")
    assert main["2126"]["name"].endswith("Low Word")
    assert main["2127"]["name"].endswith("High Word")
    assert main["2128"]["name"].endswith("Low Word")
    assert main["2178"]["type"] == main["2180"]["type"] == "TEMP1"
    assert main["2179"]["type"] == "DIGI5"
    assert main["2179"]["unit"] == "% rF"

    # The newer mapping documents the direct-only virtual SG input explicitly;
    # backend gating is handled by the SG editor rather than by hiding metadata.
    assert main["8801"]["name"] == "Virtueller SG-Ready Eingang"


def test_fw34_external_outdoor_sensor_metadata_and_fallback():
    main, _display = _load_static_maps()

    selector = main["1463"]
    assert selector["code"] == "H101"
    assert selector["value_map"]["0"].startswith("Normaler/interner AT-Fühler T04")
    assert selector["value_map"]["1"].startswith("Externer AT-Fühler aktiv")
    assert "fällt die Regelung auf T04 zurück" in selector["description"]
    assert main["2033"]["name"] == "optionaler zweiter Außentemperaturfühler"
    assert main["2034"]["bit_map"]["5"] == "S06 Fernheizung/Kühlung / Remote Heat-Cool"
    assert "noch nicht abschließend bestätigt" in main["2034"]["description"]
    assert "könnte DIN2 entsprechen" in main["2034"]["description"]
    assert "2033=409,1 ohne bestätigte Einheit" in main["2088"]["description"]
    assert main["2048"]["name"] == "Verwendete Außentemperatur / Outdoor temperature in use"
    assert "including fallback" in main["2048"]["description_en"]


def test_reverse_engineered_temperature_sources_and_diagnostics():
    main, _display = _load_static_maps()

    for register in (1049, 1231, 1464):
        assert main[str(register)]["temperature_source"] == "effective_at"

    for register in (*range(1167, 1173), 1229, 1230, 1233, 1356, 1437):
        assert main[str(register)]["temperature_source"] == "local_t04"

    assert main["1464"]["name"] == "AT-Grenzwert Heiz-/Sommerabschaltung"
    assert main["1464"]["hysteresis"] == "-3.0 K"
    assert main["1465"]["name"] == "Verzögerungszeit Heiz-/Sommerabschaltung"
    assert "1465 × 120 Scheduler-Ticks" in main["1465"]["description"]

    assert main["1561"]["mode"] == "read"
    assert main["1561"]["type"] == "MINUTES"
    assert "A34 - elapsed/120" in main["1561"]["description"]
    assert main["1852"]["mode"] == "read"
    assert main["1852"]["type"] == "RPM"
    assert main["1852"]["unit"] == "rpm"

    external_sensor = main["2033"]
    assert external_sensor["type"] == "TEMP1"
    assert external_sensor["unit"] == "°C"
    assert "Analogkanal 23" in external_sensor["description"]
    assert "Klemme 3/4" in external_sensor["description"]
    assert "Fehlerwert ist keine Temperaturangabe" in external_sensor["description"]


def test_confirmed_flow_and_multizone_mapping_metadata():
    main, _display = _load_static_maps()

    assert main["1022"]["type"] == "FLOW_M3H_X100"
    assert main["1022"]["unit"] == "m³/h"
    assert "Q_eff = Q_base" in main["1022"]["description"]
    assert [main[str(reg)]["type"] for reg in (2160, 2161, 2162)] == ["TEMP1"] * 3
    assert main["2163"]["type"] == "PERCENT"
    assert "100 - RAW" in main["2163"]["description"]
    for reg in (2140, 2141, 2142, 2143):
        assert main[str(reg)]["type"] == "RAW"
        assert "physikalische Bedeutung ist weiterhin offen" in main[str(reg)]["description"]


def test_issue_register_mappings_and_diag_bitmaps():
    main, _display = _load_static_maps()

    assert main["2109"]["type"] == "BITFIELD"
    assert main["2146"]["type"] == "BITFIELD"
    assert main["2146"]["baseline"] == "0x002C"
    assert "Heiz-/Sommerabschaltung aktiv" in main["2146"]["bit_map"]["4"]
    assert main["2146"]["bit_map"]["6"] == "Variabel, Bedeutung offen"
    assert main["1349"]["write_min"] == 1
    assert main["1464"]["temperature_source"] == "effective_at"
    assert "Heiz-/Sommerabschaltung" in main["1464"]["name"]
    assert set(str(reg) for reg in range(6073, 6081)).issubset(main)
    assert all(main[str(reg)]["type"] == "BITFIELD" for reg in range(6073, 6081))
    assert main["6073"]["bit_map"]["2"] == "internes Raw-I/O-Bit6"
    assert main["6074"]["bit_map"]["5"] == "fest 0"
    assert main["6080"]["bit_map"]["5"] == "+0x1A Bit10"

    keys = list(main)
    assert keys.index("2149") < keys.index("2151") < keys.index("2152")
    assert keys.index("2152") < keys.index("2155") < keys.index("2160")


def test_c14_write_minimum_is_loaded_and_validated():
    from core.foxair_phnix_core import RegisterMap, validate_register_write_value

    info = RegisterMap(str(MAIN_MAP_PATH)).get(1349)
    assert info.write_min == 1
    assert validate_register_write_value(1, info) == 1
    with pytest.raises(ValueError, match="mindestens 1"):
        validate_register_write_value(0, info)


def test_v35_remote_main_register_metadata():
    main, _display = _load_static_maps()

    gate = main["1540"]
    assert gate["mode"] == "r/w"
    assert gate["firmware"] == "V3.5+"
    assert gate["default"] == "0"
    assert gate["value_map"] == {"0": "Aus", "1": "Ein"}
    assert "Warmlink" in gate["app_label"]

    effective_target = main["1557"]
    assert effective_target["mode"] == "read"
    assert effective_target["type"] == "TEMP1"
    assert effective_target["firmware"] == "V3.5+"

    scaling = main["1492"]
    assert scaling["ui_visibility"] == "engineering"
    assert "rangeStart" not in scaling and "rangeEnd" not in scaling
    assert main["1430"]["ui_visibility"] == "engineering"
    assert "firmware" not in main["1430"]


def test_v35_warmlink_service_registers_stay_separate_from_main_map():
    from cloud.warmlink_codes import (
        WARMLINK_SERVICE_REGISTERS,
        WARMLINK_SERVICE_SLAVE,
    )

    main, _display = _load_static_maps()
    assert WARMLINK_SERVICE_SLAVE == 0x63
    assert set(range(8021, 8029)).issubset(WARMLINK_SERVICE_REGISTERS)
    assert set(range(8021, 8029)).isdisjoint(_numeric_keys(main))

    for register in range(8021, 8024):
        item = WARMLINK_SERVICE_REGISTERS[register]
        assert "Cap" in item["name"]
        assert item["ttl_minutes"] == 20
        assert item["effect"].startswith("effective_reference = min(")

    assert WARMLINK_SERVICE_REGISTERS[8021]["operating_mode"] == "Cooling"
    assert WARMLINK_SERVICE_REGISTERS[8022]["operating_mode"] == "Heating"
    assert WARMLINK_SERVICE_REGISTERS[8023]["operating_mode"] == "DHW"

    assert "R03 - value" in WARMLINK_SERVICE_REGISTERS[8024]["effect"]
    assert "R02 + value" in WARMLINK_SERVICE_REGISTERS[8025]["effect"]
    assert "R01 + value" in WARMLINK_SERVICE_REGISTERS[8026]["effect"]
    for register in range(8024, 8029):
        assert WARMLINK_SERVICE_REGISTERS[register]["ttl_minutes"] == 120
    for register in (8027, 8028):
        assert "Heating: target += offset" in WARMLINK_SERVICE_REGISTERS[register]["effect"]
        assert "Cooling: target -= offset" in WARMLINK_SERVICE_REGISTERS[register]["effect"]

    boost = WARMLINK_SERVICE_REGISTERS[8055]
    assert "engineering" in boost["mode"]
    assert boost["write_allowed"] is False
    assert "ttl_minutes" not in boost
    assert "RAM-only" in boost["persistence"]


def test_every_normal_register_write_uses_central_validation():
    source = (ROOT / "foxair_phnix_control.py").read_text(encoding="utf-8")
    after_send_write = source.split("    def send_register_write(", 1)[1]
    send_write = after_send_write.split("\n    def ", 1)[0]
    direct_write = after_send_write.split("    def send_write_frame(", 1)[1].split("\n    def ", 1)[0]
    timer_write = source.split("    def send_timer_values(", 1)[1].split("\n    def ", 1)[0]

    validation = "validate_register_write_value(int(value), self.regmap.get(addr))"
    assert validation in send_write
    assert send_write.index(validation) < send_write.index("_queue_display_param_user_write_from_normal")
    assert "self.send_register_write(addr, value" in direct_write
    assert ".enqueue_write(" not in direct_write
    assert "validate_register_write_value(int(value), self.regmap.get(int(addr)))" in timer_write


def test_sg_ready_editor_handles_direct_only_8801():
    source = (ROOT / "dialogs" / "sg_ready_editor_dialog.py").read_text(encoding="utf-8")
    logic = (ROOT / "core" / "sg_ready.py").read_text(encoding="utf-8")
    docs = (ROOT / "docs" / "sg_ready.md").read_text(encoding="utf-8")

    assert "READ_LABEL_VIRTUAL = \"SG virtueller Eingang 8801\"" in source
    assert "SG_MODE_OPTIONS" in source
    assert "uses_virtual_sg_input" in source
    assert "Virtueller SG-Modus (8801, nur direkt)" in source
    assert 'int(sg_mode) in (3, 7)' in logic
    assert 'str(backend_key) == "standard_modbus"' in logic
    assert "Low PV – Begrenzung über SG03 (1336)" in logic
    assert "Neutral / Normalbetrieb – keine SG-Anpassung" in logic
    assert "High PV – SG05/SG06 Anhebung, SG07 Absenkung" in logic
    assert "`5/6/7`" in docs
    assert "AI Saving / Remote Energy Control" in docs
    assert "Low PV / Neutral / High PV" in docs
    assert "10-minütige Umschaltsperre" in docs
    assert "zunächst auf `0` und anschließend wieder auf `3`" in docs
