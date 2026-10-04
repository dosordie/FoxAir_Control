from cloud.warmlink_644_catalog import (
    WARMLINK_644_APP_FAULTS,
    WARMLINK_644_APP_PARAMETERS,
    app_644_cloud_code,
)
from cloud.warmlink_api import WarmLinkCloudApi, normalize_data_values
from cloud.warmlink_codes import (
    WARMLINK_644_DISCOVERY_CODES,
    WARMLINK_CLOUD_CODE_HINTS,
    WARMLINK_PRODUCT_IDS,
    merged_cloud_metadata,
)
from workers.warmlink_cloud_worker import devices_with_known_code_fallback


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
    assert candidate["cloud_supported"] is False
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


def test_empty_discovery_keeps_known_device_code():
    assert devices_with_known_code_fallback([], " 860147058259753 ") == [{
        "deviceCode": "860147058259753",
        "discoverySource": "stored-device-code",
    }]
    assert devices_with_known_code_fallback([], None) == []


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
    assert len(response["batchFailures"]) == 1
