"""Dedicated app heartbeat transport and isolation of the cloud-live refresh."""
import threading
import time

import pytest

from cloud.warmlink_api import (
    ENDPOINT_DEVICE_CONTROL, WarmLinkCloudApi, WarmLinkCloudError,
    WarmLinkAuthError, WarmLinkDebugResponse,
)
from workers import warmlink_cloud_worker as workers
from test_cloud_polling import fake_api, poll_worker, run_cycles, success


REAL_SETTLE = workers.WarmLinkCloudWorker._settle_after_heartbeat


def scanned_session():
    from cloud.polling import CloudSession
    return CloudSession(username="user", device_code="device", devices=[{"deviceCode": "device"}],
        validated=True, scanned=True, candidates=["F23", "T04", "unmapped", "unsupported"],
        supported_codes=["F23", "T04"], static_codes=["F23"], live_codes=["T04"])


def test_heartbeat_uses_exact_endpoint_and_payload_without_general_write(monkeypatch):
    api = WarmLinkCloudApi("user", "password", initial_token="token")
    calls = []
    monkeypatch.setattr(api, "post", lambda endpoint, payload: calls.append((endpoint, payload)) or success({}))
    monkeypatch.setattr(api, "write_test_code", lambda *args, **kwargs: pytest.fail("Heartbeat used general write path"))
    response = api.send_app_heartbeat("device")
    assert api.success(response)
    assert calls == [("app/device/control", {"param": [{
        "deviceCode": "device", "protocolCode": "app_heartbeat", "value": "23205",
    }]})]
    assert "appId" not in calls[0][1] and "appId" not in calls[0][1]["param"][0]


@pytest.mark.parametrize("code", ["", "  ", None])
def test_missing_device_never_sends_heartbeat(monkeypatch, code):
    api = WarmLinkCloudApi("user", "password", initial_token="token")
    monkeypatch.setattr(api, "post", lambda *args, **kwargs: pytest.fail("No request without device"))
    with pytest.raises(ValueError):
        api.send_app_heartbeat(code)


def test_heartbeat_reuses_existing_post_relogin_mechanism(monkeypatch):
    api = WarmLinkCloudApi("user", "password", initial_token="old")
    requests, logins = [], []
    def request(endpoint, payload, *, token, method):
        requests.append((endpoint, payload, token, method))
        return {"error_code": "401"} if token == "old" else success({})
    def login(*args):
        logins.append(args)
        api.token = "renewed"
    monkeypatch.setattr(api, "_request_json", request)
    monkeypatch.setattr(api, "login", login)
    assert api.success(api.send_app_heartbeat("device"))
    assert len(logins) == 1 and len(requests) == 2
    assert [request[2] for request in requests] == ["old", "renewed"]
    assert all(endpoint == ENDPOINT_DEVICE_CONTROL and method == "POST"
               for endpoint, payload, token, method in requests)
    assert requests[0][1] == requests[1][1]


def test_live_refresh_order_once_per_cycle_and_quiet_success(fake_api, monkeypatch):
    worker = poll_worker(session=scanned_session())
    monkeypatch.setattr(worker, "_settle_after_heartbeat", lambda: fake_api.created[-1].calls.append("settle") or False)
    logs = []
    worker.log.connect(logs.append)
    run_cycles(worker, count=2)
    assert fake_api.created[-1].calls == [
        "heartbeat", "settle", ("read", ["T04"]), "status",
        "heartbeat", "settle", ("read", ["T04"]), "status",
    ]
    assert len(fake_api.created) == 1
    assert not any("heartbeat" in log.lower() for log in logs)
    assert worker.session.static_codes == ["F23"] and worker.session.live_codes == ["T04"]


def test_poll_once_on_scanned_session_is_a_live_refresh(fake_api, monkeypatch):
    worker = poll_worker(poll_once=True, session=scanned_session())
    monkeypatch.setattr(worker, "_settle_after_heartbeat", lambda: fake_api.created[-1].calls.append("settle") or False)
    worker.run()
    assert fake_api.created[-1].calls == ["heartbeat", "settle", ("read", ["T04"]), "status"]


@pytest.mark.parametrize("mode", ["static", "discovery", "initial"])
def test_non_live_modes_do_not_send_heartbeat(fake_api, monkeypatch, mode):
    def forbidden(*args):
        pytest.fail("Non-live operation sent heartbeat")
    monkeypatch.setattr(fake_api, "send_app_heartbeat", forbidden)
    monkeypatch.setattr(workers.WarmLinkCloudWorker, "_settle_after_heartbeat", forbidden)
    kwargs = {"poll_once": True}
    if mode != "initial":
        kwargs["session"] = scanned_session()
    if mode == "static":
        kwargs["reload_static"] = True
    if mode == "discovery":
        kwargs["discovery_only"] = True
    worker = poll_worker(**kwargs)
    worker.run()
    calls = fake_api.created[-1].calls
    if mode == "static":
        assert calls == [("read", ["F23"])]
    elif mode == "discovery":
        assert not any(isinstance(call, tuple) and call[0] == "read" for call in calls)
        assert "status" not in calls
    else:
        assert ("read", worker.codes) in calls


@pytest.mark.parametrize("failure", ["iot_response", "network"])
def test_normal_heartbeat_failure_still_reads_live_values(fake_api, monkeypatch, failure):
    def heartbeat(api, device):
        api.calls.append("heartbeat")
        if failure == "network":
            raise WarmLinkCloudError("timeout")
        return {"error_code": "9", "error_msg": "IoT failed", "isReusltSuc": False}
    monkeypatch.setattr(fake_api, "send_app_heartbeat", heartbeat)
    monkeypatch.setattr(workers.WarmLinkCloudWorker, "_settle_after_heartbeat",
                        lambda *_args: pytest.fail("Failed heartbeat should not wait"))
    worker = poll_worker(session=scanned_session())
    updates, logs, errors = [], [], []
    worker.data.connect(updates.append)
    worker.log.connect(logs.append)
    worker.error.connect(errors.append)
    run_cycles(worker, count=2)
    assert fake_api.created[-1].calls == ["heartbeat", ("read", ["T04"]), "status"] * 2
    assert len(updates) == 2 and all(update[0]["code"] == "T04" for update in updates)
    assert len([log for log in logs if "heartbeat" in log.lower()]) == 2
    assert errors == [] and worker.session.validated


@pytest.mark.parametrize("failure", ["auth_response", "auth_exception"])
def test_heartbeat_auth_failure_uses_existing_auth_error_path(fake_api, monkeypatch, failure):
    def heartbeat(api, device):
        api.calls.append("heartbeat")
        if failure == "auth_exception":
            raise WarmLinkAuthError("401")
        return {"error_code": "401", "error_msg": "expired"}
    monkeypatch.setattr(fake_api, "send_app_heartbeat", heartbeat)
    worker = poll_worker(poll_once=True, session=scanned_session())
    states, errors = [], []
    worker.connection_state.connect(states.append)
    worker.error.connect(errors.append)
    worker.run()
    assert fake_api.created[-1].calls == ["heartbeat"]
    assert errors and states[-1] == "ERROR"
    assert not worker.session.validated and not worker.session.scanned


def test_heartbeat_token_renewal_invalidates_static_snapshot(fake_api, monkeypatch):
    def heartbeat(api, device):
        api.calls.append("heartbeat")
        api.token = "renewed"
        return success({})
    monkeypatch.setattr(fake_api, "send_app_heartbeat", heartbeat)
    worker = poll_worker(session=scanned_session())
    tokens = []
    worker.token_updated.connect(tokens.append)
    run_cycles(worker, count=1)
    calls = fake_api.created[-1].calls
    assert calls.count("heartbeat") == 1
    assert ("read", ["T04"]) in calls and ("read", worker.codes) in calls
    assert calls.index(("read", ["T04"])) < calls.index(("read", worker.codes))
    assert "devices" not in calls and "houses" not in calls
    assert tokens and set(tokens) == {"renewed"}
    assert worker.session.scanned


def test_stop_during_actual_settle_is_responsive_and_prevents_read(fake_api, monkeypatch):
    entered = threading.Event()
    worker = poll_worker(poll_once=True, session=scanned_session())
    def settle():
        entered.set()
        return REAL_SETTLE(worker)
    monkeypatch.setattr(worker, "_settle_after_heartbeat", settle)
    thread = threading.Thread(target=worker.run)
    thread.start()
    try:
        assert entered.wait(1.0)
        started = time.monotonic()
        worker.stop()
        thread.join(0.5)
        assert not thread.is_alive() and time.monotonic() - started < 0.5
        assert fake_api.created[-1].calls == ["heartbeat"]
    finally:
        worker.stop()
        thread.join(2.0)


def test_static_reload_wake_does_not_shorten_settle(fake_api):
    from types import SimpleNamespace
    worker = poll_worker(session=scanned_session())
    waits = []
    worker.request_static_reload()
    worker._stop_event = SimpleNamespace(wait=lambda seconds: waits.append(seconds) or False)
    assert REAL_SETTLE(worker) is False
    assert waits == [workers.WARMLINK_APP_HEARTBEAT_SETTLE_S]
    assert worker._reload_event.is_set()  # It remains available for the next cycle.


@pytest.mark.parametrize("mode", ["single_read", "validation", "debug", "write_readback"])
def test_other_workers_never_send_automatic_heartbeat(monkeypatch, mode):
    monkeypatch.setattr(WarmLinkCloudApi, "send_app_heartbeat",
                        lambda *_args: pytest.fail("Non-poll worker sent heartbeat"))
    monkeypatch.setattr(WarmLinkCloudApi, "get_data_by_code", lambda api, device, codes:
        success([{"code": code, "value": 55, "dataType": "FLOAT"} for code in codes]))
    monkeypatch.setattr(WarmLinkCloudApi, "write_test_code", lambda *args, **kwargs: success({}))
    monkeypatch.setattr(WarmLinkCloudApi, "_debug_http_request", lambda *args, **kwargs:
        WarmLinkDebugResponse(url="https://example.test/device", status=200, headers={}, body="{}"))
    monkeypatch.setattr(workers.time, "sleep", lambda *_args: None)
    if mode == "single_read":
        worker = workers.WarmLinkCloudReadWorker("user", "password", "device", ["R02"], initial_token="token")
    elif mode == "validation":
        worker = workers.WarmLinkKnownDeviceValidationWorker("user", "password", "device", initial_token="token")
    elif mode == "debug":
        worker = workers.WarmLinkCloudDebugWorker("user", "password", "GET", "device", initial_token="token")
    else:
        worker = workers.WarmLinkCloudCommandWorker("user", "password", "device", "R02", "55",
            initial_token="token", dry_run=False)
    errors, finished = [], []
    worker.error.connect(errors.append)
    worker.finished.connect(lambda: finished.append(True))
    worker.run()
    assert errors == [] and finished == [True]
