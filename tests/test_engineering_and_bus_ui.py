import json
from pathlib import Path

from cloud.warmlink_codes import warmlink_service_rows
from core.bus_address_info import display_bus_address_info
from core.settings_manager import engineering_parameter_is_visible, ensure_defaults


def test_engineering_visibility_defaults_off_and_does_not_change_metadata():
    settings = ensure_defaults({})
    engineering = {"ui_visibility": "engineering", "write_allowed": False}
    assert settings["show_engineering_parameters"] is False
    assert not engineering_parameter_is_visible(engineering, settings)
    settings["show_engineering_parameters"] = True
    assert engineering_parameter_is_visible(engineering, settings)
    assert engineering["write_allowed"] is False
    assert engineering_parameter_is_visible({}, {})

    definitions = json.loads((Path(__file__).parents[1] / "data/foxair_phnix_registers.json").read_text(encoding="utf-8"))
    for register in ("1430", "1492"):
        assert not engineering_parameter_is_visible(definitions[register], {"show_engineering_parameters": False})
        assert engineering_parameter_is_visible(definitions[register], {"show_engineering_parameters": True})
        assert definitions[register]["code"] == f"MAIN{register}"


def test_service_diagnosis_is_complete_and_read_only():
    rows = warmlink_service_rows({8021: 47, 8055: 10})
    assert [int(row["register"]) for row in rows] == list(range(8021, 8029)) + [8055]
    assert rows[0]["raw"] == "47"
    assert rows[-1]["raw"] == "10"
    assert all("0x63" in row["transport"] for row in rows)
    assert all("nicht freigegeben" in row["write_status"] for row in rows)


def test_documented_bus_roles():
    expected = {
        0x00: "Mainboard-Broadcast", 0x01: "Inverterboard", 0x02: "zweiter HMI",
        0x03: "Hauptdisplay", 0x04: "Fan-Driver", 0x05: "Hydraulik",
        0x61: "Hydraulikmodul", 0x63: "Mainboard als Slave",
    }
    for address, fragment in expected.items():
        assert fragment in " ".join(display_bus_address_info(address))
    assert "separater" in display_bus_address_info(0x63)[2]
