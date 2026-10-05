import pytest

from cloud.known_devices import merge_device_sources
from cloud.warmlink_api import (
    ENDPOINT_GET_FAULT_DATA_V2,
    ENDPOINT_HOUSE_DEVICES,
    ENDPOINT_HOUSE_LIST,
    WarmLinkAuthError,
    WarmLinkCloudApi,
    normalize_house_devices,
    normalize_house_list,
)
from workers.warmlink_cloud_worker import discover_cloud_devices


def success(object_result):
    return {"isReusltSuc": True, "error_code": 0, "objectResult": object_result}


def test_normalize_house_list_keeps_owner_and_membership_metadata_only():
    houses = normalize_house_list(success([
        {"id": "100", "houseName": "A", "roleType": "0", "address": "secret"},
        {"id": "200", "houseName": "B", "roleType": "1", "latitude": 1.2},
    ]))
    assert houses == [
        {"id": "100", "houseName": "A", "roleType": "0"},
        {"id": "200", "houseName": "B", "roleType": "1"},
    ]


def test_normalize_house_devices_reads_direct_and_room_lists_and_drops_secrets():
    response = success({"data": [{
        "areaId": "area",
        "houseRelDeviceList": [{"deviceCode": "direct", "deviceNickName": "Area", "deviceSecret": "no"}],
        "roomInfoResultList": [{
            "roomId": "room",
            "houseRelDeviceList": [{
                "deviceCode": "room-device", "deviceNickName": "Room", "deviceStatus": "ONLINE",
                "deviceSecret": "no", "dtuIccid": "no", "dtuImeiMac": "no", "lat": 1,
                "lon": 2, "address": "no",
            }],
        }],
    }]})
    devices = normalize_house_devices(response, {"id": "200", "houseName": "B", "roleType": "1"})
    assert [device["deviceCode"] for device in devices] == ["direct", "room-device"]
    assert devices[1]["roomId"] == "room"
    assert devices[1]["houseId"] == "200"
    forbidden = {"deviceSecret", "dtuIccid", "dtuImeiMac", "lat", "lon", "address"}
    assert not forbidden.intersection(devices[0])
    assert not forbidden.intersection(devices[1])


def test_source_priority_is_device_list_then_house_then_manual():
    merged = merge_device_sources(
        [{"deviceCode": "B", "deviceNickName": "Cloud DeviceList"}],
        [{"deviceCode": "B", "deviceNickName": "House Device"}, {"deviceCode": "C", "deviceNickName": "House C"}],
        ["B", "C", "D"],
    )
    assert [device["deviceCode"] for device in merged] == ["B", "C", "D"]
    assert merged[0]["deviceNickName"] == "Cloud DeviceList"
    assert merged[0]["discoverySource"] == "deviceList + House"
    assert merged[1]["deviceNickName"] == "House C"
    assert merged[1]["discoverySource"] == "house"
    assert merged[2] == {"deviceCode": "D", "discoverySource": "manual"}


class DiscoveryApi:
    def get_devices(self):
        return success([{"deviceCode": "direct", "deviceNickName": "Direct"}])

    def get_houses(self):
        return success([{"id": value, "houseName": value, "roleType": "1"} for value in ("A", "B", "C")])

    def get_house_devices(self, house_id):
        if house_id == "B":
            return {"isReusltSuc": False, "error_code": 9, "error_msg": "broken"}
        return success({"data": [{"houseRelDeviceList": [{"deviceCode": house_id}]}]})

    @staticmethod
    def success(response): return bool(response.get("isReusltSuc"))
    @staticmethod
    def message(response): return str(response.get("error_msg") or "")
    @staticmethod
    def _token_expired(response): return str(response.get("error_code")) in {"401", "-100"}


def test_partial_house_failure_retains_other_house_devices_and_logs_error():
    logs = []
    devices = discover_cloud_devices(DiscoveryApi(), [], log=logs.append)
    assert [device["deviceCode"] for device in devices] == ["direct", "A", "C"]
    assert any("House B" in line and "Fehler" in line for line in logs)


def test_house_auth_failure_is_not_swallowed():
    class AuthApi(DiscoveryApi):
        def get_house_devices(self, house_id):
            return {"isReusltSuc": False, "error_code": -100, "error_msg": "please login again"}

    with pytest.raises(WarmLinkAuthError):
        discover_cloud_devices(AuthApi(), [])


def test_production_house_get_and_post_payloads(monkeypatch):
    api = WarmLinkCloudApi("user", "", initial_token="token")
    calls = []
    monkeypatch.setattr(api, "get", lambda endpoint, relogin=True: calls.append(("GET", endpoint, None)) or success([]))
    monkeypatch.setattr(api, "post", lambda endpoint, payload, relogin=True: calls.append(("POST", endpoint, payload)) or success([]))
    api.get_houses()
    api.get_house_devices("28096")
    assert calls == [
        ("GET", ENDPOINT_HOUSE_LIST, None),
        ("POST", ENDPOINT_HOUSE_DEVICES, {"appId": 16, "houseId": "28096", "level": 0}),
    ]


def test_v2_fault_request_uses_device_code_list_and_rejects_empty(monkeypatch):
    api = WarmLinkCloudApi("user", "", initial_token="token")
    captured = {}
    monkeypatch.setattr(api, "post", lambda endpoint, payload, relogin=True: captured.update(endpoint=endpoint, payload=payload) or success([]))
    api.get_fault_data_v2(["A", "B", "A"])
    assert captured == {"endpoint": ENDPOINT_GET_FAULT_DATA_V2, "payload": {"deviceCodeList": ["A", "B"]}}
    with pytest.raises(ValueError, match="deviceCodeList"):
        api.get_fault_data_v2([])
