"""Manual OTA preparation and privacy-preserving SIM status through existing workers."""
import io
import json
import threading
import urllib.error

import pytest

from cloud.device_metadata import device_iccid, redacted_device_metadata, safe_sim_status
from cloud.warmlink_api import WarmLinkCloudApi, WarmLinkCloudError, normalize_house_devices
from dialogs.cloud_dialog import WarmLinkCloudDialog
from workers import warmlink_cloud_worker as workers
from test_cloud_polling import DialogWindow, application
from test_csv_logger_transport import wait_for
from test_warmlink_request_scheduler import window

SIM_A = "test-sim-a-000000001"
SIM_B = "test-sim-b-000000002"
PRIVATE = {"dtuIccid": SIM_A, "dtuImeiMac": "test-imei-000000003",
           "msisdn": "test-phone-000000004", "imsi": "test-imsi-000000005",
           "email": "private@example.test", "userId": 0}
PUBLIC = {"expireDays": 0, "expireTime": None, "activeTime": "2026-10-10",
          "openTime": None, "cardState": 0, "onlineState": None,
          "netType": "2", "cardType": None, "cardPlatform": None, "dataService": None,
          "renewYear": 0}


@pytest.fixture
def sim_dialog(application):
    owner = DialogWindow()
    dialog = WarmLinkCloudDialog(owner)
    dialog._on_devices([{"deviceCode": "A", "dtuIccid": SIM_A, "dtuImeiMac": PRIVATE["dtuImeiMac"]},
                        {"deviceCode": "B", "dtuIccid": SIM_B}])
    dialog.device_combo.setCurrentIndex(dialog.device_combo.findData("A"))
    yield owner, dialog
    assert dialog.sim_thread is None
    dialog.close()
    owner.cloud_btn.setPollingActive(False)
    owner.deleteLater()
    application.processEvents()


def install_sim_api(monkeypatch, gate=None):
    calls = []
    entered = threading.Event()
    class FakeApi:
        def __init__(self, username, password, **kwargs):
            self.token = kwargs.get("initial_token") or "test-token"
        def get_sim_status(self, identifier):
            calls.append(identifier)
            entered.set()
            if gate:
                assert gate.wait(5)
            return dict(PUBLIC)
    monkeypatch.setattr(workers, "WarmLinkCloudApi", FakeApi)
    monkeypatch.setattr(workers, "load_cloud_credentials",
                        lambda username, password, token, **kwargs: (password, token))
    return calls, entered


def test_ota_template_prepares_exact_editable_request_and_preserves_get_data(sim_dialog, monkeypatch):
    _owner, dialog = sim_dialog
    monkeypatch.setattr(dialog, "run_debug_request", lambda: pytest.fail("Template must not send"))
    dialog._prepare_debug_ota()
    assert dialog.debug_method_combo.currentText() == "POST"
    assert dialog.debug_path_edit.text() == "app/device/ota/judgeUpgradeList?lang=de"
    assert json.loads(dialog.debug_body_edit.toPlainText()) == {"appId": "16", "deviceCode": "A"}
    dialog.debug_body_edit.setPlainText('{"appId":"edited","deviceCode":"other"}')
    assert json.loads(dialog.debug_body_edit.toPlainText())["appId"] == "edited"
    dialog._prepare_debug_get_data()
    assert dialog.debug_path_edit.text() == "app/device/getDataByCode"
    assert json.loads(dialog.debug_body_edit.toPlainText()) == {"deviceCode": "A", "protocalCodes": ["T01"]}


def test_ota_without_device_leaves_fields_unchanged_and_does_not_send(sim_dialog, monkeypatch):
    _owner, dialog = sim_dialog
    dialog.device_combo.clear()
    dialog.debug_path_edit.setText("existing/path")
    dialog.debug_body_edit.setPlainText('{"existing": true}')
    messages = []
    monkeypatch.setattr("dialogs.cloud_dialog.QMessageBox.information", lambda *args: messages.append(args))
    monkeypatch.setattr(dialog, "run_debug_request", lambda: pytest.fail("No request"))
    dialog._prepare_debug_ota()
    assert messages
    assert dialog.debug_path_edit.text() == "existing/path"
    assert json.loads(dialog.debug_body_edit.toPlainText()) == {"existing": True}


def test_ota_http_404_and_query_are_preserved(monkeypatch):
    raw = b'{"status":404,"message":"Not Found","path":"/crmservice/api/app/device/ota/judgeUpgradeList"}'
    captured = []
    def request(req, timeout):
        captured.append(req)
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, io.BytesIO(raw))
    monkeypatch.setattr("urllib.request.urlopen", request)
    api = WarmLinkCloudApi("user", "", initial_token="test-token")
    response = api.debug_request("POST", "app/device/ota/judgeUpgradeList?lang=de",
                                 {"appId": "16", "deviceCode": "A"})
    assert captured[0].full_url.endswith("judgeUpgradeList?lang=de")
    assert response.status == 404 and response.body == raw.decode()


def test_house_device_iccid_is_retained_internally_and_redacted_for_display():
    response = {"objectResult": {"data": [{"roomInfoResultList": [
        {"houseRelDeviceList": [{"deviceCode": "A", **PRIVATE, "accessToken": "secret"}]}
    ]}]}}
    device = normalize_house_devices(response)[0]
    assert device_iccid(device) == SIM_A
    view = redacted_device_metadata({"nested": device})
    text = json.dumps(view)
    for key, value in PRIVATE.items():
        if key != "userId":
            assert str(value) not in text
    assert "secret" not in text
    assert device["dtuIccid"] == SIM_A


def test_sim_api_payload_and_scalar_status_allowlist(monkeypatch):
    api = WarmLinkCloudApi("user", "", initial_token="test-token")
    calls = []
    def post(endpoint, payload):
        calls.append((endpoint, payload))
        return {"error_code": "0", "objectResult": {**PRIVATE, **PUBLIC, "extra": {"private": PRIVATE}}}
    monkeypatch.setattr(api, "post", post)
    result = api.get_sim_status(SIM_A)
    assert calls == [("dtuIccId/getInfoByIccId", {"iccId": SIM_A})]
    assert result == PUBLIC
    assert "dtuIccid" not in result and "extra" not in result
    assert safe_sim_status({"expireDays": {"unexpected": PRIVATE}})["expireDays"] is None


@pytest.mark.parametrize("identifier", ["", None])
def test_sim_api_without_iccid_never_sends(monkeypatch, identifier):
    api = WarmLinkCloudApi("user", "", initial_token="test-token")
    monkeypatch.setattr(api, "post", lambda *args: pytest.fail("Missing ICCID must not send"))
    with pytest.raises(WarmLinkCloudError):
        api.get_sim_status(identifier)


@pytest.mark.parametrize("mode", ["http", "cloud", "exception"])
def test_sim_error_never_exposes_raw_json_or_contact_identifiers(monkeypatch, mode):
    api = WarmLinkCloudApi("user", "", initial_token="test-token")
    private_json = json.dumps(PRIVATE)
    def post(*args):
        if mode == "exception":
            raise RuntimeError(private_json)
        return {"http_status": 403 if mode == "http" else 200,
                "error_code": "denied", "message": private_json, "objectResult": PRIVATE}
    monkeypatch.setattr(api, "post", post)
    with pytest.raises(WarmLinkCloudError) as raised:
        api.get_sim_status(SIM_A)
    text = str(raised.value)
    for value in PRIVATE.values():
        if isinstance(value, str):
            assert value not in text
    assert private_json not in text


def test_sim_worker_sanitizes_credential_and_unexpected_exceptions(monkeypatch):
    errors = []
    def credentials(*args, **kwargs):
        raise RuntimeError(json.dumps(PRIVATE))
    monkeypatch.setattr(workers, "load_cloud_credentials", credentials)
    worker = workers.WarmLinkCloudSimWorker("user", "", SIM_A, load_credentials=True)
    worker.error.connect(errors.append)
    worker.run()
    assert len(errors) == 1 and SIM_A not in errors[0] and "private@example.test" not in errors[0]


def test_sim_is_manual_keeps_zero_null_and_unknown_status_raw(sim_dialog, monkeypatch):
    owner, dialog = sim_dialog
    calls, _entered = install_sim_api(monkeypatch)
    dialog._on_connection_state("POLLING")
    assert calls == []
    dialog.refresh_sim_status()
    wait_for(lambda: dialog.sim_thread is None)
    assert calls == [SIM_A] and owner.cloud_read_thread is None
    assert dialog.sim_status_labels["expireDays"].text() == "0"
    assert dialog.sim_status_labels["expireTime"].text() == "—"
    assert dialog.sim_status_labels["cardState"].text() == "0"
    assert dialog.sim_status_labels["onlineState"].text() == "—"
    assert dialog.sim_status_labels["netType"].text() == "2"
    assert owner.cloud_btn.property("pollingActive") is True


def test_sim_without_metadata_iccid_creates_no_thread_or_request(sim_dialog, monkeypatch):
    _owner, dialog = sim_dialog
    dialog.devices[0]["dtuIccid"] = ""
    calls, _entered = install_sim_api(monkeypatch)
    dialog.refresh_sim_status()
    assert dialog.sim_thread is None and calls == []


def test_device_switch_clears_and_discards_old_sim_status(sim_dialog):
    _owner, dialog = sim_dialog
    context = dialog._current_sim_identity()
    dialog._sim_context = context
    dialog._on_sim_result(context, {**PUBLIC, "expireDays": 30})
    assert dialog.sim_status_labels["expireDays"].text() == "30"
    dialog.device_combo.setCurrentIndex(dialog.device_combo.findData("B"))
    assert all(label.text() == "—" for label in dialog.sim_status_labels.values())
    dialog._on_sim_result(context, {**PUBLIC, "expireDays": 99})
    assert all(label.text() == "—" for label in dialog.sim_status_labels.values())


def test_inflight_sim_response_and_token_are_discarded_after_device_change(sim_dialog, monkeypatch):
    owner, dialog = sim_dialog
    gate = threading.Event()
    calls, entered = install_sim_api(monkeypatch, gate)
    dialog.refresh_sim_status()
    try:
        wait_for(entered.is_set)
        dialog.device_combo.setCurrentIndex(dialog.device_combo.findData("B"))
        gate.set()
        wait_for(lambda: dialog.sim_thread is None)
        assert calls == [SIM_A]
        assert all(label.text() == "—" for label in dialog.sim_status_labels.values())
        assert dialog._cloud_token is None
        assert owner.cloud_read_thread is None
    finally:
        gate.set()
        wait_for(lambda: dialog.sim_thread is None)


def test_sim_data_and_errors_are_excluded_from_logs_and_raw_exports(sim_dialog, monkeypatch, tmp_path):
    owner, dialog = sim_dialog
    context = dialog._current_sim_identity()
    dialog._sim_context = context
    dialog._on_sim_result(context, {**PRIVATE, **PUBLIC})
    dialog._on_sim_error(context, json.dumps(PRIVATE))
    output = tmp_path / "cloud.json"
    monkeypatch.setattr("dialogs.cloud_dialog.QFileDialog.getSaveFileName", lambda *args: (str(output), ""))
    dialog.export_json()
    text = output.read_text() + "\n".join(owner.logs)
    for value in PRIVATE.values():
        if isinstance(value, str):
            assert value not in text
    assert "expireDays" not in output.read_text()
    column = dialog.device_columns.index("dtuIccid")
    assert dialog.device_table.item(0, column).text() != SIM_A


def test_main_close_waits_for_sim_read_using_existing_single_read_guard(window, monkeypatch):
    dialog = WarmLinkCloudDialog(window)
    window.warmlink_cloud_dialog = dialog
    dialog.save_token_cb.setChecked(False)
    dialog.username_edit.setText("user")
    dialog._on_devices([{"deviceCode": "A", "dtuIccid": SIM_A}])
    gate = threading.Event()
    _calls, entered = install_sim_api(monkeypatch, gate)
    dialog.refresh_sim_status()
    try:
        wait_for(entered.is_set)
        window.close()
        assert window.cloud_read_thread is not None
        assert window._close_after_cloud_read is True
        gate.set()
        wait_for(lambda: window.cloud_read_thread is None)
    finally:
        gate.set()
        wait_for(lambda: dialog.sim_thread is None)
        dialog.close()
        window.warmlink_cloud_dialog = None


def test_sim_result_updates_widgets_on_the_gui_thread(sim_dialog, monkeypatch, application):
    from PySide6.QtCore import QThread
    _owner, dialog = sim_dialog
    install_sim_api(monkeypatch)
    observed_threads = []
    original = dialog._on_sim_result
    def observe(context, status):
        observed_threads.append(QThread.currentThread())
        original(context, status)
    monkeypatch.setattr(dialog, "_on_sim_result", observe)
    dialog.refresh_sim_status()
    wait_for(lambda: dialog.sim_thread is None)
    assert observed_threads and all(thread is application.thread() for thread in observed_threads)
