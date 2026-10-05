import pytest

from cloud.metadata import audit_cloud_units, resolve_cloud_unit
from cloud.register_resolver import current_register_definitions, resolve_cloud_register
from cloud.warmlink_api import normalize_data_values
from cloud.warmlink_codes import WARMLINK_CLOUD_CODE_HINTS, cloud_hint, code_unit
from cloud.warmlink_value_translator import translate_cloud_value


@pytest.mark.parametrize("code,unit", [("F23", "rpm"), ("P10", "%"), ("P16", "bar")])
def test_confirmed_local_unit_beats_wrong_temp_hint(code, unit):
    hint = {**cloud_hint(code), "unit": "°C", "cloud_dataType": "TEMP"}
    register = resolve_cloud_register(code, hint)
    definition = current_register_definitions()[str(register)]
    assert resolve_cloud_unit(code, hint) == unit
    assert translate_cloud_value(code, 58, definition, hint, {"dataType": "TEMP"}).display == f"58 {unit}"


def test_explicit_live_unit_beats_local_and_static_metadata():
    hint = {**cloud_hint("P10"), "unit": "°C"}
    assert resolve_cloud_unit("P10", hint, {"unit": "rpm"}) == "rpm"
    assert code_unit("P10", {"unit": "rpm"}) == "rpm"


@pytest.mark.parametrize("unit", [None, "", "   ", 12, {"name": "°C"}])
def test_invalid_live_unit_is_not_unit_evidence(unit):
    assert resolve_cloud_unit("P10", cloud_hint("P10"), {"unit": unit}) == "%"


def test_temp_does_not_imply_temperature_and_candidates_do_not_override():
    assert resolve_cloud_unit("unknown", {"cloud_dataType": "TEMP"}) == ""
    assert resolve_cloud_unit("F23", {**cloud_hint("F23"), "confidence": "candidate", "unit": "W"}, definition={"unit": "rpm"}) == "W"
    assert code_unit("T09") == "°C"  # existing temperature evidence, no local unit


def test_normalization_preserves_optional_live_metadata_and_original():
    item = {"protocolCode": "F23", "currentValue": 70, "dataType": "TEMP",
            "unit": "rpm", "dataTypeAi": "number", "tmJson": {"step": 1},
            "rangeStart": 0, "rangeEnd": 100, "precision": 0}
    row = normalize_data_values({"objectResult": [item]}, ["F23", "P10"])[0]
    for field in ("unit", "dataTypeAi", "tmJson", "rangeStart", "rangeEnd", "precision"):
        assert row[field] == item[field]
    assert row["raw"] == item
    assert row["supported"] and row["value"] == 70
    minimal = normalize_data_values({"objectResult": [{"code": "P10", "value": 58}]}, ["P10"])[0]
    assert "unit" not in minimal and "tmJson" not in minimal
    shorthand = {"P10": 58}
    assert normalize_data_values({"objectResult": [shorthand]}, ["P10"])[0]["raw"] == shorthand


def test_unit_audit_is_clean_and_detects_conflicts_with_evidence():
    report = audit_cloud_units(WARMLINK_CLOUD_CODE_HINTS)
    assert report["checked"] > 250
    assert not report["conflicts"]
    bad = {**cloud_hint("F23"), "unit": "°C"}
    report = audit_cloud_units({"F23": bad, "T09": cloud_hint("T09"),
                                "candidate": {"confidence": "candidate", "unit": "W"}})
    assert report["checked"] == 2
    assert report["conflicts"] == [{"code": "F23", "register": 1089, "hint_unit": "°C", "local_unit": "rpm"}]
    assert report["missing_local_unit"] == ["T09"]


def test_all_confirmed_local_units_override_injected_contradictory_hint():
    definitions = current_register_definitions()
    for code, hint in WARMLINK_CLOUD_CODE_HINTS.items():
        register = resolve_cloud_register(code, hint)
        if register is None:
            continue
        definition = definitions[str(register)]
        unit = definition.get("unit")
        if unit:
            bad_hint = {**hint, "unit": "wrong-unit", "cloud_dataType": "TEMP"}
            assert resolve_cloud_unit(code, bad_hint) == unit, code
