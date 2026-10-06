"""Audit every reviewed mapping through the actual MAIN projection path."""

import time

import pytest

from cloud.mapping_audit import audit_cloud_mappings
from cloud.register_resolver import (
    resolve_cloud_projection_register, resolve_cloud_register,
)
from cloud.warmlink_codes import (
    WARMLINK_644_DISCOVERY_CODES, WARMLINK_CLOUD_CODE_HINTS,
    WARMLINK_GL9_TESTED_UNSUPPORTED_CODES, cloud_hint, merged_cloud_metadata,
)
from core.foxair_phnix_core import DecodedRegister
from dialogs.cloud_dialog import WarmLinkCloudDialog
from test_cloud_single_read_and_values import application, CloudWindow, cloud_row
from test_cloud_polling import DialogWindow


CONFIRMED_CODES = sorted(
    code for code, hint in WARMLINK_CLOUD_CODE_HINTS.items()
    if hint.get("confidence") == "confirmed" and hint.get("modbus_register") is not None
)


@pytest.mark.parametrize("code", CONFIRMED_CODES)
@pytest.mark.parametrize("local_present", [False, True], ids=["cloud-only", "local-overlay"])
def test_every_confirmed_mapping_projects_to_main(application, code, local_present):
    window = CloudWindow()
    hint = cloud_hint(code)
    register = hint["modbus_register"]
    assert str(register) in window.register_defs
    assert resolve_cloud_register(code, hint) == register
    assert resolve_cloud_projection_register(code, hint) == register
    assert window._validated_cloud_modbus_register(code, hint)[::2] == (register, "")
    if local_present:
        info = window.regmap.get(register)
        local = DecodedRegister(0x63, register, 0, 3, 4321, 4321, "local value",
                                info.name, info.dtype, time.time())
        window._upsert_register_row(local, changed=False)
        window.last_values[register] = 4321
    window.apply_cloud_rows_to_main([cloud_row("1", code)])
    assert window.cloud_overlay_by_reg[register]["code"] == code
    assert window.cloud_overlay_by_reg[register]["engineering_value"] == 1
    assert register in window.table_rows
    assert window.register_table.rowCount() == 1
    if local_present:
        assert window.latest_regs[register] is local
        assert window.last_values[register] == 4321
        assert window.register_value_sources(register).local_raw == 4321
    else:
        assert register not in window.last_values
        assert window.latest_regs[register].local_raw_value is None
        assert window.latest_regs[register].cloud_value == 1
    window.deleteLater()


def test_static_audit_reports_aliases_without_claiming_runtime_support():
    report = audit_cloud_mappings()
    assert not report["errors"]
    assert report["counts"]["confirmed_mapped"] == len(CONFIRMED_CODES)
    assert report["counts"]["supported"] is None
    assert report["counts"]["supported_unmapped"] is None
    assert all(entry["supported"] is None for entry in report["codes"])
    assert report["aliases"] == [
        {"main_register": 1206, "codes": ["1206", "E03-3"]},
        {"main_register": 1208, "codes": ["1208", "E03-5"]},
        {"main_register": 2029, "codes": ["2029", "InputCurrent1"]},
    ]


@pytest.mark.parametrize("alias", audit_cloud_mappings()["aliases"])
def test_aliases_keep_one_main_row_and_accept_each_code(application, alias):
    window = CloudWindow()
    register = alias["main_register"]
    codes = alias["codes"]
    window.apply_cloud_rows_to_main([cloud_row("7", code) for code in codes])
    assert window.register_table.rowCount() == 1
    assert window.cloud_overlay_by_reg[register]["code"] == codes[0]
    # A later single response from the other alias updates the same row.
    row = window.table_rows[register]
    window.apply_cloud_rows_to_main([cloud_row("8", codes[1])])
    assert window.register_table.rowCount() == 1
    assert window.table_rows[register] == row
    assert window.cloud_overlay_by_reg[register]["code"] == codes[1]
    assert window.cloud_overlay_by_reg[register]["engineering_value"] == 8
    window.deleteLater()


def test_audit_current_support_is_independent_of_mapping_and_historical_tests():
    report = audit_cloud_mappings([
        cloud_row("0", "2119"), cloud_row("35", "CP2-1"), cloud_row("512", "Fault8"),
        cloud_row("", "Switch2168", supported=False), cloud_row("1", "new-device-code"),
    ])
    entries = {entry["code"]: entry for entry in report["codes"]}
    assert not report["errors"]
    assert report["counts"]["supported"] == 4
    assert report["counts"]["supported_unmapped"] == 3
    assert entries["2119"]["gl9_tested_supported"] is True
    assert entries["2119"]["supported"] is True
    assert entries["2119"]["mapping_intentionally_absent"]
    assert entries["Switch2168"]["supported"] is False
    assert entries["CP1-4"]["supported"] is None
    assert not entries["new-device-code"]["known"]
    assert entries["new-device-code"]["mapping_missing"]


def test_audit_detects_broken_targets_and_unreviewed_numeric_aliases():
    report = audit_cloud_mappings(hints={
        "Fault1": {"confidence": "confirmed", "modbus_register": 2081},
        "2119": {"confidence": "confirmed", "modbus_register": 2119},
    }, register_defs={"2119": {"name": "Energy high"}}, discovery_codes=["2119", "Fault1"])
    assert {error["error"] for error in report["errors"]} == {
        "target_missing", "confirmed_mapping_unresolved",
    }
    assert report["counts"]["confirmed_mapped"] == 0


UNMAPPED_APP_CODES = ["CP1-4", *(f"CP2-{point}" for point in range(1, 8)),
                      "Zone 2 Curve Offset", "2119", "Switch2168"]


@pytest.mark.parametrize("code", UNMAPPED_APP_CODES)
def test_unmapped_app_codes_stay_in_discovery_without_main_guesses(application, code):
    assert code in WARMLINK_644_DISCOVERY_CODES
    assert merged_cloud_metadata(code)["app_known"]
    hint = cloud_hint(code)
    assert hint["mapping_intentionally_absent"]
    assert not hint["write_allowed"]
    assert "modbus_register" not in hint
    assert resolve_cloud_register(code, hint) is None
    assert resolve_cloud_projection_register(code, hint) is None
    window = CloudWindow()
    window.apply_cloud_rows_to_main([cloud_row("0", code)])
    assert not window.cloud_overlay_by_reg and not window.table_rows
    assert window.cloud_last_rows[0]["code"] == code
    window.deleteLater()


def test_supported_unmapped_values_remain_visible_in_cloud_dialog(application):
    window = DialogWindow()
    dialog = WarmLinkCloudDialog(window)
    dialog.tabs.setCurrentIndex(1)
    dialog.show()
    rows = [cloud_row("0", "2119"), cloud_row("35", "CP1-4"), cloud_row("40", "CP2-1")]
    dialog._on_data(rows)
    assert {row["code"] for row in dialog.data_rows} == {row["code"] for row in rows}
    assert set(dialog._data_codes) == {row["code"] for row in rows}
    assert not window.table_rows and not window.cloud_overlay_by_reg
    dialog.close()
    window.deleteLater()


@pytest.mark.parametrize("code", ["I28", "H55", "T100", "T101"])
def test_923_codes_are_not_in_644_catalog_or_mapping(code):
    assert code not in WARMLINK_644_DISCOVERY_CODES
    assert not cloud_hint(code)
    assert resolve_cloud_projection_register(code, cloud_hint(code)) is None


def test_sg_binary_word_and_distinct_numeric_cloud_code(application):
    assert "Switch2168" in WARMLINK_GL9_TESTED_UNSUPPORTED_CODES
    window = CloudWindow()
    window.apply_cloud_rows_to_main([
        cloud_row("0010110000000000", "S01~S10", dataType="BINARY"),
        cloud_row("3", "SG Status", dataType="DIGI1"),
        cloud_row("0", "2119", dataType="DIGI1"),
    ])
    assert window.cloud_overlay_by_reg[2034]["engineering_value"] == 0x2C00 == 11264
    assert window.cloud_overlay_by_reg[2133]["engineering_value"] == 3
    assert 2119 not in window.table_rows
    assert window.register_table.rowCount() == 2
    window.deleteLater()
