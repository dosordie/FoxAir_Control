from cloud.known_devices import (
    merge_discovered_and_known_devices,
    normalize_known_device_codes,
    remove_known_device_code,
    select_available_device_code,
    validation_has_value,
)
from workers import warmlink_cloud_worker


def device(code, **metadata):
    return {"deviceCode": code, **metadata}


def test_merge_appends_manual_device_to_discovery():
    assert [item["deviceCode"] for item in merge_discovered_and_known_devices(
        [device("A")], ["B"],
    )] == ["A", "B"]


def test_merge_deduplicates_and_preserves_automatic_metadata():
    automatic = device(
        "B", deviceNickName="Wärmepumpe", deviceId="id-b",
        productId="product-b", productionCode="production-b", status="online",
    )
    merged = merge_discovered_and_known_devices([device("A"), automatic], ["B"])
    assert [item["deviceCode"] for item in merged] == ["A", "B"]
    assert merged[1] == {**automatic, "discoverySource": "deviceList"}


def test_saved_manual_selection_wins_over_first_automatic_device():
    merged = merge_discovered_and_known_devices([device("A")], ["B"])
    assert select_available_device_code(merged, "B") == "B"


def test_multiple_manual_devices_and_empty_discovery_are_supported():
    merged = merge_discovered_and_known_devices([], [" B ", "C", "D"])
    assert [item["deviceCode"] for item in merged] == ["B", "C", "D"]
    assert all(item["discoverySource"] == "manual" for item in merged)


def test_remove_manual_device_from_settings_and_dropdown_source():
    known = remove_known_device_code(["B", "C"], "B")
    assert known == ["C"]
    assert [item["deviceCode"] for item in merge_discovered_and_known_devices([], known)] == ["C"]


def test_removing_manual_registration_keeps_automatic_device_visible():
    known = remove_known_device_code(["B"], "B")
    merged = merge_discovered_and_known_devices([device("B", deviceNickName="Cloud")], known)
    assert merged == [device("B", deviceNickName="Cloud", discoverySource="deviceList")]


def test_known_device_settings_are_trimmed_deduplicated_and_accept_old_structures():
    assert normalize_known_device_codes([
        " B ", {"deviceCode": "C", "source": "manual"}, "B", "", None,
    ]) == ["B", "C"]


def test_validation_requires_at_least_one_real_cloud_value():
    assert validation_has_value([{"supported": True, "value": "644", "dataType": "string"}])
    assert not validation_has_value([{"supported": False, "value": ""}])
    assert not validation_has_value([])


class FakeValidationApi:
    response = {}

    def __init__(self, *args, **kwargs):
        self.token = "refreshed-token"

    def get_data_by_code(self, device_code, codes):
        assert device_code == "B"
        assert codes == ["MainBoard Version", "code_version"]
        return self.response

    @staticmethod
    def success(response):
        return bool(response.get("isReusltSuc"))

    @staticmethod
    def _token_expired(response):
        return False

    @staticmethod
    def message(response):
        return str(response.get("error_msg", ""))


def test_successful_get_data_validation_emits_device_for_persistence(monkeypatch):
    FakeValidationApi.response = {
        "isReusltSuc": True,
        "objectResult": [{"code": "MainBoard Version", "value": "644", "dataType": "string"}],
    }
    monkeypatch.setattr(warmlink_cloud_worker, "WarmLinkCloudApi", FakeValidationApi)
    worker = warmlink_cloud_worker.WarmLinkKnownDeviceValidationWorker("user", "pw", " B ")
    validated = []
    errors = []
    worker.validated.connect(lambda code, rows: validated.append((code, rows)))
    worker.error.connect(errors.append)
    worker.run()
    assert errors == []
    assert validated[0][0] == "B"
    assert validated[0][1][0]["value"] == "644"


def test_failed_get_data_validation_does_not_emit_device(monkeypatch):
    FakeValidationApi.response = {"isReusltSuc": False, "error_msg": "no permission"}
    monkeypatch.setattr(warmlink_cloud_worker, "WarmLinkCloudApi", FakeValidationApi)
    worker = warmlink_cloud_worker.WarmLinkKnownDeviceValidationWorker("user", "pw", "B")
    validated = []
    errors = []
    worker.validated.connect(lambda code, rows: validated.append((code, rows)))
    worker.error.connect(errors.append)
    worker.run()
    assert validated == []
    assert errors == ["no permission"]
