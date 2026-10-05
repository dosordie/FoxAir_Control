from copy import deepcopy

import pytest

from cloud.metadata import (
    audit_cloud_ranges, current_register_knowledge, resolve_cloud_range,
)
from cloud.register_resolver import current_register_definitions, resolve_cloud_register
from cloud.warmlink_api import normalize_data_values
from cloud.warmlink_codes import WARMLINK_CLOUD_CODE_HINTS, cloud_hint
from dialogs.cloud_table_helpers import data_table_values


@pytest.mark.parametrize("code,expected", [
    ("P10", (0, 100)), ("F23", (10, 1300)), ("F25", (10, 1300)),
    ("F26", (10, 1300)), ("D23", (0, 240)), ("E14", (0, 500)),
    ("P02", (0, 120)), ("P03", (0, 30)), ("P09", (0, 30)), ("P13", (0, 30)),
])
def test_confirmed_engineering_ranges_beat_incorrect_static_hint(code, expected):
    hint = {**cloud_hint(code), "rangeStart": "-20", "rangeEnd": "250"}
    result = resolve_cloud_range(code, hint)
    assert (result.minimum, result.maximum) == expected
    assert result.source == "knowledge" and result.confirmed
    register = resolve_cloud_register(code, hint)
    evidence = current_register_knowledge()[str(register)]["range"]
    assert evidence["representation"] == "engineering"
    assert evidence["source"] and evidence["evidence"]
    actual = cloud_hint(code)
    assert float(actual["rangeStart"]) == expected[0]
    assert float(actual["rangeEnd"]) == expected[1]


def test_live_range_overrides_confirmed_local_and_static_bounds():
    result = resolve_cloud_range("P10", cloud_hint("P10"), {"rangeStart": 0, "rangeEnd": 250})
    assert (result.minimum, result.maximum) == (0, 250)
    assert result.source == "live"
    assert result.confirmed


@pytest.mark.parametrize("live,expected", [
    ({"rangeStart": 0}, (0, "")),
    ({"rangeEnd": "85"}, ("", "85")),
    ({"rangeStart": 0, "rangeEnd": None}, (0, "")),
    ({"rangeStart": "", "rangeEnd": 0}, ("", 0)),
])
def test_partial_live_range_does_not_invent_or_mix_other_boundary(live, expected):
    result = resolve_cloud_range("P10", cloud_hint("P10"), live)
    assert (result.minimum, result.maximum) == expected
    assert result.source == "live"


@pytest.mark.parametrize("value", [True, "NaN", "Infinity", "0 bis 100", [], {}])
def test_invalid_live_bound_does_not_become_numeric_metadata(value):
    result = resolve_cloud_range("P10", cloud_hint("P10"), {"rangeStart": value, "rangeEnd": 100})
    assert (result.minimum, result.maximum) == (0, 100)
    assert result.source == "knowledge"


def test_inverted_live_range_falls_back_to_reviewed_local_range():
    result = resolve_cloud_range("P10", cloud_hint("P10"), {"rangeStart": 100, "rangeEnd": 0})
    assert result.source == "knowledge"


def test_register_definition_has_priority_over_structured_knowledge():
    definitions = deepcopy(current_register_definitions())
    definitions["1205"]["range"] = {
        "min": 10, "max": 90, "unit": "%", "representation": "engineering",
        "confidence": "confirmed", "source": "reviewed test definition",
    }
    result = resolve_cloud_range("P10", cloud_hint("P10"), definitions=definitions)
    assert (result.minimum, result.maximum) == (10, 90)
    assert result.source == "register"


@pytest.mark.parametrize("changes", [
    {"confidence": "candidate"}, {"representation": "raw"}, {"source": ""},
    {"max": None}, {"unit": "rpm"},
])
def test_unconfirmed_raw_incomplete_or_wrong_unit_local_range_is_not_evidence(changes):
    knowledge = deepcopy(current_register_knowledge())
    knowledge["1205"]["range"].update(changes)
    result = resolve_cloud_range("P10", cloud_hint("P10"), knowledge=knowledge)
    assert result.source == "hint" and not result.confirmed
    report = audit_cloud_ranges({"P10": cloud_hint("P10")}, knowledge=knowledge)
    assert report["local_ranges"] == 0
    assert not report["conflicts"]


def test_unconfirmed_mapping_cannot_use_local_range():
    hint = {**cloud_hint("P10"), "confidence": "candidate"}
    result = resolve_cloud_range("P10", hint)
    assert result.source == "hint" and not result.confirmed
    assert audit_cloud_ranges({"P10": hint})["checked"] == 0


@pytest.mark.parametrize("code", [
    "D22", "D30", "P08", "P12", "P15", "P16", "C12", "R01", "R02", "R03",
    "R08", "R09", "R10", "R11", "R29", "R30", "R32", "R33",
])
def test_doubtful_or_dynamic_static_bounds_are_removed(code):
    hint = cloud_hint(code)
    assert "rangeStart" not in hint and "rangeEnd" not in hint
    assert hint["range_note"]
    result = resolve_cloud_range(code, hint)
    assert (result.minimum, result.maximum) == ("", "")
    assert result.source == "unknown" and not result.confirmed


def test_unknown_local_range_does_not_flag_explicit_cloud_range():
    hint = {**cloud_hint("P16"), "rangeStart": "0", "rangeEnd": "250"}
    result = resolve_cloud_range("P16", hint)
    assert (result.minimum, result.maximum) == ("0", "250")
    assert result.source == "hint" and not result.confirmed
    live = resolve_cloud_range("P16", hint, {"rangeStart": 0, "rangeEnd": 250})
    assert live.source == "live"
    report = audit_cloud_ranges({"P16": hint})
    assert not report["conflicts"]
    assert report["missing_local_range"] == ["P16"]


def test_no_runtime_extraction_from_description_default_enum_or_unit():
    knowledge = {"1205": {"description": "0 bis 100%", "default": 50}}
    hint = {**cloud_hint("P10")}
    hint.pop("rangeStart")
    hint.pop("rangeEnd")
    result = resolve_cloud_range("P10", hint, knowledge=knowledge)
    assert result.source == "unknown"
    assert (result.minimum, result.maximum) == ("", "")


def test_live_unit_change_does_not_reuse_ranges_in_a_different_unit():
    assert resolve_cloud_range("P10", cloud_hint("P10"), {"unit": "rpm"}).source == "unknown"
    live = {"unit": "rpm", "rangeStart": 10, "rangeEnd": 1300}
    result = resolve_cloud_range("P10", cloud_hint("P10"), live)
    assert (result.minimum, result.maximum, result.unit) == (10, 1300, "rpm")


def test_range_audit_flags_only_confirmed_numeric_conflicts():
    hints = {
        "P10": {**cloud_hint("P10"), "rangeStart": "0", "rangeEnd": "250"},
        "P16": {**cloud_hint("P16"), "rangeStart": "0", "rangeEnd": "250"},
        "F25": {**cloud_hint("F25"), "rangeStart": "10.00", "rangeEnd": "1300.0"},
    }
    report = audit_cloud_ranges(hints)
    assert report["checked"] == 3 and report["local_ranges"] == 2
    assert report["conflicts"] == [{"code": "P10", "register": 1205,
        "hint_range": ["0", "250"], "local_range": [0, 100], "source": "knowledge"}]
    assert report["unverified_static_ranges"] == ["P16"]


def test_all_reviewed_ranges_pass_final_audit():
    report = audit_cloud_ranges(WARMLINK_CLOUD_CODE_HINTS)
    assert report["checked"] >= 262
    assert report["local_ranges"] >= 64
    assert not report["conflicts"]


def test_cloud_table_and_mapping_export_resolve_ranges_without_altering_live_rows():
    from dialogs.cloud_dialog import WarmLinkCloudDialog

    item = {"code": "P10", "value": 58}
    row = normalize_data_values({"objectResult": [item]}, ["P10"])[0]
    values, _status = data_table_values(row)
    assert values[4:6] == [0, 100]
    assert row["rangeStart"] is None and row["raw"] == item
    assert WarmLinkCloudDialog._mapping_candidate_cloud_values(None, row)[5:7] == [0, 100]
    live_row = {**row, "rangeStart": 0, "rangeEnd": 250}
    assert data_table_values(live_row)[0][4:6] == [0, 250]
    assert WarmLinkCloudDialog._mapping_candidate_cloud_values(None, live_row)[5:7] == [0, 250]
