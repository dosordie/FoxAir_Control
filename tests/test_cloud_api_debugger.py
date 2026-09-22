import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cloud.warmlink_api import WarmLinkCloudApi, WarmLinkDebugResponse


class FakeResponse:
    status = 200
    headers = {"Content-Type": "application/json", "X-Trace": "abc"}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return b'{"ok":true}'


def test_debug_request_uses_configured_host_relative_service_path_and_existing_token(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    api = WarmLinkCloudApi(
        "user@example.test", "", base_url="https://cloud.example.test:8443/crmservice/api",
        timeout=7, initial_token="existing-token",
    )

    response = api.debug_request("GET", "cloudservice/api/device/test")

    request = captured["request"]
    assert request.full_url == "https://cloud.example.test:8443/cloudservice/api/device/test"
    assert request.method == "GET"
    assert request.get_header("X-token") == "existing-token"
    assert request.data is None
    assert captured["timeout"] == 7
    assert response.status == 200
    assert response.headers["X-Trace"] == "abc"
    assert response.body == '{"ok":true}'
    assert api.reused_initial_token is True


def test_debug_request_serializes_json_body(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        assert timeout == 15.0
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    api = WarmLinkCloudApi("user", "", initial_token="token")

    api.debug_request("PUT", "app/device/example", {"value": "ä", "enabled": True})

    request = captured["request"]
    assert request.full_url.endswith("/crmservice/api/app/device/example")
    assert request.method == "PUT"
    assert json.loads(request.data.decode("utf-8")) == {"value": "ä", "enabled": True}
    assert request.get_header("Content-type") == "application/json;charset=utf-8"


@pytest.mark.parametrize("path", ["https://other.example/api", "http://other.example/api", "//other.example/api"])
def test_debug_request_rejects_absolute_paths_before_sending_token(path):
    api = WarmLinkCloudApi("user", "", initial_token="secret")

    with pytest.raises(ValueError, match="relative API-Pfade"):
        api.debug_request("DELETE", path)


@pytest.mark.parametrize(
    "expired_body",
    [
        '{"error_code":-100,"message":"token invalid"}',
        '{"error_code":0,"message":"please login again"}',
    ],
)
def test_debug_request_relogs_in_for_phnix_json_auth_errors(monkeypatch, expired_body):
    api = WarmLinkCloudApi("user", "password", initial_token="expired-token")
    requests = []
    responses = iter(
        [
            WarmLinkDebugResponse("https://cloud.example/api", 200, {}, expired_body),
            WarmLinkDebugResponse("https://cloud.example/api", 200, {}, '{"success":true}'),
        ]
    )

    def fake_request(method, endpoint, body):
        requests.append((method, endpoint, body, api.token))
        return next(responses)

    login_calls = []

    def fake_login(preferred_method, use_fallbacks):
        login_calls.append((preferred_method, use_fallbacks))
        api.token = "renewed-token"
        return True

    monkeypatch.setattr(api, "_debug_http_request", fake_request)
    monkeypatch.setattr(api, "login", fake_login)

    response = api.debug_request("POST", "app/device/example", {"value": 1})

    assert response.body == '{"success":true}'
    assert login_calls == [("md5", True)]
    assert [request[3] for request in requests] == ["expired-token", "renewed-token"]
