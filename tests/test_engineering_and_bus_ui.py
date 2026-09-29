import json
from pathlib import Path

from cloud.warmlink_codes import WARMLINK_SERVICE_SLAVE, warmlink_service_metadata
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
    for register in ("1430", "1492", "1540"):
        assert not engineering_parameter_is_visible(definitions[register], {"show_engineering_parameters": False})
        assert engineering_parameter_is_visible(definitions[register], {"show_engineering_parameters": True})

    assert definitions["1430"]["code"] == "MAIN1430"
    assert definitions["1492"]["code"] == "MAIN1492"
    assert definitions["1540"]["code"] == "REMOTE1540"


def test_service_metadata_is_transport_scoped_and_read_only():
    known = warmlink_service_metadata(WARMLINK_SERVICE_SLAVE, 8022)
    unknown = warmlink_service_metadata(WARMLINK_SERVICE_SLAVE, 8099)
    assert known["name"] == "Heating Compressor Frequency Cap"
    assert known["type"] == "uint16"
    assert known["write_allowed"] is False
    assert unknown == {
        "name": "Warmlink Service Register 8099", "type": "RAW",
        "mode": "service-observed", "write_allowed": False,
    }
    assert warmlink_service_metadata(0x01, 8022) is None


def test_documented_bus_roles():
    expected = {
        0x00: "Mainboard-Broadcast", 0x01: "Inverterboard", 0x02: "zweiter HMI",
        0x03: "Hauptdisplay", 0x04: "Fan-Driver", 0x05: "Hydraulik",
        0x61: "Hydraulikmodul", 0x63: "Mainboard als Slave",
    }
    for address, fragment in expected.items():
        assert fragment in " ".join(display_bus_address_info(address))
    assert "separater" in display_bus_address_info(0x63)[2]
