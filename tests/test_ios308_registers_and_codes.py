"""Confirmed register semantics and conservative iOS request coverage."""
import json
from pathlib import Path

import pytest

from cloud.register_resolver import resolve_cloud_register
from cloud.warmlink_codes import (
    ALL_WARMLINK_CLOUD_CODES, WARMLINK_644_DISCOVERY_CODES,
    WARMLINK_SERVICE_REGISTERS, cloud_hint, cloud_modbus_register,
)
from cloud.warmlink_ios308_catalog import WARMLINK_IOS308_CODES, WARMLINK_IOS308_PWM_CODES
from cloud.warmlink_api import normalize_data_values
from cloud.polling import CloudSession
from core.foxair_phnix_core import RegisterMap, format_value_by_type
from workers.warmlink_cloud_worker import supported_codes_for_next_poll

ROOT = Path(__file__).parents[1]


def definitions():
    return json.loads((ROOT / "data/foxair_phnix_registers.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize(("service", "mirror"), [
    (8001, 2151), (8002, 2153), (8003, 2156), (8004, 2154),
    (8005, 2155), (8007, 2157), (8008, 2158),
])
def test_ems_sources_and_read_only_mirrors(service, mirror):
    metadata = WARMLINK_SERVICE_REGISTERS[service]
    assert metadata["main_mirror"] == mirror
    assert metadata["write_allowed"] is False
    register = definitions()[str(mirror)]
    assert register["mode"] == "read" and register["write_allowed"] is False
    assert register["service_source"] == {"slave_addr": "0x63", "register": service}
    assert not register.get("unit")
    assert not metadata.get("unit")


def test_all_ten_service_inputs_exist_and_other_namespaces_remain_separate():
    assert set(range(8001, 8011)) <= WARMLINK_SERVICE_REGISTERS.keys()
    assert all(WARMLINK_SERVICE_REGISTERS[n]["write_allowed"] is False for n in range(8001, 8011))
    assert WARMLINK_SERVICE_REGISTERS[8004]["main_mirror"] != 1427
    assert "main_mirror" not in WARMLINK_SERVICE_REGISTERS[8006]
    assert "main_mirror" not in WARMLINK_SERVICE_REGISTERS[8009]
    assert "main_mirror" not in WARMLINK_SERVICE_REGISTERS[8010]
    data = definitions()
    assert data["1427"]["mode"] != "service-observed"
    assert data["8801"]["mode"] == "r/w"
    assert set(data["8801"]["value_map"]) == {"1", "2", "3", "4"}
    assert "service_source" not in data["8801"]


def test_frequency_limits_only_have_confirmed_labels_and_unknown_bits_stay_raw():
    info = RegisterMap(str(ROOT / "data/foxair_phnix_registers.json")).get(2139)
    assert info.dtype == "BITFIELD"
    assert set(info.bit_map) == {1, 3, 4, 5, 6, 8, 10}
    mask = sum(1 << bit for bit in info.bit_map)
    rendered = format_value_by_type(mask, info.dtype, info.value_map, info.bit_map)
    for label in info.bit_map.values():
        assert label in rendered
    unknown = format_value_by_type(1 << 15, info.dtype, None, info.bit_map)
    assert "0x8000" in unknown and "1000000000000000" in unknown
    assert "B15:" not in unknown


def test_ems_state_is_u16_bitfield_not_zone_or_enum():
    data = definitions()["2152"]
    assert data["type"] == "BITFIELD" and data["mode"] == "read"
    assert "value_map" not in data
    assert {0, 1, 2} <= {int(bit) for bit in data["bit_map"]}
    info = RegisterMap(str(ROOT / "data/foxair_phnix_registers.json")).get(2152)
    rendered = format_value_by_type(5, info.dtype, info.value_map, info.bit_map)
    assert "0x0005" in rendered and "0000000000000101" in rendered


@pytest.mark.parametrize("register", [2154, 2156])
def test_power_mirrors_are_signed_raw_without_units_or_scaling(register):
    info = RegisterMap(str(ROOT / "data/foxair_phnix_registers.json")).get(register)
    assert info.dtype == "INT16"
    assert format_value_by_type(0xFFFE, info.dtype) == "-2"
    assert format_value_by_type(123, info.dtype) == "123"


def test_soc_is_not_timer_or_invented_percent_and_knowledge_agrees():
    data = definitions()
    knowledge = json.loads((ROOT / "data/foxair_phnix_knowledge.json").read_text(encoding="utf-8"))
    assert data["2155"]["type"] == "RAW" and "Timer" not in data["2155"]["name"]
    assert "Battery_SoC" in data["2155"]["app_label_goheating_pro"]
    assert "Batterieladezustand" in knowledge["2155"]["description"]
    assert all(str(n) in data and str(n) in knowledge for n in range(2151, 2159))
    assert data["2105"]["name"] == "Softwarecode"
    assert data["2105"]["app_label_goheating_pro"] == "MainBoard Version"


def test_oem_labels_are_provenance_without_replacing_precise_names():
    labels = {
    "2011": "Power State",
    "2012": "Mode State",
    "2013": "Compensate Limit Temp",
    "2045": "Inlet Water Temp.",
    "2046": "Outlet Water Temp.",
    "2047": "DHW Tank Temp.",
    "2048": "Ambient  Temp. (AT)",
    "2052": "Buffer Tank Temp.",
    "2054": "Power Input(ODU+IDU)",
    "2059": "Capacity Output(ODU+IDU)",
    "2060": "COP/EER(ODU+IDU)",
    "2071": "Compressor Frequency",
    "2076": "Target Speed of Fan Motor",
    "2077": "Water Flow Rate",
    "2105": "MainBoard Version",
    "2151": "Current EMS Strategy Command",
    "2152": "EMS Strategy Command State",
    "2153": "Electricity_Price",
    "2154": "OnGrid Power",
    "2155": "Battery_SoC",
    "2156": "Battery_Power"
}
    data = definitions()
    for register, label in labels.items():
        assert data[register]["app_label_goheating_pro"] == label
    assert data["2013"]["type"] == "TEMP1"
    assert data["2054"]["name"] == "Elektrische Leistung / Unit Power"
    assert data["2059"]["name"] == "Wärmeleistung / Unit Capacity"
    assert data["2060"]["name"] == "COP"
    assert data["2071"]["name"] == "Kompressor-Sollfrequenz"


def test_protected_service_commands_keep_existing_limits_and_write_blocks():
    for n in range(8021, 8024):
        metadata = WARMLINK_SERVICE_REGISTERS[n]
        assert metadata["ttl_minutes"] == 20
        assert metadata["ttl_group"] == "frequency_caps"
        assert metadata["write_allowed"] is False
    for n in range(8024, 8029):
        metadata = WARMLINK_SERVICE_REGISTERS[n]
        assert metadata["ttl_minutes"] == 120
        assert metadata["ttl_group"] == "target_offsets"
        assert metadata["type"] == "int16" and metadata["write_allowed"] is False
    assert WARMLINK_SERVICE_REGISTERS[8055]["type"] == "signed int16"
    assert WARMLINK_SERVICE_REGISTERS[8055]["write_allowed"] is False
    assert WARMLINK_SERVICE_REGISTERS[8055]["persistence"] == "RAM-only; Boot-Default 0; kein eigener Mainboard-TTL"


def test_additive_coverage_keeps_work_baseline_and_exact_literal_codes():
    baseline = json.loads((ROOT / "tests/fixtures/warmlink_work_ffe6f194_codes.json").read_text())
    assert len(WARMLINK_IOS308_CODES) == len(set(WARMLINK_IOS308_CODES)) == 108
    assert set(baseline["all_codes"]) <= set(ALL_WARMLINK_CLOUD_CODES)
    assert set(baseline["discovery_codes"]) <= set(WARMLINK_644_DISCOVERY_CODES)
    assert set(WARMLINK_IOS308_CODES) <= set(ALL_WARMLINK_CLOUD_CODES)
    assert set(WARMLINK_IOS308_CODES) <= set(WARMLINK_644_DISCOVERY_CODES)
    assert len(ALL_WARMLINK_CLOUD_CODES) == len(set(ALL_WARMLINK_CLOUD_CODES)) == 505
    assert len(WARMLINK_644_DISCOVERY_CODES) == len(set(WARMLINK_644_DISCOVERY_CODES)) == 530
    assert "S01~S11" in WARMLINK_IOS308_CODES and "O25~O27" in WARMLINK_IOS308_CODES


@pytest.mark.parametrize("code", [
    "Run_Mode", "1250", "1256", "1268", "CP2-1", "CompPreHeatRemainTim", *WARMLINK_IOS308_PWM_CODES,
])
def test_observed_unknown_codes_have_no_invented_mapping_or_write_grant(code):
    hint = cloud_hint(code)
    assert not hint["write_allowed"]
    assert hint["confidence"] == "unknown"
    assert resolve_cloud_register(code, hint) is None
    assert resolve_cloud_register(code, {**hint, "modbus_register": 1250}) is None
    assert not hint.get("unit") or code == "CP2-1"  # Existing observed TEMP metadata is preserved.


@pytest.mark.parametrize("code", WARMLINK_IOS308_PWM_CODES)
@pytest.mark.parametrize("value", ["", None, "0", 0])
def test_pwm_empty_null_and_zero_stay_distinct_and_retryable(code, value):
    rows = normalize_data_values({"objectResult": [{"code": code, "value": value}]}, [code])
    row = rows[0]
    assert row["value"] == value
    empty = value in (None, "")
    assert row["supported"] is not empty
    assert row["cloud_supported"] is None if empty else row["cloud_supported"] is True
    session = CloudSession()
    session.merge(rows)
    session.classify([code], rows)
    assert session.retry_codes == ([code] if empty else [])
    assert session.supported_codes == ([] if empty else [code])
    assert supported_codes_for_next_poll([code], rows) == [code]


def test_confirmed_h36_and_zone1_curve_mappings_remain_authoritative():
    assert cloud_hint("H36")["confidence"] == "confirmed"
    assert cloud_modbus_register("H36") == 1236 and cloud_hint("H36")["write_allowed"] is True
    assert cloud_modbus_register("CP1-1") == 1250
    assert cloud_hint("CP1-1")["write_allowed"] is False


def test_empty_app_candidates_do_not_abort_a_valid_discovered_session(monkeypatch):
    from cloud.warmlink_api import WarmLinkCloudApi
    from workers import warmlink_cloud_worker as workers
    codes = list(WARMLINK_IOS308_PWM_CODES)
    class EmptyAppApi(WarmLinkCloudApi):
        def get_data_by_code_batched(self, device_code, requested, **kwargs):
            return {"objectResult": [{"code": code, "value": ""} for code in requested]}
        def get_device_status(self, device_code):
            return {"isResultSuc": True}
    monkeypatch.setattr(workers, "WarmLinkCloudApi", EmptyAppApi)
    session = CloudSession(username="user", device_code="device", validated=True,
                           devices_cached=True, devices=[{"deviceCode": "device"}])
    worker = workers.WarmLinkCloudWorker("user", "", codes, device_code="device",
        initial_token="test-token", session=session, poll_once=True)
    errors, states = [], []
    worker.error.connect(errors.append)
    worker.connection_state.connect(states.append)
    worker.run()
    assert errors == [] and states[-1] == "CONNECTED"
    assert worker.session.retry_codes == codes
    assert all(row["cloud_supported"] is None for row in worker.session.rows.values())
