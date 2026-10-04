import pytest

from cloud.warmlink_644_catalog import (
    WARMLINK_644_APP_FAULTS,
    WARMLINK_644_APP_PARAMETERS,
    app_644_cloud_code,
)
from cloud.warmlink_api import (
    WarmLinkAuthError,
    WarmLinkCloudApi,
    WarmLinkCloudError,
    normalize_data_values,
)
from cloud.warmlink_codes import (
    WARMLINK_644_DISCOVERY_CODES,
    WARMLINK_CLOUD_CODE_HINTS,
    WARMLINK_PRODUCT_IDS,
    merged_cloud_metadata,
)
from workers.warmlink_cloud_worker import (
    devices_with_known_code_fallback,
    supported_codes_for_next_poll,
)


def test_official_644_catalog_is_complete_and_has_key_labels():
    assert len(WARMLINK_644_APP_PARAMETERS) == 254
    expected = {
        "P10": "Speed of Circulation Pump",
        "P11": "Target Temp. Diff. for Pump Speed Control",
        "P12": "Pump Speed Adjust Range for Each Period",
        "H31": "Circulation Pump Type",
        "D26": "Enable Defrosting Communication in Cascade",
        "O12": "Crankcase Heater",
        "O13": "Bottom Plate Heater",
        "T02": "Outlet Water Temp",
        "T30": "Compressor Frequency",
        "T39": "Water Flow",
    }
    assert {code: WARMLINK_644_APP_PARAMETERS[code]["app_label"] for code in expected} == expected


def test_app_evidence_does_not_override_confirmed_metadata_or_grant_writes():
    merged = merged_cloud_metadata("A03")
    assert merged["name"] == WARMLINK_CLOUD_CODE_HINTS["A03"]["name"]
    assert merged["app_label_644"] == "Shutdown Ambient Temp."
    assert merged["confidence"] == "confirmed"
    assert merged["modbus_register"] == 1037
    assert merged["write_allowed"] is True  # pre-existing, confirmed grant

    candidate = merged_cloud_metadata("O12")
    assert candidate["app_known"] is True
    assert candidate["cloud_hint_known"] is False
    assert candidate["cloud_supported"] is None
    assert candidate["write_allowed"] is False
    assert candidate["write_confirmed"] is False


def test_catalog_spellings_product_id_and_fault_namespace_are_separate():
    assert app_644_cloud_code("E03_1") == "E03-1"
    assert "E03_1" not in WARMLINK_644_DISCOVERY_CODES
    assert "E03-1" in WARMLINK_644_DISCOVERY_CODES
    assert "1737029209242152961" in WARMLINK_PRODUCT_IDS
    assert len(WARMLINK_644_APP_FAULTS) == 93
    assert WARMLINK_644_APP_FAULTS["F01"]["app_label"] == "Compressor Activation Failure"
    assert WARMLINK_644_APP_PARAMETERS["F01"]["app_label"] == "Fan Motor Type"


def test_fault9_fault10_are_cloud_live_and_modbus_mapping_stays_inferred():
    for code, register in (("Fault9", 2083), ("Fault10", 2084)):
        hint = WARMLINK_CLOUD_CODE_HINTS[code]
        assert code in WARMLINK_644_DISCOVERY_CODES
        assert hint["cloud_live_confirmed"] is True
        assert hint["cloud_dataType"] == "BINARY"
        assert hint["modbus_register"] == register
        assert hint["modbus_mapping_confidence"] == "strongly-inferred-family-644"
        assert hint["confidence"] == "candidate"
        assert hint["write_allowed"] is False


def test_o11_remains_app_only_and_points_to_grouped_alarm_word():
    merged = merged_cloud_metadata("O11")
    assert merged["app_known"] is True
    assert merged["cloud_hint_known"] is False
    assert merged["cloud_supported"] is None
    assert merged["modbus_mapped"] is False
    assert merged["write_confirmed"] is False
    assert "O01~023 bit 10" in merged["note"]


def test_empty_discovery_keeps_known_device_code():
    assert devices_with_known_code_fallback([], " 860147058259753 ") == [{
        "deviceCode": "860147058259753",
        "discoverySource": "stored-device-code",
    }]
    assert devices_with_known_code_fallback([], None) == []


def test_discovery_reduces_followup_poll_to_live_supported_codes():
    discovery = [f"Code{i}" for i in range(418)]
    rows = [
        {"code": code, "supported": index < 150}
        for index, code in enumerate(discovery)
    ]
    poll_codes = supported_codes_for_next_poll(discovery, rows)
    assert poll_codes == discovery[:150]
    assert not set(discovery[150:]) & set(poll_codes)


def test_batched_dump_survives_unsupported_batch():
    class FakeApi(WarmLinkCloudApi):
        def __init__(self):
            pass

        def get_data_by_code(self, device_code, codes):
            if "bad" in codes:
                return {"isReusltSuc": False, "error_msg": "unsupported"}
            return {"isReusltSuc": True, "objectResult": [
                {"code": code, "value": "1", "dataType": "ENUM"} for code in codes
            ]}

    response = FakeApi().get_data_by_code_batched("device", ["ok", "bad", "later"], batch_size=3)
    rows = normalize_data_values(response, ["ok", "bad", "later"])
    assert {row["code"] for row in rows if row["supported"]} == {"ok", "later"}
    assert next(row for row in rows if row["code"] == "bad")["supported"] is False
    assert next(row for row in rows if row["code"] == "bad")["cloud_supported"] is False
    assert next(row for row in rows if row["code"] == "ok")["cloud_supported"] is True
    assert len(response["batchFailures"]) == 1


def test_batched_dump_does_not_bisect_transport_failures():
    class OfflineApi(WarmLinkCloudApi):
        def __init__(self):
            self.calls = 0

        def get_data_by_code(self, device_code, codes):
            self.calls += 1
            raise OSError("offline")

    api = OfflineApi()
    try:
        api.get_data_by_code_batched("device", ["A03", "A04", "A05"])
    except OSError as exc:
        assert str(exc) == "offline"
    else:
        raise AssertionError("transport failure was swallowed")
    assert api.calls == 1


@pytest.mark.parametrize(
    ("response", "error_type"),
    [
        ({"http_status": 401, "isReusltSuc": False}, WarmLinkAuthError),
        ({"error_code": "-100", "isReusltSuc": False}, WarmLinkAuthError),
        ({"http_status": 500, "isReusltSuc": False}, WarmLinkCloudError),
        ({"http_status": 429, "isReusltSuc": False}, WarmLinkCloudError),
    ],
)
def test_batched_dump_does_not_bisect_global_api_failures(response, error_type):
    class FailedApi(WarmLinkCloudApi):
        def __init__(self):
            self.calls = 0

        def get_data_by_code(self, device_code, codes):
            self.calls += 1
            return dict(response)

    api = FailedApi()
    with pytest.raises(error_type):
        api.get_data_by_code_batched("device", ["A03", "A04", "A05"])
    assert api.calls == 1
