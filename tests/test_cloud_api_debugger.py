import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cloud.warmlink_api import WarmLinkCloudApi


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
